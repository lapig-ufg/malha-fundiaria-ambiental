#Importar módulos
from qgis import processing
import subprocess
import os
from concurrent.futures import ThreadPoolExecutor # Para paralelismo
import datetime
import numpy
import geopandas as gpd
import rasterio
from exactextract import exact_extract
from osgeo import ogr
from rasterio.mask import mask
import numpy as np


# Configuração do Ambiente Standalone
qgis_prefix = r'C:\Program Files\QGIS 3.xx\apps\qgis'
gdal_prefix = r'C:\\Program Files\\QGIS 3.44.4\\bin\\'

#Hierarquização do Brasil
def processar_brasil_final(folderIn, listData, folderOut):
    """
    ext_coords: [xmin, ymin, xmax, ymax] em metros (ESRI:102033)
    listData: [{'src': 'car.gpkg', 'order': 10}, {'src': 'sigef.gpkg', 'order': 1}]
    """
    gdal_path = os.path.join(gdal_prefix, 'gdal_rasterize.exe')

    path_overlap = os.path.join(folderOut, 'brasil_contagem_overlap_10m.tif')
    path_tenure = os.path.join(folderOut, 'brasil_landtenure_hierarquia_10m.tif')

    # Opções para suportar bilhões de pixels (Brasil 10m)
    # TILED=YES é vital para conseguir abrir o arquivo depois sem travar
    creation_opts = [
        '-co', 'COMPRESS=LZW',
        '-co', 'BIGTIFF=YES',
        '-co', 'TILED=YES',
        '-co', 'BLOCKXSIZE=1024',
        '-co', 'BLOCKYSIZE=1024',
        '-co', 'NUM_THREADS=ALL_CPUS'
    ]

    #Criar uma imagem zerada
    print("Criando base vazia do Brasil...")
    primeira_camada = os.path.join(folderIn, listData[0]['src'])

    cmd_create = [
        gdal_path,
        '-burn', '0', # Não pinta nada, apenas cria o ficheiro
        '-tr', '10', '10',
        '-te', str(-1522717.72), str(-215371.54), str(3070231.55), str(4209750.56),
        '-ot', 'byte', # Int16 permite contagem acima de 255
        #'-a_nodata', '0',
        '-co', 'COMPRESS=LZW', '-co', 'BIGTIFF=YES', '-co', 'TILED=YES',
        primeira_camada, path_overlap
    ]

    subprocess.run(cmd_create)

    #Contagem de sobreposição
    # Objetivo: Pixel = nº de camadas sobrepostas
    print(f"[{datetime.datetime.now()}] Iniciando Contagem de Overlap...")
    
    for i, item in enumerate(listData):
        lyr_path = os.path.join(folderIn, item['src'])
        cmd_ov = [
            gdal_path,
            '-burn', '1',        # Cada camada vale 1 na contagem
            '-add',              # SOMA 1 ao valor atual do pixel
            lyr_path, path_overlap
        ]
        subprocess.run(cmd_ov)
        print(f"  > Camada {os.path.basename(item['src'])[0:-4]} contabilizada no overlap.")

    # --- 2. PRODUTO: LAND TENURE (HIERARQUIA) ---
    # Objetivo: O valor do pixel é o 'order' da camada de maior prioridade
    print(f"\n[{datetime.datetime.now()}] Iniciando Hierarquia de Terras...")
    
    # IMPORTANTE: Ordenamos do MAIOR 'order' para o MENOR 'order'.
    # Assim, a camada de maior prioridade (ex: 1) é pintada por ÚLTIMO,
    # substituindo qualquer valor que estivesse lá.
    list_hierarquia = sorted(listData, key=lambda x: x['order'], reverse=True)

    subprocess.run([
        gdal_path, '-burn', '0', '-tr', '10', '10',
        '-te', str(-1522717.72), str(-215371.54), str(3070231.55), str(4209750.56),
        '-ot', 'Byte', 
        '-co', 'COMPRESS=LZW', '-co', 'BIGTIFF=YES', '-co', 'TILED=YES',
        os.path.join(folderIn, listData[0]['src']), path_tenure
    ])

    for item in list_hierarquia:
        print(f"Pintando Prioridade {item['order']}: {item['src']}")
        # SEM a flag -add. O valor novo esmaga o antigo.
        subprocess.run([
            gdal_path, '-burn', str(int(item['order'])),
            os.path.join(folderIn, item['src']), path_tenure
        ])
        
    print(f"\n[{datetime.datetime.now()}] Processamento concluído com sucesso!")


def selectedFeature_v2(path_raster, path_vetor, ordem_prioridade, path_output):
    log = open('C:/Users/Bernard/Documents/Projetos/MalhaFundiaria/datasets/tipos_malha_fundiaria/BR/logs/log_filtro_camadas.txt','w')
    if not os.path.exists(path_output):
        os.makedirs(path_output)

    raster_path = os.path.join(path_raster, 'brasil_landtenure_hierarquia_10m.tif')
    
    # 1. Abrir o Raster
    with rasterio.open(raster_path) as src:
        raster_crs = src.crs.to_string()
        nodata = src.nodata

        for w in ordem_prioridade:
            if int(w['order']) > 2:

                weight = int(w['order'])
                mask_name = w['src'][0:-4]
                vetor_input = os.path.join(path_vetor, w['src'])
                output_file = os.path.join(path_output, f'selected_mask_{mask_name}.shp')
                log.writelines(f"\n[{datetime.datetime.now()}] --- Processando: {mask_name} (Peso: {weight}) ---")
                log.writelines('\n')
                print(f"\n[{datetime.datetime.now()}] --- Processando: {mask_name} (Peso: {weight}) ---")

                if not os.path.exists(vetor_input): continue

                # 2. Ler Vetor usando OGR (Nativo do QGIS, ignora erros de PyOgrio)
                ds = ogr.Open(vetor_input)
                if ds is None:
                    print(f"  Erro ao abrir vetor: {vetor_input}")
                    continue
            
                lyr = ds.GetLayer()
            
                # Criar um GeoPackage de saída para os selecionados
                driver_out = ogr.GetDriverByName("ESRI Shapefile")
                if os.path.exists(output_file): driver_out.DeleteDataSource(output_file)
                out_ds = driver_out.CreateDataSource(output_file)
                out_lyr = out_ds.CreateLayer(mask_name, geom_type=lyr.GetGeomType(), srs=lyr.GetSpatialRef())
            
                # Copiar campos do original para o novo
                lyr_def = lyr.GetLayerDefn()
                for i in range(lyr_def.GetFieldCount()):
                    fld_defn = lyr_def.GetFieldDefn(i)
                    fld_name = fld_defn.GetName()
    
                    # SÓ CRIA O CAMPO SE O NOME NÃO FOR VAZIO
                    if fld_name and fld_name.strip():
                        out_lyr.CreateField(fld_defn)
                    else:
                        print(f"  [Aviso] Pulando campo inválido no índice {i}")

                # 3. Processar feição por feição (Loop de Geometrias)
                log.writelines(f"  [2/3] Analisando {lyr.GetFeatureCount()} feições...")
                log.writelines('\n')
                print(f"  [2/3] Analisando {lyr.GetFeatureCount()} feições...")
                count_selected = 0
                out_lyr.StartTransaction()
            
                for feat in lyr:
                    geom = feat.GetGeometryRef()
                    if geom is None: continue
                
                    # Converter geometria OGR para formato GeoJSON/Python para o rasterio
                    geom_json = eval(geom.ExportToJson()) 
                
                    try:
                        # Recorte rápido (Windows-based sampling)
                        out_image, _ = mask(src, [geom_json], crop=True,filled=False,all_touched=True)
                        out_image = out_image[0]
                                               
                        valid_pixels = out_image.compressed()
                        pixels_validos = valid_pixels.size
                        pixels_alvo = np.sum(valid_pixels == weight) #np.sum(out_image == weight)
                        
                        # Critério: 10% de sobreposição
                        if pixels_validos > 0 and (pixels_alvo / pixels_validos) >= 0.1:
                            out_lyr.CreateFeature(feat)
                            count_selected += 1
                    except Exception as e:
                        continue
                        
                out_lyr.CommitTransaction()
                out_ds = None # Fecha e salva o arquivo
                ds = None
                log.writelines(f"  [3/3] Sucesso! {count_selected} feições salvas em Shapefile.")
                log.writelines('\n')
                print(f"  [3/3] Sucesso! {count_selected} feições salvas em Shapefile.")
    log.writelines(f"\n[{datetime.datetime.now()}] Concluído!")
    log.close()
    print(f"\n[{datetime.datetime.now()}] Concluído!")
