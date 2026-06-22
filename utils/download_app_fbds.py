import os
import requests
import unicodedata
from bs4 import BeautifulSoup
import geopandas as gpd
import os

def normalizar_nome(txt):
    # Remove acentos e caracteres especiais
    nksel = unicodedata.normalize('NFKD', txt)
    sem_acentos = "".join([c for c in nksel if not unicodedata.combining(c)])
    # Transforma em maiúsculas e troca espaços por sublinhados
    return sem_acentos.upper().replace(" ", "_") 
    
def baixar_arquivos_fbds(codigo_ibge:str, folder:str,estado:str, municipio:str):
    # URL da pasta onde os arquivos estão localizados
    url_pasta = f"https://geo.fbds.org.br/{estado}/{municipio}/APP/"
    prefixo = f"{estado}_{codigo_ibge}_APP"
    
    # Pasta local onde os arquivos serão salvos
    pasta_destino = folder#f"dados_{municipio}"
    if not os.path.exists(pasta_destino):
        os.makedirs(pasta_destino)

    print(f"Acessando: {url_pasta}")
    
    try:
        response = requests.get(url_pasta)
        response.raise_for_status()
        
        # Analisa o HTML para encontrar os links dos arquivos
        soup = BeautifulSoup(response.text, 'html.parser')
        links = soup.find_all('a')
        
        arquivos_encontrados = 0
        for link in links:
            nome_arquivo = os.path.basename(link.get('href'))
            
            # Filtra arquivos que começam com o prefixo (ex: GO_5200050_APP)
            if nome_arquivo[0:-4] == prefixo:#nome_arquivo.startswith(prefixo):
                url_download = url_pasta + nome_arquivo
                caminho_local = os.path.join(pasta_destino, nome_arquivo)
                
                print(f"Baixando: {nome_arquivo}...")
                res_file = requests.get(url_download)
                with open(caminho_local, 'wb') as f:
                    f.write(res_file.content)
                arquivos_encontrados += 1
        
        if arquivos_encontrados == 0:
            print("Nenhum arquivo encontrado com esse prefixo.")
        else:
            print(f"\nDownload concluído! {arquivos_encontrados} arquivos salvos em: {pasta_destino}")

    except Exception as e:
        print(f"Erro ao processar: {e}")


def reprojetar_shapefiles(pasta_origem, pasta_destino, epsg_alvo="ESRI:102033"):
    # Cria a pasta de destino se não existir
    if not os.path.exists(pasta_destino):
        os.makedirs(pasta_destino)
    
    # Lista todos os arquivos .shp na pasta de origem
    arquivos = [f for f in os.listdir(pasta_origem) if f.endswith('.shp')]
    
    if not arquivos:
        print("Nenhum arquivo .shp encontrado para converter.")
        return

    for arquivo in arquivos:
        caminho_entrada = os.path.join(pasta_origem, arquivo)
        caminho_saida = os.path.join(pasta_destino, 'proj_'+arquivo)
        
        print(f"Lendo {arquivo}...")
        
        # 1. Carregar o arquivo
        gdf = gpd.read_file(caminho_entrada)
        
        # 2. Reprojetar (to_crs)
        # Nota: 102033 muitas vezes é reconhecido pelo prefixo ESRI
        print(f"Reprojetando para {epsg_alvo}...")
        gdf_reprojetado = gdf.to_crs(epsg_alvo)
        
        # 3. Salvar o novo arquivo
        gdf_reprojetado.to_file(caminho_saida)
        print(f"Salvo com sucesso em: {caminho_saida}\n")

#Lista dos Municipios pela Unidade de Federação
def listMunEstados(UF:str) -> dict:
    
    #Lista dos municipios goianos
    uf = UF
    url = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios"

    listMun = {}
    response = requests.get(url)
    response.raise_for_status()
    dados = response.json()
    
    for dado in dados:
        listMun[str(dado['id'])] =  normalizar_nome(dado['nome'])
    
    return listMun
    

if __name__  == 'main':
    
    #Pasta de Saida
    outputfolder = input('Pasta de saida dos arquivos:')
    
    #Arquivos de Log's
    logfile = os.path.join(outputfolder,'log.txt')
    logfile = open(logfile,'w')   
    logfile.writelines('Municipios sem APP no FBDS')
    logfile.writelines('\n')
    
    #Acessar todos as Unidades de Federação
    url = 'https://servicodados.ibge.gov.br/api/v1/localidades/estados?orderBy=nome'
    response = requests.get(url)
    dados = response.json()
    estados = [estado['sigla']  for estado in dados]
    
    #Iteração sobre todos os estados
    for estado in estados:
        listMunEstados = listMunEstados(estado)
        for key in listMun.keys():
            print('BAIXANDO:'+listMun[key]+'...') 
            try:
                baixar_arquivos_fbds(key, outputfolder,estado,listMun[key])
            except:
                print(listMun[key]+'/'+estado,' ausência da base fbds...')
                logfile.writelines(listMun[key]+'/'+estado)
                logfile.writelines('\n')
                continue
            print('Finalizado...')
    
    logfile.close()
    
