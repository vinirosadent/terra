"""
Modulo: paginas/orcamento.py
Responsabilidade: pagina "Orcamento & Metas" — planejamento anual de
receitas e despesas com periodicidade mensal recorrente ou anual pontual,
suporte a parcelamento e liquidacao de itens fechados.

Estrutura:
- Resumo orcamentario (so leitura) com pivot mes-a-mes agrupado por
  Custos Fixos / Custos Variaveis / Receitas
- Form de cadastrar (com UI condicional pra mensal vs anual, sem st.form)
- Form de Editar / Apagar / Liquidar (com st.form, dentro de selectbox)

Conceitos:
- Grupo: conjunto de linhas em `orcamentos` que pertencem ao mesmo "item
  logico" do orcamento. Identificado por `grupo_id` (ex: "cref-2026").
  Operacoes (editar/apagar/liquidar) afetam o grupo todo.
- Mensal recorrente: 12 linhas com mesmo valor (1 por mes do ano).
- Anual pontual: 1 a 12 linhas em meses especificos (parcelado ou nao),
  todas com mesmo grupo_id.
- Liquidacao: marca o grupo como "fechado". So vale pra DESPESAS ANUAIS.
  Mensais e receitas nao liquidam.

Linhas legadas (criadas antes do refactor) tem grupo_id NULL. O codigo
trata elas calculando um "grupo logico" virtual baseado em (categoria, ano).

Status: ativo (refatorado na Etapa I-pre · Patch 2).

Para usar:
    from paginas import orcamento as pg_orcamento
    elif menu == "🎯 Orçamento & Metas":
        pg_orcamento.render()
"""

import re
from datetime import date, datetime, timezone

import streamlit as st
import pandas as pd

from db import buscar_dados, inserir_dados, atualizar_dados, deletar_dados
from utils import resetar_form


# ============================================================================
# Constantes
# ============================================================================

MESES_LABEL = {
    1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez",
}

MESES_LABEL_FULL = {
    1: "Janeiro", 2: "Fevereiro", 3: "Marco", 4: "Abril", 5: "Maio",
    6: "Junho", 7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro",
    11: "Novembro", 12: "Dezembro",
}

# Categorias de receita: lista hardcoded.
# Decisao do usuario: migracao pra `modalidades` fica pro master reset
# (Etapa H.4 ou similar). Por enquanto continua como estava.
CATEGORIAS_RECEITA_LEGADAS = [
    "Academia", "Personal", "Calistenia", "Assessoria", "Inscrição Evento",
]

# Modos de pagamento de item anual
MODO_AVISTA = "A vista (1 mes so)"
MODO_PARCELADO = "Parcelado em N meses"
MODO_DISTRIBUIDO = "Distribuir nos 12 meses"


# ============================================================================
# Entry point
# ============================================================================

def render():
    """Ponto de entrada da pagina Orcamento & Metas."""
    fk = st.session_state.form_key

    st.title("🎯 Planejamento de Orçamentos Mensais")

    # Seletor de ano
    ano_atual = date.today().year
    c_ano1, _ = st.columns([1, 4])
    ano_selecionado = c_ano1.selectbox(
        "📅 Ano de Planejamento",
        options=[ano_atual - 1, ano_atual, ano_atual + 1],
        index=1,
        key=f"orc_ano_sel_{fk}",
    )

    # Carrega dados
    df_cat_saida = buscar_dados("categorias_saida", order="nome")
    df_orc_ano = buscar_dados("orcamentos", eq={"ano": ano_selecionado})

    # Resumo (so leitura)
    _render_resumo_anual(ano_selecionado, df_cat_saida, df_orc_ano)

    st.markdown("---")

    # Form de cadastrar
    with st.expander("➕ Cadastrar novo orcamento", expanded=df_orc_ano.empty):
        _render_form_cadastrar(ano_selecionado, df_cat_saida, df_orc_ano)

    # Form de acoes (editar / apagar). Liquidacao acontece via lancamento de
    # saida em Caixa/Operacoes — nao aqui.
    if not df_orc_ano.empty:
        st.markdown("---")
        with st.expander("✏️ Editar / 🗑️ Apagar item"):
            _render_form_acoes(ano_selecionado, df_cat_saida, df_orc_ano)


# ============================================================================
# Resumo (so leitura)
# ============================================================================

def _render_resumo_anual(ano, df_cat_saida, df_orc_ano):
    """Pivot mes-a-mes agrupado por Fixo/Variavel/Receita + balanco."""
    st.subheader(f"📊 Resumo Orcamentario - {ano}")

    if df_orc_ano.empty:
        st.info(
            f"Nenhum orcamento planejado pra {ano}. "
            "Use o formulario abaixo pra cadastrar o primeiro item."
        )
        return

    grupos = _calcular_grupos(ano, df_cat_saida, df_orc_ano)

    despesas_fixas = [g for g in grupos if g["tipo"] == "Despesa" and g["tipo_custo"] == "Fixo"]
    despesas_var = [g for g in grupos if g["tipo"] == "Despesa" and g["tipo_custo"] != "Fixo"]
    receitas = [g for g in grupos if g["tipo"] == "Receita"]

    # Balanco anual no TOPO (visao executiva primeiro)
    tot_rec = sum(g["total"] for g in receitas)
    tot_fix = sum(g["total"] for g in despesas_fixas)
    tot_var = sum(g["total"] for g in despesas_var)
    tot_desp = tot_fix + tot_var
    lucro = tot_rec - tot_desp

    st.markdown("#### 🧮 Balanco Anual Projetado")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Receita prevista", f"R$ {tot_rec:,.2f}")
    c2.metric("Custos Fixos", f"R$ {tot_fix:,.2f}", delta_color="inverse")
    c3.metric("Custos Variaveis", f"R$ {tot_var:,.2f}", delta_color="inverse")
    c4.metric("Lucro projetado", f"R$ {lucro:,.2f}")

    st.markdown("---")

    # Tabelas detalhadas DEPOIS (drill-down)
    if despesas_fixas or despesas_var:
        st.markdown("#### 🔴 DESPESAS PREVISTAS")

        if despesas_fixas:
            st.markdown("##### 🟦 Custos Fixos")
            st.markdown(
                _renderizar_tabela_grupos(despesas_fixas, mostrar_status=True),
                unsafe_allow_html=True,
            )

        if despesas_var:
            st.markdown("##### 🟧 Custos Variaveis")
            st.markdown(
                _renderizar_tabela_grupos(despesas_var, mostrar_status=True),
                unsafe_allow_html=True,
            )

    if receitas:
        st.markdown("#### 🟢 RECEITAS PROJETADAS")
        st.markdown(
            _renderizar_tabela_grupos(receitas, mostrar_status=False),
            unsafe_allow_html=True,
        )


def _calcular_grupos(ano, df_cat_saida, df_orc_ano):
    """Agrupa linhas de orcamentos por grupo_id (real ou virtual pra legados).

    Retorna lista de dicts, um por grupo, com chaves:
        grupo_id, categoria, tipo, tipo_periodo, tipo_custo,
        liquidado, liquidado_em, valores_meses, total, df_grupo
    """
    df = df_orc_ano.copy()

    # Mes numerico extraido de "YYYY-MM"
    df["mes_num"] = df["mes"].apply(
        lambda x: int(x.split("-")[1]) if isinstance(x, str) and "-" in x else 0
    )

    # Grupo logico: real (grupo_id) ou virtual (legados sem grupo_id)
    df["grupo_logico"] = df.apply(
        lambda r: (
            r["grupo_id"] if pd.notna(r["grupo_id"])
            else f"legado__{r['categoria']}-{ano}"
        ),
        axis=1,
    )

    # Lookup de tipo_custo (so pra despesa)
    cat_lookup = {}
    if not df_cat_saida.empty:
        cat_lookup = df_cat_saida.set_index("nome")["tipo_custo"].to_dict()

    grupos = []
    for grupo_logico, df_grupo in df.groupby("grupo_logico"):
        primeira = df_grupo.iloc[0]

        valores_meses = {m: 0.0 for m in range(1, 13)}
        for _, r in df_grupo.iterrows():
            if 1 <= r["mes_num"] <= 12:
                v = float(r["valor"]) if pd.notna(r["valor"]) else 0.0
                valores_meses[r["mes_num"]] += v

        # tipo_custo so pra despesa, com default seguro
        if primeira["tipo"] == "Despesa":
            tipo_custo = cat_lookup.get(primeira["categoria"], "Variável")
        else:
            tipo_custo = None

        # liquidado: any() do grupo (basta uma linha liquidada pra grupo virar)
        liquidado = bool(df_grupo["liquidado"].any()) if "liquidado" in df_grupo.columns else False

        # liquidado_em: maximo do grupo (mais recente)
        liq_em = None
        if "liquidado_em" in df_grupo.columns:
            liqs = df_grupo["liquidado_em"].dropna()
            if not liqs.empty:
                liq_em = liqs.max()

        # tipo_periodo: pega da primeira linha (assume consistencia no grupo)
        tipo_periodo = primeira.get("tipo_periodo", "mensal")
        if pd.isna(tipo_periodo):
            tipo_periodo = "mensal"

        grupos.append({
            "grupo_id": grupo_logico,
            "categoria": primeira["categoria"],
            "tipo": primeira["tipo"],
            "tipo_periodo": tipo_periodo,
            "tipo_custo": tipo_custo,
            "liquidado": liquidado,
            "liquidado_em": liq_em,
            "valores_meses": valores_meses,
            "total": sum(valores_meses.values()),
            "df_grupo": df_grupo,
        })

    # Ordena: mensal primeiro, depois anual; dentro de cada por categoria
    grupos.sort(key=lambda g: (g["tipo_periodo"] != "mensal", g["categoria"]))
    return grupos


def _renderizar_tabela_grupos(grupos, mostrar_status=True):
    """HTML estilizada de tabela com pivot mes-a-mes + total + status."""
    if not grupos:
        return ""

    style_override = (
        '<style>'
        '.tabela-orc thead tr th:first-child { display: table-cell !important; }'
        '.tabela-orc tbody th { display: none; }'
        '.tabela-orc th, .tabela-orc td { font-size: 12px; padding: 6px 6px; }'
        '.tabela-orc td.num { text-align: right; font-variant-numeric: tabular-nums; }'
        '.tabela-orc td.zero { color: #ccc; }'
        '</style>'
    )

    # Cabecalho
    cabecalho_meses = "".join(
        f'<th style="text-align:right;">{MESES_LABEL[m]}</th>' for m in range(1, 13)
    )
    th_status = '<th style="text-align:left;">Status</th>' if mostrar_status else ''
    cabecalho = (
        '<tr style="background-color:#f8f9fa;border-bottom:2px solid #dee2e6;">'
        '<th style="text-align:left;">Categoria</th>'
        '<th style="text-align:left;">Tipo</th>'
        f'{cabecalho_meses}'
        '<th style="text-align:right;">Total</th>'
        f'{th_status}'
        '</tr>'
    )

    # Linhas
    linhas_html = []
    for g in grupos:
        # Tipo periodo com icone
        if g["tipo_periodo"] == "mensal":
            tipo_label = '📅 Mensal'
        else:
            tipo_label = '💰 Anual'

        # Valores mensais
        valores_html = ""
        for m in range(1, 13):
            v = g["valores_meses"].get(m, 0.0)
            classe = "num zero" if v == 0 else "num"
            v_str = f"{v:,.0f}"
            valores_html += f'<td class="{classe}">{v_str}</td>'

        # Total
        total_str = f"R$ {g['total']:,.2f}"

        # Status (so se mostrar_status=True)
        if mostrar_status:
            if g["tipo_periodo"] == "mensal":
                status_html = '<td>—</td>'
            elif g["liquidado"]:
                status_html = '<td style="color:#2E7D32;font-weight:500;">✓ Liquidado</td>'
            else:
                status_html = '<td style="color:#9e9e9e;">Em aberto</td>'
        else:
            status_html = ""

        linhas_html.append(
            f'<tr style="border-bottom:1px solid #f0f0f0;">'
            f'<td>{g["categoria"]}</td>'
            f'<td>{tipo_label}</td>'
            f'{valores_html}'
            f'<td class="num"><b>{total_str}</b></td>'
            f'{status_html}'
            f'</tr>'
        )

    tabela = (
        '<table class="tabela-orc" '
        'style="width:100%;border-collapse:collapse;border:1px solid #dee2e6;'
        'border-radius:8px;overflow:hidden;font-family:inherit;">'
        f'<thead>{cabecalho}</thead>'
        f'<tbody>{"".join(linhas_html)}</tbody>'
        '</table>'
    )

    return style_override + tabela


# ============================================================================
# Form de Cadastrar (sem st.form pra suportar UI condicional)
# ============================================================================

def _render_form_cadastrar(ano, df_cat_saida, df_orc_ano):
    """Form de cadastrar novo orcamento. Sem st.form pra ter UI condicional."""
    fk = st.session_state.form_key

    # Linha 1: Tipo + Categoria
    col1, col2 = st.columns(2)
    with col1:
        tipo = st.selectbox(
            "Tipo",
            options=["Despesa", "Receita"],
            key=f"orc_add_tipo_{fk}",
        )

    with col2:
        if tipo == "Despesa":
            cats_disp = df_cat_saida["nome"].tolist() if not df_cat_saida.empty else []
            if not cats_disp:
                st.warning(
                    "⚠️ Cadastre primeiro um Centro de Custo em "
                    "⚙️ Configurações > Centros de Custo."
                )
                return
            categoria = st.selectbox(
                "Categoria",
                options=cats_disp,
                key=f"orc_add_cat_desp_{fk}",
            )
        else:
            categoria = st.selectbox(
                "Categoria",
                options=CATEGORIAS_RECEITA_LEGADAS,
                key=f"orc_add_cat_rec_{fk}",
            )

    # Mostra tipo de custo (Fixo/Variavel) se for despesa
    if tipo == "Despesa" and categoria:
        cat_row = df_cat_saida[df_cat_saida["nome"] == categoria]
        if not cat_row.empty:
            tipo_custo_atual = cat_row.iloc[0]["tipo_custo"]
            cor = "🟦" if tipo_custo_atual == "Fixo" else "🟧"
            st.caption(f"{cor} Tipo contabil: **{tipo_custo_atual}**")

    st.markdown("---")

    # Linha 2: Periodicidade
    tipo_periodo_label = st.radio(
        "Periodicidade",
        options=["Mensal recorrente", "Anual pontual"],
        horizontal=True,
        help=(
            "Mensal recorrente: o mesmo valor todo mes (ex: aluguel R$ 1.000/mes). "
            "Anual pontual: valor anual total que pode ser pago a vista, parcelado, "
            "ou distribuido (ex: CREF R$ 3.000 em 4x)."
        ),
        key=f"orc_add_periodo_{fk}",
    )

    # Mapeia label → valor de banco (constraint do banco aceita 'mensal' ou 'anual')
    tipo_periodo_db = "mensal" if tipo_periodo_label == "Mensal recorrente" else "anual"

    # Campos especificos
    valor_mensal = None
    valor_anual = None
    meses_pagamento = None

    if tipo_periodo_db == "mensal":
        valor_mensal = st.number_input(
            "Valor mensal (R$)",
            min_value=0.01,
            max_value=9999999.99,
            value=None,
            step=10.0,
            format="%.2f",
            help="Sera replicado pros 12 meses do ano.",
            key=f"orc_add_valor_mensal_{fk}",
        )
    else:  # anual
        valor_anual = st.number_input(
            "Valor anual total (R$)",
            min_value=0.01,
            max_value=9999999.99,
            value=None,
            step=100.0,
            format="%.2f",
            key=f"orc_add_valor_anual_{fk}",
        )

        modo_pagamento = st.radio(
            "Como pagar",
            options=[MODO_AVISTA, MODO_PARCELADO, MODO_DISTRIBUIDO],
            key=f"orc_add_modo_{fk}",
        )

        if modo_pagamento == MODO_AVISTA:
            mes_avista_label = st.selectbox(
                "Mes do pagamento",
                options=list(MESES_LABEL_FULL.values()),
                key=f"orc_add_mes_avista_{fk}",
            )
            mes_num = next(
                k for k, v in MESES_LABEL_FULL.items() if v == mes_avista_label
            )
            meses_pagamento = [mes_num]

        elif modo_pagamento == MODO_PARCELADO:
            num_parcelas = st.number_input(
                "Numero de parcelas",
                min_value=2, max_value=12, value=4, step=1,
                key=f"orc_add_num_parc_{fk}",
            )
            meses_label_sel = st.multiselect(
                f"Meses de pagamento (selecione exatamente {num_parcelas})",
                options=list(MESES_LABEL_FULL.values()),
                key=f"orc_add_meses_parc_{fk}",
            )
            if len(meses_label_sel) != num_parcelas:
                st.caption(
                    f"⚠️ Selecione exatamente **{num_parcelas}** meses "
                    f"(atualmente: {len(meses_label_sel)})"
                )
            meses_pagamento = sorted([
                next(k for k, v in MESES_LABEL_FULL.items() if v == m_label)
                for m_label in meses_label_sel
            ])

        else:  # MODO_DISTRIBUIDO
            meses_pagamento = list(range(1, 13))
            if valor_anual:
                st.caption(
                    f"💡 Valor sera dividido por 12: "
                    f"**R$ {float(valor_anual) / 12:.2f}/mes**"
                )

    st.markdown("---")

    # Botao submit
    if st.button(
        "✅ Cadastrar orcamento",
        type="primary",
        use_container_width=True,
        key=f"orc_add_btn_{fk}",
    ):
        erro = _validar_cadastro(
            tipo_periodo_db=tipo_periodo_db,
            valor_mensal=valor_mensal,
            valor_anual=valor_anual,
            meses_pagamento=meses_pagamento,
        )
        if erro:
            st.error(erro)
        else:
            try:
                _inserir_lote_orcamento(
                    tipo=tipo,
                    categoria=categoria,
                    ano=ano,
                    tipo_periodo=tipo_periodo_db,
                    valor_mensal=valor_mensal,
                    valor_anual=valor_anual,
                    meses_pagamento=meses_pagamento,
                    df_orc_ano=df_orc_ano,
                )
                st.session_state.sucesso_msg = "Orcamento cadastrado com sucesso!"
                resetar_form()
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao cadastrar: {e}")


def _validar_cadastro(tipo_periodo_db, valor_mensal, valor_anual, meses_pagamento):
    """Valida campos do form de cadastro. Retorna mensagem de erro ou None."""
    if tipo_periodo_db == "mensal":
        if valor_mensal is None or valor_mensal <= 0:
            return "Informe um valor mensal maior que zero."
    else:  # anual
        if valor_anual is None or valor_anual <= 0:
            return "Informe um valor anual maior que zero."
        if not meses_pagamento:
            return "Selecione pelo menos um mes de pagamento."
        if len(meses_pagamento) < 1 or len(meses_pagamento) > 12:
            return "O numero de parcelas deve estar entre 1 e 12."
        if len(set(meses_pagamento)) != len(meses_pagamento):
            return "Tem mes duplicado na selecao."
    return None


def _inserir_lote_orcamento(
    tipo, categoria, ano, tipo_periodo,
    valor_mensal, valor_anual, meses_pagamento,
    df_orc_ano,
):
    """Insere as N linhas de um item de orcamento, todas com mesmo grupo_id."""
    grupo_id = _gerar_grupo_id(categoria, ano, df_orc_ano)

    if tipo_periodo == "mensal":
        # 12 linhas com mesmo valor
        for m in range(1, 13):
            inserir_dados("orcamentos", {
                "ano": ano,
                "mes": f"{ano}-{m:02d}",
                "categoria": categoria,
                "valor": float(valor_mensal),
                "tipo": tipo,
                "tipo_periodo": "mensal",
                "grupo_id": grupo_id,
                "liquidado": False,
            })
    else:  # anual
        valor_por_parcela = float(valor_anual) / len(meses_pagamento)
        for m in meses_pagamento:
            inserir_dados("orcamentos", {
                "ano": ano,
                "mes": f"{ano}-{m:02d}",
                "categoria": categoria,
                "valor": valor_por_parcela,
                "tipo": tipo,
                "tipo_periodo": "anual",
                "grupo_id": grupo_id,
                "liquidado": False,
            })


def _gerar_grupo_id(categoria, ano, df_existentes):
    """Gera slug 'categoria-ano' com sufixo se ja existir grupo identico."""
    base = re.sub(r"[^a-z0-9]+", "-", str(categoria).lower()).strip("-")
    if not base:
        base = "item"
    base = f"{base}-{ano}"

    if df_existentes.empty or "grupo_id" not in df_existentes.columns:
        return base

    grupos_existentes = set(g for g in df_existentes["grupo_id"].dropna().tolist())
    if base not in grupos_existentes:
        return base

    i = 2
    while f"{base}-{i}" in grupos_existentes:
        i += 1
    return f"{base}-{i}"


# ============================================================================
# Form de Acoes (Editar / Apagar / Liquidar)
# ============================================================================

def _render_form_acoes(ano, df_cat_saida, df_orc_ano):
    """Form unificado pra editar, apagar ou liquidar um grupo."""
    fk = st.session_state.form_key

    grupos = _calcular_grupos(ano, df_cat_saida, df_orc_ano)

    if not grupos:
        st.info("Nenhum item disponivel pra editar.")
        return

    # Monta opcoes do selectbox
    opcoes_labels = {}
    for g in grupos:
        if g["tipo_periodo"] == "mensal":
            status_str = "—"
        elif g["liquidado"]:
            status_str = "✓ Liquidado"
        else:
            status_str = "Em aberto"
        periodo_label = "Mensal" if g["tipo_periodo"] == "mensal" else "Anual"
        label = (
            f"{g['categoria']} ({g['tipo']}, {periodo_label}) — "
            f"R$ {g['total']:,.2f} — {status_str}"
        )
        opcoes_labels[g["grupo_id"]] = label

    grupo_id_sel = st.selectbox(
        "Selecione o item",
        options=list(opcoes_labels.keys()),
        format_func=lambda gid: opcoes_labels[gid],
        key=f"orc_acao_sel_{fk}",
    )
    grupo_sel = next(g for g in grupos if g["grupo_id"] == grupo_id_sel)

    # Acao. Liquidacao foi removida daqui — agora acontece via lancamento
    # de saida em Caixa/Operacoes (Patch 3 futuro).
    acao = st.radio(
        "Acao",
        options=["✏️ Editar valor", "🗑️ Apagar"],
        horizontal=True,
        key=f"orc_acao_radio_{fk}",
    )

    st.markdown("---")

    if acao == "✏️ Editar valor":
        _form_editar_grupo(grupo_sel, fk)
    elif acao == "🗑️ Apagar":
        _form_apagar_grupo(grupo_sel, fk)


def _form_editar_grupo(grupo, fk):
    """Editar valor do grupo (mantem categoria, periodicidade, etc)."""
    if grupo["liquidado"]:
        st.warning(
            "⚠️ Item liquidado nao pode ser editado aqui. "
            "Pra reabrir, edite ou apague o lancamento de saida correspondente "
            "em ⏳ Caixa/Operacoes — a liquidacao acontece la."
        )
        return

    n_linhas = len(grupo["df_grupo"])

    if grupo["tipo_periodo"] == "mensal":
        st.write(
            f"Editando **{grupo['categoria']}** "
            f"(mensal recorrente, {n_linhas} linhas no banco)."
        )
        # Valor mensal: pega da primeira linha (todas devem ser iguais)
        valor_atual_mensal = float(grupo["df_grupo"].iloc[0]["valor"]) if n_linhas > 0 else 0.0

        with st.form(f"f_edit_grupo_{grupo['grupo_id']}_{fk}"):
            novo_valor = st.number_input(
                "Novo valor mensal (R$)",
                min_value=0.01,
                max_value=9999999.99,
                value=float(valor_atual_mensal),
                step=10.0,
                format="%.2f",
                help=f"Vai atualizar o valor das {n_linhas} linhas mensais do grupo.",
                key=f"orc_edit_valor_{grupo['grupo_id']}_{fk}",
            )

            if st.form_submit_button("Salvar novo valor", type="primary", use_container_width=True):
                if novo_valor and novo_valor > 0:
                    try:
                        for _, row in grupo["df_grupo"].iterrows():
                            atualizar_dados(
                                "orcamentos",
                                {"valor": float(novo_valor)},
                                "id", int(row["id"]),
                            )
                        st.session_state.sucesso_msg = (
                            f"Valor mensal atualizado pra R$ {novo_valor:.2f}!"
                        )
                        resetar_form()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")
                else:
                    st.error("Valor deve ser maior que zero.")

    else:  # anual
        parcela_label = "parcela" if n_linhas == 1 else "parcelas"
        st.write(
            f"Editando **{grupo['categoria']}** "
            f"(anual pontual, {n_linhas} {parcela_label} no banco)."
        )

        with st.form(f"f_edit_grupo_{grupo['grupo_id']}_{fk}"):
            novo_total = st.number_input(
                "Novo valor anual total (R$)",
                min_value=0.01,
                max_value=9999999.99,
                value=float(grupo["total"]),
                step=100.0,
                format="%.2f",
                help=f"Vai ser dividido em {n_linhas} {parcela_label} iguais.",
                key=f"orc_edit_valor_{grupo['grupo_id']}_{fk}",
            )

            if st.form_submit_button("Salvar novo valor", type="primary", use_container_width=True):
                if novo_total and novo_total > 0:
                    try:
                        novo_por_parcela = float(novo_total) / n_linhas
                        for _, row in grupo["df_grupo"].iterrows():
                            atualizar_dados(
                                "orcamentos",
                                {"valor": novo_por_parcela},
                                "id", int(row["id"]),
                            )
                        st.session_state.sucesso_msg = (
                            f"Valor anual atualizado pra R$ {novo_total:.2f} "
                            f"({n_linhas}x R$ {novo_por_parcela:.2f})."
                        )
                        resetar_form()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")
                else:
                    st.error("Valor deve ser maior que zero.")


def _form_apagar_grupo(grupo, fk):
    """Apaga todas as linhas do grupo."""
    n_linhas = len(grupo["df_grupo"])
    periodo_label = "Mensal" if grupo["tipo_periodo"] == "mensal" else "Anual"
    st.warning(
        f"⚠️ Apagar **{grupo['categoria']}** "
        f"({grupo['tipo']}, {periodo_label}) — "
        f"{n_linhas} linhas no banco, total R$ {grupo['total']:,.2f}.\n\n"
        "Esta acao **nao pode ser desfeita**."
    )

    confirmacao = st.checkbox(
        "Sim, quero apagar permanentemente",
        key=f"orc_apg_conf_{grupo['grupo_id']}_{fk}",
    )

    if confirmacao:
        if st.button(
            "🗑️ Apagar definitivamente",
            type="primary",
            key=f"orc_apg_btn_{grupo['grupo_id']}_{fk}",
        ):
            try:
                for _, row in grupo["df_grupo"].iterrows():
                    deletar_dados("orcamentos", "id", int(row["id"]))
                st.session_state.sucesso_msg = f"Item '{grupo['categoria']}' apagado."
                resetar_form()
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao apagar: {e}")
