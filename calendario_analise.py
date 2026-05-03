"""
calendario_analise.py
Modulo de calculos puros para a aba "Analise de Uso" do Calendario (Etapa F.7).

Funcoes puras (sem Streamlit) que retornam DataFrames e dicts.
A UI consome essas funcoes em paginas/calendario.py::_render_aba_analise.

Estrutura interna:
    1. Receita: buscar_lancamentos_periodo, enriquecer_lancamentos_com_atividade
    2. KPIs:    calcular_kpis_receita
    3. Ocupacao: _unir_intervalos, _intervalos_unidos_lista, calcular_horas_ocupadas_ambiente,
                 calcular_horas_funcionamento, calcular_ocupacao_periodo
    4. Heatmap: gerar_dados_heatmap, _distribuir_em_slots
    5. Comparativo: calcular_periodo_anterior
    6. Orquestrador: carregar_dados_brutos, calcular_painel_completo

Convencoes:
    - dia_semana: 0=segunda ... 6=domingo (Python weekday())
    - hora: int 0-23
    - Internamente trabalho com minutos (int) pra evitar imprecisao de float;
      so converto pra horas (float) no retorno.
    - DataFrames vazios sao retornados com colunas explicitas pra evitar erros downstream.
"""

import datetime as dt
from datetime import date, timedelta

import pandas as pd

from db import buscar_dados


# Convencao Python: 0=segunda ... 6=domingo
DIAS_SEMANA_NOMES = ["Segunda", "Terca", "Quarta", "Quinta", "Sexta", "Sabado", "Domingo"]


# ============================================================================
# 1. RECEITA
# ============================================================================

def buscar_lancamentos_periodo(data_ini, data_fim):
    """Le lancamentos de Entrada e filtra por data no Python.

    Retorna DataFrame com colunas: id, data (Timestamp), valor_liquido (float),
    categoria (string).

    db.py::buscar_dados nao suporta BETWEEN, entao o filtro e feito no DataFrame.
    Volume baixo (~50 alunos x meses), performance nao e preocupacao.
    """
    df = buscar_dados("lancamentos", eq={"tipo": "Entrada"})

    if df.empty:
        return pd.DataFrame(columns=["id", "data", "valor_liquido", "categoria"])

    df["data"] = pd.to_datetime(df["data"], errors="coerce")

    inicio = pd.Timestamp(data_ini)
    fim = pd.Timestamp(data_fim)
    df = df[(df["data"] >= inicio) & (df["data"] <= fim)].copy()

    df["valor_liquido"] = pd.to_numeric(df["valor_liquido"], errors="coerce").fillna(0.0)
    df["categoria"] = df["categoria"].fillna("").astype(str)

    return df[["id", "data", "valor_liquido", "categoria"]].reset_index(drop=True)


def enriquecer_lancamentos_com_atividade(df_lanc, df_atividades):
    """Cruza lancamentos.categoria (texto) com atividades_entrada.nome (texto).

    Match case-insensitive com TRIM (LOWER+TRIM dos dois lados).
    Lancamentos sem match recebem ambiente_id=NaN, usa_espaco=False, classificada=False.

    Retorna df_lanc com colunas extras:
        - ambiente_id: int ou NaN
        - usa_espaco: bool
        - classificada: bool (True se a categoria bate com algum nome em atividades_entrada)
    """
    df = df_lanc.copy()

    if df.empty:
        df["ambiente_id"] = pd.Series(dtype="float64")
        df["usa_espaco"] = pd.Series(dtype="bool")
        df["classificada"] = pd.Series(dtype="bool")
        return df

    if df_atividades.empty:
        df["ambiente_id"] = float("nan")
        df["usa_espaco"] = False
        df["classificada"] = False
        return df

    df_ativ = df_atividades.copy()
    df_ativ["_nome_norm"] = df_ativ["nome"].astype(str).str.strip().str.lower()

    map_amb = dict(zip(df_ativ["_nome_norm"], df_ativ["ambiente_id"]))
    map_usa = dict(zip(df_ativ["_nome_norm"], df_ativ["usa_espaco"]))
    nomes_norm_set = set(df_ativ["_nome_norm"])

    df["_cat_norm"] = df["categoria"].astype(str).str.strip().str.lower()
    df["ambiente_id"] = df["_cat_norm"].map(map_amb)
    df["usa_espaco"] = df["_cat_norm"].map(map_usa).fillna(False).astype(bool)
    df["classificada"] = df["_cat_norm"].isin(nomes_norm_set)

    return df.drop(columns=["_cat_norm"])


# ============================================================================
# 2. KPIs DE RECEITA
# ============================================================================

def calcular_kpis_receita(df_lanc_enriquecido, df_ambientes):
    """Calcula todos os KPIs de receita do periodo a partir do DataFrame enriquecido.

    Retorna dict:
        {
            'receita_total': float,
            'receita_espaco': float,
            'receita_extra_espaco': float,
            'receita_nao_classificada': float,
            'm2_rentavel': float,
            'm2_total': float,
            'r_por_m2_rentavel': float,
            'r_por_m2_total': float,
            'receita_por_ambiente': {amb_id: {nome, area_m2, rentavel, receita, r_por_m2}},
            'extras_por_categoria': {categoria_str: float},
        }
    """
    if df_lanc_enriquecido.empty:
        receita_total = 0.0
        receita_espaco = 0.0
        receita_extra = 0.0
        receita_nao_class = 0.0
    else:
        receita_total = float(df_lanc_enriquecido["valor_liquido"].sum())
        df_class = df_lanc_enriquecido[df_lanc_enriquecido["classificada"]]
        df_nao_class = df_lanc_enriquecido[~df_lanc_enriquecido["classificada"]]
        receita_espaco = float(df_class[df_class["usa_espaco"]]["valor_liquido"].sum())
        receita_extra = float(df_class[~df_class["usa_espaco"]]["valor_liquido"].sum())
        receita_nao_class = float(df_nao_class["valor_liquido"].sum())

    if df_ambientes.empty:
        m2_rentavel = 0.0
        m2_total = 0.0
        df_amb_ativos = pd.DataFrame()
    else:
        df_amb_ativos = df_ambientes[df_ambientes["ativo"]].copy()
        if df_amb_ativos.empty:
            m2_total = 0.0
            m2_rentavel = 0.0
        else:
            m2_total = float(df_amb_ativos["area_m2"].sum())
            m2_rentavel = float(df_amb_ativos[df_amb_ativos["rentavel"]]["area_m2"].sum())

    r_por_m2_rentavel = receita_espaco / m2_rentavel if m2_rentavel > 0 else 0.0
    r_por_m2_total = receita_espaco / m2_total if m2_total > 0 else 0.0

    receita_por_ambiente = {}
    if not df_amb_ativos.empty:
        for _, amb in df_amb_ativos.iterrows():
            amb_id = int(amb["id"])
            area = float(amb["area_m2"])

            if df_lanc_enriquecido.empty:
                rec = 0.0
            else:
                df_a = df_lanc_enriquecido[
                    df_lanc_enriquecido["usa_espaco"]
                    & (df_lanc_enriquecido["ambiente_id"] == amb_id)
                ]
                rec = float(df_a["valor_liquido"].sum())

            receita_por_ambiente[amb_id] = {
                "nome": str(amb["nome"]),
                "area_m2": area,
                "rentavel": bool(amb["rentavel"]),
                "receita": rec,
                "r_por_m2": rec / area if area > 0 else 0.0,
            }

    extras_por_categoria = {}
    if not df_lanc_enriquecido.empty:
        df_extras = df_lanc_enriquecido[
            df_lanc_enriquecido["classificada"] & ~df_lanc_enriquecido["usa_espaco"]
        ]
        if not df_extras.empty:
            extras_por_categoria = (
                df_extras.groupby("categoria")["valor_liquido"]
                .sum()
                .to_dict()
            )

    return {
        "receita_total": receita_total,
        "receita_espaco": receita_espaco,
        "receita_extra_espaco": receita_extra,
        "receita_nao_classificada": receita_nao_class,
        "m2_rentavel": m2_rentavel,
        "m2_total": m2_total,
        "r_por_m2_rentavel": r_por_m2_rentavel,
        "r_por_m2_total": r_por_m2_total,
        "receita_por_ambiente": receita_por_ambiente,
        "extras_por_categoria": extras_por_categoria,
    }


# ============================================================================
# 3. OCUPACAO (uniao de intervalos)
# ============================================================================

def _hora_str_para_minutos(hora_str):
    """Converte 'HH:MM' ou 'HH:MM:SS' em minutos a partir de 00:00."""
    if not hora_str:
        return 0
    s = str(hora_str)[:5]
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def _unir_intervalos(intervalos):
    """Recebe lista de tuplas (inicio_min, fim_min) e retorna o total de minutos cobertos.

    Sobreposicoes contam 1 vez. Ex: [(60, 120), (90, 180)] -> 120 minutos.
    """
    if not intervalos:
        return 0
    intervalos_ord = sorted(intervalos, key=lambda x: x[0])
    total_minutos = 0
    cur_ini, cur_fim = intervalos_ord[0]
    for ini, fim in intervalos_ord[1:]:
        if ini <= cur_fim:
            cur_fim = max(cur_fim, fim)
        else:
            total_minutos += cur_fim - cur_ini
            cur_ini, cur_fim = ini, fim
    total_minutos += cur_fim - cur_ini
    return total_minutos


def _intervalos_unidos_lista(intervalos):
    """Como _unir_intervalos mas retorna a lista de tuplas mergeadas (nao a soma)."""
    if not intervalos:
        return []
    intervalos_ord = sorted(intervalos, key=lambda x: x[0])
    resultado = [intervalos_ord[0]]
    for ini, fim in intervalos_ord[1:]:
        cur_ini, cur_fim = resultado[-1]
        if ini <= cur_fim:
            resultado[-1] = (cur_ini, max(cur_fim, fim))
        else:
            resultado.append((ini, fim))
    return resultado


def calcular_horas_ocupadas_ambiente(ambiente_id, data_ini, data_fim, df_regras):
    """Soma de horas em que `ambiente_id` esteve ocupado no periodo.

    Itera dia a dia. Pra cada dia, filtra regras com:
        - mesmo dia_semana
        - data_inicio <= dia
        - data_fim is NaN OR data_fim >= dia
    Coleta intervalos do dia, faz uniao (1h ocupada vale 1h, mesmo se 2 profs sobrepostos).
    """
    if df_regras.empty:
        return 0.0

    df_amb = df_regras[df_regras["ambiente_id"] == ambiente_id].copy()
    if df_amb.empty:
        return 0.0

    df_amb["_di"] = pd.to_datetime(df_amb["data_inicio"], errors="coerce")
    df_amb["_df"] = pd.to_datetime(df_amb["data_fim"], errors="coerce")

    total_minutos = 0
    dia_atual = data_ini
    while dia_atual <= data_fim:
        dia_semana = dia_atual.weekday()
        dia_ts = pd.Timestamp(dia_atual)

        df_dia = df_amb[
            (df_amb["dia_semana"] == dia_semana)
            & (df_amb["_di"] <= dia_ts)
            & (df_amb["_df"].isna() | (df_amb["_df"] >= dia_ts))
        ]

        if not df_dia.empty:
            intervalos = []
            for _, regra in df_dia.iterrows():
                ini_min = _hora_str_para_minutos(regra["hora_inicio"])
                fim_min = _hora_str_para_minutos(regra["hora_fim"])
                if fim_min > ini_min:
                    intervalos.append((ini_min, fim_min))
            total_minutos += _unir_intervalos(intervalos)

        dia_atual += dt.timedelta(days=1)

    return total_minutos / 60.0


def calcular_horas_funcionamento(data_ini, data_fim, df_horario):
    """Soma horas que a academia esteve aberta no periodo.

    Itera dia a dia. Pra cada dia, filtra blocos de horario_funcionamento
    com vigencia que cobre o dia. Soma duracoes (validacao do CRUD garante
    que blocos por dia nao se sobrepoem).
    """
    if df_horario.empty:
        return 0.0

    df = df_horario[df_horario["ativo"]].copy()
    if df.empty:
        return 0.0

    df["_vd"] = pd.to_datetime(df["vigente_desde"], errors="coerce")
    df["_va"] = pd.to_datetime(df["vigente_ate"], errors="coerce")

    total_minutos = 0
    dia_atual = data_ini
    while dia_atual <= data_fim:
        dia_semana = dia_atual.weekday()
        dia_ts = pd.Timestamp(dia_atual)

        df_dia = df[
            (df["dia_semana"] == dia_semana)
            & (df["_vd"] <= dia_ts)
            & (df["_va"].isna() | (df["_va"] >= dia_ts))
        ]

        for _, bloco in df_dia.iterrows():
            ini_min = _hora_str_para_minutos(bloco["hora_inicio"])
            fim_min = _hora_str_para_minutos(bloco["hora_fim"])
            if fim_min > ini_min:
                total_minutos += fim_min - ini_min

        dia_atual += dt.timedelta(days=1)

    return total_minutos / 60.0


def calcular_ocupacao_periodo(data_ini, data_fim, df_ambientes, df_regras, df_horario):
    """Retorna DataFrame com uma linha por ambiente ATIVO contendo:

        ambiente_id, nome, area_m2, rentavel, horas_ocupadas,
        horas_funcionamento, ocupacao_pct
    """
    if df_ambientes.empty:
        return pd.DataFrame(columns=[
            "ambiente_id", "nome", "area_m2", "rentavel",
            "horas_ocupadas", "horas_funcionamento", "ocupacao_pct"
        ])

    horas_func = calcular_horas_funcionamento(data_ini, data_fim, df_horario)

    linhas = []
    df_amb_ativos = df_ambientes[df_ambientes["ativo"]]
    for _, amb in df_amb_ativos.iterrows():
        amb_id = int(amb["id"])
        h_ocup = calcular_horas_ocupadas_ambiente(amb_id, data_ini, data_fim, df_regras)
        ocup_pct = (h_ocup / horas_func * 100) if horas_func > 0 else 0.0

        linhas.append({
            "ambiente_id": amb_id,
            "nome": str(amb["nome"]),
            "area_m2": float(amb["area_m2"]),
            "rentavel": bool(amb["rentavel"]),
            "horas_ocupadas": h_ocup,
            "horas_funcionamento": horas_func,
            "ocupacao_pct": ocup_pct,
        })

    return pd.DataFrame(linhas)


# ============================================================================
# 4. HEATMAP DIA x HORA
# ============================================================================

def _distribuir_em_slots(contagem, dia_semana, ini_min, fim_min):
    """Adiciona horas em slots horarios (resolucao 1h, indice de hora 5-23).

    Aulas que cruzam fronteira de hora distribuem proporcionalmente.
    Ex: 9:30-10:30 -> slot (X, 9) ganha 0.5h, slot (X, 10) ganha 0.5h.
    """
    cur = ini_min
    while cur < fim_min:
        hora_atual = cur // 60
        proxima_hora_min = (hora_atual + 1) * 60
        fim_no_slot = min(proxima_hora_min, fim_min)

        duracao_h = (fim_no_slot - cur) / 60.0

        if 5 <= hora_atual <= 23:
            chave = (dia_semana, hora_atual)
            contagem[chave] = contagem.get(chave, 0.0) + duracao_h

        cur = fim_no_slot


def gerar_dados_heatmap(data_ini, data_fim, df_regras, ambiente_id_filtro=None):
    """Gera DataFrame com horas ocupadas por slot (dia_semana, hora).

    Colunas: dia_semana (0-6), hora (5-23), horas_ocupadas (float)

    Comportamento de sobreposicao:
        - Sempre faz uniao DENTRO do mesmo ambiente (2 profs no mesmo amb e horario = 1x).
        - Quando ambiente_id_filtro=None, soma horas ENTRE ambientes (2 ambs paralelos = 2x).
          Justificativa: pro heatmap, "neste slot acontecem N horas-aula em algum lugar".
        - Quando ambiente_id_filtro=int, foca naquele ambiente especifico.
    """
    slots_zerados = [{"dia_semana": d, "hora": h, "horas_ocupadas": 0.0}
                     for d in range(7) for h in range(5, 24)]
    df_heat = pd.DataFrame(slots_zerados)

    if df_regras.empty:
        return df_heat

    df = df_regras.copy()
    if "ativo" in df.columns:
        df = df[df["ativo"]]
    if ambiente_id_filtro is not None:
        df = df[df["ambiente_id"] == ambiente_id_filtro]

    if df.empty:
        return df_heat

    df["_di"] = pd.to_datetime(df["data_inicio"], errors="coerce")
    df["_df"] = pd.to_datetime(df["data_fim"], errors="coerce")

    contagem = {(d, h): 0.0 for d in range(7) for h in range(5, 24)}

    dia_atual = data_ini
    while dia_atual <= data_fim:
        dia_semana = dia_atual.weekday()
        dia_ts = pd.Timestamp(dia_atual)

        df_dia = df[
            (df["dia_semana"] == dia_semana)
            & (df["_di"] <= dia_ts)
            & (df["_df"].isna() | (df["_df"] >= dia_ts))
        ]

        if not df_dia.empty:
            # Une intra-ambiente sempre, soma entre ambientes
            for _amb_id, df_amb_dia in df_dia.groupby("ambiente_id"):
                intervalos_amb = []
                for _, regra in df_amb_dia.iterrows():
                    ini_min = _hora_str_para_minutos(regra["hora_inicio"])
                    fim_min = _hora_str_para_minutos(regra["hora_fim"])
                    if fim_min > ini_min:
                        intervalos_amb.append((ini_min, fim_min))
                intervalos_unidos = _intervalos_unidos_lista(intervalos_amb)
                for ini, fim in intervalos_unidos:
                    _distribuir_em_slots(contagem, dia_semana, ini, fim)

        dia_atual += dt.timedelta(days=1)

    # Atualiza df_heat
    for (d, h), horas in contagem.items():
        mask = (df_heat["dia_semana"] == d) & (df_heat["hora"] == h)
        df_heat.loc[mask, "horas_ocupadas"] = horas

    return df_heat


# ============================================================================
# 5. PERIODO ANTERIOR
# ============================================================================

def calcular_periodo_anterior(data_ini, data_fim, granularidade):
    """Calcula o periodo anterior segundo a granularidade.

    granularidade: 'mensal' | 'trimestral' | 'anual'

    Retorna (data_ini_ant, data_fim_ant) ou (None, None) se nao for periodo "limpo".

    Exemplos:
        ('mensal', 2026-04-01, 2026-04-30) -> (2026-03-01, 2026-03-31)
        ('trimestral', 2026-04-01, 2026-06-30) -> (2026-01-01, 2026-03-31)
        ('anual', 2026-01-01, 2026-12-31) -> (2025-01-01, 2025-12-31)
    """
    if granularidade == "mensal":
        if data_ini.day != 1:
            return None, None
        if data_ini.month == 1:
            ano_ant, mes_ant = data_ini.year - 1, 12
        else:
            ano_ant, mes_ant = data_ini.year, data_ini.month - 1
        ini_ant = date(ano_ant, mes_ant, 1)
        if mes_ant == 12:
            fim_ant = date(ano_ant, 12, 31)
        else:
            fim_ant = date(ano_ant, mes_ant + 1, 1) - timedelta(days=1)
        return ini_ant, fim_ant

    if granularidade == "trimestral":
        mes = data_ini.month
        trimestre = (mes - 1) // 3 + 1
        ano = data_ini.year
        if trimestre == 1:
            ano_ant, trimestre_ant = ano - 1, 4
        else:
            ano_ant, trimestre_ant = ano, trimestre - 1
        mes_ini_ant = (trimestre_ant - 1) * 3 + 1
        ini_ant = date(ano_ant, mes_ini_ant, 1)
        mes_fim_ant = mes_ini_ant + 2
        if mes_fim_ant == 12:
            fim_ant = date(ano_ant, 12, 31)
        else:
            fim_ant = date(ano_ant, mes_fim_ant + 1, 1) - timedelta(days=1)
        return ini_ant, fim_ant

    if granularidade == "anual":
        ano_ant = data_ini.year - 1
        return date(ano_ant, 1, 1), date(ano_ant, 12, 31)

    return None, None


# ============================================================================
# 6. ORQUESTRADOR
# ============================================================================

def carregar_dados_brutos():
    """Carrega tabelas de referencia uma vez para reuso (multiplas chamadas no mesmo render).

    Retorna dict: {nome_tabela: DataFrame}
    """
    return {
        "ambientes": buscar_dados("ambientes"),
        "atividades_entrada": buscar_dados("atividades_entrada"),
        "agenda_regras": buscar_dados("agenda_regras", eq={"ativo": True}),
        "horario_funcionamento": buscar_dados("horario_funcionamento"),
    }


def calcular_painel_completo(data_ini, data_fim, dados_brutos):
    """Funcao orquestradora: roda todos os calculos pro periodo informado.

    Retorna dict:
        {
            'kpis': dict (de calcular_kpis_receita),
            'ocupacao': DataFrame (de calcular_ocupacao_periodo),
            'lancamentos_enriquecidos': DataFrame,
        }
    """
    df_lanc = buscar_lancamentos_periodo(data_ini, data_fim)
    df_lanc_enr = enriquecer_lancamentos_com_atividade(df_lanc, dados_brutos["atividades_entrada"])
    kpis = calcular_kpis_receita(df_lanc_enr, dados_brutos["ambientes"])
    df_ocup = calcular_ocupacao_periodo(
        data_ini, data_fim,
        dados_brutos["ambientes"],
        dados_brutos["agenda_regras"],
        dados_brutos["horario_funcionamento"],
    )
    return {
        "kpis": kpis,
        "ocupacao": df_ocup,
        "lancamentos_enriquecidos": df_lanc_enr,
    }
