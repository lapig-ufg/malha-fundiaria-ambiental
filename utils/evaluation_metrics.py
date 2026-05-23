"""
Módulo: evalution_metrics.py
Descrição: Processamento escalável via DuckDB Spatial para avaliação do iGPP 2025.
           Compara duas bases fundiárias agregando resultados por Brasil e Estados,
           gerando tabelas analíticas e gráficos comparativos de qualidade geométrica.
"""

import os
import duckdb
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns


def inicializar_contexto_duckdb():
    """Inicializa a conexão DuckDB e instala a extensão espacial obrigatória."""
    conn = duckdb.connect(database=":memory:")
    conn.execute("INSTALL spatial;")
    conn.execute("LOAD spatial;")
    return conn


def extrair_metricas_base(conn, caminho_arquivo, label_base,is_mfa=True):
    """
    Executa a query analítica espacial otimizada utilizando projeção Albers
    (ESRI:102033) para cálculo preciso de áreas em escala nacional.
    """
    # Query adaptada com tratamento de agrupamento e injeção do identificador da base
    if is_mfa:
         query = f"""
        WITH metricas_base AS (
            SELECT 
                -- Mapeia o Estado a partir de um atributo comum (ex: 'sigla_uf' ou substring do nome do arquivo se necessário)
                -- Modifique o campo abaixo conforme a estrutura real dos seus atributos de UF
                --COALESCE(sigla_uf, 'ND') AS estado,
                CD_UF as estado,
                ST_Area(geometry) AS area,
                ST_Perimeter(geometry) AS perimetro,
                ST_IsValid(geometry) AS valida,
                 (4 * PI() * ST_Area(geometry)) / 
                    NULLIF(ST_Perimeter(geometry) ^ 2, 0) AS circularidade,
                ST_Area(geometry) / 
                    NULLIF(ST_Area(ST_ConvexHull(geometry)), 0) AS solidez
            FROM '{caminho_arquivo}'
        ),
        stats_estado AS (
            SELECT 
                estado,
                '{label_base}' AS base,
                COUNT(*) AS total_reg,
                COUNT(*) FILTER (WHERE NOT valida) AS qtd_invalidos,
                COUNT(*) FILTER (WHERE area < 1.0) AS poligonos_zerados_tiny,
                COUNT(*) FILTER (WHERE circularidade < 0.12 AND area < 1000) AS poligonos_ruins_slivers,
                AVG(circularidade) AS indice_circularidade_medio,
                AVG(solidez) AS indice_solidez_medio,
                SUM(area) AS area_total_malha
            FROM metricas_base
            GROUP BY estado
        )
        SELECT 
            estado,
            base,
            total_reg,
            qtd_invalidos,
            poligonos_zerados_tiny,
            poligonos_ruins_slivers,
            ROUND(indice_circularidade_medio, 4) AS indice_circularidade_medio,
            ROUND(indice_solidez_medio, 4) AS indice_solidez_medio,
            ROUND(area_total_malha / 10000, 2) AS area_total_ha
        FROM stats_estado;
        """
    else:
        query = f"""
        WITH metricas_base AS (
            SELECT 
                -- Mapeia o Estado a partir de um atributo comum (ex: 'sigla_uf' ou substring do nome do arquivo se necessário)
                -- Modifique o campo abaixo conforme a estrutura real dos seus atributos de UF
                --COALESCE(sigla_uf, 'ND') AS estado,
                (cd_mun /100000)::INT32 AS estado,
                ST_Area(ST_Transform(geom, 'EPSG:4674', 'ESRI:102033')) AS area,
                ST_Perimeter(ST_Transform(geom, 'EPSG:4674', 'ESRI:102033')) AS perimetro,
                ST_IsValid(geom) AS valida,
                (4 * PI() * ST_Area(ST_Transform(geom, 'EPSG:4674', 'ESRI:102033'))) / 
                    NULLIF(ST_Perimeter(ST_Transform(geom, 'EPSG:4674', 'ESRI:102033')) ^ 2, 0) AS circularidade,
                ST_Area(ST_Transform(geom, 'EPSG:4674', 'ESRI:102033')) / 
                    NULLIF(ST_Area(ST_ConvexHull(ST_Transform(geom, 'EPSG:4674', 'ESRI:102033'))), 0) AS solidez
            FROM ST_READ('{caminho_arquivo}')
            WHERE 'categoria_fundiari.' != 'ASRFG' 
        ),
        stats_estado AS (
            SELECT 
                estado,
                '{label_base}' AS base,
                COUNT(*) AS total_reg,
                COUNT(*) FILTER (WHERE NOT valida) AS qtd_invalidos,
                COUNT(*) FILTER (WHERE area < 1.0) AS poligonos_zerados_tiny,
                COUNT(*) FILTER (WHERE circularidade < 0.12 AND area < 1000) AS poligonos_ruins_slivers,
                AVG(circularidade) AS indice_circularidade_medio,
                AVG(solidez) AS indice_solidez_medio,
                SUM(area) AS area_total_malha
            FROM metricas_base
            GROUP BY estado
        )
        SELECT 
            estado,
            base,
            total_reg,
            qtd_invalidos,
            poligonos_zerados_tiny,
            poligonos_ruins_slivers,
            ROUND(indice_circularidade_medio, 4) AS indice_circularidade_medio,
            ROUND(indice_solidez_medio, 4) AS indice_solidez_medio,
            ROUND(area_total_malha / 10000, 2) AS area_total_ha
        FROM stats_estado;
        """
    return conn.execute(query).df()


def gerar_graficos_comparativos(df_completo, output_dir):
    """Gera visualizações estatísticas avançadas para comparação das bases."""
    os.makedirs(output_dir, exist_ok=True)
    sns.set_theme(style="whitegrid")
    
    # Gráfico 1: Comparação de Área Total Coberta por Estado
    plt.figure(figsize=(14, 6))
    sns.barplot(data=df_completo, x="estado", y="area_total_ha", hue="base", palette="viridis")
    plt.title("Comparativo de Cobertura de Área por Estado (Hectares) - iGPP 2025", fontsize=14, fontweight='bold')
    plt.xlabel("Unidade da Federação (UF)")
    plt.ylabel("Área Total (Ha)")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "comparativo_cobertura_estados.png"), dpi=300)
    plt.close()

    # Gráfico 2: Inconsistências Críticas (Slivers e Inválidos)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    
    sns.boxplot(data=df_completo, x="base", y="poligonos_ruins_slivers", ax=ax1, palette="Set2")
    ax1.set_title("Distribuição de Polígonos Ruins (Slivers) por Base", fontsize=12, fontweight='bold')
    ax1.set_ylabel("Quantidade de Slivers")
    
    sns.barplot(data=df_completo, x="estado", y="qtd_invalidos", hue="base", ax=ax2, palette="mako")
    ax2.set_title("Topologia Crítica: Polígonos Inválidos por UF", fontsize=12, fontweight='bold')
    ax2.set_ylabel("Qtd de Geometrias Inválidas")
    ax2.tick_params(axis='x', rotation=45)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "diagnostico_topologia_critica.png"), dpi=300)
    plt.close()


def main():
    # Caminhos dos datasets informados (Substitua pelos caminhos reais de produção)
    caminho_base_1 = 'D:/LAPIG/Doutorado/tese/Qualificacao/datasets/iGPP/pa_br_malhafundiaria_2025.gpkg'
    caminho_base_2 = 'D:/LAPIG/Doutorado/tese/Qualificacao/datasets/balanco_passivo_ambiental_br_v3.parquet'
    
    print("[INFO] Inicializando motor de processamento DuckDB Spatial...")
    conn = inicializar_contexto_duckdb()
    
    print("[INFO] Processando Métricas Espaciais da Base A (Referência)...")
    df_base_a = extrair_metricas_base(conn, caminho_base_1, "Base A (Referência)",is_mfa=False)
    
    print("[INFO] Processando Métricas Espaciais da Base B (Comparativa)...")
    # Nota: Caso queira testar o script de imediato, pode apontar para o mesmo arquivo com labels distintas
    df_base_b = extrair_metricas_base(conn, caminho_base_2, "Base B (Comparativa)")
    
    # Unificação dos DataFrames para análise cross-base
    df_estados = pd.concat([df_base_a, df_base_b], ignore_index=True)
    
    print("[INFO] Consolidando Métricas a Nível Brasil (Nacional)...")
    df_brasil = df_estados.groupby('base').agg({
        'total_reg': 'sum',
        'qtd_invalidos': 'sum',
        'poligonos_zerados_tiny': 'sum',
        'poligonos_ruins_slivers': 'sum',
        'indice_circularidade_medio': 'mean',
        'indice_solidez_medio': 'mean',
        'area_total_ha': 'sum'
    }).reset_index()
    
    # Outputs em console / salvamento de tabelas estruturadas
    print("\n================ TABELA DE AVALIAÇÃO - BRASIL ================")
    print(df_brasil.to_string(index=False))
    df_brasil.to_csv("analise_quality_fundiaria_brasil.csv", index=False)
    
    print("\n================ TABELA DE AVALIAÇÃO - ESTADOS (Amostra) ================")
    print(df_estados.sort_values(by=['estado', 'base']).head(10).to_string(index=False))
    df_estados.to_csv("analise_quality_fundiaria_estados.csv", index=False)
    
    print("\n[INFO] Renderizando dashboards gráficos de controle de qualidade...")
    gerar_graficos_comparativos(df_estados, output_dir="./outputs_diagnostico")
    print("[SUCESSO] Processamento finalizado. Arquivos e plots salvos em disco.")


if __name__ == "__main__":
    main()
