# Importar módulos
from qgis import processing
import datetime


# ──────────────────────────────────────────────────────────────────────────────
#  Utilitários de Log
# ──────────────────────────────────────────────────────────────────────────────

def _agora():
    """Retorna timestamp formatado."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _duracao(inicio: datetime.datetime) -> str:
    """Calcula e formata a duração desde `inicio` até agora."""
    delta = datetime.datetime.now() - inicio
    total = int(delta.total_seconds())
    h, resto = divmod(total, 3600)
    m, s     = divmod(resto, 60)
    if h > 0:
        return f"{h}h {m:02d}m {s:02d}s"
    if m > 0:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def _area_camada_m2(layer_path: str) -> float:
    """
    Soma a área de todas as feições de um arquivo vetorial em m².
    Retorna 0.0 se o arquivo não existir ou não for válido.
    """
    from qgis.core import QgsVectorLayer
    lyr = QgsVectorLayer(layer_path, "_area_tmp", "ogr")
    if not lyr.isValid():
        return 0.0
    return sum(f.geometry().area() for f in lyr.getFeatures())


def _fmt_area(m2: float) -> str:
    """Formata área em m², ha ou km² conforme a magnitude."""
    if m2 >= 1_000_000:
        return f"{m2 / 1_000_000:,.4f} km²"
    if m2 >= 10_000:
        return f"{m2 / 10_000:,.4f} ha"
    return f"{m2:,.2f} m²"


def _banner(texto: str, char: str = "═", largura: int = 70) -> None:
    """Imprime um banner delimitado."""
    linha = char * largura
    print(f"\n{linha}")
    print(f"  {texto}")
    print(linha)


def _log_etapa(numero: str, descricao: str, inicio: datetime.datetime) -> None:
    """Imprime linha de conclusão de uma sub-etapa com duração."""
    print(f"   ✔  [{_agora()}] Etapa {numero} — {descricao}  |  ⏱ {_duracao(inicio)}")


# ──────────────────────────────────────────────────────────────────────────────
#  preparar_camada
# ──────────────────────────────────────────────────────────────────────────────

def preparar_camada(camada):
    """
    Remove TODOS os campos exceto os essenciais e adiciona/atualiza a fonte_origem.
    Campos mantidos: 'fonte', 'cod_malha', 'cls_malha'.
    """
    whitelist = ['fonte', 'cod_malha', 'cls_malha']
    fields_to_del = [i for i, f in enumerate(camada.fields()) if f.name() not in whitelist]
    if fields_to_del:
        camada.dataProvider().deleteAttributes(fields_to_del)
        camada.updateFields()


# ──────────────────────────────────────────────────────────────────────────────
#  filtrar_invalidos
# ──────────────────────────────────────────────────────────────────────────────

def filtrar_invalidos(input_path, output_path):
    """Extrai apenas geometrias válidas para evitar erros no Difference."""
    t0 = datetime.datetime.now()
    print(f"   │  [{_agora()}] Filtrando geometrias inválidas...")
    processing.run("native:extractbyexpression", {
        'INPUT':      input_path,
        'EXPRESSION': 'is_valid($geometry)',
        'OUTPUT':     output_path
    })
    print(f"   │  ✔  [{_agora()}] Geometrias inválidas removidas  |  ⏱ {_duracao(t0)}")


# ──────────────────────────────────────────────────────────────────────────────
#  remover_slivers
# ──────────────────────────────────────────────────────────────────────────────

def remover_slivers(input_path, output_path, area_minima=5.0):
    """Remove polígonos menores que a área mínima (slivers)."""
    t0 = datetime.datetime.now()
    print(f"   │  [{_agora()}] Removendo slivers (< {area_minima} m²)...")

    area_antes = _area_camada_m2(input_path)
    processing.run("native:extractbyexpression", {
        'INPUT':      input_path,
        'EXPRESSION': f'$area > {area_minima}',
        'OUTPUT':     output_path
    })
    area_depois = _area_camada_m2(output_path)
    perda       = area_antes - area_depois

    print(f"   │  ✔  [{_agora()}] Slivers removidos  "
          f"|  Área antes: {_fmt_area(area_antes)}  "
          f"|  Após: {_fmt_area(area_depois)}  "
          f"|  Perda: {_fmt_area(perda)}  "
          f"|  ⏱ {_duracao(t0)}")


# ──────────────────────────────────────────────────────────────────────────────
#  processar_recorte_prioritario
# ──────────────────────────────────────────────────────────────────────────────

def construcao_malha_fundiaria(lista_prioridade, output_folder, area_sliver=1.0):
    import os
    from qgis.core import (
        QgsVectorLayer, QgsProject, QgsFeatureRequest,
        QgsFeature, QgsApplication, QgsDataSourceUri,
        QgsSpatialIndex, QgsGeometry, QgsField
    )
    logfile = open('C:/Users/Bernard/Documents/Projetos/MalhaFundiaria/datasets/tipos_malha_fundiaria/BR/logs/log_integracao_fundiaria_v2.txt','w')
    t_global = datetime.datetime.now()
    _banner(f"INICIANDO PROCESSAMENTO HIERÁRQUICO  |  {_agora()}")
    print(f"  Camadas na fila : {len(lista_prioridade)}")
    print(f"  Pasta de saída  : {output_folder}")
    print(f"  Área mínima     : {area_sliver} m² (remoção de slivers)")
    logfile.writelines(f"INICIANDO PROCESSAMENTO HIERÁRQUICO  |  {_agora()} \n")
    logfile.writelines(f"  Pasta de saída  : {output_folder} \n")
    logfile.writelines(f"  Área mínima     : {area_sliver} m² (remoção de slivers \n")
    
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    temp_folder = os.path.join(output_folder, "temp_proc")
    
    if not os.path.exists(temp_folder):
        os.makedirs(temp_folder)

    camadas_finais_paths = []
    lista_mascaras_paths = []
    
    # ──────────────────────────────────────────────────────────────────────────
    for i in range(len(lista_prioridade)):
        t_camada = datetime.datetime.now()
        label    = os.path.basename(lista_prioridade[i])[0:-4]
        print('Versão 02 - Integração')
        _banner(
            f"[Camada {i+1}/{len(lista_prioridade)}]  {label}  |  início: {_agora()}",
            char="─"
        )
        logfile.writelines(f"[Camada {i+1}/{len(lista_prioridade)}]  {label}  |  início: {_agora()} \n")
        # ── 1. Carregar camada ────────────────────────────────────────────────
        t0  = datetime.datetime.now()
        print(f"   │")
        print(f"   ├─ [ETAPA 1/6] Carregando camada — {_agora()}")
        logfile.writelines(f"   ├─ [ETAPA 1/6] Carregando camada — {_agora()} \n")
        lyr_raw = QgsVectorLayer(lista_prioridade[i], label, "ogr")

        if not lyr_raw.isValid():
            logfile.writelines(f"   └─ ✘  ERRO: não foi possível carregar '{label}'. Pulando. \n")
            print(f"   └─ ✘  ERRO: não foi possível carregar '{label}'. Pulando.")
            continue

        n_feicoes   = lyr_raw.featureCount()
        area_bruta  = sum(f.geometry().area() for f in lyr_raw.getFeatures())
        _log_etapa("1/6", f"Camada carregada  |  {n_feicoes} feição(ões)  "
                           f"|  Área total: {_fmt_area(area_bruta)}", t0)
        logfile.writelines(f"1/6 Camada carregada  |  {n_feicoes} feição(ões)  |  Área total: {_fmt_area(area_bruta)} \n")
        # ── 2. Preparar atributos ─────────────────────────────────────────────
        print(f"   │")
        print(f"   ├─ [ETAPA 2/6] Preparando atributos — {_agora()}")
        logfile.writelines(f"   ├─ [ETAPA 2/6] Preparando atributos — {_agora()} \n")
        
        t0 = datetime.datetime.now()
        
        fix_res = processing.run("native:fixgeometries", {'INPUT': lyr_raw, 'OUTPUT': 'memory:'})
        lyr_fix = fix_res['OUTPUT']
        preparar_camada(lyr_fix)
        
        _log_etapa("2/6", "Atributos preparados", t0)
        final_path = os.path.join(output_folder, f"{i:02d}_{label}.gpkg")
        
        # ── 3. Corrigir geometria ─────────────────────────────────────────────
        print(f"   │")
        print(f"   ├─ [ETAPA 3/6] Corrigindo geometrias — {_agora()}")
        logfile.writelines(f"   ├─ [ETAPA 3/6] Corrigindo geometrias — {_agora()} \n")
        
        t0       = datetime.datetime.now()
        path_fix = os.path.join(temp_folder, f"fix_{label}_v4c.gpkg")
        processing.run("native:fixgeometries", {'INPUT': lyr_raw, 'OUTPUT': path_fix})
        area_apos_fix = _area_camada_m2(path_fix)
        perda_fix     = area_bruta - area_apos_fix
        _log_etapa("3/6",
                   f"Geometrias corrigidas  "
                   f"|  Área após fix: {_fmt_area(area_apos_fix)}  "
                   f"|  Perda: {_fmt_area(perda_fix)}",
                   t0)
        logfile.writelines("3/6 Geometrias corrigidas  \n")
        logfile.writelines(f"|  Área após fix: {_fmt_area(area_apos_fix)}  \n")
        logfile.writelines(f"|  Perda: {_fmt_area(perda_fix)} \n")
        final_layer_path = os.path.join(output_folder, f"{i:02d}_{label}.gpkg")

        if i == 0:
            # ── 4a. Camada-base: apenas remover slivers ───────────────────────
            print(f"   │")
            print(f"   ├─ [ETAPA 4/6] Remoção de slivers (camada-base) — {_agora()}")
            logfile.writelines(f"   ├─ [ETAPA 4/6] Remoção de slivers (camada-base) — {_agora()} \n")
            t0 = datetime.datetime.now()
            remover_slivers(path_fix, final_layer_path, area_sliver)
            _log_etapa("4/6", "Slivers removidos da camada-base", t0)
            logfile.writelines("4/6 Slivers removidos da camada-base {t0} \n")

        else:
            # ── 4b. Criar máscara acumulada ───────────────────────────────────
            print(f"   │")
            print(f"   ├─ [ETAPA 4/6] Construindo máscara acumulada "
                  f"({len(lista_mascaras_paths)} camada(s)) — {_agora()}")
            logfile.writelines(f" ├─ [ETAPA 4/6] Construindo máscara acumulada \n")
            logfile.writelines(f"({len(lista_mascaras_paths)} camada(s)) — {_agora()} \n")
            t0        = datetime.datetime.now()
            raw_mask  = os.path.join(temp_folder, f"raw_mask_{i}_v4c.gpkg")
            clean_mask = os.path.join(temp_folder, f"clean_mask_{i}_v4c.gpkg")

            processing.run("native:mergevectorlayers",
                           {'LAYERS': lista_mascaras_paths, 'OUTPUT': raw_mask})
            filtrar_invalidos(raw_mask, clean_mask)
            area_mascara = _area_camada_m2(clean_mask)
            _log_etapa("4/6",
                       f"Máscara pronta  |  Área mascarada: {_fmt_area(area_mascara)}",
                       t0)
            logfile.writelines(f"4/6 Máscara pronta  |  Área mascarada: {_fmt_area(area_mascara)} {t0}\n")
            
            # CRIAR ÍNDICE ESPACIAL (O pulo do gato para 20 núcleos)
            lyr_mask = QgsVectorLayer(clean_mask, "mask_temp", "ogr")
            index = QgsSpatialIndex(lyr_mask.getFeatures())
            
            # ── 5. Difference ─────────────────────────────────────────────────
            print(f"   │")
            print(f"   ├─ [ETAPA 5/6] Recorte hierárquico (Difference) — {_agora()}")
            logfile.writelines(f"   ├─ [ETAPA 5/6] Recorte hierárquico (Difference) — {_agora()} \n")
            t0        = datetime.datetime.now()
            path_diff = os.path.join(temp_folder, f"diff_{label}.gpkg")

            try:
                processing.run("native:difference", {
                    'INPUT':   path_fix,
                    'OVERLAY': lyr_mask,#clean_mask,
                    'OUTPUT':  path_diff
                })
                print(f"   │  ✔  Difference padrão concluído")
                logfile.writelines(f"   │  ✔  Difference padrão concluído \n")
            except Exception as e_diff:
                print(f"   │  ⚠  Difference direto falhou: {e_diff}")
                print(f"   │     Aplicando Buffer(0) como contorno...")
                path_b0 = os.path.join(temp_folder, f"b0_{label}_v4c.gpkg")
                processing.run("native:buffer",
                               {'INPUT': path_fix, 'DISTANCE': 0, 'OUTPUT': path_b0})
                processing.run("native:difference",
                               {'INPUT': path_b0, 'OVERLAY': clean_mask, 'OUTPUT': path_diff})
                print(f"   │  ✔  Difference com Buffer(0) concluído")

            # Calcular perda real imóvel a imóvel
            area_apos_diff = _area_camada_m2(path_diff)
            perda_diff     = area_apos_fix - area_apos_diff
            pct_perda      = (perda_diff / area_apos_fix * 100) if area_apos_fix > 0 else 0.0

            _log_etapa("5/6",
                       f"Difference concluído  "
                       f"|  Área original : {_fmt_area(area_apos_fix)}  "
                       f"|  Área resultante: {_fmt_area(area_apos_diff)}  "
                       f"|  Perda por recorte: {_fmt_area(perda_diff)} ({pct_perda:.2f} %)",
                       t0)
            logfile.writelines(f"5/6 Difference concluído  \n" )
            logfile.writelines(f"|  Área original : {_fmt_area(area_apos_fix)}  \n")
            logfile.writelines(f"|  Área resultante: {_fmt_area(area_apos_diff)}  \n")
            logfile.writelines(f"|  Perda por recorte: {_fmt_area(perda_diff)} ({pct_perda:.2f} %) \n" )
         
            # ── 6. Remover slivers pós-recorte ───────────────────────────────
            print(f"   │")
            print(f"   ├─ [ETAPA 6/6] Remoção de slivers pós-recorte — {_agora()}")
            logfile.writelines(f"   ├─ [ETAPA 6/6] Remoção de slivers pós-recorte — {_agora()} \n")
            t0 = datetime.datetime.now()
            remover_slivers(path_diff, final_layer_path, area_sliver)
            _log_etapa("6/6", "Slivers pós-recorte removidos", t0)
            logfile.writelines(f"6/6 Slivers pós-recorte removidos {t0} \n")
        # ── Resumo da camada ──────────────────────────────────────────────────
        area_final   = _area_camada_m2(final_layer_path)
        perda_total  = area_bruta - area_final
        pct_total    = (perda_total / area_bruta * 100) if area_bruta > 0 else 0.0

        print(f"   │")
        print(f"   └─ ✔  [{_agora()}]  {label}  CONCLUÍDA  |  ⏱ {_duracao(t_camada)}")
        print(f"          ┌──────────────────────────────────────────────────")
        print(f"          │  Área bruta (entrada) : {_fmt_area(area_bruta)}")
        logfile.writelines(f"          │  Área bruta (entrada) : {_fmt_area(area_bruta)} \n")
        print(f"          │  Área final  (saída)  : {_fmt_area(area_final)}")
        logfile.writelines(f"          │  Área final  (saída)  : {_fmt_area(area_final)} \n")
        print(f"          │  Perda total          : {_fmt_area(perda_total)}  ({pct_total:.2f} %)")
        logfile.writelines(f"          │  Perda total          : {_fmt_area(perda_total)}  ({pct_total:.2f} %) \n")
        print(f"          └──────────────────────────────────────────────────")

        camadas_finais_paths.append(final_layer_path)
        lista_mascaras_paths.append(final_layer_path)

    # ── Unificação Final ──────────────────────────────────────────────────────
    _banner(f"GERANDO MALHA FINAL UNIFICADA  |  {_agora()}")
    logfile.writelines(f"GERANDO MALHA FINAL UNIFICADA  |  {_agora()}")
    t0 = datetime.datetime.now()
    final_output = os.path.join(output_folder, "MALHA_FUNDIARIA_BR_CONSOLIDADA.gpkg")

    processing.run("native:mergevectorlayers", {
        'LAYERS': camadas_finais_paths,
        'OUTPUT': final_output
    })

    area_consolidada = _area_camada_m2(final_output)
    print(f"   ✔  [{_agora()}] Merge finalizado  "
          f"|  Área consolidada: {_fmt_area(area_consolidada)}  "
          f"|  ⏱ {_duracao(t0)}")
    logfile.writelines(f"   ✔  [{_agora()}] Merge finalizado  \n")
    logfile.writelines(f"|  Área consolidada: {_fmt_area(area_consolidada)}  \n")
    logfile.writelines(f"|  ⏱ {_duracao(t0)} \n")

    # ── Relatório global ──────────────────────────────────────────────────────
    _banner(f"RELATÓRIO FINAL  |  {_agora()}")
    logfile.writelines(f"RELATÓRIO FINAL  |  {_agora()} \n")
    print(f"  Arquivo gerado  : {final_output}")
    logfile.writelines(f"  Arquivo gerado  : {final_output} \n")
    print(f"  Área total final: {_fmt_area(area_consolidada)}")
    logfile.writelines(f"  Área total final: {_fmt_area(area_consolidada)} \n")
    print(f"  Tempo total     : {_duracao(t_global)}")
    logfile.writelines(f"  Tempo total     : {_duracao(t_global)} \n")
    print("═" * 70)
    logfile.writelines("═===================================================== \n")
    logfile.close()




    return final_output
