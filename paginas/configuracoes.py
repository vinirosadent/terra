"""
Modulo: paginas/configuracoes.py
Responsabilidade: pagina "Configuracoes" — sub-abas de Servicos/Modalidades,
Centros de Custo, Impostos/Taxas e Seguranca (Login).

Status: ativo (preenchido na Etapa D, passo D.7).

Para usar:
    from paginas import configuracoes as pg_configuracoes
    # ...
    elif menu == "⚙️ Configurações":
        pg_configuracoes.render()

Notas:
- A sub-aba "Seguranca (Login)" tem codigo comentado desde a Etapa B
  (autenticacao migrada para Supabase Auth). Foi migrada AS-IS para
  preservar historico. Cleanup completo (remover do st.radio + remover
  bloco comentado) sera feito no passo D.14.
"""

import streamlit as st

from db import buscar_dados, inserir_dados, atualizar_dados, deletar_dados
from utils import resetar_form


def render():
    fk = st.session_state.form_key

    st.title("⚙️ Cadastros e Configurações")

    aba_config = st.radio("Selecione a Configuração:", ["Serviços / Modalidades", "Centros de Custo", "Impostos / Taxas"], horizontal=True, key=f"rad_conf_{fk}")
    st.markdown("---")

    if aba_config == "Serviços / Modalidades":
        df_a = buscar_dados('atividades_entrada', order='nome')
        if not df_a.empty:
            st.dataframe(df_a[['nome', 'valor_padrao']].rename(columns={"nome":"Modalidade / Serviço", "valor_padrao":"Valor Padrão de Tabela (R$)"}), use_container_width=True)

        acao_mod = st.radio("Ação:", ["➕ Adicionar", "✏️ Editar", "🗑️ Remover"], horizontal=True, key=f"acao_mod_{fk}")

        if acao_mod == "➕ Adicionar":
            with st.form("fa_add"):
                n_a = st.text_input("Nome da Nova Modalidade", key=f"na_add_{fk}")
                v_a = st.number_input("Valor Padrão de Tabela (R$)", min_value=0.0, value=None, format="%.2f", key=f"va_add_{fk}")
                if st.form_submit_button("Confirmar Adição", type="primary"):
                    if n_a and v_a is not None:
                        inserir_dados('atividades_entrada', {'nome': n_a, 'valor_padrao': v_a})
                        st.session_state.sucesso_msg = "Nova Modalidade adicionada ao sistema!"
                        resetar_form()
                        st.rerun()
        elif acao_mod == "✏️ Editar":
            if not df_a.empty:
                sel_a = st.selectbox("Selecione a Modalidade", df_a['nome'].tolist(), key=f"sel_mod_ed_{fk}")
                d_a = df_a[df_a['nome'] == sel_a].iloc[0]
                mod_id = d_a['id']

                nn_a = st.text_input("Novo Nome da Modalidade", value=d_a['nome'], key=f"nn_{mod_id}_{fk}")
                nv_a = st.number_input("Novo Valor Padrão de Tabela (R$)", value=float(d_a['valor_padrao']), format="%.2f", key=f"nv_{mod_id}_{fk}")

                if st.button("Salvar Edição", type="primary"):
                    atualizar_dados('atividades_entrada', {'nome': nn_a, 'valor_padrao': nv_a}, 'id', int(mod_id))
                    st.session_state.sucesso_msg = "Modalidade atualizada com sucesso!"
                    resetar_form()
                    st.rerun()
        elif acao_mod == "🗑️ Remover":
            if not df_a.empty:
                del_a = st.selectbox("Selecione a Modalidade para Remoção", df_a['nome'].tolist(), key=f"del_mod_{fk}")
                st.markdown("<div class='btn-danger'>", unsafe_allow_html=True)
                if st.button("Excluir Permanente do Sistema"):
                    deletar_dados('atividades_entrada', 'id', int(df_a[df_a['nome']==del_a]['id'].iloc[0]))
                    st.session_state.sucesso_msg = "Modalidade removida!"
                    resetar_form()
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

    elif aba_config == "Centros de Custo":
        df_c = buscar_dados('categorias_saida', order='nome')
        if not df_c.empty:
            st.dataframe(df_c[['nome', 'tipo_custo']].rename(columns={"nome":"Centro de Custo Financeiro", "tipo_custo":"Tipo Contábil"}), use_container_width=True)

        acao_cc = st.radio("Ação:", ["➕ Adicionar", "✏️ Editar", "🗑️ Remover"], horizontal=True, key=f"acao_cc_{fk}")

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
                nt_c = st.selectbox("Tipo de Custo Contábil", ["Fixo", "Variável"], index=0 if d_c['tipo_custo'] == 'Fixo' else 1, key=f"nt_cc_{cc_id}_{fk}")

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
                    deletar_dados('categorias_saida', 'id', int(df_c[df_c['nome']==del_c]['id'].iloc[0]))
                    st.session_state.sucesso_msg = "Centro de custo removido!"
                    resetar_form()
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

    elif aba_config == "Impostos / Taxas":
        df_i = buscar_dados('impostos', order='nome')
        if not df_i.empty:
            st.dataframe(df_i[['nome', 'aliquota']].rename(columns={"nome":"Nomenclatura do Imposto/Taxa", "aliquota":"Alíquota Contratual (%)"}), use_container_width=True)

        acao_imp = st.radio("Ação:", ["➕ Adicionar", "✏️ Editar", "🗑️ Remover"], horizontal=True, key=f"acao_imp_{fk}")

        if acao_imp == "➕ Adicionar":
            with st.form("fi_add"):
                n_i = st.text_input("Nome do Imposto ou Taxa", key=f"ni_add_{fk}")
                v_i = st.number_input("Alíquota Aplicável (%)", min_value=0.0, value=None, format="%.2f", key=f"vi_add_{fk}")
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
                nv_i = st.number_input("Nova Alíquota Aplicável (%)", value=float(d_i['aliquota']), format="%.2f", key=f"nv_imp_{imp_id}_{fk}")

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
                    deletar_dados('impostos', 'id', int(df_i[df_i['nome']==del_i]['id'].iloc[0]))
                    st.session_state.sucesso_msg = "Imposto/Taxa removido!"
                    resetar_form()
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

