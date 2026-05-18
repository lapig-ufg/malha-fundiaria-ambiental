#Importar módulos
from qgis.core import  QgsProject, QgsVectorLayer, QgsFeatureRequest, QgsFeature, QgsApplication,QgsDataSourceUri, QgsSpatialIndex,QgsGeometry
from qgis import processing
import sys
from qgis.analysis import QgsNativeAlgorithms
import os
import datetime

# Configuração do Ambiente Standalone
qgis_prefix = r'C:\Program Files\QGIS 3.xx\apps\qgis'
QgsApplication.setPrefixPath(qgis_prefix, True)
qgs = QgsApplication([], False)
qgs.initQgis()

sys.path.append(r'C:\PROGRA~1\QGIS34~1.4\apps\qgis\python\plugins')

import processing
from processing.core.Processing import Processing
Processing.initialize() 

# 4. Adicionar os algoritmos nativos
QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())


#Salvar camadas excluidas 
def salvar_camada_excluidos(lista_feicoes, campos, pasta_saida, nome_arquivo):
    """
    Cria um GeoPackage para armazenar as feições que foram barradas em qualquer etapa.
    """
    if not lista_feicoes:
        return

    #Definir o caminho completo
    caminho_final = os.path.join(pasta_saida, nome_arquivo)
    
    # 2. Criar uma camada temporária em memória com a mesma estrutura da camada original
    # Usamos MultiPolygon porque é o padrão do CAR
    uri = "MultiPolygon?crs=EPSG:4674" # Ou use o CRS da sua camada original
    camada_temp = QgsVectorLayer(uri, "temp_excluidos", "memory")
    provider = camada_temp.dataProvider()

    # 3. Adicionar os campos originais + o campo de motivo (caso ele não exista nos campos passados)
    provider.addAttributes(campos)
    camada_temp.updateFields()

    # 4. Adicionar as feições à camada de memória
    provider.addFeatures(lista_feicoes)

    # 5. Salvar a camada de memória em um arquivo GeoPackage no disco
    params = {
        'INPUT': camada_temp,
        'OUTPUT': caminho_final,
        'LAYER_NAME': 'excluidos',
        'DATASOURCE_OPTIONS': '',
        'LAYER_OPTIONS': ''
    }
    
    # native:savefeatures é o comando mais seguro para exportar arquivos no QGIS Standalone
    processing.run("native:savefeatures", params)
    print(f"--> Arquivo de auditoria gerado: {nome_arquivo} ({len(lista_feicoes)} feições)")


def analisar_sobreposicao_car(layer,outfolder):
    
    if not os.path.exists(outfolder): os.makedirs(outfolder)
    coluna_modulo = 'mod_fical_calc' # Certifique-se que este nome está correto no seu banco
    
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Criando Índice Espacial e Cache...")
    all_features = {f.id(): f for f in layer.getFeatures()}
    geom_cache = {f.id(): f.geometry() for f in all_features.values()}
    index = QgsSpatialIndex(layer.getFeatures())
    
    ids_com_sobreposicao = []

    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Analisando tolerâncias de sobreposição...")
    for f_id, feat in all_features.items():
        geom = feat.geometry()
        area_original = geom.area()
        if area_original <= 0: continue
        
        # Pega o valor do módulo fiscal do imóvel atual
        val_modulo = feat.attribute(coluna_modulo)
        if val_modulo is None:
            val_modulo = 0 
            
        # Limiar de tolerância para considerar sobrepoisção do Imóvel do CAR
        if val_modulo < 4.0:
            limite_tolerancia = 10.0
        elif 4.0 <= val_modulo <= 15.0:
            limite_tolerancia = 5.0
        else: # Acima de 15
            limite_tolerancia = 3.0
        # -----------------------------------------

        candidates = index.intersects(geom.boundingBox())
        inter_area = 0
        
        for c_id in candidates:
            if c_id == f_id: continue
            other_geom = geom_cache[c_id]
            
            # Só calcula intersecção real se houver toque
            if geom.intersects(other_geom):
                intersection = geom.intersection(other_geom)
                inter_area += intersection.area()
                
                # Otimização: Se já passou do limite, não precisa somar o resto
                if (inter_area / area_original) * 100 > limite_tolerancia:
                    break
        
        if (inter_area / area_original) * 100 > limite_tolerancia:
            ids_com_sobreposicao.append(f_id)

    # --- 1. Exportar SEM Sobreposição (Aceitos dentro da tolerância) ---
    print(f"Exportando CAR aceito (dentro da tolerância)...")
    path_sem = os.path.join(outfolder, 'car_aceito_tolerancia.gpkg')
    fids_sem = list(set(all_features.keys()) - set(ids_com_sobreposicao))
    
    temp_sem = QgsVectorLayer(f"MultiPolygon?crs={layer.crs().authid()}", "sem_sob", "memory")
    temp_sem.dataProvider().addAttributes(layer.fields())
    temp_sem.updateFields()
    temp_sem.dataProvider().addFeatures([all_features[fid] for fid in fids_sem])
    processing.run("native:savefeatures", {'INPUT': temp_sem, 'OUTPUT': path_sem})

    # --- 2. Processar COM Sobreposição (Recorte Hierárquico) ---
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Iniciando Recorte Hierárquico dos conflitos...")
   
    # O restante do código de ordenação e recorte permanece igual para garantir a topologia
    print(f"Ordenando {len(ids_com_sobreposicao)} imóveis para recorte...")
    
    feats_sob = [all_features[fid] for fid in ids_com_sobreposicao]
    feats_ordenadas = sorted(feats_sob, key=lambda f: f.attribute(coluna_modulo) or 999999)

    path_com_recortado = os.path.join(outfolder, 'car_conflitos_resolvidos.gpkg')
    layer_resultado = QgsVectorLayer(f"MultiPolygon?crs={layer.crs().authid()}", "resultado", "memory")
    layer_resultado.dataProvider().addAttributes(layer.fields())
    layer_resultado.updateFields()

    processed_index = QgsSpatialIndex()
    processed_geoms = {}

    print("Iniciando recorte hierárquico...")
    
    ids_excluidos_conflito = []

    for i, feat in enumerate(feats_ordenadas):
            geom_atual = feat.geometry()
            
            # Busca apenas quem já foi processado e está perto
            candidates = processed_index.intersects(geom_atual.boundingBox())
            for c_id in candidates:
                geom_fixa = processed_geoms[c_id]
                if geom_atual.intersects(geom_fixa):
                    geom_atual = geom_atual.difference(geom_fixa)
                    if geom_atual.isEmpty(): 
                        break
            
            if not geom_atual.isEmpty() and geom_atual.area() > 1.0:
                #feat.setGeometry(geom_atual)
                #layer_resultado.addFeature(feat)
                #processed_index.addFeature(feat)
                #processed_geoms[feat.id()] = geom_atual
                feat.setGeometry(geom_atual)
                layer_resultado.dataProvider().addFeatures([feat])
                
                # ADICIONA AO ÍNDICE para os próximos imóveis
                new_id = feat.id()
                processed_index.addFeature(feat)
                processed_geoms[new_id] = geom_atual
            else:
                
                    salvar_camada_excluidos(feicoes_excluidas, final_clean.fields(), outfolder, 'car_excluidos_grilagem.gpkg')
            if i % 500 == 0:
                print(f"Processado: {i}/{len(feats_ordenadas)} imóveis.")

    processing.run("native:savefeatures", {'INPUT': layer_resultado, 'OUTPUT': path_com_recortado})
    print(f"Processamento concluído. Tolerâncias aplicadas: <4MF:10%, 4-15MF:5%, >15MF:3%.")

def processar_car_prioridade_atual(outfolder):
    
    # 1. Carregar Camadas
    uri = QgsDataSourceUri()
    uri.setConnection("localhost", "5432", "postgis", "postgres", "123456")

    #uri.setDataSource("mfa", "11_base_cartografica_municipios", "geom")
    uri.setDataSource("mfa", "11_base_cartografica_municipios", "geom")
    layer_mun = QgsVectorLayer(uri.uri(), "municipio_PostGIS", "postgres")
    print('Total de Municipios:',layer_mun.featureCount())

    uri.setDataSource("mfa", "10_malha_fundiaria_imoveis_rurais_car_calc", "geom")
    #uri.setSql("cod_estado = 'GO'")
    layer_car = QgsVectorLayer(uri.uri(), "car_PostGIS", "postgres")
    print('Total de CARS:',layer_car.featureCount())
    if not layer_car.isValid():
        print("Erro ao carregar base CAR.")
        return

    # 2. Filtro Inicial (Status e Tipologia)
    print("Filtrando Status e Tipologia...")
    query = (
        "NOT \"des_condic\" LIKE 'Suspenso%' AND "
        "NOT \"des_condic\" LIKE 'Cancelado%' AND "
        #"\"cod_estado\" LIKE 'GO' AND "
        "\"ind_tipo\" NOT IN ('AST', 'PCT')"
    )
    layer_car.setSubsetString(query)

    # 3. Ordenação por Data (Do mais recente para o mais antigo)
    # Criamos uma camada temporária ordenada para que o 'Delete Duplicates' pegue o topo
    print("Ordenando registros pelo campo...")
    expressao_composta = '"dat_atuali" DESC, "mod_fical_calc" ASC'
    layer_ordenada = processing.run("native:orderbyexpression", {
        'INPUT': layer_car,
        'EXPRESSION': expressao_composta,
        'ASCENDING': False, 
        'NULLS_FIRST': False,
        'OUTPUT': 'memory:car_ordenado'
    })['OUTPUT']
    print('Total de camadas ordenadas:',layer_ordenada.featureCount())

    # 4. Corrigir Geometrias
    fix_geo = processing.run("native:fixgeometries", {
        'INPUT': layer_ordenada,
        'OUTPUT': 'memory:temp_fix'
    })['OUTPUT']

    # 5. Remover Geometrias Duplicadas
    # O QGIS mantém a primeira feição encontrada. Como ordenamos, ele manterá a MAIS ATUAL.
    print("Removendo geometrias duplicadas (Mantendo a mais recente)...")
    no_double_geo = processing.run("native:deleteduplicategeometries", {
        'INPUT': fix_geo,
        'OUTPUT': 'memory:temp_no_double'
    })['OUTPUT']
    print('Total de camadas não duplicadas:',no_double_geo.featureCount())
    
    # 6. Remover Duplicados por Atributo (Mesmo COD_IMOVEL)
    print("Removendo duplicados por Código de Imóvel...")
    final_clean = processing.run("native:removeduplicatesbyattribute", {
        'INPUT': no_double_geo,
        'FIELDS': ['cod_imovel'], 
        'OUTPUT': 'memory:car_limpo_final'
    })['OUTPUT']
    print('Total de camadas não duplicadas por camada de imovel:',no_double_geo.featureCount())
    

    # 7. Filtro de Área (Imóvel < Município)
    print("Validando consistência de área com a malha municipal...")
    
    # 2. Join por Tabela (Muito mais rápido que o espacial)
    #---------------------------------------------------------------------------------------Grilagem Digital---------------------------------
   
    print("Retirando Grilagem Digital...")
    municipios_area = {str(f['CD_MUN']).split(): f['AREA_KM2'] for f in layer_mun.getFeatures()}
    
    #Lista dos imóveis excluidos e validos
    feicoes_validas = []
    feicoes_excluidas = []
    
    for imovel in final_clean.getFeatures():
        cod_mun = str(imovel['codmun']).strip()
        if cod_mun in municipios_area:
            area_imovel_km2 = imovel.geometry().area() / 1000000.0
            if area_imovel_km2 < municipios_area[cod_mun]:
                feicoes_validas.append(imovel)
            else:
                imovel.setAttribute(imovel.fieldNameIndex('motivo_excl'), 'Area Maior que Municipio')
                feicoes_excluidas.append(imovel)
        else:
            imovel.setAttribute(imovel.fieldNameIndex('motivo_excl'), 'Codigo Municipio Nao Encontrado')
            feicoes_excluidas.append(imovel) 

    # Exportar logo os barrados por área/código
    if feicoes_excluidas:
        salvar_camada_excluidos(feicoes_excluidas, final_clean.fields(), outfolder, 'car_excluidos_grilagem.gpkg')
    
    crs_authid = final_clean.crs().authid()
    uri = f"MultiPolygon?crs={crs_authid}"

    # 2. Criar a camada em memória
    # O nome "CAR_Validado" é como ela apareceria na legenda do QGIS
    camada_final_validada = QgsVectorLayer(uri, "CAR_Saneado_Grilagem", "memory")    
    provider = camada_final_validada.dataProvider()
    camada_final_validada.startEditing()
    provider.addAttributes(final_clean.fields())
    camada_final_validada.updateFields()
    provider.addFeatures(feicoes_validas)
    camada_final_validada.commitChanges()
    provider = None
    
    print("Iniciando análise de sobreposição espacial (Self-Intersection)...")

    #----------------------------------------------------------------------------Análise de sobreposição
    analisar_sobreposicao_car(camada_final_validada,outfolder)
    print('Finalizado.....')

# Exemplo: Certifique-se de usar o nome correto do campo de data do seu arquivo
saida = input('Digite o arquivo de saida:')
print('Incio do processamento dos imóveis do CAR...',datetime.datetime.now())
processar_car_prioridade_atual(saida)
print('Fim do processamento dos imóveis do CAR',datetime.datetime.now())
#Finalização Limpa
qgs.exitQgis()
