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

import pandas as pd
import streamlit as st

from db import buscar_dados, inserir_dados, atualizar_dados


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
    """Aba 1 - Calendario (placeholder ate F.4)."""
    st.info(
        "Calendario em construcao (Etapa F.4).\n\n"
        "Quando estiver pronto, aqui sera possivel registrar as atividades "
        "(aulas, treinos) diretamente no calendario, alem de visualizar o "
        "uso da academia em formato mensal ou semanal."
    )


def _render_aba_analise():
    """Aba 2 - Analise de Uso (placeholder ate F.7)."""
    st.info(
        "Analise de Uso em construcao (Etapa F.7).\n\n"
        "Esta aba mostrara graficos de ocupacao por profissional, por ambiente, "
        "heatmap de horarios mais cheios e KPIs de uso da academia."
    )


def _render_aba_funcionamento():
    """Aba 3 - Horario de Funcionamento (placeholder ate F.3)."""
    st.info(
        "Cadastro de Horario de Funcionamento em construcao (Etapa F.3).\n\n"
        "Aqui sera possivel cadastrar, editar e remover os blocos de horario "
        "em que a academia esta aberta para cada dia da semana "
        "(ex: segunda 06h-09h e 17h-22h)."
    )


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
