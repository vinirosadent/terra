"""
Modulo: paginas/configuracoes.py
Responsabilidade: pagina "Configuracoes" - cadastros base do sistema.

Status: ativo (reescrito na Etapa H.2.1 — unificacao de cadastros).

Para usar:
    from paginas import configuracoes as pg_configuracoes
    elif menu == "⚙️ Configurações":
        pg_configuracoes.render()

Sub-abas:
    1. Modalidades       - servicos da academia (Academia, Personal, Calistenia, Kids, ...).
                           Tem cor (mostrada no calendario), professor e local associados.
    2. Tipos             - variacoes de preco dentro de uma modalidade
                           (ex: Academia Regular R$ 295, Academia Premium R$ 350).
    3. Professores       - cadastro base de profissionais (movido do Calendario na H.2).
    4. Locais            - cadastro base de espacos fisicos (movido do Calendario na H.2,
                           antes chamado de "Ambientes").
    5. Centros de Custo  - categorias de saida (Fixo / Variavel).
    6. Impostos / Taxas  - aliquotas aplicaveis.

Notas importantes:
- A tabela `atividades_entrada` (servicos antigos com Academia Regular 295 etc) continua
  existindo no banco mas NAO e mais editavel pela UI. Sera limpa no Reset da Etapa H.4.
- Modalidades exigem professor obrigatorio. Schema permite NULL (ON DELETE SET NULL),
  mas a UI obriga selecao pra evitar dados orfaos.
- Local "Nao usa espaco" grava ambiente_id=NULL no banco. Isso e usado pelo F.7
  (Analise de Uso) pra distinguir receita do espaco fisico vs receita extra-espaco.
"""

import streamlit as st
import pandas as pd

from db import buscar_dados, inserir_dados, atualizar_dados, deletar_dados
from utils import resetar_form


# ============================================================================
# Constantes
# ============================================================================

# Paleta fixa de 12 cores (mesma usada na sub-aba Professores migrada do Calendario).
# Em Modalidades, cores PODEM se repetir (sem aviso de "em uso"), pois a relacao
# 1 modalidade = 1 cor unica nao e regra dura.
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
# Usado na sub-aba Professores.
TIPOS_PROFESSOR = {
    "treino": "Treino",
    "calistenia": "Calistenia",
    "kids": "Kids",
    "outro": "Outro",
}

# Label especial pro dropdown de Local em Modalidades.
# Quando selecionado, grava ambiente_id=NULL no banco.
OPCAO_NAO_USA_ESPACO = "Nao usa espaco"


# ============================================================================
# Entry point
# ============================================================================

def render():
    """Ponto de entrada da pagina Configuracoes."""
    fk = st.session_state.form_key

    st.title("⚙️ Cadastros e Configurações")

    aba_config = st.radio(
        "Selecione a Configuração:",
        [
            "Modalidades",
            "Tipos",
            "Professores",
            "Locais",
            "Centros de Custo",
            "Impostos / Taxas",
        ],
        horizontal=True,
        key=f"rad_conf_{fk}",
    )
    st.markdown("---")

    if aba_config == "Modalidades":
        _render_sub_modalidades()
    elif aba_config == "Tipos":
        _render_sub_tipos()
    elif aba_config == "Professores":
        _render_sub_professores()
    elif aba_config == "Locais":
        _render_sub_locais()
    elif aba_config == "Centros de Custo":
        _render_sub_centros_custo()
    elif aba_config == "Impostos / Taxas":
        _render_sub_impostos()


# ============================================================================
# SUB-ABA: Modalidades
# ============================================================================

def _render_sub_modalidades():
    """Sub-aba Modalidades: cadastro dos servicos da academia."""
    st.markdown("### Modalidades cadastradas")
    st.caption(
        "Cadastre os servicos que a academia oferece. Cada modalidade tem cor "
        "(usada no calendario), professor associado e local. Os tipos com seus "
        "precos sao cadastrados na sub-aba **Tipos**."
    )

    df_m = buscar_dados("modalidades", order="id")
    df_p_todos = buscar_dados("profissionais")
    df_a_todos = buscar_dados("ambientes")

    if df_m.empty:
        df_m = pd.DataFrame(columns=[
            "id", "nome", "cor_hex", "professor_id", "ambiente_id",
            "ativo", "created_at",
        ])

    # Listagem
    if df_m.empty:
        st.info("Nenhuma modalidade cadastrada ainda. Use o formulario abaixo pra cadastrar a primeira.")
    else:
        st.markdown(_renderizar_tabela_modalidades(df_m, df_p_todos, df_a_todos), unsafe_allow_html=True)

    st.markdown("---")

    # Formulario de cadastrar
    with st.expander("Cadastrar nova modalidade", expanded=df_m.empty):
        _form_adicionar_modalidade(df_m, df_p_todos, df_a_todos)

    if df_m.empty:
        return

    # Formulario de editar / inativar / reativar
    with st.expander("Editar / Inativar / Reativar modalidade"):
        _form_editar_modalidade(df_m, df_p_todos, df_a_todos)


def _form_adicionar_modalidade(df_m, df_p_todos, df_a_todos):
    """Form de cadastrar nova modalidade."""
    fk = st.session_state.form_key

    # So profissionais ATIVOS aparecem no dropdown
    df_p_ativos = df_p_todos[df_p_todos["ativo"]] if not df_p_todos.empty else pd.DataFrame()

    if df_p_ativos.empty:
        st.warning(
            "⚠️ Nenhum professor ativo cadastrado. "
            "Cadastre pelo menos um professor antes de criar modalidades."
        )
        return

    # So ambientes ATIVOS aparecem no dropdown (mais "Nao usa espaco")
    df_a_ativos = df_a_todos[df_a_todos["ativo"]] if not df_a_todos.empty else pd.DataFrame()

    with st.form(f"form_add_modalidade_{fk}", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            novo_nome = st.text_input(
                "Nome da modalidade",
                max_chars=80,
                placeholder="Ex: Academia, Personal, Calistenia",
                key=f"mod_add_nome_{fk}",
            )

            # Professor (obrigatorio)
            profs_dict = {row["nome"]: int(row["id"]) for _, row in df_p_ativos.iterrows()}
            novo_prof_nome = st.selectbox(
                "Professor",
                options=list(profs_dict.keys()),
                key=f"mod_add_prof_{fk}",
            )
            novo_prof_id = profs_dict[novo_prof_nome]

            # Local: 3 opcoes (Em cima, Embaixo, Nao usa espaco)
            opcoes_local = []
            for _, row in df_a_ativos.iterrows():
                opcoes_local.append(row["nome"])
            opcoes_local.append(OPCAO_NAO_USA_ESPACO)

            novo_local = st.radio(
                "Local",
                options=opcoes_local,
                horizontal=True,
                key=f"mod_add_local_{fk}",
            )

        with col2:
            opcoes_cores = [c["hex"] for c in PALETA_CORES]

            st.markdown("**Cor de identificacao**")
            st.markdown(_renderizar_paleta(cores_em_uso=set()), unsafe_allow_html=True)

            nova_cor = st.selectbox(
                "Selecione a cor",
                options=opcoes_cores,
                format_func=lambda hexcode: _formatar_cor(hexcode, cores_em_uso=set()),
                label_visibility="collapsed",
                key=f"mod_add_cor_{fk}",
            )

            st.markdown(_renderizar_amostra_cor(nova_cor), unsafe_allow_html=True)

        submitted = st.form_submit_button(
            "Cadastrar modalidade",
            use_container_width=True,
            type="primary",
        )

        if submitted:
            erro = _validar_modalidade(novo_nome, df_m, modalidade_id_editando=None)
            if erro:
                st.error(erro)
            else:
                # Resolve ambiente_id a partir do label de Local
                if novo_local == OPCAO_NAO_USA_ESPACO:
                    novo_amb_id = None
                else:
                    novo_amb_id = int(df_a_ativos[df_a_ativos["nome"] == novo_local]["id"].iloc[0])

                try:
                    inserir_dados("modalidades", {
                        "nome": novo_nome.strip(),
                        "cor_hex": nova_cor,
                        "professor_id": novo_prof_id,
                        "ambiente_id": novo_amb_id,
                        "ativo": True,
                    })
                    st.session_state.sucesso_msg = f"Modalidade '{novo_nome.strip()}' cadastrada com sucesso!"
                    resetar_form()
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao cadastrar modalidade: {e}")


def _form_editar_modalidade(df_m, df_p_todos, df_a_todos):
    """Form de editar / inativar / reativar modalidade existente."""
    fk = st.session_state.form_key

    df_p_ativos = df_p_todos[df_p_todos["ativo"]] if not df_p_todos.empty else pd.DataFrame()
    df_a_ativos = df_a_todos[df_a_todos["ativo"]] if not df_a_todos.empty else pd.DataFrame()

    df_sel = df_m.copy()
    df_sel["label"] = df_sel.apply(
        lambda r: f"{r['nome']} - {'Ativo' if r['ativo'] else 'Inativo'}",
        axis=1,
    )
    opcoes_ids = df_sel["id"].tolist()
    mod_id_sel = st.selectbox(
        "Selecione uma modalidade",
        options=opcoes_ids,
        format_func=lambda mid: df_sel.loc[df_sel["id"] == mid, "label"].values[0],
        key=f"mod_ed_sel_{fk}",
    )
    mod_atual = df_sel.loc[df_sel["id"] == mod_id_sel].iloc[0]

    with st.form(f"form_edit_modalidade_{mod_id_sel}_{fk}"):
        col1, col2 = st.columns(2)

        with col1:
            nome_edit = st.text_input(
                "Nome da modalidade",
                value=mod_atual["nome"],
                max_chars=80,
                key=f"mod_ed_nome_{mod_id_sel}_{fk}",
            )

            # Professor: lista ATIVOS + o atual (mesmo se inativo, pra nao zerar
            # o campo se o professor ficou inativo apos cadastro da modalidade)
            profs_disponiveis = df_p_ativos.copy()
            prof_atual_id = mod_atual.get("professor_id")
            if pd.notna(prof_atual_id) and not df_p_todos.empty:
                prof_atual_row = df_p_todos[df_p_todos["id"] == int(prof_atual_id)]
                if not prof_atual_row.empty and not prof_atual_row.iloc[0]["ativo"]:
                    # Adiciona o professor atual (inativo) na lista
                    profs_disponiveis = pd.concat(
                        [profs_disponiveis, prof_atual_row], ignore_index=True
                    )

            if profs_disponiveis.empty:
                st.warning("Nenhum professor disponivel.")
                profs_dict = {}
                idx_prof = 0
            else:
                profs_dict = {row["nome"]: int(row["id"]) for _, row in profs_disponiveis.iterrows()}
                if pd.notna(prof_atual_id) and int(prof_atual_id) in profs_dict.values():
                    nome_atual = [k for k, v in profs_dict.items() if v == int(prof_atual_id)][0]
                    idx_prof = list(profs_dict.keys()).index(nome_atual)
                else:
                    idx_prof = 0

            prof_edit_nome = st.selectbox(
                "Professor",
                options=list(profs_dict.keys()) if profs_dict else ["(nenhum)"],
                index=idx_prof,
                key=f"mod_ed_prof_{mod_id_sel}_{fk}",
            )
            prof_edit_id = profs_dict.get(prof_edit_nome) if profs_dict else None

            # Local: ambientes ATIVOS + "Nao usa espaco" + ambiente atual se inativo
            opcoes_local = []
            for _, row in df_a_ativos.iterrows():
                opcoes_local.append(row["nome"])
            opcoes_local.append(OPCAO_NAO_USA_ESPACO)

            amb_atual_id = mod_atual.get("ambiente_id")
            if pd.notna(amb_atual_id) and not df_a_todos.empty:
                amb_atual_row = df_a_todos[df_a_todos["id"] == int(amb_atual_id)]
                if not amb_atual_row.empty and not amb_atual_row.iloc[0]["ativo"]:
                    nome_amb_inativo = amb_atual_row.iloc[0]["nome"]
                    if nome_amb_inativo not in opcoes_local:
                        opcoes_local.insert(-1, nome_amb_inativo)

            if pd.isna(amb_atual_id):
                local_default = OPCAO_NAO_USA_ESPACO
            else:
                amb_row = df_a_todos[df_a_todos["id"] == int(amb_atual_id)]
                local_default = amb_row.iloc[0]["nome"] if not amb_row.empty else OPCAO_NAO_USA_ESPACO

            idx_local = opcoes_local.index(local_default) if local_default in opcoes_local else 0

            local_edit = st.radio(
                "Local",
                options=opcoes_local,
                index=idx_local,
                horizontal=True,
                key=f"mod_ed_local_{mod_id_sel}_{fk}",
            )

        with col2:
            opcoes_cores = [c["hex"] for c in PALETA_CORES]
            idx_cor_atual = opcoes_cores.index(mod_atual["cor_hex"]) if mod_atual["cor_hex"] in opcoes_cores else 0

            st.markdown("**Cor de identificacao**")
            st.markdown(_renderizar_paleta(cores_em_uso=set()), unsafe_allow_html=True)

            cor_edit = st.selectbox(
                "Selecione a cor",
                options=opcoes_cores,
                index=idx_cor_atual,
                format_func=lambda hexcode: _formatar_cor(hexcode, cores_em_uso=set()),
                label_visibility="collapsed",
                key=f"mod_ed_cor_{mod_id_sel}_{fk}",
            )

            st.markdown(_renderizar_amostra_cor(cor_edit), unsafe_allow_html=True)

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            btn_salvar = st.form_submit_button("Salvar alteracoes", use_container_width=True, type="primary")
        with col_btn2:
            if mod_atual["ativo"]:
                btn_toggle = st.form_submit_button("Inativar", use_container_width=True)
            else:
                btn_toggle = st.form_submit_button("Reativar", use_container_width=True)

        if btn_salvar:
            erro = _validar_modalidade(nome_edit, df_m, modalidade_id_editando=int(mod_id_sel))
            if erro:
                st.error(erro)
            elif prof_edit_id is None:
                st.error("Selecione um professor valido.")
            else:
                # Resolve ambiente_id a partir do label de Local
                if local_edit == OPCAO_NAO_USA_ESPACO:
                    amb_edit_id = None
                else:
                    amb_row = df_a_todos[df_a_todos["nome"] == local_edit]
                    amb_edit_id = int(amb_row["id"].iloc[0]) if not amb_row.empty else None

                try:
                    atualizar_dados("modalidades", {
                        "nome": nome_edit.strip(),
                        "cor_hex": cor_edit,
                        "professor_id": prof_edit_id,
                        "ambiente_id": amb_edit_id,
                    }, "id", int(mod_id_sel))
                    st.session_state.sucesso_msg = "Modalidade atualizada com sucesso!"
                    resetar_form()
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")

        if btn_toggle:
            try:
                novo_status = not bool(mod_atual["ativo"])
                atualizar_dados("modalidades", {"ativo": novo_status}, "id", int(mod_id_sel))
                msg = "Modalidade reativada." if novo_status else "Modalidade inativada."
                st.session_state.sucesso_msg = msg
                resetar_form()
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao alterar status: {e}")


def _validar_modalidade(nome, df_existente, modalidade_id_editando=None):
    """Valida nome da modalidade. Retorna mensagem de erro ou None se OK."""
    if not nome or not nome.strip():
        return "O nome da modalidade nao pode ficar vazio."
    nome_limpo = nome.strip()
    if len(nome_limpo) < 2:
        return "O nome da modalidade precisa ter pelo menos 2 caracteres."
    df_check = df_existente.copy()
    if modalidade_id_editando is not None:
        df_check = df_check[df_check["id"] != modalidade_id_editando]
    if not df_check.empty:
        nomes_existentes = df_check["nome"].astype(str).str.strip().str.lower().tolist()
        if nome_limpo.lower() in nomes_existentes:
            return f"Ja existe uma modalidade com o nome '{nome_limpo}'."
    return None


def _renderizar_tabela_modalidades(df_m, df_p_todos, df_a_todos):
    """Renderiza tabela HTML estilizada de modalidades.

    Inclui style inline com classe `tabela-modalidades` para sobrescrever
    a regra CSS global do app que esconde th:first-child em tabelas
    (necessaria pra st.dataframe em outras paginas).
    """
    style_override = (
        '<style>'
        '.tabela-modalidades thead tr th:first-child { display: table-cell !important; }'
        '.tabela-modalidades tbody th { display: none; }'
        '</style>'
    )

    cabecalho = (
        '<tr style="background-color:#f8f9fa;border-bottom:2px solid #dee2e6;">'
        '<th style="padding:10px 12px;text-align:left;font-weight:600;">ID</th>'
        '<th style="padding:10px 12px;text-align:left;font-weight:600;">Nome</th>'
        '<th style="padding:10px 12px;text-align:left;font-weight:600;">Cor</th>'
        '<th style="padding:10px 12px;text-align:left;font-weight:600;">Professor</th>'
        '<th style="padding:10px 12px;text-align:left;font-weight:600;">Local</th>'
        '<th style="padding:10px 12px;text-align:left;font-weight:600;">Status</th>'
        '</tr>'
    )

    linhas_html = []
    for _, row in df_m.iterrows():
        # Cor: bolinha + nome
        cor_hex = row.get("cor_hex", "#888888")
        cor_nome = next((c["nome"] for c in PALETA_CORES if c["hex"] == cor_hex), cor_hex)
        bolinha = (
            f'<span style="display:inline-block;width:18px;height:18px;'
            f'border-radius:50%;background-color:{cor_hex};'
            f'border:1px solid #ccc;vertical-align:middle;margin-right:8px;"></span>'
        )
        cor_celula = f'{bolinha}<span style="vertical-align:middle;">{cor_nome}</span>'

        # Professor: lookup
        prof_id = row.get("professor_id")
        if pd.notna(prof_id) and not df_p_todos.empty:
            prof_row = df_p_todos[df_p_todos["id"] == int(prof_id)]
            prof_nome = prof_row.iloc[0]["nome"] if not prof_row.empty else "?"
        else:
            prof_nome = "—"

        # Local: lookup ou "Nao usa espaco"
        amb_id = row.get("ambiente_id")
        if pd.notna(amb_id) and not df_a_todos.empty:
            amb_row = df_a_todos[df_a_todos["id"] == int(amb_id)]
            local_label = amb_row.iloc[0]["nome"] if not amb_row.empty else "?"
        else:
            local_label = "Nao usa espaco"

        # Status
        status_label = "Ativo" if row["ativo"] else "Inativo"
        cor_status = "#2E7D32" if row["ativo"] else "#9e9e9e"
        status_celula = f'<span style="color:{cor_status};font-weight:500;">{status_label}</span>'

        linhas_html.append(
            f'<tr style="border-bottom:1px solid #f0f0f0;">'
            f'<td style="padding:8px 12px;">{row["id"]}</td>'
            f'<td style="padding:8px 12px;">{row["nome"]}</td>'
            f'<td style="padding:8px 12px;">{cor_celula}</td>'
            f'<td style="padding:8px 12px;">{prof_nome}</td>'
            f'<td style="padding:8px 12px;">{local_label}</td>'
            f'<td style="padding:8px 12px;">{status_celula}</td>'
            f'</tr>'
        )

    tabela = (
        '<table class="tabela-modalidades" '
        'style="width:100%;border-collapse:collapse;border:1px solid #dee2e6;'
        'border-radius:8px;overflow:hidden;font-family:inherit;font-size:14px;">'
        f'<thead>{cabecalho}</thead>'
        f'<tbody>{"".join(linhas_html)}</tbody>'
        '</table>'
    )

    return style_override + tabela


# ============================================================================
# SUB-ABA: Tipos
# ============================================================================

def _render_sub_tipos():
    """Sub-aba Tipos: cadastro de variacoes de preco por modalidade."""
    fk = st.session_state.form_key

    st.markdown("### Tipos cadastrados")
    st.caption(
        "Tipos sao variacoes de preco dentro de uma modalidade. Selecione "
        "primeiro a modalidade abaixo, depois cadastre os tipos com seus valores."
    )

    df_m_todos = buscar_dados("modalidades", order="nome")
    df_m_ativas = df_m_todos[df_m_todos["ativo"]] if not df_m_todos.empty else pd.DataFrame()

    if df_m_ativas.empty:
        st.warning(
            "⚠️ Nenhuma modalidade ativa cadastrada. "
            "Va na sub-aba **Modalidades** e cadastre pelo menos uma antes."
        )
        return

    # Filtro de modalidade no topo
    mods_dict = {row["nome"]: int(row["id"]) for _, row in df_m_ativas.iterrows()}
    mod_nome_sel = st.selectbox(
        "Modalidade",
        options=list(mods_dict.keys()),
        key=f"tipo_mod_filtro_{fk}",
    )
    mod_id_sel = mods_dict[mod_nome_sel]

    st.markdown("---")

    # Listagem de tipos da modalidade selecionada
    df_t_todos = buscar_dados("planos", eq={"modalidade_id": mod_id_sel}, order="id")

    if df_t_todos.empty:
        df_t_todos = pd.DataFrame(columns=[
            "id", "modalidade_id", "nome", "valor_padrao", "ativo", "created_at",
        ])

    st.markdown(f"#### Tipos de **{mod_nome_sel}**")

    if df_t_todos.empty:
        st.info(f"Nenhum tipo cadastrado para {mod_nome_sel}. Use o formulario abaixo.")
    else:
        st.markdown(_renderizar_tabela_tipos(df_t_todos), unsafe_allow_html=True)

    st.markdown("---")

    # Formulario de cadastrar
    with st.expander("Cadastrar novo tipo", expanded=df_t_todos.empty):
        _form_adicionar_tipo(mod_id_sel, mod_nome_sel, df_t_todos)

    if df_t_todos.empty:
        return

    # Formulario de editar / inativar / reativar
    with st.expander("Editar / Inativar / Reativar tipo"):
        _form_editar_tipo(mod_id_sel, mod_nome_sel, df_t_todos)


def _form_adicionar_tipo(modalidade_id, modalidade_nome, df_t):
    """Form de cadastrar novo tipo dentro de uma modalidade."""
    fk = st.session_state.form_key

    with st.form(f"form_add_tipo_{modalidade_id}_{fk}", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            novo_nome = st.text_input(
                "Nome do tipo",
                max_chars=80,
                placeholder="Ex: Regular, 2x semana, Premium",
                key=f"tipo_add_nome_{modalidade_id}_{fk}",
            )

        with col2:
            novo_valor = st.number_input(
                "Valor (R$)",
                min_value=0.01,
                max_value=99999.99,
                value=None,
                step=10.0,
                format="%.2f",
                key=f"tipo_add_valor_{modalidade_id}_{fk}",
            )

        submitted = st.form_submit_button(
            f"Cadastrar tipo em {modalidade_nome}",
            use_container_width=True,
            type="primary",
        )

        if submitted:
            erro = _validar_tipo(novo_nome, modalidade_id, df_t, tipo_id_editando=None)
            if erro:
                st.error(erro)
            elif novo_valor is None or novo_valor <= 0:
                st.error("O valor deve ser maior que zero.")
            else:
                try:
                    inserir_dados("planos", {
                        "modalidade_id": int(modalidade_id),
                        "nome": novo_nome.strip(),
                        "valor_padrao": float(novo_valor),
                        "ativo": True,
                    })
                    st.session_state.sucesso_msg = f"Tipo '{novo_nome.strip()}' cadastrado em {modalidade_nome}!"
                    resetar_form()
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao cadastrar tipo: {e}")


def _form_editar_tipo(modalidade_id, modalidade_nome, df_t):
    """Form de editar / inativar / reativar tipo existente."""
    fk = st.session_state.form_key

    df_sel = df_t.copy()
    df_sel["label"] = df_sel.apply(
        lambda r: f"{r['nome']} - R$ {float(r['valor_padrao']):.2f} - {'Ativo' if r['ativo'] else 'Inativo'}",
        axis=1,
    )
    opcoes_ids = df_sel["id"].tolist()
    tipo_id_sel = st.selectbox(
        "Selecione um tipo",
        options=opcoes_ids,
        format_func=lambda tid: df_sel.loc[df_sel["id"] == tid, "label"].values[0],
        key=f"tipo_ed_sel_{modalidade_id}_{fk}",
    )
    tipo_atual = df_sel.loc[df_sel["id"] == tipo_id_sel].iloc[0]

    with st.form(f"form_edit_tipo_{tipo_id_sel}_{fk}"):
        col1, col2 = st.columns(2)

        with col1:
            nome_edit = st.text_input(
                "Nome do tipo",
                value=tipo_atual["nome"],
                max_chars=80,
                key=f"tipo_ed_nome_{tipo_id_sel}_{fk}",
            )

        with col2:
            valor_edit = st.number_input(
                "Valor (R$)",
                min_value=0.01,
                max_value=99999.99,
                value=float(tipo_atual["valor_padrao"]),
                step=10.0,
                format="%.2f",
                key=f"tipo_ed_valor_{tipo_id_sel}_{fk}",
            )

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            btn_salvar = st.form_submit_button("Salvar alteracoes", use_container_width=True, type="primary")
        with col_btn2:
            if tipo_atual["ativo"]:
                btn_toggle = st.form_submit_button("Inativar", use_container_width=True)
            else:
                btn_toggle = st.form_submit_button("Reativar", use_container_width=True)

        if btn_salvar:
            erro = _validar_tipo(nome_edit, modalidade_id, df_t, tipo_id_editando=int(tipo_id_sel))
            if erro:
                st.error(erro)
            elif valor_edit is None or valor_edit <= 0:
                st.error("O valor deve ser maior que zero.")
            else:
                try:
                    atualizar_dados("planos", {
                        "nome": nome_edit.strip(),
                        "valor_padrao": float(valor_edit),
                    }, "id", int(tipo_id_sel))
                    st.session_state.sucesso_msg = "Tipo atualizado com sucesso!"
                    resetar_form()
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")

        if btn_toggle:
            try:
                novo_status = not bool(tipo_atual["ativo"])
                atualizar_dados("planos", {"ativo": novo_status}, "id", int(tipo_id_sel))
                msg = "Tipo reativado." if novo_status else "Tipo inativado."
                st.session_state.sucesso_msg = msg
                resetar_form()
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao alterar status: {e}")


def _validar_tipo(nome, modalidade_id, df_existente, tipo_id_editando=None):
    """Valida nome do tipo. Retorna mensagem de erro ou None se OK.

    Duplicidade e checada APENAS dentro da mesma modalidade
    (UNIQUE (modalidade_id, nome) no schema).
    """
    if not nome or not nome.strip():
        return "O nome do tipo nao pode ficar vazio."
    nome_limpo = nome.strip()
    if len(nome_limpo) < 2:
        return "O nome do tipo precisa ter pelo menos 2 caracteres."
    df_check = df_existente.copy()
    if tipo_id_editando is not None:
        df_check = df_check[df_check["id"] != tipo_id_editando]
    df_check = df_check[df_check["modalidade_id"] == modalidade_id]
    if not df_check.empty:
        nomes_existentes = df_check["nome"].astype(str).str.strip().str.lower().tolist()
        if nome_limpo.lower() in nomes_existentes:
            return f"Ja existe um tipo com o nome '{nome_limpo}' nesta modalidade."
    return None


def _renderizar_tabela_tipos(df_t):
    """Renderiza tabela HTML estilizada de tipos."""
    style_override = (
        '<style>'
        '.tabela-tipos thead tr th:first-child { display: table-cell !important; }'
        '.tabela-tipos tbody th { display: none; }'
        '</style>'
    )

    cabecalho = (
        '<tr style="background-color:#f8f9fa;border-bottom:2px solid #dee2e6;">'
        '<th style="padding:10px 12px;text-align:left;font-weight:600;">ID</th>'
        '<th style="padding:10px 12px;text-align:left;font-weight:600;">Nome</th>'
        '<th style="padding:10px 12px;text-align:right;font-weight:600;">Valor</th>'
        '<th style="padding:10px 12px;text-align:left;font-weight:600;">Status</th>'
        '</tr>'
    )

    linhas_html = []
    for _, row in df_t.iterrows():
        valor_str = f"R$ {float(row['valor_padrao']):.2f}".replace(".", ",")
        status_label = "Ativo" if row["ativo"] else "Inativo"
        cor_status = "#2E7D32" if row["ativo"] else "#9e9e9e"
        status_celula = f'<span style="color:{cor_status};font-weight:500;">{status_label}</span>'

        linhas_html.append(
            f'<tr style="border-bottom:1px solid #f0f0f0;">'
            f'<td style="padding:8px 12px;">{row["id"]}</td>'
            f'<td style="padding:8px 12px;">{row["nome"]}</td>'
            f'<td style="padding:8px 12px;text-align:right;">{valor_str}</td>'
            f'<td style="padding:8px 12px;">{status_celula}</td>'
            f'</tr>'
        )

    tabela = (
        '<table class="tabela-tipos" '
        'style="width:100%;border-collapse:collapse;border:1px solid #dee2e6;'
        'border-radius:8px;overflow:hidden;font-family:inherit;font-size:14px;">'
        f'<thead>{cabecalho}</thead>'
        f'<tbody>{"".join(linhas_html)}</tbody>'
        '</table>'
    )

    return style_override + tabela


# ============================================================================
# SUB-ABA: Professores
# (migrada do paginas/calendario.py — sub-aba Configuracoes > Professores)
# ============================================================================

def _render_sub_professores():
    """Sub-aba Professores: cadastro base de profissionais."""
    fk = st.session_state.form_key

    st.markdown("### Professores cadastrados")
    st.caption(
        "Cadastre os profissionais que atuam na academia. A cor e usada como "
        "fallback visual em locais que ainda referenciam o professor diretamente. "
        "Apos a Etapa H concluida, a cor das atividades vira da Modalidade."
    )

    df_prof = buscar_dados("profissionais", order="id")

    if df_prof.empty:
        df_prof = pd.DataFrame(columns=["id", "nome", "tipo", "cor_hex", "ativo", "created_at"])

    # Listagem
    if df_prof.empty:
        st.info("Nenhum professor cadastrado ainda. Use o formulario abaixo pra cadastrar o primeiro.")
    else:
        st.markdown(_renderizar_tabela_professores(df_prof), unsafe_allow_html=True)

    st.markdown("---")

    # Cadastrar novo
    with st.expander("Cadastrar novo professor", expanded=df_prof.empty):
        with st.form(f"form_novo_professor_{fk}", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                novo_nome = st.text_input("Nome do professor", max_chars=80, key=f"prof_add_nome_{fk}")
                novo_tipo = st.selectbox(
                    "Tipo / Modalidade",
                    options=list(TIPOS_PROFESSOR.keys()),
                    format_func=lambda x: TIPOS_PROFESSOR[x],
                    key=f"prof_add_tipo_{fk}",
                )
            with col2:
                cores_em_uso = set(df_prof["cor_hex"].tolist()) if not df_prof.empty else set()
                opcoes_cores = [c["hex"] for c in PALETA_CORES]

                st.markdown("**Cor de identificacao**")
                st.markdown(_renderizar_paleta(cores_em_uso), unsafe_allow_html=True)

                nova_cor = st.selectbox(
                    "Selecione a cor",
                    options=opcoes_cores,
                    format_func=lambda hexcode: _formatar_cor(hexcode, cores_em_uso),
                    label_visibility="collapsed",
                    key=f"prof_add_cor_{fk}",
                )
                st.markdown(_renderizar_amostra_cor(nova_cor), unsafe_allow_html=True)

            submitted = st.form_submit_button(
                "Cadastrar professor",
                use_container_width=True,
                type="primary",
            )

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
                        st.session_state.sucesso_msg = f"Professor '{novo_nome.strip()}' cadastrado!"
                        resetar_form()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao cadastrar professor: {e}")

    if df_prof.empty:
        return

    # Editar / Inativar / Reativar
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
            key=f"prof_ed_sel_{fk}",
        )
        prof_atual = df_sel.loc[df_sel["id"] == prof_id_sel].iloc[0]

        with st.form(f"form_editar_professor_{prof_id_sel}_{fk}"):
            col1, col2 = st.columns(2)
            with col1:
                nome_edit = st.text_input(
                    "Nome do professor",
                    value=prof_atual["nome"],
                    max_chars=80,
                    key=f"prof_ed_nome_{prof_id_sel}_{fk}",
                )
                tipo_edit = st.selectbox(
                    "Tipo / Modalidade",
                    options=list(TIPOS_PROFESSOR.keys()),
                    index=list(TIPOS_PROFESSOR.keys()).index(prof_atual["tipo"]) if prof_atual["tipo"] in TIPOS_PROFESSOR else 0,
                    format_func=lambda x: TIPOS_PROFESSOR[x],
                    key=f"prof_ed_tipo_{prof_id_sel}_{fk}",
                )
            with col2:
                cores_em_uso_edit = set(df_prof[df_prof["id"] != prof_id_sel]["cor_hex"].tolist())
                opcoes_cores = [c["hex"] for c in PALETA_CORES]
                idx_cor_atual = opcoes_cores.index(prof_atual["cor_hex"]) if prof_atual["cor_hex"] in opcoes_cores else 0

                st.markdown("**Cor de identificacao**")
                st.markdown(_renderizar_paleta(cores_em_uso_edit), unsafe_allow_html=True)

                cor_edit = st.selectbox(
                    "Selecione a cor",
                    options=opcoes_cores,
                    index=idx_cor_atual,
                    format_func=lambda hexcode: _formatar_cor(hexcode, cores_em_uso_edit),
                    label_visibility="collapsed",
                    key=f"prof_ed_cor_{prof_id_sel}_{fk}",
                )
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
                        st.session_state.sucesso_msg = "Alteracoes salvas com sucesso."
                        resetar_form()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")

            if btn_toggle:
                try:
                    novo_status = not bool(prof_atual["ativo"])
                    atualizar_dados("profissionais", {"ativo": novo_status}, "id", int(prof_id_sel))
                    msg = "Professor reativado." if novo_status else "Professor inativado."
                    st.session_state.sucesso_msg = msg
                    resetar_form()
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao alterar status: {e}")


def _validar_professor(nome, df_existente, professor_id_editando=None):
    """Valida nome do professor. Retorna mensagem de erro ou None se OK."""
    if not nome or not nome.strip():
        return "O nome do professor nao pode ficar vazio."
    nome_limpo = nome.strip()
    if len(nome_limpo) < 2:
        return "O nome do professor precisa ter pelo menos 2 caracteres."
    df_check = df_existente.copy()
    if professor_id_editando is not None:
        df_check = df_check[df_check["id"] != professor_id_editando]
    if not df_check.empty:
        nomes_existentes = df_check["nome"].astype(str).str.strip().str.lower().tolist()
        if nome_limpo.lower() in nomes_existentes:
            return f"Ja existe um professor com o nome '{nome_limpo}'."
    return None


def _renderizar_tabela_professores(df_prof):
    """Tabela HTML estilizada de professores com bolinha de cor."""
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


# ============================================================================
# SUB-ABA: Locais
# (migrada do paginas/calendario.py — sub-aba Configuracoes > Ambientes)
# ============================================================================

def _render_sub_locais():
    """Sub-aba Locais: cadastro base de espacos fisicos.

    Locais 'rentaveis' podem receber atividades. Locais 'nao rentaveis'
    (banheiros, recepcao) contam pra area total mas nao recebem atividades.
    """
    fk = st.session_state.form_key

    st.markdown("### Locais cadastrados")
    st.caption(
        "Cadastre os espacos fisicos da academia. Locais 'rentaveis' podem "
        "receber atividades pagas. Locais 'nao rentaveis' (banheiros, cozinha, "
        "recepcao) contam pra area total do imovel mas nao recebem atividades."
    )

    df_amb = buscar_dados("ambientes", order="id")

    if df_amb.empty:
        df_amb = pd.DataFrame(columns=["id", "nome", "area_m2", "rentavel", "ativo", "created_at"])

    # Listagem
    if df_amb.empty:
        st.info("Nenhum local cadastrado ainda. Use o formulario abaixo pra cadastrar o primeiro.")
    else:
        st.markdown(_renderizar_tabela_locais(df_amb), unsafe_allow_html=True)

        # KPIs rapidos
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

    # Cadastrar novo
    with st.expander("Cadastrar novo local", expanded=df_amb.empty):
        with st.form(f"form_novo_local_{fk}", clear_on_submit=True):
            col1, col2 = st.columns([2, 1])
            with col1:
                novo_nome = st.text_input(
                    "Nome do local",
                    max_chars=80,
                    placeholder="Ex: Embaixo, Em cima, Recepcao",
                    key=f"local_add_nome_{fk}",
                )
            with col2:
                nova_area = st.number_input(
                    "Area (m²)",
                    min_value=0.01,
                    max_value=10000.0,
                    value=10.0,
                    step=0.5,
                    format="%.2f",
                    key=f"local_add_area_{fk}",
                )

            novo_rentavel = st.checkbox(
                "Rentavel (pode receber atividades pagas)",
                value=True,
                help="Marque se este espaco recebe atividades pagas. Banheiros, cozinha e recepcao normalmente NAO sao rentaveis.",
                key=f"local_add_rent_{fk}",
            )

            submitted = st.form_submit_button(
                "Cadastrar local",
                use_container_width=True,
                type="primary",
            )

            if submitted:
                erro = _validar_local(novo_nome, df_amb, ambiente_id_editando=None)
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
                        st.session_state.sucesso_msg = f"Local '{novo_nome.strip()}' cadastrado!"
                        resetar_form()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao cadastrar local: {e}")

    if df_amb.empty:
        return

    # Editar / Inativar / Reativar
    with st.expander("Editar / Inativar / Reativar local"):
        df_sel = df_amb.copy()
        df_sel["label"] = df_sel.apply(
            lambda r: f"{r['nome']} ({r['area_m2']:.2f} m²) - {'Rentavel' if r['rentavel'] else 'Nao rentavel'} - {'Ativo' if r['ativo'] else 'Inativo'}",
            axis=1,
        )
        opcoes_ids = df_sel["id"].tolist()
        amb_id_sel = st.selectbox(
            "Selecione um local",
            options=opcoes_ids,
            format_func=lambda aid: df_sel.loc[df_sel["id"] == aid, "label"].values[0],
            key=f"local_ed_sel_{fk}",
        )
        amb_atual = df_sel.loc[df_sel["id"] == amb_id_sel].iloc[0]

        with st.form(f"form_editar_local_{amb_id_sel}_{fk}"):
            col1, col2 = st.columns([2, 1])
            with col1:
                nome_edit = st.text_input(
                    "Nome do local",
                    value=amb_atual["nome"],
                    max_chars=80,
                    key=f"local_ed_nome_{amb_id_sel}_{fk}",
                )
            with col2:
                area_edit = st.number_input(
                    "Area (m²)",
                    min_value=0.01,
                    max_value=10000.0,
                    value=float(amb_atual["area_m2"]),
                    step=0.5,
                    format="%.2f",
                    key=f"local_ed_area_{amb_id_sel}_{fk}",
                )

            rentavel_edit = st.checkbox(
                "Rentavel (pode receber atividades pagas)",
                value=bool(amb_atual["rentavel"]),
                key=f"local_ed_rent_{amb_id_sel}_{fk}",
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
                erro = _validar_local(nome_edit, df_amb, ambiente_id_editando=amb_id_sel)
                if erro:
                    st.error(erro)
                else:
                    try:
                        atualizar_dados("ambientes", {
                            "nome": nome_edit.strip(),
                            "area_m2": float(area_edit),
                            "rentavel": bool(rentavel_edit),
                        }, "id", int(amb_id_sel))
                        st.session_state.sucesso_msg = "Alteracoes salvas com sucesso."
                        resetar_form()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")

            if btn_toggle:
                try:
                    novo_status = not bool(amb_atual["ativo"])
                    atualizar_dados("ambientes", {"ativo": novo_status}, "id", int(amb_id_sel))
                    msg = "Local reativado." if novo_status else "Local inativado."
                    st.session_state.sucesso_msg = msg
                    resetar_form()
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao alterar status: {e}")


def _validar_local(nome, df_existente, ambiente_id_editando=None):
    """Valida nome do local. Retorna mensagem de erro ou None se OK."""
    if not nome or not nome.strip():
        return "O nome do local nao pode ficar vazio."
    nome_limpo = nome.strip()
    if len(nome_limpo) < 2:
        return "O nome do local precisa ter pelo menos 2 caracteres."
    df_check = df_existente.copy()
    if ambiente_id_editando is not None:
        df_check = df_check[df_check["id"] != ambiente_id_editando]
    if not df_check.empty:
        nomes_existentes = df_check["nome"].astype(str).str.strip().str.lower().tolist()
        if nome_limpo.lower() in nomes_existentes:
            return f"Ja existe um local com o nome '{nome_limpo}'."
    return None


def _renderizar_tabela_locais(df_amb):
    """Tabela HTML estilizada de locais."""
    style_override = (
        '<style>'
        '.tabela-locais thead tr th:first-child { display: table-cell !important; }'
        '.tabela-locais tbody th { display: none; }'
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
        '<table class="tabela-locais" '
        'style="width:100%;border-collapse:collapse;border:1px solid #dee2e6;'
        'border-radius:8px;overflow:hidden;font-family:inherit;font-size:14px;">'
        f'<thead>{cabecalho}</thead>'
        f'<tbody>{"".join(linhas_html)}</tbody>'
        '</table>'
    )

    return style_override + tabela


# ============================================================================
# SUB-ABA: Centros de Custo (mantida igual ao codigo da Etapa D.7)
# ============================================================================

def _render_sub_centros_custo():
    """Sub-aba Centros de Custo: cadastro de categorias de saida."""
    fk = st.session_state.form_key

    df_c = buscar_dados('categorias_saida', order='nome')
    if not df_c.empty:
        st.dataframe(
            df_c[['nome', 'tipo_custo']].rename(columns={
                "nome": "Centro de Custo Financeiro",
                "tipo_custo": "Tipo Contábil",
            }),
            use_container_width=True,
        )

    acao_cc = st.radio(
        "Ação:",
        ["➕ Adicionar", "✏️ Editar", "🗑️ Remover"],
        horizontal=True,
        key=f"acao_cc_{fk}",
    )

    if acao_cc == "➕ Adicionar":
        with st.form("fc_add"):
            n_c = st.text_input("Nome do Novo Centro de Custo", key=f"nc_add_{fk}")
            t_c = st.selectbox("Tipo de Custo Contábil", ["Fixo", "Variável"])
            if st.form_submit_button("Confirmar Adição", type="primary"):
                if n_c:
                    inserir_dados('categorias_saida', {'nome': n_c, 'tipo_custo': t_c})
                    st.session_state.sucesso_msg = "Centro de custo adicionado com sucesso!"
                    resetar_form()
                    st.rerun()
    elif acao_cc == "✏️ Editar":
        if not df_c.empty:
            sel_c = st.selectbox("Selecione o Centro de Custo", df_c['nome'].tolist(), key=f"sel_cc_ed_{fk}")
            d_c = df_c[df_c['nome'] == sel_c].iloc[0]
            cc_id = d_c['id']

            nn_c = st.text_input("Novo Nome do Centro de Custo", value=sel_c, key=f"nn_cc_{cc_id}_{fk}")
            nt_c = st.selectbox(
                "Tipo de Custo Contábil",
                ["Fixo", "Variável"],
                index=0 if d_c['tipo_custo'] == 'Fixo' else 1,
                key=f"nt_cc_{cc_id}_{fk}",
            )

            if st.button("Salvar Edição", type="primary"):
                atualizar_dados('categorias_saida', {'nome': nn_c, 'tipo_custo': nt_c}, 'id', int(cc_id))
                st.session_state.sucesso_msg = "Centro de custo atualizado com sucesso!"
                resetar_form()
                st.rerun()
    elif acao_cc == "🗑️ Remover":
        if not df_c.empty:
            del_c = st.selectbox("Selecione o Custo para Remoção", df_c['nome'].tolist(), key=f"del_cc_{fk}")
            st.markdown("<div class='btn-danger'>", unsafe_allow_html=True)
            if st.button("Excluir Permanente do Sistema"):
                deletar_dados('categorias_saida', 'id', int(df_c[df_c['nome'] == del_c]['id'].iloc[0]))
                st.session_state.sucesso_msg = "Centro de custo removido!"
                resetar_form()
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)


# ============================================================================
# SUB-ABA: Impostos / Taxas (mantida igual ao codigo da Etapa D.7)
# ============================================================================

def _render_sub_impostos():
    """Sub-aba Impostos / Taxas: cadastro de aliquotas."""
    fk = st.session_state.form_key

    df_i = buscar_dados('impostos', order='nome')
    if not df_i.empty:
        st.dataframe(
            df_i[['nome', 'aliquota']].rename(columns={
                "nome": "Nomenclatura do Imposto/Taxa",
                "aliquota": "Alíquota Contratual (%)",
            }),
            use_container_width=True,
        )

    acao_imp = st.radio(
        "Ação:",
        ["➕ Adicionar", "✏️ Editar", "🗑️ Remover"],
        horizontal=True,
        key=f"acao_imp_{fk}",
    )

    if acao_imp == "➕ Adicionar":
        with st.form("fi_add"):
            n_i = st.text_input("Nome do Imposto ou Taxa", key=f"ni_add_{fk}")
            v_i = st.number_input(
                "Alíquota Aplicável (%)",
                min_value=0.0,
                value=None,
                format="%.2f",
                key=f"vi_add_{fk}",
            )
            if st.form_submit_button("Confirmar Adição", type="primary"):
                if n_i and v_i is not None:
                    inserir_dados('impostos', {'nome': n_i, 'aliquota': v_i})
                    st.session_state.sucesso_msg = "Imposto/Taxa adicionado com sucesso!"
                    resetar_form()
                    st.rerun()
    elif acao_imp == "✏️ Editar":
        if not df_i.empty:
            sel_i = st.selectbox("Selecione o Imposto ou Taxa", df_i['nome'].tolist(), key=f"sel_imp_ed_{fk}")
            d_i = df_i[df_i['nome'] == sel_i].iloc[0]
            imp_id = d_i['id']

            nn_i = st.text_input("Novo Nome do Imposto", value=d_i['nome'], key=f"nn_imp_{imp_id}_{fk}")
            nv_i = st.number_input(
                "Nova Alíquota Aplicável (%)",
                value=float(d_i['aliquota']),
                format="%.2f",
                key=f"nv_imp_{imp_id}_{fk}",
            )

            if st.button("Salvar Edição", type="primary"):
                atualizar_dados('impostos', {'nome': nn_i, 'aliquota': nv_i}, 'id', int(imp_id))
                st.session_state.sucesso_msg = "Imposto/Taxa atualizado com sucesso!"
                resetar_form()
                st.rerun()
    elif acao_imp == "🗑️ Remover":
        if not df_i.empty:
            del_i = st.selectbox("Selecione o Imposto para Remoção", df_i['nome'].tolist(), key=f"del_imp_{fk}")
            st.markdown("<div class='btn-danger'>", unsafe_allow_html=True)
            if st.button("Excluir Permanente do Sistema"):
                deletar_dados('impostos', 'id', int(df_i[df_i['nome'] == del_i]['id'].iloc[0]))
                st.session_state.sucesso_msg = "Imposto/Taxa removido!"
                resetar_form()
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)


# ============================================================================
# Helpers compartilhados (paleta de cores)
# ============================================================================

def _formatar_cor(hexcode, cores_em_uso):
    """Formata o nome da cor no selectbox, marcando as ja em uso."""
    nome_cor = next((c["nome"] for c in PALETA_CORES if c["hex"] == hexcode), hexcode)
    sufixo = " (em uso)" if hexcode in cores_em_uso else ""
    return f"{nome_cor}{sufixo}"


def _renderizar_paleta(cores_em_uso):
    """Renderiza paleta visual de 12 cores."""
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
    """Renderiza amostra grande da cor selecionada."""
    nome_cor = next((c["nome"] for c in PALETA_CORES if c["hex"] == hexcode), hexcode)
    return (
        f'<div style="margin-top:8px;padding:12px;background-color:{hexcode};'
        f'border-radius:8px;border:1px solid #ccc;text-align:center;'
        f'font-weight:500;color:#333;">'
        f'Cor selecionada: {nome_cor}'
        f'</div>'
    )