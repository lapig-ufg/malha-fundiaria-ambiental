# 1. Configuração do DuckDB e Carga da Extensão Espacial
import pandas as pd
import duckdb
import matplotlib.pyplot as plt
import seaborn as sns

con = duckdb.connect()
con.execute("INSTALL spatial; LOAD spatial;")

#Tabelas de dados
listClass = {
    'tih':'Territórios Sociais e de Proteção',
    'tinh':'Territórios Sociais e de Proteção',
    'tqd':'Territórios Sociais e de Proteção',
    'tqnd':'Territórios Sociais e de Proteção',
    'ucus':'Territórios Sociais e de Proteção',
    'ucpi':'Territórios Sociais e de Proteção',
    'am':'Territórios Sociais e de Proteção',
    'ma':'Territórios Sociais e de Proteção',
    'mu':'Territórios Sociais e de Proteção',
    'asses':'Reforma Agrária',
    'glbp':'Reforma Agrária',
    'fnpd':'Reforma Agrária',
    'carss':'Imóveis Rurais Privados',
    'carcs':'Imóveis Rurais Privados',
    'sigef_snci':'Imóveis Rurais Privados'
}
TABELA_IBGE = {
    11: 'RO', 12: 'AC', 13: 'AM', 14: 'RR', 15: 'PA', 16: 'AP', 17: 'TO',
    21: 'MA', 22: 'PI', 23: 'CE', 24: 'RN', 25: 'PB', 26: 'PE', 27: 'AL',
    28: 'SE', 29: 'BA', 31: 'MG', 32: 'ES', 33: 'RJ', 35: 'SP', 41: 'PR',
    42: 'SC', 43: 'RS', 50: 'MS', 51: 'MT', 52: 'GO', 53: 'DF'
}


# 2. Query Otimizada para Agregação Espacial de Big Data
sql = """
    SELECT 
        CD_UF,
        fonte,
        SUM(ST_Area(geom)) / 10000 AS area_total_ha
    FROM 
        '/content/drive/MyDrive/tese/teste_malha/DADOS_FINAIS/malha_fundiaria_consolidade_br.parquet'
    WHERE 
        CD_UF IS NOT NULL
    GROUP BY 
        CD_UF, 
        fonte
    ORDER BY 
        CD_UF, 
        area_total_ha DESC
"""

print("[*] Executando agregação espacial no DuckDB...")
df_malha = con.execute(sql).df()

# Tratamento do mapeamento via dicionário de forma segura contra KeyError
# Usamos .get(x, 'Não Classificado') para o caso de alguma fonte não mapeada no dicionário
print("[*] Aplicando reclassificação para agrupamento fundiário...")
df_malha['grp'] = df_malha['fonte'].apply(lambda x: listClass.get(x, 'Outros/Não Identificado') if isinstance(listClass, dict) else listClass(x))
df_malha['nm_uf'] = df_malha['CD_UF'].apply(lambda x: TABELA_IBGE[int(x)])
# 3. Pivotagem Segura contra Duplicidades (Solução do Erro)
# Substituição do .pivot() por .pivot_table() agregando registros duplicados com 'sum'
print("[*] Pivotando matriz de dados e consolidando áreas...")
df_pivot = df_malha.pivot_table(
    index='nm_uf', 
    columns='grp', 
    values='area_total_ha', 
    aggfunc='sum'
).fillna(0)

# Ordenação dos estados pelo total geral de área fundiária mapeada para gerar um ranking visual harmônico
df_pivot['total_geral'] = df_pivot.sum(axis=1)
df_pivot = df_pivot.sort_values(by='total_geral', ascending=False)
df_pivot = df_pivot.drop(columns=['total_geral'])

# 4. Visualização de Alta Performance (Stacked Bar Chart)
sns.set_theme(style="whitegrid")

# Ajuste dinâmico do número de cores com base na quantidade real de grupos gerados
num_classes = len(df_pivot.columns)
cmap = plt.cm.get_cmap('tab20', num_classes) 

ax = df_pivot.plot(
    kind='bar', 
    stacked=True, 
    figsize=(16, 9), 
    colormap=cmap, 
    width=0.8
)

# 5. Ajustes Técnicos e Estéticos (Padrão de Publicação Científica / PEP 8)
plt.title('Distribuição Quali-Quantitativa das Classes Fundiárias por Estado', fontsize=16, fontweight='bold')
plt.xlabel('Código da Unidade Federativa (CD_UF)', fontsize=12)
plt.ylabel('Área Total Ocupada (Hectares - ha)', fontsize=12)
plt.xticks(rotation=45)

# Posicionamento inteligente da legenda fora do plot para evitar oclusão de dados
plt.legend(
    title="Grupo Fundiário (grp)", 
    bbox_to_anchor=(1.02, 1), 
    loc='upper left', 
    borderaxespad=0.
)

# Formatação explícita do eixo Y com separadores de milhar
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, loc: "{:,.0f}".format(x)))

plt.tight_layout()
plt.show()