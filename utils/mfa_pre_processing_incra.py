#Importar módulos
from qgis.core import  QgsProject, QgsVectorLayer, QgsFeatureRequest, QgsFeature, QgsApplication,QgsDataSourceUri, QgsSpatialIndex,QgsGeometry,QgsField
from qgis import processing
import sys
from qgis.analysis import QgsNativeAlgorithms
import os
from PyQt5.QtCore import QVariant
import glob
import shutil
import time
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

def analisar_sobreposicao_otimizado(layer_path, saida):
    
    #print(f"Lendo arquivo: {os.path.basename(layer_path)}")
    layer = layer_path#QgsVectorLayer(layer_path, "camada_entrada", "memory")
    
    # 1. Carregamos as features e já ordenamos por área (Menor -> Prioridade)
    features_ordenadas = sorted([f for f in layer.getFeatures()], key=lambda f: f.geometry().area())
    
    layer_resultado = QgsVectorLayer(f"Polygon?crs={layer.crs().authid()}", "resultado", "memory")
    layer_resultado.dataProvider().addAttributes(layer.fields())
    layer_resultado.updateFields()

    # 2. ÍNDICE ESPACIAL DINÂMICO
    # Em vez de uma lista estática, usamos o índice para filtrar candidatos ao recorte
    index = QgsSpatialIndex()
    
    # Dicionário para recuperar geometrias processadas via ID
    processed_geoms = {} 

    print("Iniciando recorte hierárquico com filtro espacial...")
    
    #with edit(layer_resultado): # Uso do context manager para commit em bloco
    
    for i, feat in enumerate(features_ordenadas):
            geom_atual = feat.geometry()
            
            # BUSCA ESPACIAL: Pega apenas IDs de geometrias que intersectam o bounding box da atual
            candidate_ids = index.intersects(geom_atual.boundingBox())
        
            for c_id in candidate_ids:
                geom_fixa = processed_geoms[c_id]
                if geom_atual.intersects(geom_fixa):
                    geom_atual = geom_atual.difference(geom_fixa)
                    if geom_atual.isEmpty():
                       break
            
            if not geom_atual.isEmpty() and geom_atual.area() > 1.0:
                feat.setGeometry(geom_atual)
                layer_resultado.dataProvider().addFeatures([feat])
                
                # ADICIONA AO ÍNDICE para os próximos imóveis
                new_id = feat.id()
                index.addFeature(feat)
                processed_geoms[new_id] = geom_atual

            if i % 500 == 0:
                print(f"Processado: {i}/{len(features_ordenadas)} imóveis. Memória estável.")

    processing.run("native:savefeatures", {'INPUT': layer_resultado, 'OUTPUT': saida})
   

def consolidar_malhas_qgis(saida):
    """
    Utiliza o motor de processamento do QGIS para priorizar a malha SIGEF.
    """
    #Carregar as camadas
    uri = QgsDataSourceUri()
    uri.setConnection("localhost", "5432", "postgis", "postgres", "123456")    
    
    uri.setDataSource("mfa", "13_malha_fundiaria_gleba_publica_sigef", "geom")
    layer_sigef = QgsVectorLayer(uri.uri(), "SIGEF_PostGIS", "postgres")
    
    uri.setDataSource("mfa", "13_malha_fundiaria_gleba_publica_snci", "geom")
    layer_snci = QgsVectorLayer(uri.uri(), "SNCI_PostGIS", "postgres")
    
    
    print('Corrigindo a geometria SIGEF')
    fix_geo_sigef = processing.run("native:fixgeometries", {
        'INPUT': layer_sigef,
        'OUTPUT': 'memory:fix_sigef'
    })['OUTPUT']
    
    print('Corrigindo a geometria SNCI')
    fix_geo_snci = processing.run("native:fixgeometries", {
        'INPUT': layer_snci,
        'OUTPUT': 'memory:fix_snci'
    })['OUTPUT']
    
    if not layer_sigef.isValid() or not layer_snci.isValid():
        print("Erro ao carregar as camadas. Verifique os caminhos.")
        return

    print("Iniciando recorte da base SNCI...")

    # 2. Executar 'Difference': Remove do SNCI o que está sobreposto pelo SIGEF
    # Isso garante que não haverá duplicidade geométrica.
    params_diff = {
        'INPUT': fix_geo_snci,
        'OVERLAY': fix_geo_sigef,
        'OUTPUT': 'memory:SNCI_Recortado'
    }
    result_diff = processing.run("native:difference", params_diff)
    snci_recortado = result_diff['OUTPUT']

    print("Limpando resíduos topológicos (Slivers)...")
    
    # 3. Opcional: Filtrar polígonos irrelevantes gerados pelo recorte (ex: < 1m2)
    # No QGIS, isso pode ser feito via seleção por expressão
    snci_recortado.setSubsetString("area($geometry) > 5")

    print("Unificando camadas...")

    # 4. Mesclar as camadas: SIGEF (íntegro) + SNCI (apenas áreas não certificadas)
    #outputFile = output
    params_merge = {
        'LAYERS': [layer_sigef, snci_recortado],
        'CRS': 'ESRI:102033',
        'OUTPUT': 'memory:Malha_Consolidada_Final'
    }
    result_final = processing.run("native:mergevectorlayers", params_merge)['OUTPUT']
    
    print("Processo concluído. Camada 'Malha_Consolidada_Final' adicionada.")
    analisar_sobreposicao_otimizado(result_final,saida)
 

# Exemplo de chamada (ajuste os caminhos para sua realidade):
saida = input('Digite o arquivo de saida:')

#Inicio do processamento
print('Inicio do processamento',datetime.datetime.now())

#Integração INCRA / SNCI
consolidar_malhas_qgis(saida)

#Final do processamento
print('Final do processamento', datetime.datetime.now())

#Finalização Limpa
qgs.exitQgis()
