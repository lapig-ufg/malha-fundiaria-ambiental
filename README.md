# Algoritmo de Malha Fundiária Ambiental: Metodologia e Processamento Territorial 

## Sobre
O material apresenta o desenvolvimento de um algoritmo avançado voltado para a criação de uma malha fundiária ambiental integrada e precisa para o território brasileiro. O processo é estruturado em cinco etapas principais, que abrangem desde a coleta e tratamento de dados brutos até a resolução de conflitos de sobreposição territorial por meio do método multicritério AHP. Essa metodologia transforma registros diversos em um produto geoespacial padronizado, garantindo segurança jurídica e precisão técnica ao classificar áreas como propriedades privadas, terras indígenas e unidades de conservação. Além de fornecer uma visão detalhada dos ativos ambientais, o sistema permite atualizações mensais para apoiar análises territoriais de escala nacional. O objetivo final é oferecer uma ferramenta robusta para a gestão territorial, capaz de identificar com clareza a ocupação do solo e a conformidade ambiental no Brasil.
** **
## Etapas Metodológicas

O algoritmo de malha fundiária ambiental é composto por cinco etapas principais, conforme detalhado nos documentos:

* **1 - Data Ingestion:** Collection and organization of land and territorial data, including private properties, indigenous lands, and conservation units.

* **2 - Pré-processamento de dados:** Inclui a correção topológica para eliminar inconsistências geométricas, reprojeção das camadas, filtragem (como a exclusão de imóveis com status cancelado ou suspenso no CAR) e resolução de duplicidades e sobreposições.

* **3 - Conversão Matricial:**  Realiza a rasterização das camadas fundiárias processadas, transformando-as em uma imagem multibanda onde cada banda corresponde exclusivamente a uma camada fundiária.

* **4 - Análise de sobreposição fundiária:** Identifica áreas com ou sem conflito. Para áreas com sobreposição, o algoritmo aplica o método multicritério AHP (Processo Hierárquico Analítico) para determinar qual camada deve prevalecer com base em critérios como segurança jurídica e precisão geométrica.

* **5- Integração Ambiental:** Integra os ativos ambientais (como Áreas de Preservação Permanente - APP) à malha fundiária, gerando o produto final consolidado

** **
## Requisito

* Python versão 3.9 acima

* QGIS Desktop versão 3.44 acima

* GDAL 

* Duckdb
  



## Histórico de versões

* v 1.0
    * Construção da Malha Fundiária Ambiental para o estado de Goiás. 
  
  
