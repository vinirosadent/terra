"""
Pagina Calendario - Etapa F do projeto Terra.

Esta pagina concentra o calendario de uso da academia, analise de ocupacao,
horario de funcionamento e configuracoes (professores e ambientes).

Estrutura de abas:
    1. Calendario              - visualizacao mensal/semanal + cadastro de
                                 atividades direto no calendario (F.4 / F.5)
    2. Analise de Uso          - graficos e KPIs de ocupacao (F.7)
    3. Horario de Funcionamento - blocos por dia da semana (F.3)
    4. Configuracoes
        4a. Professores        - CRUD de profissionais (F.2)
        4b. Ambientes          - CRUD de ambientes (F.2)
"""

import calendar as _calendar_lib
import datetime as dt
from datetime import date, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from streamlit_calendar import calendar

from db import buscar_dados, inserir_dados, atualizar_dados, deletar_dados


# Fuso horario fixo da academia (Sao Paulo, Brasil)
_TZ_ACADEMIA = ZoneInfo("America/Sao_Paulo")


# Paleta fixa de cores para profissionais.
# Ordem: as 3 primeiras sao "reservadas" (irmao verde, calistenia azul, kids rosa),
# mas todas estao disponiveis para selecao no cadastro.
PALETA_CORES = [
    {"hex": "#2E7D32", "nome": "Verde"},
    {"hex": "#90CAF9", "nome": "Azul claro"},
    {"hex": "#F8BBD0", "nome": "Rosa claro"},
    {"hex": "#CE93D8", "nome": "Roxo claro"},
    {"hex": "#FFE082", "nome": "Amarelo"},
    {"hex": "#FFAB91", "nome": "Laranja claro"},
    {"hex": "#5C6BC0", "nome": "Azul escuro"},
    {"hex": "#78909C", "nome": "Cinza escuro"},
    {"hex": "#A5D6A7", "nome": "Verde claro"},
    {"hex": "#EF9A9A", "nome": "Vermelho claro"},
    {"hex": "#80CBC4", "nome": "Turquesa"},
    {"hex": "#BCAAA4", "nome": "Marrom claro"},
]

# Mapeamento dos tipos do banco (em ingles minusculo) para exibicao em portugues.
TIPOS_PROFESSOR = {
    "treino": "Treino",
    "calistenia": "Calistenia",
    "kids": "Kids",
    "outro": "Outro",
}


def render():
    """Ponto de entrada da pagina Calendario."""
    st.title("Calendario")

    aba_calendario, aba_analise, aba_funcionamento, aba_config = st.tabs(
        ["Calendario", "Analise de Uso", "Horario de Funcionamento", "Configuracoes"]
    )

    with aba_calendario:
        _render_aba_calendario()

    with aba_analise:
        _render_aba_analise()

    with aba_funcionamento:
        _render_aba_funcionamento()

    with aba_config:
        _render_aba_configuracoes()


def _render_aba_calendario():
    """Aba 1 - Calendario read-only (F.4).

    Renderiza um calendario por ambiente rentavel ativo, lado a lado,
    com eventos gerados a partir das regras vigentes em agenda_regras.
    Read-only: criar/editar regras via drag-drop fica para F.5.
    """
    st.markdown("### 📅 Calendario de Uso")

    # Mensagem de sucesso de operacao previa (sobrevive ao rerun do dialog)
    if "f5_msg_sucesso" in st.session_state:
        st.success(st.session_state.pop("f5_msg_sucesso"))

    # Controles superiores: mes + visao + ambiente
    # Ambiente: selectbox que persiste em session_state pra escolher qual
    # calendario renderizar (so 1 por vez agora, em vez de 2 lado-a-lado)
    df_ambientes_topo = buscar_dados("ambientes", eq={"ativo": True, "rentavel": True})

    col_mes, col_visao, col_amb = st.columns([2, 1, 2])

    with col_mes:
        hoje = dt.date.today()
        mes_referencia = st.date_input(
            "Mes de referencia",
            value=hoje.replace(day=1),
            format="DD/MM/YYYY",
            key="f4_mes_ref",
        )
        ano = mes_referencia.year
        mes = mes_referencia.month

    with col_visao:
        visao = st.radio(
            "Visao",
            options=["Mensal", "Semanal"],
            horizontal=True,
            key="f4_visao",
        )

    with col_amb:
        if df_ambientes_topo.empty:
            ambiente_selecionado_id = None
            st.caption("⚠️ Nenhum ambiente rentavel ativo")
        else:
            ambientes_dict = {}
            for _, row in df_ambientes_topo.iterrows():
                area_str = f" ({row.get('area_m2', '?')} m²)" if row.get("area_m2") else ""
                label = f"🏢 {row['nome']}{area_str}"
                ambientes_dict[label] = int(row["id"])

            opcoes_labels = list(ambientes_dict.keys())
            ambiente_label = st.selectbox(
                "Ambiente",
                options=opcoes_labels,
                key="f5_ambiente_selecionado",
            )
            ambiente_selecionado_id = ambientes_dict[ambiente_label]

    st.markdown("---")

    # Busca regras vigentes e gera eventos
    df_regras = _buscar_regras_vigentes_mes(ano, mes)
    eventos_por_ambiente = _gerar_eventos_do_mes(ano, mes, df_regras)

    # Renderizacao single-ambient com caixa lateral (60/40)
    if ambiente_selecionado_id is None:
        st.warning("Nenhum ambiente rentavel ativo cadastrado. Cadastre em Configuracoes > Ambientes.")
    else:
        col_calendario, col_caixa = st.columns([6, 4])

        with col_calendario:
            ambiente_atual = df_ambientes_topo[
                df_ambientes_topo["id"] == ambiente_selecionado_id
            ].iloc[0].to_dict()
            eventos_do_ambiente = eventos_por_ambiente.get(ambiente_selecionado_id, [])
            _renderizar_calendario_unico(
                ambiente=ambiente_atual,
                eventos=eventos_do_ambiente,
                ano=ano,
                mes=mes,
                visao=visao,
            )

            if df_regras.empty:
                st.caption(
                    "Sem regras cadastradas ainda. Arraste no calendario semanal "
                    "pra cadastrar a primeira."
                )

        with col_caixa:
            _renderizar_caixa_acao()

    # ============================================================
    # SECAO TEMPORARIA · Cadastro de historico de regras
    # Sera removida apos populacao inicial (estimativa: 1-2 meses)
    # ============================================================
    st.markdown("---")
    with st.expander("📅 Cadastrar historico (uso temporario)", expanded=st.session_state.get("f5_hist_aberto", False)):
        st.caption(
            "Use esse formulario apenas para cadastrar regras que comecaram "
            "antes de hoje (inicializacao do sistema). Para regras novas, "
            "use o drag-drop direto no calendario semanal acima."
        )
        if not st.session_state.get("f5_hist_aberto", False):
            if st.button("➕ Adicionar regra historica", key="f5_btn_historico", type="secondary"):
                st.session_state["f5_hist_aberto"] = True
                st.rerun()
        else:
            _renderizar_form_regra_historica()
    # ============================================================
    # FIM SECAO TEMPORARIA
    # ============================================================


def _render_aba_analise():
    """Aba 2 - Analise de Uso (placeholder ate F.7)."""
    st.info(
        "Analise de Uso em construcao (Etapa F.7).\n\n"
        "Esta aba mostrara graficos de ocupacao por profissional, por ambiente, "
        "heatmap de horarios mais cheios e KPIs de uso da academia."
    )


def _render_aba_funcionamento():
    """Aba 3 - Cadastro de Horario de Funcionamento (F.3)."""
    st.markdown("### Horario de Funcionamento da Academia")
    st.caption(
        "Cadastre os blocos de horario em que a academia esta aberta para cada "
        "dia da semana. E possivel cadastrar mais de um bloco por dia "
        "(ex: segunda 06h-09h E 17h-22h). Mudancas sao registradas com "
        "historico para analise de rentabilidade por epoca."
    )

    df_func = buscar_dados("horario_funcionamento", order="dia_semana")
    if df_func.empty:
        df_func = pd.DataFrame(columns=[
            "id", "dia_semana", "hora_inicio", "hora_fim",
            "ativo", "created_at", "vigente_desde", "vigente_ate"
        ])

    # Filtrar apenas blocos vigentes hoje
    hoje = date.today()
    df_vigentes = _filtrar_vigentes_hoje(df_func, hoje)

    # KPI: total de horas semanais de funcionamento
    if not df_vigentes.empty:
        total_horas = _calcular_total_horas_semanais(df_vigentes)
        st.metric("Total de horas semanais de funcionamento", f"{total_horas:.1f} h")

    st.markdown("---")

    # Renderizar dia a dia (segunda = 0, ..., domingo = 6)
    for dia_idx, dia_nome in enumerate(DIAS_SEMANA):
        with st.container():
            st.markdown(f"#### {dia_nome}")

            # Blocos vigentes deste dia
            df_dia = df_vigentes[df_vigentes["dia_semana"] == dia_idx].sort_values("hora_inicio")

            if df_dia.empty:
                st.caption("Sem blocos cadastrados — academia fechada.")
            else:
                for _, bloco in df_dia.iterrows():
                    _render_linha_bloco(bloco, df_func)

            # Form pra adicionar bloco neste dia
            with st.expander(f"+ adicionar bloco em {dia_nome.lower()}"):
                _render_form_adicionar_bloco(dia_idx, dia_nome, df_func)

            st.markdown("")  # espacamento


def _render_aba_configuracoes():
    """Aba 4 - Configuracoes (sub-abas: Professores e Ambientes)."""
    st.markdown("**Cadastros base do Calendario.** Configure os professores e os ambientes da academia.")

    sub_professores, sub_ambientes = st.tabs(["Professores", "Ambientes"])

    with sub_professores:
        _render_sub_professores()

    with sub_ambientes:
        _render_sub_ambientes()


def _render_sub_professores():
    """Sub-aba: Cadastro de Professores (F.2)."""
    st.markdown("### Professores cadastrados")
    st.caption("Cadastre os profissionais que dao aulas na academia. A cor e usada para identificar as atividades no calendario.")

    df_prof = buscar_dados("profissionais", order="id")

    if df_prof.empty:
        df_prof = pd.DataFrame(columns=["id", "nome", "tipo", "cor_hex", "ativo", "created_at"])

    # ----------------------------------------------------------------------
    # 1) Listagem
    # ----------------------------------------------------------------------
    if df_prof.empty:
        st.info("Nenhum professor cadastrado ainda. Use o formulario abaixo para cadastrar o primeiro.")
    else:
        st.markdown(_renderizar_tabela_professores(df_prof), unsafe_allow_html=True)

    st.markdown("---")

    # ----------------------------------------------------------------------
    # 2) Cadastrar novo professor
    # ----------------------------------------------------------------------
    with st.expander("Cadastrar novo professor", expanded=df_prof.empty):
        with st.form("form_novo_professor", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                novo_nome = st.text_input("Nome do professor", max_chars=80)
                novo_tipo = st.selectbox(
                    "Tipo / Modalidade",
                    options=list(TIPOS_PROFESSOR.keys()),
                    format_func=lambda x: TIPOS_PROFESSOR[x],
                )
            with col2:
                cores_em_uso = set(df_prof["cor_hex"].tolist()) if not df_prof.empty else set()
                opcoes_cores = [c["hex"] for c in PALETA_CORES]

                # Paleta completa visivel acima do selectbox
                st.markdown("**Cor de identificacao**")
                st.markdown(_renderizar_paleta(cores_em_uso), unsafe_allow_html=True)

                nova_cor = st.selectbox(
                    "Selecione a cor",
                    options=opcoes_cores,
                    format_func=lambda hexcode: _formatar_cor(hexcode, cores_em_uso),
                    label_visibility="collapsed",
                )

                # Amostra grande da cor selecionada
                st.markdown(_renderizar_amostra_cor(nova_cor), unsafe_allow_html=True)

            submitted = st.form_submit_button("Cadastrar professor", use_container_width=True, type="primary")

            if submitted:
                erro = _validar_professor(novo_nome, df_prof, professor_id_editando=None)
                if erro:
                    st.error(erro)
                else:
                    try:
                        inserir_dados("profissionais", {
                            "nome": novo_nome.strip(),
                            "tipo": novo_tipo,
                            "cor_hex": nova_cor,
                            "ativo": True,
                        })
                        st.success(f"Professor '{novo_nome.strip()}' cadastrado com sucesso.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao cadastrar professor: {e}")

    # ----------------------------------------------------------------------
    # 3) Editar / Inativar / Reativar professor existente
    # ----------------------------------------------------------------------
    if df_prof.empty:
        return

    with st.expander("Editar / Inativar / Reativar professor"):
        df_sel = df_prof.copy()
        df_sel["label"] = df_sel.apply(
            lambda r: f"{r['nome']} ({TIPOS_PROFESSOR.get(r['tipo'], r['tipo'])}) - {'Ativo' if r['ativo'] else 'Inativo'}",
            axis=1,
        )
        opcoes_ids = df_sel["id"].tolist()
        prof_id_sel = st.selectbox(
            "Selecione um professor",
            options=opcoes_ids,
            format_func=lambda pid: df_sel.loc[df_sel["id"] == pid, "label"].values[0],
        )

        prof_atual = df_sel.loc[df_sel["id"] == prof_id_sel].iloc[0]

        with st.form(f"form_editar_professor_{prof_id_sel}"):
            col1, col2 = st.columns(2)
            with col1:
                nome_edit = st.text_input("Nome do professor", value=prof_atual["nome"], max_chars=80)
                tipo_edit = st.selectbox(
                    "Tipo / Modalidade",
                    options=list(TIPOS_PROFESSOR.keys()),
                    index=list(TIPOS_PROFESSOR.keys()).index(prof_atual["tipo"]) if prof_atual["tipo"] in TIPOS_PROFESSOR else 0,
                    format_func=lambda x: TIPOS_PROFESSOR[x],
                )
            with col2:
                cores_em_uso_edit = set(df_prof[df_prof["id"] != prof_id_sel]["cor_hex"].tolist())
                opcoes_cores = [c["hex"] for c in PALETA_CORES]
                idx_cor_atual = opcoes_cores.index(prof_atual["cor_hex"]) if prof_atual["cor_hex"] in opcoes_cores else 0

                # Paleta completa visivel acima do selectbox
                st.markdown("**Cor de identificacao**")
                st.markdown(_renderizar_paleta(cores_em_uso_edit), unsafe_allow_html=True)

                cor_edit = st.selectbox(
                    "Selecione a cor",
                    options=opcoes_cores,
                    index=idx_cor_atual,
                    format_func=lambda hexcode: _formatar_cor(hexcode, cores_em_uso_edit),
                    label_visibility="collapsed",
                )

                # Amostra grande da cor selecionada
                st.markdown(_renderizar_amostra_cor(cor_edit), unsafe_allow_html=True)

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                btn_salvar = st.form_submit_button("Salvar alteracoes", use_container_width=True, type="primary")
            with col_btn2:
                if prof_atual["ativo"]:
                    btn_toggle = st.form_submit_button("Inativar", use_container_width=True)
                else:
                    btn_toggle = st.form_submit_button("Reativar", use_container_width=True)

            if btn_salvar:
                erro = _validar_professor(nome_edit, df_prof, professor_id_editando=prof_id_sel)
                if erro:
                    st.error(erro)
                else:
                    try:
                        atualizar_dados("profissionais", {
                            "nome": nome_edit.strip(),
                            "tipo": tipo_edit,
                            "cor_hex": cor_edit,
                        }, "id", int(prof_id_sel))
                        st.success("Alteracoes salvas com sucesso.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")

            if btn_toggle:
                try:
                    novo_status = not bool(prof_atual["ativo"])
                    atualizar_dados("profissionais", {"ativo": novo_status}, "id", int(prof_id_sel))
                    msg = "Professor reativado." if novo_status else "Professor inativado."
                    st.success(msg)
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao alterar status: {e}")


def _formatar_cor(hexcode, cores_em_uso):
    """Formata o nome da cor no selectbox, marcando as ja em uso."""
    nome_cor = next((c["nome"] for c in PALETA_CORES if c["hex"] == hexcode), hexcode)
    sufixo = " (em uso)" if hexcode in cores_em_uso else ""
    return f"{nome_cor}{sufixo}"


def _validar_professor(nome, df_existente, professor_id_editando=None):
    """Valida nome do professor. Retorna mensagem de erro ou None se OK."""
    if not nome or not nome.strip():
        return "O nome do professor nao pode ficar vazio."
    nome_limpo = nome.strip()
    if len(nome_limpo) < 2:
        return "O nome do professor precisa ter pelo menos 2 caracteres."
    # Checar duplicidade (case-insensitive), ignorando o proprio registro em edicao
    df_check = df_existente.copy()
    if professor_id_editando is not None:
        df_check = df_check[df_check["id"] != professor_id_editando]
    if not df_check.empty:
        nomes_existentes = df_check["nome"].astype(str).str.strip().str.lower().tolist()
        if nome_limpo.lower() in nomes_existentes:
            return f"Ja existe um professor com o nome '{nome_limpo}'."
    return None


def _renderizar_tabela_professores(df_prof):
    """Renderiza tabela HTML com bolinha colorida na coluna Cor.

    Inclui style inline com classe `tabela-professores` para sobrescrever
    a regra CSS global do app que esconde th:first-child em tabelas
    (necessaria para esconder o index do st.dataframe em outras paginas).
    """
    # Sobrescreve regra global de styles.py SO para esta tabela.
    # A regra global "thead tr th:first-child {display:none}" foi feita para
    # st.dataframe e estava escondendo nossa coluna ID. Aqui forcamos display.
    style_override = (
        '<style>'
        '.tabela-professores thead tr th:first-child { display: table-cell !important; }'
        '.tabela-professores tbody th { display: none; }'
        '</style>'
    )

    cabecalho = (
        '<tr style="background-color:#f8f9fa;border-bottom:2px solid #dee2e6;">'
        '<th style="padding:10px 12px;text-align:left;font-weight:600;">ID</th>'
        '<th style="padding:10px 12px;text-align:left;font-weight:600;">Nome</th>'
        '<th style="padding:10px 12px;text-align:left;font-weight:600;">Tipo</th>'
        '<th style="padding:10px 12px;text-align:left;font-weight:600;">Cor</th>'
        '<th style="padding:10px 12px;text-align:left;font-weight:600;">Status</th>'
        '</tr>'
    )

    linhas_html = []
    for _, row in df_prof.iterrows():
        tipo_label = TIPOS_PROFESSOR.get(row["tipo"], row["tipo"])
        status_label = "Ativo" if row["ativo"] else "Inativo"
        cor_nome = next((c["nome"] for c in PALETA_CORES if c["hex"] == row["cor_hex"]), row["cor_hex"])
        bolinha = (
            f'<span style="display:inline-block;width:18px;height:18px;'
            f'border-radius:50%;background-color:{row["cor_hex"]};'
            f'border:1px solid #ccc;vertical-align:middle;margin-right:8px;"></span>'
        )
        cor_celula = f'{bolinha}<span style="vertical-align:middle;">{cor_nome}</span>'
        cor_status = "#2E7D32" if row["ativo"] else "#9e9e9e"
        status_celula = f'<span style="color:{cor_status};font-weight:500;">{status_label}</span>'
        linhas_html.append(
            f'<tr style="border-bottom:1px solid #f0f0f0;">'
            f'<td style="padding:8px 12px;">{row["id"]}</td>'
            f'<td style="padding:8px 12px;">{row["nome"]}</td>'
            f'<td style="padding:8px 12px;">{tipo_label}</td>'
            f'<td style="padding:8px 12px;">{cor_celula}</td>'
            f'<td style="padding:8px 12px;">{status_celula}</td>'
            f'</tr>'
        )

    tabela = (
        '<table class="tabela-professores" '
        'style="width:100%;border-collapse:collapse;border:1px solid #dee2e6;'
        'border-radius:8px;overflow:hidden;font-family:inherit;font-size:14px;">'
        f'<thead>{cabecalho}</thead>'
        f'<tbody>{"".join(linhas_html)}</tbody>'
        '</table>'
    )

    return style_override + tabela


def _renderizar_paleta(cores_em_uso):
    """Renderiza a paleta completa de 12 cores em formato grid visual."""
    blocos = []
    for cor in PALETA_CORES:
        em_uso = cor["hex"] in cores_em_uso
        opacidade = "0.5" if em_uso else "1"
        borda = "2px solid #d32f2f" if em_uso else "1px solid #ccc"
        titulo = f'{cor["nome"]}{" (em uso)" if em_uso else ""}'
        blocos.append(
            f'<div title="{titulo}" style="display:inline-block;'
            f'width:32px;height:32px;border-radius:6px;'
            f'background-color:{cor["hex"]};border:{borda};'
            f'opacity:{opacidade};margin:2px;vertical-align:middle;"></div>'
        )
    return (
        '<div style="margin-bottom:8px;padding:8px;background-color:#f8f9fa;'
        'border-radius:8px;">' + "".join(blocos) + '</div>'
    )


def _renderizar_amostra_cor(hexcode):
    """Renderiza uma amostra grande da cor selecionada."""
    nome_cor = next((c["nome"] for c in PALETA_CORES if c["hex"] == hexcode), hexcode)
    return (
        f'<div style="margin-top:8px;padding:12px;background-color:{hexcode};'
        f'border-radius:8px;border:1px solid #ccc;text-align:center;'
        f'font-weight:500;color:#333;">'
        f'Cor selecionada: {nome_cor}'
        f'</div>'
    )


def _renderizar_tabela_ambientes(df_amb):
    """Renderiza tabela HTML estilizada de ambientes.

    Mesma logica de sobrescrita CSS da tabela de professores: usa classe
    `tabela-ambientes` para sobrescrever a regra global de styles.py que
    esconde th:first-child em tabelas (necessaria para st.dataframe em
    outras paginas).
    """
    style_override = (
        '<style>'
        '.tabela-ambientes thead tr th:first-child { display: table-cell !important; }'
        '.tabela-ambientes tbody th { display: none; }'
        '</style>'
    )

    cabecalho = (
        '<tr style="background-color:#f8f9fa;border-bottom:2px solid #dee2e6;">'
        '<th style="padding:10px 12px;text-align:left;font-weight:600;">ID</th>'
        '<th style="padding:10px 12px;text-align:left;font-weight:600;">Nome</th>'
        '<th style="padding:10px 12px;text-align:right;font-weight:600;">Area (m²)</th>'
        '<th style="padding:10px 12px;text-align:left;font-weight:600;">Rentavel</th>'
        '<th style="padding:10px 12px;text-align:left;font-weight:600;">Status</th>'
        '</tr>'
    )

    linhas_html = []
    for _, row in df_amb.iterrows():
        rentavel_label = '💰 Sim' if row["rentavel"] else '🚫 Nao'
        cor_rentavel = '#2E7D32' if row["rentavel"] else '#9e9e9e'
        rentavel_celula = f'<span style="color:{cor_rentavel};font-weight:500;">{rentavel_label}</span>'

        status_label = "Ativo" if row["ativo"] else "Inativo"
        cor_status = "#2E7D32" if row["ativo"] else "#9e9e9e"
        status_celula = f'<span style="color:{cor_status};font-weight:500;">{status_label}</span>'

        linhas_html.append(
            f'<tr style="border-bottom:1px solid #f0f0f0;">'
            f'<td style="padding:8px 12px;">{row["id"]}</td>'
            f'<td style="padding:8px 12px;">{row["nome"]}</td>'
            f'<td style="padding:8px 12px;text-align:right;">{float(row["area_m2"]):.2f}</td>'
            f'<td style="padding:8px 12px;">{rentavel_celula}</td>'
            f'<td style="padding:8px 12px;">{status_celula}</td>'
            f'</tr>'
        )

    tabela = (
        '<table class="tabela-ambientes" '
        'style="width:100%;border-collapse:collapse;border:1px solid #dee2e6;'
        'border-radius:8px;overflow:hidden;font-family:inherit;font-size:14px;">'
        f'<thead>{cabecalho}</thead>'
        f'<tbody>{"".join(linhas_html)}</tbody>'
        '</table>'
    )

    return style_override + tabela


def _validar_ambiente(nome, df_existente, ambiente_id_editando=None):
    """Valida nome do ambiente. Retorna mensagem de erro ou None se OK."""
    if not nome or not nome.strip():
        return "O nome do ambiente nao pode ficar vazio."
    nome_limpo = nome.strip()
    if len(nome_limpo) < 2:
        return "O nome do ambiente precisa ter pelo menos 2 caracteres."
    # Checar duplicidade (case-insensitive), ignorando o proprio registro em edicao
    df_check = df_existente.copy()
    if ambiente_id_editando is not None:
        df_check = df_check[df_check["id"] != ambiente_id_editando]
    if not df_check.empty:
        nomes_existentes = df_check["nome"].astype(str).str.strip().str.lower().tolist()
        if nome_limpo.lower() in nomes_existentes:
            return f"Ja existe um ambiente com o nome '{nome_limpo}'."
    return None


# ============================================================================
# Helpers da aba Horario de Funcionamento (F.3)
# ============================================================================

# Convencao de dia_semana: 0=segunda, 1=terca, ..., 6=domingo
# Padrao Python datetime.weekday()
DIAS_SEMANA = [
    "Segunda-feira",
    "Terca-feira",
    "Quarta-feira",
    "Quinta-feira",
    "Sexta-feira",
    "Sabado",
    "Domingo",
]


def _filtrar_vigentes_hoje(df, hoje):
    """Retorna apenas blocos vigentes hoje.

    Vigente hoje = vigente_desde <= hoje E (vigente_ate IS NULL OR vigente_ate >= hoje).

    Usa pd.Timestamp para comparacao porque lida bem com NaT na coluna
    vigente_ate (quando o bloco ainda esta em vigencia, vigente_ate e NULL
    no banco, NaT no DataFrame).
    """
    if df.empty:
        return df
    df_copy = df.copy()
    hoje_ts = pd.Timestamp(hoje)
    df_copy["_vigente_desde_ts"] = pd.to_datetime(df_copy["vigente_desde"], errors="coerce")
    df_copy["_vigente_ate_ts"] = pd.to_datetime(df_copy["vigente_ate"], errors="coerce")
    cond_desde = df_copy["_vigente_desde_ts"] <= hoje_ts
    cond_ate = df_copy["_vigente_ate_ts"].isna() | (df_copy["_vigente_ate_ts"] >= hoje_ts)
    return df_copy[cond_desde & cond_ate].drop(columns=["_vigente_desde_ts", "_vigente_ate_ts"])


def _calcular_total_horas_semanais(df_vigentes):
    """Soma total de horas vigentes de funcionamento na semana."""
    total_segundos = 0
    for _, bloco in df_vigentes.iterrows():
        ini = pd.to_datetime(str(bloco["hora_inicio"]))
        fim = pd.to_datetime(str(bloco["hora_fim"]))
        total_segundos += (fim - ini).total_seconds()
    return total_segundos / 3600.0


def _validar_sobreposicao(dia_semana, hora_inicio, hora_fim, df_vigentes, bloco_id_excluir=None):
    """Verifica sobreposicao com blocos vigentes do mesmo dia da semana.

    Retorna mensagem de erro ou None se OK. bloco_id_excluir e passado
    quando estamos editando um bloco existente, para nao comparar com
    ele mesmo.
    """
    if df_vigentes.empty:
        return None
    df_dia = df_vigentes[df_vigentes["dia_semana"] == dia_semana]
    if bloco_id_excluir is not None:
        df_dia = df_dia[df_dia["id"] != bloco_id_excluir]
    if df_dia.empty:
        return None
    novo_ini = pd.to_datetime(str(hora_inicio)).time()
    novo_fim = pd.to_datetime(str(hora_fim)).time()
    for _, existente in df_dia.iterrows():
        existente_ini = pd.to_datetime(str(existente["hora_inicio"])).time()
        existente_fim = pd.to_datetime(str(existente["hora_fim"])).time()
        # Sobreposicao: novo.inicio < existente.fim AND novo.fim > existente.inicio
        if novo_ini < existente_fim and novo_fim > existente_ini:
            return (
                f"Sobreposicao com bloco existente: "
                f"{existente_ini.strftime('%H:%M')} - {existente_fim.strftime('%H:%M')}. "
                f"Edite ou remova o bloco existente antes de cadastrar este."
            )
    return None


def _render_linha_bloco(bloco, df_func_completo):
    """Renderiza uma linha visual de um bloco vigente com botoes editar e remover."""
    bloco_id = int(bloco["id"])
    hora_ini_str = str(bloco["hora_inicio"])[:5]  # HH:MM
    hora_fim_str = str(bloco["hora_fim"])[:5]

    col_info, col_edit, col_del = st.columns([5, 1, 1])
    with col_info:
        st.markdown(f"• **{hora_ini_str}** - **{hora_fim_str}**")
    with col_edit:
        if st.button("✏️", key=f"btn_edit_{bloco_id}", help="Editar bloco", use_container_width=True):
            st.session_state[f"editando_bloco_{bloco_id}"] = True
            st.rerun()
    with col_del:
        if st.button("🗑️", key=f"btn_del_{bloco_id}", help="Remover bloco", use_container_width=True):
            _remover_bloco(bloco_id, bloco)
            st.rerun()

    # Form de edicao (aparece apenas quando o usuario clicou em editar)
    if st.session_state.get(f"editando_bloco_{bloco_id}", False):
        with st.form(f"form_edit_bloco_{bloco_id}"):
            st.markdown("**Editar bloco**")
            col_h1, col_h2 = st.columns(2)
            with col_h1:
                nova_ini = st.time_input(
                    "Hora inicio",
                    value=pd.to_datetime(str(bloco["hora_inicio"])).time(),
                    step=1800,  # 30 minutos
                )
            with col_h2:
                nova_fim = st.time_input(
                    "Hora fim",
                    value=pd.to_datetime(str(bloco["hora_fim"])).time(),
                    step=1800,
                )
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                btn_salvar = st.form_submit_button("Salvar", type="primary", use_container_width=True)
            with col_btn2:
                btn_cancelar = st.form_submit_button("Cancelar", use_container_width=True)

            if btn_salvar:
                if nova_fim <= nova_ini:
                    st.error("Hora fim deve ser maior que hora inicio.")
                else:
                    df_vigentes = _filtrar_vigentes_hoje(df_func_completo, date.today())
                    erro = _validar_sobreposicao(
                        int(bloco["dia_semana"]), nova_ini, nova_fim,
                        df_vigentes, bloco_id_excluir=bloco_id
                    )
                    if erro:
                        st.error(erro)
                    else:
                        try:
                            _editar_bloco(bloco_id, bloco, nova_ini, nova_fim)
                            del st.session_state[f"editando_bloco_{bloco_id}"]
                            st.success("Bloco editado com sucesso.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao editar: {e}")

            if btn_cancelar:
                del st.session_state[f"editando_bloco_{bloco_id}"]
                st.rerun()


def _render_form_adicionar_bloco(dia_idx, dia_nome, df_func):
    """Form pra adicionar novo bloco em um dia especifico."""
    with st.form(f"form_add_bloco_{dia_idx}", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            nova_ini = st.time_input(
                "Hora inicio",
                value=pd.to_datetime("05:00").time(),
                step=1800,  # 30 minutos
                key=f"add_ini_{dia_idx}",
            )
        with col2:
            nova_fim = st.time_input(
                "Hora fim",
                value=pd.to_datetime("23:30").time(),
                step=1800,
                key=f"add_fim_{dia_idx}",
            )
        submitted = st.form_submit_button(
            f"Adicionar bloco em {dia_nome.lower()}",
            type="primary",
            use_container_width=True,
        )

        if submitted:
            if nova_fim <= nova_ini:
                st.error("Hora fim deve ser maior que hora inicio.")
            else:
                df_vigentes = _filtrar_vigentes_hoje(df_func, date.today())
                erro = _validar_sobreposicao(dia_idx, nova_ini, nova_fim, df_vigentes)
                if erro:
                    st.error(erro)
                else:
                    try:
                        inserir_dados("horario_funcionamento", {
                            "dia_semana": int(dia_idx),
                            "hora_inicio": nova_ini.strftime("%H:%M:%S"),
                            "hora_fim": nova_fim.strftime("%H:%M:%S"),
                            "ativo": True,
                            "vigente_desde": date.today().isoformat(),
                        })
                        st.success(f"Bloco {nova_ini.strftime('%H:%M')}-{nova_fim.strftime('%H:%M')} adicionado em {dia_nome.lower()}.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao adicionar: {e}")


def _editar_bloco(bloco_id, bloco_atual, nova_ini, nova_fim):
    """Edita um bloco. Logica: se cadastrado hoje, UPDATE in-place;
    senao, encerra vigencia do antigo e cria novo."""
    hoje = date.today()
    vigente_desde = pd.to_datetime(str(bloco_atual["vigente_desde"])).date()

    if vigente_desde == hoje:
        # Cadastrado hoje, sem historico real -> UPDATE in-place
        atualizar_dados("horario_funcionamento", {
            "hora_inicio": nova_ini.strftime("%H:%M:%S"),
            "hora_fim": nova_fim.strftime("%H:%M:%S"),
        }, "id", bloco_id)
    else:
        # Tem historico -> encerra antigo + cria novo
        ontem = hoje - timedelta(days=1)
        atualizar_dados("horario_funcionamento", {
            "vigente_ate": ontem.isoformat(),
        }, "id", bloco_id)
        inserir_dados("horario_funcionamento", {
            "dia_semana": int(bloco_atual["dia_semana"]),
            "hora_inicio": nova_ini.strftime("%H:%M:%S"),
            "hora_fim": nova_fim.strftime("%H:%M:%S"),
            "ativo": True,
            "vigente_desde": hoje.isoformat(),
        })


def _remover_bloco(bloco_id, bloco_atual):
    """Remove um bloco. Logica: se cadastrado hoje, DELETE fisico;
    senao, soft delete (vigente_ate = hoje)."""
    hoje = date.today()
    vigente_desde = pd.to_datetime(str(bloco_atual["vigente_desde"])).date()

    if vigente_desde == hoje:
        # Cadastrado hoje, sem historico real -> DELETE fisico
        deletar_dados("horario_funcionamento", "id", bloco_id)
    else:
        # Tem historico -> soft delete
        atualizar_dados("horario_funcionamento", {
            "vigente_ate": hoje.isoformat(),
        }, "id", bloco_id)


def _render_sub_ambientes():
    """Sub-aba: Cadastro de Ambientes (F.2)."""
    st.markdown("### Ambientes cadastrados")
    st.caption(
        "Cadastre os espacos fisicos da academia. Ambientes 'rentaveis' podem "
        "receber atividades (aulas, treinos, eventos). Ambientes 'nao rentaveis' "
        "(banheiros, cozinha, recepcao) contam para a area total do imovel mas "
        "nao recebem atividades pagas."
    )

    df_amb = buscar_dados("ambientes", order="id")

    if df_amb.empty:
        df_amb = pd.DataFrame(columns=["id", "nome", "area_m2", "rentavel", "ativo", "created_at"])

    # ----------------------------------------------------------------------
    # 1) Listagem
    # ----------------------------------------------------------------------
    if df_amb.empty:
        st.info("Nenhum ambiente cadastrado ainda. Use o formulario abaixo para cadastrar o primeiro.")
    else:
        st.markdown(_renderizar_tabela_ambientes(df_amb), unsafe_allow_html=True)

        # KPIs rapidos: area total e area rentavel
        df_ativos = df_amb[df_amb["ativo"]]
        area_total = float(df_ativos["area_m2"].sum()) if not df_ativos.empty else 0.0
        area_rentavel = float(df_ativos[df_ativos["rentavel"]]["area_m2"].sum()) if not df_ativos.empty else 0.0
        col_k1, col_k2, col_k3 = st.columns(3)
        with col_k1:
            st.metric("Area total (ativos)", f"{area_total:.2f} m²")
        with col_k2:
            st.metric("Area rentavel", f"{area_rentavel:.2f} m²")
        with col_k3:
            pct = (area_rentavel / area_total * 100) if area_total > 0 else 0
            st.metric("% rentavel", f"{pct:.1f}%")

    st.markdown("---")

    # ----------------------------------------------------------------------
    # 2) Cadastrar novo ambiente
    # ----------------------------------------------------------------------
    with st.expander("Cadastrar novo ambiente", expanded=df_amb.empty):
        with st.form("form_novo_ambiente", clear_on_submit=True):
            col1, col2 = st.columns([2, 1])
            with col1:
                novo_nome = st.text_input("Nome do ambiente", max_chars=80, placeholder="Ex: Embaixo, Recepcao, Cozinha")
            with col2:
                nova_area = st.number_input(
                    "Area (m²)",
                    min_value=0.01,
                    max_value=10000.0,
                    value=10.0,
                    step=0.5,
                    format="%.2f",
                )

            novo_rentavel = st.checkbox(
                "Rentavel (pode receber atividades pagas)",
                value=True,
                help="Marque se este espaco pode receber atividades. Banheiros, cozinha e recepcao normalmente NAO sao rentaveis.",
            )

            submitted = st.form_submit_button("Cadastrar ambiente", use_container_width=True, type="primary")

            if submitted:
                erro = _validar_ambiente(novo_nome, df_amb, ambiente_id_editando=None)
                if erro:
                    st.error(erro)
                else:
                    try:
                        inserir_dados("ambientes", {
                            "nome": novo_nome.strip(),
                            "area_m2": float(nova_area),
                            "rentavel": bool(novo_rentavel),
                            "ativo": True,
                        })
                        st.success(f"Ambiente '{novo_nome.strip()}' cadastrado com sucesso.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao cadastrar ambiente: {e}")

    # ----------------------------------------------------------------------
    # 3) Editar / Inativar / Reativar ambiente existente
    # ----------------------------------------------------------------------
    if df_amb.empty:
        return

    with st.expander("Editar / Inativar / Reativar ambiente"):
        df_sel = df_amb.copy()
        df_sel["label"] = df_sel.apply(
            lambda r: f"{r['nome']} ({r['area_m2']:.2f} m²) - {'Rentavel' if r['rentavel'] else 'Nao rentavel'} - {'Ativo' if r['ativo'] else 'Inativo'}",
            axis=1,
        )
        opcoes_ids = df_sel["id"].tolist()
        amb_id_sel = st.selectbox(
            "Selecione um ambiente",
            options=opcoes_ids,
            format_func=lambda aid: df_sel.loc[df_sel["id"] == aid, "label"].values[0],
        )

        amb_atual = df_sel.loc[df_sel["id"] == amb_id_sel].iloc[0]

        with st.form(f"form_editar_ambiente_{amb_id_sel}"):
            col1, col2 = st.columns([2, 1])
            with col1:
                nome_edit = st.text_input("Nome do ambiente", value=amb_atual["nome"], max_chars=80)
            with col2:
                area_edit = st.number_input(
                    "Area (m²)",
                    min_value=0.01,
                    max_value=10000.0,
                    value=float(amb_atual["area_m2"]),
                    step=0.5,
                    format="%.2f",
                )

            rentavel_edit = st.checkbox(
                "Rentavel (pode receber atividades pagas)",
                value=bool(amb_atual["rentavel"]),
                help="Marque se este espaco pode receber atividades.",
            )

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                btn_salvar = st.form_submit_button("Salvar alteracoes", use_container_width=True, type="primary")
            with col_btn2:
                if amb_atual["ativo"]:
                    btn_toggle = st.form_submit_button("Inativar", use_container_width=True)
                else:
                    btn_toggle = st.form_submit_button("Reativar", use_container_width=True)

            if btn_salvar:
                erro = _validar_ambiente(nome_edit, df_amb, ambiente_id_editando=amb_id_sel)
                if erro:
                    st.error(erro)
                else:
                    try:
                        atualizar_dados("ambientes", {
                            "nome": nome_edit.strip(),
                            "area_m2": float(area_edit),
                            "rentavel": bool(rentavel_edit),
                        }, "id", int(amb_id_sel))
                        st.success("Alteracoes salvas com sucesso.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")

            if btn_toggle:
                try:
                    novo_status = not bool(amb_atual["ativo"])
                    atualizar_dados("ambientes", {"ativo": novo_status}, "id", int(amb_id_sel))
                    msg = "Ambiente reativado." if novo_status else "Ambiente inativado."
                    st.success(msg)
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao alterar status: {e}")


# ============================================================================
# Helpers da aba Calendario (F.4)
# ============================================================================


def _buscar_regras_vigentes_mes(ano, mes):
    """Busca regras de agenda_regras vigentes em qualquer dia do mes informado.

    Uma regra e vigente no mes se:
    - ativo = TRUE
    - data_inicio <= ultimo_dia_do_mes
    - data_fim IS NULL OR data_fim >= primeiro_dia_do_mes

    Retorna DataFrame com colunas: id, profissional_id, ambiente_id,
    dia_semana, hora_inicio, hora_fim, data_inicio, data_fim, ativo,
    profissional_nome, profissional_cor, ambiente_nome.
    """
    # Calcula primeiro e ultimo dia do mes
    primeiro_dia = dt.date(ano, mes, 1)
    ultimo_dia_num = _calendar_lib.monthrange(ano, mes)[1]
    ultimo_dia = dt.date(ano, mes, ultimo_dia_num)

    # Busca todas as regras ativas
    df_regras = buscar_dados("agenda_regras", eq={"ativo": True})

    if df_regras.empty:
        return pd.DataFrame(columns=[
            "id", "profissional_id", "ambiente_id", "dia_semana",
            "hora_inicio", "hora_fim", "data_inicio", "data_fim", "ativo",
            "profissional_nome", "profissional_cor", "ambiente_nome",
        ])

    # Filtra por vigencia que intersecta o mes
    df_regras["data_inicio_dt"] = pd.to_datetime(df_regras["data_inicio"], errors="coerce")
    df_regras["data_fim_dt"] = pd.to_datetime(df_regras["data_fim"], errors="coerce")

    primeiro_ts = pd.Timestamp(primeiro_dia)
    ultimo_ts = pd.Timestamp(ultimo_dia)

    mask_inicio = df_regras["data_inicio_dt"] <= ultimo_ts
    mask_fim = df_regras["data_fim_dt"].isna() | (df_regras["data_fim_dt"] >= primeiro_ts)
    df_regras = df_regras[mask_inicio & mask_fim].copy()

    if df_regras.empty:
        return pd.DataFrame(columns=[
            "id", "profissional_id", "ambiente_id", "dia_semana",
            "hora_inicio", "hora_fim", "data_inicio", "data_fim", "ativo",
            "profissional_nome", "profissional_cor", "ambiente_nome",
        ])

    # Enriquece com dados de profissionais e ambientes
    df_prof = buscar_dados("profissionais")
    df_amb = buscar_dados("ambientes")

    if not df_prof.empty:
        df_regras = df_regras.merge(
            df_prof[["id", "nome", "cor_hex"]].rename(
                columns={"id": "profissional_id", "nome": "profissional_nome", "cor_hex": "profissional_cor"}
            ),
            on="profissional_id",
            how="left",
        )
    else:
        df_regras["profissional_nome"] = "?"
        df_regras["profissional_cor"] = "#888888"

    if not df_amb.empty:
        df_regras = df_regras.merge(
            df_amb[["id", "nome"]].rename(
                columns={"id": "ambiente_id", "nome": "ambiente_nome"}
            ),
            on="ambiente_id",
            how="left",
        )
    else:
        df_regras["ambiente_nome"] = "?"

    df_regras = df_regras.drop(columns=["data_inicio_dt", "data_fim_dt"], errors="ignore")
    return df_regras


def _gerar_eventos_do_mes(ano, mes, df_regras):
    """Expande regras recorrentes em ocorrencias reais do mes.

    Para cada regra, percorre os dias do mes e gera um evento sempre que:
    - dia.weekday() bate com regra.dia_semana (formato Python: 0=segunda ... 6=domingo)
    - regra.data_inicio <= dia <= regra.data_fim (ou data_fim e None)

    Retorna dict {ambiente_id: [lista de eventos no formato FullCalendar]}.
    """
    eventos_por_ambiente = {}

    if df_regras.empty:
        return eventos_por_ambiente

    ultimo_dia_num = _calendar_lib.monthrange(ano, mes)[1]

    for _, regra in df_regras.iterrows():
        # Parsea datas de inicio/fim da regra
        data_inicio_regra = regra.get("data_inicio")
        data_fim_regra = regra.get("data_fim")

        # data_inicio: vem como str ou date do banco
        if pd.isna(data_inicio_regra):
            data_inicio_regra = None
        elif isinstance(data_inicio_regra, str):
            data_inicio_regra = dt.date.fromisoformat(data_inicio_regra)

        # data_fim: pode vir None, NaN (NULL no banco), str ou date
        if pd.isna(data_fim_regra):
            data_fim_regra = None
        elif isinstance(data_fim_regra, str):
            data_fim_regra = dt.date.fromisoformat(data_fim_regra)

        dia_semana_regra = int(regra["dia_semana"])
        hora_inicio = str(regra["hora_inicio"])
        hora_fim = str(regra["hora_fim"])

        # Normaliza hora pra "HH:MM"
        if len(hora_inicio) > 5:
            hora_inicio = hora_inicio[:5]
        if len(hora_fim) > 5:
            hora_fim = hora_fim[:5]

        # Loop pelos dias do mes
        for dia_num in range(1, ultimo_dia_num + 1):
            dia = dt.date(ano, mes, dia_num)

            # Filtro por dia_semana (Python convention: 0=segunda)
            if dia.weekday() != dia_semana_regra:
                continue

            # Filtro por vigencia da regra
            if data_inicio_regra and dia < data_inicio_regra:
                continue
            if data_fim_regra and dia > data_fim_regra:
                continue

            # title vazio: bloco mostra so a cor (legenda no topo identifica
            # o profissional). extendedProps guarda dados pra usar no menu
            # de bloco (Tarefa 5).
            evento = {
                "id": str(regra["id"]),
                "title": " ",
                "start": f"{dia.isoformat()}T{hora_inicio}:00",
                "end": f"{dia.isoformat()}T{hora_fim}:00",
                "backgroundColor": regra.get("profissional_cor", "#888888"),
                "borderColor": regra.get("profissional_cor", "#888888"),
                "textColor": "#ffffff",
                "extendedProps": {
                    "profissional_nome": regra.get("profissional_nome", "?"),
                    "ambiente_nome": regra.get("ambiente_nome", "?"),
                    "hora_inicio": hora_inicio,
                    "hora_fim": hora_fim,
                },
            }

            ambiente_id = regra["ambiente_id"]
            if ambiente_id not in eventos_por_ambiente:
                eventos_por_ambiente[ambiente_id] = []
            eventos_por_ambiente[ambiente_id].append(evento)

    return eventos_por_ambiente


def _renderizar_calendarios_lado_a_lado(df_ambientes, eventos_por_ambiente, ano, mes, visao):
    """Renderiza um calendario por ambiente rentavel, lado a lado em colunas.

    Se houver 2 ambientes: 2 colunas iguais.
    Se houver 1 ambiente: ocupa toda a largura.
    Se houver 3+ ambientes: empilha em linhas de 2.
    """
    ambientes_lista = df_ambientes.to_dict("records")

    if visao == "Mensal":
        initial_view = "dayGridMonth"
    else:
        initial_view = "timeGridWeek"

    initial_date = dt.date(ano, mes, 1).isoformat()

    # Configuracoes interativas variam por visao
    is_semanal = (visao == "Semanal")

    options_base = {
        "headerToolbar": {
            "left": "prev,next today",
            "center": "title",
            "right": ""
        },
        "initialView": initial_view,
        "initialDate": initial_date,
        "firstDay": 0,
        "fixedWeekCount": True,
        "showNonCurrentDates": True,
        "editable": is_semanal,
        "eventStartEditable": is_semanal,
        "eventDurationEditable": is_semanal,
        "selectable": is_semanal,
        "selectMirror": is_semanal,
        "locale": "pt-br",
        "timeZone": "America/Sao_Paulo",
        "buttonText": {
            "today": "Hoje"
        },
        "slotMinTime": "05:00:00",
        "slotMaxTime": "23:30:00",
        "allDaySlot": False,
        "height": 650,
    }

    # Renderiza em pares (2 por linha)
    for i in range(0, len(ambientes_lista), 2):
        par = ambientes_lista[i:i + 2]

        if len(par) == 2:
            cols = st.columns(2)
        else:
            cols = [st.container()]

        for col, ambiente in zip(cols, par):
            with col:
                area_str = f" ({ambiente.get('area_m2', '?')} m²)" if ambiente.get("area_m2") else ""
                st.markdown(f"#### 🏢 {ambiente['nome']}{area_str}")

                eventos = eventos_por_ambiente.get(ambiente["id"], [])

                # Key unica por ambiente + mes + visao pra evitar colisao de state
                cal_key = f"cal_{ambiente['id']}_{ano}_{mes}_{visao}"

                # Captura interacao do usuario (drag, click, etc)
                cal_state = calendar(
                    events=eventos,
                    options=options_base,
                    key=cal_key,
                )

                # Processa interacao se houve
                if is_semanal and cal_state:
                    _processar_interacao_calendario(cal_state, ambiente["id"], cal_key)


def _renderizar_calendario_unico(ambiente, eventos, ano, mes, visao):
    """Renderiza UM calendario (single-ambient).

    Usado no layout 60/40 onde so um ambiente e mostrado por vez,
    com a caixa de acao na coluna lateral. Substituiu o layout
    antigo de 2 calendarios lado a lado (`_renderizar_calendarios_lado_a_lado`).
    """
    if visao == "Mensal":
        initial_view = "dayGridMonth"
    else:
        initial_view = "timeGridWeek"

    initial_date = dt.date(ano, mes, 1).isoformat()
    is_semanal = (visao == "Semanal")

    options = {
        "headerToolbar": {
            "left": "prev,next today",
            "center": "title",
            "right": ""
        },
        "initialView": initial_view,
        "initialDate": initial_date,
        "firstDay": 0,
        "fixedWeekCount": True,
        "showNonCurrentDates": True,
        "editable": is_semanal,
        "eventStartEditable": is_semanal,
        "eventDurationEditable": is_semanal,
        "selectable": is_semanal,
        "selectMirror": is_semanal,
        "locale": "pt-br",
        "timeZone": "America/Sao_Paulo",
        "buttonText": {
            "today": "Hoje"
        },
        "slotMinTime": "05:00:00",
        "slotMaxTime": "23:30:00",
        "allDaySlot": False,
        "height": 750,
    }

    area_str = f" ({ambiente.get('area_m2', '?')} m²)" if ambiente.get("area_m2") else ""
    st.markdown(f"#### 🏢 {ambiente['nome']}{area_str}")

    # Legenda de cores (substitui texto dentro dos blocos)
    _renderizar_legenda_profissionais()

    cal_key = f"cal_unico_{ambiente['id']}_{ano}_{mes}_{visao}"

    cal_state = calendar(
        events=eventos,
        options=options,
        key=cal_key,
    )

    if is_semanal and cal_state:
        _processar_interacao_calendario(cal_state, ambiente["id"], cal_key)
    elif not is_semanal and cal_state:
        # Mensal so processa eventClick (encerrar), nao select (criar)
        _processar_interacao_calendario(cal_state, ambiente["id"], cal_key)


def _renderizar_legenda_profissionais():
    """Legenda horizontal de profissionais ativos com suas cores.

    Substitui o texto que estava dentro dos blocos do calendario.
    Le profissionais ativos ordenados por nome.
    """
    df_prof = buscar_dados("profissionais", eq={"ativo": True}, order="nome")

    if df_prof.empty:
        return

    itens_html = []
    for _, row in df_prof.iterrows():
        cor = row.get("cor_hex", "#888888")
        nome = row["nome"]
        item = (
            f'<span style="display:inline-flex;align-items:center;'
            f'margin-right:18px;font-size:14px;">'
            f'<span style="display:inline-block;width:14px;height:14px;'
            f'border-radius:50%;background-color:{cor};border:1px solid #ccc;'
            f'margin-right:6px;"></span>'
            f'<span>{nome}</span>'
            f'</span>'
        )
        itens_html.append(item)

    legenda_html = (
        '<div style="padding:8px 12px;background-color:#f8f9fa;'
        'border:1px solid #dee2e6;border-radius:6px;margin-bottom:8px;">'
        + "".join(itens_html) +
        '</div>'
    )

    st.markdown(legenda_html, unsafe_allow_html=True)


def _processar_interacao_calendario(cal_state, ambiente_id, cal_key):
    """Despacha cal_state pra session_state (em vez de abrir modal).

    streamlit-calendar retorna dict com chaves 'select' (drag pra criar)
    ou 'eventClick' (clique em evento existente). Em vez de abrir um
    @st.dialog (que sofre com loop de rerun), gravamos a intencao em
    session_state e a caixa de acao inline (renderizada abaixo dos
    calendarios) detecta e mostra o form.

    Importante: comparamos com a ultima interacao processada pra evitar
    re-disparar a mesma acao apos um rerun (cal_state persiste).
    """
    if not cal_state:
        return

    # Detecta arrastar pra criar (so visao semanal)
    if "select" in cal_state and cal_state["select"]:
        sel = cal_state["select"]
        if not sel.get("allDay"):
            assinatura = f"select|{ambiente_id}|{sel.get('start')}|{sel.get('end')}"
            ultima = st.session_state.get("f5_ultima_interacao_processada")
            if assinatura != ultima:
                st.session_state["f5_acao_pendente"] = {
                    "tipo": "criar",
                    "origem": "drag",
                    "ambiente_id": ambiente_id,
                    "start_iso": sel["start"],
                    "end_iso": sel["end"],
                    "cal_key": cal_key,
                }
                st.session_state["f5_ultima_interacao_processada"] = assinatura
                st.rerun()
            return

    # Detecta clique em evento existente -> abre MENU do bloco
    # (em vez de ir direto pra encerrar — agora menu pergunta o que fazer)
    if "eventClick" in cal_state and cal_state["eventClick"]:
        evt = cal_state["eventClick"].get("event", {})
        regra_id = evt.get("id")
        data_clicada_iso = evt.get("start")

        if regra_id and data_clicada_iso:
            assinatura = f"eventClick|{regra_id}|{data_clicada_iso}"
            ultima = st.session_state.get("f5_ultima_interacao_processada")
            if assinatura != ultima:
                try:
                    regra_id_int = int(regra_id)
                    st.session_state["f5_acao_pendente"] = {
                        "tipo": "menu_bloco",
                        "regra_id": regra_id_int,
                        "data_clicada_iso": data_clicada_iso,
                        "ambiente_id": ambiente_id,
                    }
                    st.session_state["f5_ultima_interacao_processada"] = assinatura
                    st.rerun()
                except (ValueError, TypeError):
                    pass
        return


def _inserir_regra(
    profissional_id,
    ambiente_id,
    dia_semana,
    hora_inicio,
    hora_fim,
    data_inicio=None,
    data_fim=None,
):
    """INSERT em agenda_regras.

    data_inicio: date object. Se None, usa hoje (default uso continuo).
    data_fim: date object ou None. Default None (regra recorrente sem fim).
              Usado quando regra ja foi encerrada no passado (cadastro historico).

    Retorna True se nao houve excecao.
    """
    if data_inicio is None:
        data_inicio = dt.date.today()

    dados = {
        "profissional_id": profissional_id,
        "ambiente_id": ambiente_id,
        "dia_semana": int(dia_semana),
        "hora_inicio": hora_inicio,
        "hora_fim": hora_fim,
        "data_inicio": data_inicio.isoformat(),
        "data_fim": data_fim.isoformat() if data_fim else None,
        "ativo": True,
    }

    try:
        inserir_dados("agenda_regras", dados)
        return True
    except Exception as e:
        st.error(f"Erro ao cadastrar regra: {type(e).__name__} — {e}")
        return False


def _encerrar_regra(regra_id, data_encerrar, data_inicio_regra):
    """Encerra uma regra existente.

    Logica:
    - Se data_encerrar == data_inicio_regra (regra criada hoje, sem historico):
      DELETE fisico (limpa banco)
    - Caso contrario: UPDATE setando data_fim = data_encerrar - 1 dia

    Retorna True se nao houve excecao.
    """
    try:
        if data_encerrar == data_inicio_regra:
            # Regra cadastrada hoje sem historico — DELETE fisico
            deletar_dados("agenda_regras", "id", regra_id)
        else:
            # Encerra com data_fim = vespera
            data_fim_iso = (data_encerrar - dt.timedelta(days=1)).isoformat()
            atualizar_dados(
                "agenda_regras",
                {"data_fim": data_fim_iso},
                "id",
                regra_id,
            )
        return True
    except Exception as e:
        st.error(f"Erro ao encerrar regra: {type(e).__name__} — {e}")
        return False


def _renderizar_caixa_acao():
    """Caixa de acao lateral (coluna direita do layout 60/40).

    Le `f5_acao_pendente` em session_state e renderiza:
    - tipo='menu_bloco': menu com 3 opcoes (encerrar / cadastrar nova / cancelar)
    - tipo='criar': form de cadastro
    - tipo='encerrar': form de encerramento
    - sem chave: dica de uso
    """
    acao = st.session_state.get("f5_acao_pendente")

    if not acao:
        with st.container(border=True):
            st.markdown("##### 💡 Como usar")
            st.markdown(
                "**Pra cadastrar uma nova regra:** mude pra visao "
                "**Semanal** e arraste o mouse no horario desejado."
            )
            st.markdown(
                "**Pra encerrar ou cadastrar atividade sobre uma regra existente:** "
                "clique uma vez no bloco — um menu aparecera aqui."
            )
            st.caption(
                "Use o expander **'Cadastrar historico'** abaixo do "
                "calendario pra cadastrar regras antigas (que comecaram "
                "antes de hoje)."
            )
            st.warning(
                "⚠️ **Arrastar um bloco existente** pra mover ou redimensionar "
                "ainda nao salva a alteracao — em desenvolvimento. Pra "
                "mudar uma regra, encerre a antiga e cadastre uma nova."
            )
        return

    tipo = acao.get("tipo")
    if tipo == "menu_bloco":
        _renderizar_menu_bloco(acao)
    elif tipo == "criar":
        _renderizar_form_criar_regra(acao)
    elif tipo == "encerrar":
        _renderizar_form_encerrar_regra(acao)
    elif tipo == "editar":
        _renderizar_form_editar_regra(acao)


def _renderizar_menu_bloco(acao):
    """Menu que aparece ao clicar em um bloco existente.

    Mostra resumo do bloco + 3 botoes:
    - Encerrar regra
    - Cadastrar nova atividade neste horario
    - Cancelar
    """
    regra_id = acao["regra_id"]
    data_clicada_iso = acao["data_clicada_iso"]
    ambiente_id = acao["ambiente_id"]

    df_regra = buscar_dados("agenda_regras", eq={"id": regra_id})

    st.markdown("##### 🎯 O que fazer com este bloco?")

    with st.container(border=True):
        if df_regra.empty:
            st.error("Regra nao encontrada.")
            if st.button("Fechar", key=f"f5_menu_close_notfound_{regra_id}"):
                st.session_state.pop("f5_acao_pendente", None)
                st.rerun()
            return

        regra = df_regra.iloc[0]

        df_prof = buscar_dados("profissionais", eq={"id": int(regra["profissional_id"])})
        profissional_nome = df_prof.iloc[0]["nome"] if not df_prof.empty else "?"

        hora_ini_str = str(regra["hora_inicio"])[:5]
        hora_fim_str = str(regra["hora_fim"])[:5]

        # Resumo do bloco
        st.markdown(
            f"**{profissional_nome}**, {hora_ini_str} - {hora_fim_str}"
        )

        st.markdown("---")

        # Opcao 1: encerrar
        if st.button(
            "⏹️ Encerrar regra",
            key=f"f5_menu_encerrar_{regra_id}",
            use_container_width=True,
        ):
            st.session_state["f5_acao_pendente"] = {
                "tipo": "encerrar",
                "regra_id": regra_id,
                "data_clicada_iso": data_clicada_iso,
            }
            st.rerun()

        # Opcao 2: cadastrar nova atividade neste horario
        if st.button(
            "➕ Cadastrar nova atividade neste horario",
            key=f"f5_menu_criar_sobre_{regra_id}",
            use_container_width=True,
        ):
            # Calcula a data ISO completa pra start e end (data clicada + horario do bloco)
            data_clicada_dt = dt.datetime.fromisoformat(
                data_clicada_iso.rstrip("Z").split(".")[0]
            )
            data_iso_str = data_clicada_dt.date().isoformat()

            start_iso = f"{data_iso_str}T{hora_ini_str}:00"
            end_iso = f"{data_iso_str}T{hora_fim_str}:00"

            cal_key = f"cal_unico_{ambiente_id}"

            st.session_state["f5_acao_pendente"] = {
                "tipo": "criar",
                "origem": "menu",
                "ambiente_id": ambiente_id,
                "start_iso": start_iso,
                "end_iso": end_iso,
                "cal_key": cal_key,
            }
            st.rerun()

        # Opcao 3: editar atividade
        if st.button(
            "✏️ Editar esta atividade",
            key=f"f5_menu_editar_{regra_id}",
            use_container_width=True,
        ):
            st.session_state["f5_acao_pendente"] = {
                "tipo": "editar",
                "regra_id": regra_id,
                "data_clicada_iso": data_clicada_iso,
            }
            st.rerun()

        # Opcao 4: cancelar
        if st.button(
            "✖️ Cancelar",
            key=f"f5_menu_cancel_{regra_id}",
            use_container_width=True,
        ):
            st.session_state.pop("f5_acao_pendente", None)
            st.rerun()


def _renderizar_form_criar_regra(acao):
    """Form inline de criacao de regra (substitui o antigo dialog).

    Renderizado dentro de container destacado abaixo dos calendarios
    quando `f5_acao_pendente` tem tipo='criar'.
    """
    ambiente_id = acao["ambiente_id"]
    start_iso = acao["start_iso"]
    end_iso = acao["end_iso"]
    cal_key = acao["cal_key"]

    # Parse das datas/horas do drag
    # streamlit-calendar com timeZone='America/Sao_Paulo' retorna ISO com sufixo
    # 'Z' enganador, mas o horario JA esta em fuso local SP. Ignoramos o 'Z' e
    # parseamos como naive — sem nenhuma conversao de fuso.
    start_dt = dt.datetime.fromisoformat(start_iso.rstrip("Z").split(".")[0])
    end_dt = dt.datetime.fromisoformat(end_iso.rstrip("Z").split(".")[0])

    dia_semana = start_dt.weekday()
    hora_inicio = start_dt.strftime("%H:%M")
    hora_fim = end_dt.strftime("%H:%M")

    nomes_dias = ["Segunda", "Terca", "Quarta", "Quinta", "Sexta", "Sabado", "Domingo"]
    dia_nome = nomes_dias[dia_semana]

    df_amb = buscar_dados("ambientes", eq={"id": ambiente_id})
    ambiente_nome = df_amb.iloc[0]["nome"] if not df_amb.empty else "?"

    df_prof = buscar_dados("profissionais", eq={"ativo": True})

    st.markdown("##### ➕ Cadastrar nova regra")

    with st.container(border=True):
        if df_prof.empty:
            st.warning("Nenhum profissional ativo cadastrado. Cadastre em Configuracoes > Professores antes.")
            if st.button("Fechar", key=f"f5_form_criar_close_{cal_key}"):
                st.session_state.pop("f5_acao_pendente", None)
                st.rerun()
            return

        st.markdown(f"**Ambiente:** {ambiente_nome}")
        st.markdown(f"**Dia da semana:** {dia_nome} (toda {dia_nome.lower()})")

        # Hora: editavel quando origem=menu (cadastro sobreposto), fixa quando origem=drag
        origem = acao.get("origem", "drag")

        if origem == "menu":
            # Editavel: usuario pode ajustar dentro do bloco existente
            st.caption(
                f"Bloco original: {hora_inicio} - {hora_fim}. "
                f"Ajuste os campos abaixo pra criar atividade dentro desse intervalo."
            )
            col_hi, col_hf = st.columns(2)
            with col_hi:
                hora_inicio_t = st.time_input(
                    "Hora inicio",
                    value=dt.datetime.strptime(hora_inicio, "%H:%M").time(),
                    step=dt.timedelta(minutes=30),
                    key=f"f5_form_criar_hi_{cal_key}",
                )
            with col_hf:
                hora_fim_t = st.time_input(
                    "Hora fim",
                    value=dt.datetime.strptime(hora_fim, "%H:%M").time(),
                    step=dt.timedelta(minutes=30),
                    key=f"f5_form_criar_hf_{cal_key}",
                )
            # Sobrescreve hora_inicio e hora_fim com valores ajustados
            hora_inicio = hora_inicio_t.strftime("%H:%M")
            hora_fim = hora_fim_t.strftime("%H:%M")
        else:
            # Fixa: usuario arrastou exatamente o intervalo que queria
            st.markdown(f"**Horario:** {hora_inicio} - {hora_fim}")

        # Validacao de horario
        erro_hora = None
        if hora_fim <= hora_inicio:
            erro_hora = "Hora fim deve ser maior que hora inicio."
            st.error(erro_hora)

        # Aviso de vigencia
        hoje = dt.date.today()
        hoje_str = hoje.strftime("%d/%m/%Y")
        hoje_dia_semana = hoje.weekday()
        dias_ate_proximo = (dia_semana - hoje_dia_semana) % 7
        primeira_ocorrencia = hoje + dt.timedelta(days=dias_ate_proximo)
        primeira_ocorrencia_str = primeira_ocorrencia.strftime("%d/%m/%Y")

        if dia_semana == hoje_dia_semana:
            msg_ocorrencia = f"A primeira ocorrencia sera **hoje ({primeira_ocorrencia_str})**."
        else:
            msg_ocorrencia = (
                f"A primeira ocorrencia sera **{primeira_ocorrencia_str}** "
                f"(proxima {dia_nome.lower()})."
            )

        st.info(
            f"📅 Esta regra valera **a partir de hoje ({hoje_str})**, recorrente "
            f"toda {dia_nome.lower()}. {msg_ocorrencia}"
        )

        if origem == "drag":
            st.warning(
                "💡 **Quer cadastrar uma regra que comecou ANTES de hoje?** "
                "Cancele esta caixa e use **'Cadastrar historico (uso temporario)'** "
                "abaixo do calendario."
            )

        st.markdown("---")

        profissionais_dict = {row["nome"]: row["id"] for _, row in df_prof.iterrows()}
        profissional_nome = st.selectbox(
            "Profissional",
            options=list(profissionais_dict.keys()),
            key=f"f5_form_criar_prof_{cal_key}",
        )
        profissional_id = profissionais_dict[profissional_nome]

        st.markdown("---")
        col_cancel, col_ok = st.columns([1, 1])

        with col_cancel:
            if st.button("Cancelar", key=f"f5_form_criar_cancel_{cal_key}", use_container_width=True):
                st.session_state.pop("f5_acao_pendente", None)
                st.rerun()

        with col_ok:
            if st.button(
                "✅ Cadastrar",
                key=f"f5_form_criar_ok_{cal_key}",
                type="primary",
                use_container_width=True,
                disabled=(erro_hora is not None),
            ):
                with st.spinner("Cadastrando..."):
                    sucesso = _inserir_regra(
                        profissional_id=profissional_id,
                        ambiente_id=ambiente_id,
                        dia_semana=dia_semana,
                        hora_inicio=hora_inicio,
                        hora_fim=hora_fim,
                    )
                if sucesso:
                    st.session_state["f5_msg_sucesso"] = "Regra cadastrada!"
                    st.session_state.pop("f5_acao_pendente", None)
                    st.rerun()


def _renderizar_form_encerrar_regra(acao):
    """Form inline de encerramento de regra (substitui o antigo dialog).

    Renderizado dentro de container destacado abaixo dos calendarios
    quando `f5_acao_pendente` tem tipo='encerrar'.
    """
    regra_id = acao["regra_id"]
    data_clicada_iso = acao["data_clicada_iso"]

    df_regra = buscar_dados("agenda_regras", eq={"id": regra_id})

    st.markdown("##### ⏹️ Encerrar regra")

    with st.container(border=True):
        if df_regra.empty:
            st.error("Regra nao encontrada (pode ter sido removida em outra aba).")
            if st.button("Fechar", key=f"f5_form_enc_close_{regra_id}"):
                st.session_state.pop("f5_acao_pendente", None)
                st.rerun()
            return

        regra = df_regra.iloc[0]

        df_prof = buscar_dados("profissionais", eq={"id": int(regra["profissional_id"])})
        df_amb = buscar_dados("ambientes", eq={"id": int(regra["ambiente_id"])})

        profissional_nome = df_prof.iloc[0]["nome"] if not df_prof.empty else "?"
        ambiente_nome = df_amb.iloc[0]["nome"] if not df_amb.empty else "?"

        nomes_dias = ["Segunda", "Terca", "Quarta", "Quinta", "Sexta", "Sabado", "Domingo"]
        dia_nome = nomes_dias[int(regra["dia_semana"])]

        hora_ini_str = str(regra["hora_inicio"])[:5]
        hora_fim_str = str(regra["hora_fim"])[:5]

        if isinstance(regra["data_inicio"], str):
            data_inicio_obj = dt.date.fromisoformat(regra["data_inicio"])
        else:
            data_inicio_obj = regra["data_inicio"]

        st.markdown(f"**Profissional:** {profissional_nome}")
        st.markdown(f"**Ambiente:** {ambiente_nome}")
        st.markdown(f"**Dia:** Toda {dia_nome.lower()}, {hora_ini_str} - {hora_fim_str}")
        st.markdown(f"**Vigente desde:** {data_inicio_obj.strftime('%d/%m/%Y')}")

        st.markdown("---")
        st.markdown("**A partir de qual data esta regra deixa de valer?**")

        data_clicada = dt.datetime.fromisoformat(
            data_clicada_iso.rstrip("Z").split(".")[0]
        ).date()

        data_encerrar = st.date_input(
            "Encerrar a partir de",
            value=data_clicada,
            format="DD/MM/YYYY",
            key=f"f5_form_enc_data_{regra_id}",
            help="A regra continuara aparecendo no calendario ate a vespera dessa data.",
        )

        erro = None
        if data_encerrar < data_inicio_obj:
            erro = (
                f"Data de encerramento ({data_encerrar.strftime('%d/%m/%Y')}) nao pode ser "
                f"anterior a data de inicio ({data_inicio_obj.strftime('%d/%m/%Y')})."
            )

        if erro:
            st.error(erro)
        else:
            vespera = data_encerrar - dt.timedelta(days=1)
            st.info(
                f"ℹ️ A regra continuara aparecendo no calendario ate **{vespera.strftime('%d/%m/%Y')}** "
                f"e desaparece a partir de {data_encerrar.strftime('%d/%m/%Y')}."
            )

        st.markdown("---")
        col_cancel, col_ok = st.columns([1, 1])

        with col_cancel:
            if st.button("Cancelar", key=f"f5_form_enc_cancel_{regra_id}", use_container_width=True):
                st.session_state.pop("f5_acao_pendente", None)
                st.rerun()

        with col_ok:
            if st.button(
                "⏹️ Encerrar regra",
                key=f"f5_form_enc_ok_{regra_id}",
                type="primary",
                use_container_width=True,
                disabled=(erro is not None),
            ):
                with st.spinner("Encerrando regra..."):
                    sucesso = _encerrar_regra(
                        regra_id=regra_id,
                        data_encerrar=data_encerrar,
                        data_inicio_regra=data_inicio_obj,
                    )
                if sucesso:
                    vespera = data_encerrar - dt.timedelta(days=1)
                    if data_encerrar <= dt.date.today() and data_inicio_obj == data_encerrar:
                        msg = "Regra removida (cadastrada hoje, sem historico)."
                    else:
                        msg = f"Regra encerrada (vigente ate {vespera.strftime('%d/%m/%Y')})"
                    st.session_state["f5_msg_sucesso"] = msg
                    st.session_state.pop("f5_acao_pendente", None)
                    st.rerun()


def _renderizar_form_editar_regra(acao):
    """Form inline de edicao de regra existente.

    Permite mudar dia_semana e horario. Profissional/ambiente nao editaveis.

    Logica de aplicacao da edicao (preserva historico):
    - data_aplicar > data_inicio_original: encerra antiga + cria nova
    - data_aplicar == data_inicio_original: UPDATE direto (sem historico pra preservar)
    - data_aplicar < data_inicio_original: erro, bloqueia
    """
    regra_id = acao["regra_id"]
    data_clicada_iso = acao["data_clicada_iso"]

    df_regra = buscar_dados("agenda_regras", eq={"id": regra_id})

    st.markdown("##### ✏️ Editar atividade")

    with st.container(border=True):
        if df_regra.empty:
            st.error("Regra nao encontrada (pode ter sido removida em outra aba).")
            if st.button("Fechar", key=f"f5_form_edit_close_{regra_id}"):
                st.session_state.pop("f5_acao_pendente", None)
                st.rerun()
            return

        regra = df_regra.iloc[0]

        df_prof = buscar_dados("profissionais", eq={"id": int(regra["profissional_id"])})
        df_amb = buscar_dados("ambientes", eq={"id": int(regra["ambiente_id"])})

        profissional_nome = df_prof.iloc[0]["nome"] if not df_prof.empty else "?"
        ambiente_nome = df_amb.iloc[0]["nome"] if not df_amb.empty else "?"

        nomes_dias = ["Segunda", "Terca", "Quarta", "Quinta", "Sexta", "Sabado", "Domingo"]
        dia_atual = int(regra["dia_semana"])

        hora_ini_atual_str = str(regra["hora_inicio"])[:5]
        hora_fim_atual_str = str(regra["hora_fim"])[:5]

        if isinstance(regra["data_inicio"], str):
            data_inicio_obj = dt.date.fromisoformat(regra["data_inicio"])
        else:
            data_inicio_obj = regra["data_inicio"]

        # Resumo (nao editavel)
        st.markdown(f"**Profissional:** {profissional_nome}")
        st.markdown(f"**Ambiente:** {ambiente_nome}")
        st.caption(
            f"Atual: {nomes_dias[dia_atual]}, {hora_ini_atual_str} - {hora_fim_atual_str}, "
            f"vigente desde {data_inicio_obj.strftime('%d/%m/%Y')}"
        )

        st.markdown("---")
        st.markdown("**Novos valores**")

        # Dia da semana editavel
        dia_novo_nome = st.selectbox(
            "Dia da semana",
            options=nomes_dias,
            index=dia_atual,
            key=f"f5_form_edit_dia_{regra_id}",
        )
        dia_novo = nomes_dias.index(dia_novo_nome)

        # Horario editavel
        col_hi, col_hf = st.columns(2)
        with col_hi:
            hora_inicio_t = st.time_input(
                "Hora inicio",
                value=dt.datetime.strptime(hora_ini_atual_str, "%H:%M").time(),
                step=dt.timedelta(minutes=30),
                key=f"f5_form_edit_hi_{regra_id}",
            )
        with col_hf:
            hora_fim_t = st.time_input(
                "Hora fim",
                value=dt.datetime.strptime(hora_fim_atual_str, "%H:%M").time(),
                step=dt.timedelta(minutes=30),
                key=f"f5_form_edit_hf_{regra_id}",
            )

        st.markdown("---")
        st.markdown("**A partir de qual data esta edicao se aplica?**")

        data_clicada = dt.datetime.fromisoformat(
            data_clicada_iso.rstrip("Z").split(".")[0]
        ).date()

        data_aplicar = st.date_input(
            "Aplicar a partir de",
            value=data_clicada,
            format="DD/MM/YYYY",
            key=f"f5_form_edit_data_{regra_id}",
            help=(
                "Use 'hoje' pra mudancas imediatas. "
                "Use uma data futura pra agendar a mudanca pra mais tarde. "
                "A regra original continua valida ate a vespera dessa data."
            ),
        )

        # Validacoes
        erro = None
        if hora_fim_t <= hora_inicio_t:
            erro = "Hora fim deve ser maior que hora inicio."
        elif data_aplicar < data_inicio_obj:
            erro = (
                f"Data de aplicacao ({data_aplicar.strftime('%d/%m/%Y')}) nao pode "
                f"ser anterior ao inicio da regra ({data_inicio_obj.strftime('%d/%m/%Y')})."
            )

        # Verifica se houve mudanca de fato
        hora_inicio_nova_str = hora_inicio_t.strftime("%H:%M")
        hora_fim_nova_str = hora_fim_t.strftime("%H:%M")
        sem_mudanca = (
            dia_novo == dia_atual
            and hora_inicio_nova_str == hora_ini_atual_str
            and hora_fim_nova_str == hora_fim_atual_str
        )

        if erro:
            st.error(erro)
        elif sem_mudanca:
            st.info("ℹ️ Nenhuma alteracao detectada. Ajuste algum campo pra editar.")
        else:
            # Mostra preview do que vai acontecer
            if data_aplicar == data_inicio_obj:
                st.info(
                    f"📅 Esta edicao **substituira** a regra atual completamente "
                    f"(sem historico — a regra ja comecava em {data_inicio_obj.strftime('%d/%m/%Y')})."
                )
            else:
                vespera = data_aplicar - dt.timedelta(days=1)
                st.info(
                    f"📅 A regra atual sera **encerrada em {vespera.strftime('%d/%m/%Y')}** "
                    f"e uma nova regra com os novos valores comecara em "
                    f"**{data_aplicar.strftime('%d/%m/%Y')}**."
                )

        st.markdown("---")
        col_cancel, col_ok = st.columns([1, 1])

        with col_cancel:
            if st.button("Cancelar", key=f"f5_form_edit_cancel_{regra_id}", use_container_width=True):
                st.session_state.pop("f5_acao_pendente", None)
                st.rerun()

        with col_ok:
            if st.button(
                "✏️ Confirmar edicao",
                key=f"f5_form_edit_ok_{regra_id}",
                type="primary",
                use_container_width=True,
                disabled=(erro is not None) or sem_mudanca,
            ):
                with st.spinner("Editando regra..."):
                    sucesso = _editar_regra(
                        regra_id=regra_id,
                        regra_original=regra,
                        dia_novo=dia_novo,
                        hora_inicio_nova=hora_inicio_nova_str,
                        hora_fim_nova=hora_fim_nova_str,
                        data_aplicar=data_aplicar,
                        data_inicio_original=data_inicio_obj,
                    )
                if sucesso:
                    if data_aplicar == data_inicio_obj:
                        msg = "Regra editada (substituicao direta)."
                    else:
                        msg = (
                            f"Regra editada (antiga vigente ate "
                            f"{(data_aplicar - dt.timedelta(days=1)).strftime('%d/%m/%Y')}, "
                            f"nova a partir de {data_aplicar.strftime('%d/%m/%Y')})."
                        )
                    st.session_state["f5_msg_sucesso"] = msg
                    st.session_state.pop("f5_acao_pendente", None)
                    st.rerun()


def _editar_regra(regra_id, regra_original, dia_novo, hora_inicio_nova, hora_fim_nova, data_aplicar, data_inicio_original):
    """Aplica edicao de regra com 2 caminhos:

    1. data_aplicar == data_inicio_original: UPDATE direto (sem historico)
    2. data_aplicar > data_inicio_original: encerra antiga + cria nova

    Retorna True se nao houve excecao.
    """
    try:
        if data_aplicar == data_inicio_original:
            # UPDATE direto na regra original
            atualizar_dados(
                "agenda_regras",
                {
                    "dia_semana": int(dia_novo),
                    "hora_inicio": hora_inicio_nova,
                    "hora_fim": hora_fim_nova,
                },
                "id",
                regra_id,
            )
        else:
            # Encerra antiga + cria nova
            vespera_iso = (data_aplicar - dt.timedelta(days=1)).isoformat()
            atualizar_dados(
                "agenda_regras",
                {"data_fim": vespera_iso},
                "id",
                regra_id,
            )
            inserir_dados(
                "agenda_regras",
                {
                    "profissional_id": int(regra_original["profissional_id"]),
                    "ambiente_id": int(regra_original["ambiente_id"]),
                    "dia_semana": int(dia_novo),
                    "hora_inicio": hora_inicio_nova,
                    "hora_fim": hora_fim_nova,
                    "data_inicio": data_aplicar.isoformat(),
                    "data_fim": None,
                    "ativo": True,
                },
            )
        return True
    except Exception as e:
        st.error(f"Erro ao editar regra: {type(e).__name__} — {e}")
        return False


def _renderizar_form_regra_historica():
    """Form inline de cadastro de regra historica (dentro do expander).

    Renderizado quando `f5_hist_aberto` em session_state e True.
    Mesmo conteudo do antigo @st.dialog, mas inline no expander.
    """
    df_prof = buscar_dados("profissionais", eq={"ativo": True})
    df_amb = buscar_dados("ambientes", eq={"ativo": True})

    if df_prof.empty:
        st.warning("Nenhum profissional ativo cadastrado. Cadastre em Configuracoes > Professores antes.")
        if st.button("Fechar", key="f5_hist_close_no_prof"):
            st.session_state.pop("f5_hist_aberto", None)
            st.rerun()
        return

    if df_amb.empty:
        st.warning("Nenhum ambiente ativo cadastrado. Cadastre em Configuracoes > Ambientes antes.")
        if st.button("Fechar", key="f5_hist_close_no_amb"):
            st.session_state.pop("f5_hist_aberto", None)
            st.rerun()
        return

    profissionais_dict = {row["nome"]: row["id"] for _, row in df_prof.iterrows()}
    profissional_nome = st.selectbox(
        "Profissional",
        options=list(profissionais_dict.keys()),
        key="f5_hist_prof",
    )
    profissional_id = profissionais_dict[profissional_nome]

    ambientes_dict = {row["nome"]: row["id"] for _, row in df_amb.iterrows()}
    ambiente_nome = st.selectbox(
        "Ambiente",
        options=list(ambientes_dict.keys()),
        key="f5_hist_amb",
    )
    ambiente_id = ambientes_dict[ambiente_nome]

    nomes_dias = ["Segunda", "Terca", "Quarta", "Quinta", "Sexta", "Sabado", "Domingo"]
    dia_nome = st.selectbox(
        "Dia da semana",
        options=nomes_dias,
        key="f5_hist_dia",
    )
    dia_semana = nomes_dias.index(dia_nome)

    col_hi, col_hf = st.columns(2)
    with col_hi:
        hora_inicio_t = st.time_input(
            "Hora inicio",
            value=dt.time(18, 0),
            step=dt.timedelta(minutes=30),
            key="f5_hist_hi",
        )
    with col_hf:
        hora_fim_t = st.time_input(
            "Hora fim",
            value=dt.time(19, 0),
            step=dt.timedelta(minutes=30),
            key="f5_hist_hf",
        )

    st.markdown("---")
    st.markdown("**Periodo de vigencia**")

    col_di, col_df = st.columns(2)
    with col_di:
        data_inicio = st.date_input(
            "De",
            value=dt.date.today() - dt.timedelta(days=120),
            format="DD/MM/YYYY",
            key="f5_hist_di",
        )
    with col_df:
        data_fim = st.date_input(
            "Ate",
            value=dt.date.today(),
            format="DD/MM/YYYY",
            key="f5_hist_df",
        )

    em_andamento = st.checkbox(
        "Aula ainda em andamento (sem data fim)",
        value=False,
        key="f5_hist_andamento",
        help="Se marcado, a regra nao tem data fim — continua aparecendo no calendario indefinidamente.",
    )

    erro = None
    if hora_fim_t <= hora_inicio_t:
        erro = "Hora fim deve ser maior que hora inicio."
    elif not em_andamento and data_fim < data_inicio:
        erro = "Data 'Ate' deve ser maior ou igual a data 'De'."

    if erro:
        st.error(erro)

    st.markdown("---")
    col_cancel, col_ok = st.columns([1, 1])

    with col_cancel:
        if st.button("Cancelar", key="f5_hist_cancel", use_container_width=True):
            st.session_state.pop("f5_hist_aberto", None)
            st.rerun()

    with col_ok:
        if st.button(
            "✅ Cadastrar regra historica",
            key="f5_hist_ok",
            type="primary",
            use_container_width=True,
            disabled=(erro is not None),
        ):
            data_fim_param = None if em_andamento else data_fim
            with st.spinner("Cadastrando regra historica..."):
                sucesso = _inserir_regra(
                    profissional_id=profissional_id,
                    ambiente_id=ambiente_id,
                    dia_semana=dia_semana,
                    hora_inicio=hora_inicio_t.strftime("%H:%M"),
                    hora_fim=hora_fim_t.strftime("%H:%M"),
                    data_inicio=data_inicio,
                    data_fim=data_fim_param,
                )
            if sucesso:
                if em_andamento:
                    msg = f"Regra historica cadastrada (a partir de {data_inicio.strftime('%d/%m/%Y')}, em andamento)"
                else:
                    msg = (
                        f"Regra historica cadastrada "
                        f"({data_inicio.strftime('%d/%m/%Y')} a "
                        f"{data_fim.strftime('%d/%m/%Y')})"
                    )
                st.session_state["f5_msg_sucesso"] = msg
                st.session_state.pop("f5_hist_aberto", None)
                st.rerun()
