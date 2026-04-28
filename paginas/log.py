"""
Modulo: paginas/log.py
Responsabilidade: pagina "Log de Lancamentos" — diario de lancamentos com
filtros (tipo, mes) e ajustes (editar/remover) por lancamento individual.

Status: ativo (preenchido na Etapa D, passo D.6).

Para usar:
    from paginas import log as pg_log
    # ...
    elif menu == "📜 Log de Lançamentos":
        pg_log.render()

A funcao render() le st.session_state.form_key (variavel global Streamlit),
chama buscar/atualizar/deletar de db.py e resetar_form de utils.py.
"""

import streamlit as st
import pandas as pd

from db import buscar_dados, atualizar_dados, deletar_dados
from utils import resetar_form


def render():
    fk = st.session_state.form_key

    st.title("📜 Diário de Lançamentos (Log)")
    st.write("Confira abaixo tudo o que foi registrado no sistema.")

    df_log = buscar_dados('lancamentos', order='id', order_desc=True)

    if df_log.empty:
        st.info("Nenhum lançamento encontrado.")
    else:
        df_log['data'] = pd.to_datetime(df_log['data'])

        c1, c2, c3 = st.columns([2, 2, 2])
        f_tipo = c1.selectbox("Filtrar Tipo:", ["Ver Tudo", "Entrada", "Saida"])

        df_log['Mes/Ano'] = df_log['data'].dt.strftime('%m/%Y')
        meses_disp = ["Ver Tudo"] + sorted(df_log['Mes/Ano'].unique().tolist(), reverse=True)
        f_mes = c2.selectbox("Filtrar Mês:", meses_disp)

        df_f = df_log.copy()
        if f_tipo != "Ver Tudo":
            df_f = df_f[df_f['tipo'] == f_tipo]
        if f_mes != "Ver Tudo":
            df_f = df_f[df_f['Mes/Ano'] == f_mes]

        df_f['Data_Formatada'] = df_f['data'].dt.strftime('%d/%m/%Y')

        df_display = df_f[['id', 'Data_Formatada', 'tipo', 'categoria', 'descricao', 'valor_bruto', 'metodo_pagamento']].rename(columns={
            'id': 'ID',
            'Data_Formatada': 'Data',
            'tipo': 'Tipo',
            'categoria': 'Categoria',
            'descricao': 'Detalhes/Nome',
            'valor_bruto': 'Valor Bruto (R$)',
            'metodo_pagamento': 'Método'
        })

        st.dataframe(df_display, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("⚠️ Ajustes de Lançamento")
        st.write("Selecione um registro abaixo caso precise corrigir um valor, data ou excluí-lo.")

        id_opcoes = df_f['id'].astype(str) + " - " + df_f['descricao'].astype(str) + " (R$ " + df_f['valor_bruto'].astype(str) + ")"
        id_selecionado = st.selectbox("Selecione o Lançamento:", ["Selecione..."] + id_opcoes.tolist())

        if id_selecionado != "Selecione...":
            id_real = int(id_selecionado.split(" - ")[0])
            dados_lanc = df_f[df_f['id'] == id_real].iloc[0]

            acao_log = st.radio("O que deseja fazer com este lançamento?", ["✏️ Editar", "🗑️ Remover"], horizontal=True)

            if acao_log == "✏️ Editar":
                st.markdown("#### ✏️ Atualizar Dados")
                with st.form("form_editar_log"):
                    c_ed1, c_ed2 = st.columns(2)

                    data_atual = pd.to_datetime(dados_lanc['Data_Formatada'], format='%d/%m/%Y')
                    nova_data = c_ed1.date_input("Nova Data", value=data_atual, format="DD/MM/YYYY")
                    novo_valor = c_ed2.number_input("Novo Valor (R$)", value=float(dados_lanc['valor_bruto']), format="%.2f")

                    c_ed3, c_ed4 = st.columns(2)
                    nova_desc = c_ed3.text_input("Nova Descrição", value=str(dados_lanc['descricao']))

                    metodos_lista = ["PIX", "Dinheiro", "Cartão"]
                    idx_metodo = metodos_lista.index(dados_lanc['metodo_pagamento']) if dados_lanc['metodo_pagamento'] in metodos_lista else 0
                    novo_met = c_ed4.selectbox("Novo Método", metodos_lista, index=idx_metodo)

                    if st.form_submit_button("Salvar Alterações", type="primary"):
                        atualizar_dados('lancamentos', {
                            'data': nova_data.strftime('%Y-%m-%d'),
                            'valor_bruto': novo_valor,
                            'valor_liquido': novo_valor,
                            'descricao': nova_desc,
                            'metodo_pagamento': novo_met
                        }, 'id', id_real)

                        st.session_state.sucesso_msg = "Lançamento atualizado com sucesso!"
                        resetar_form()
                        st.rerun()

            elif acao_log == "🗑️ Remover":
                st.warning("⚠️ Tem certeza? Esta ação apagará o registro do banco de dados definitivamente.")
                st.markdown('<div class="btn-danger">', unsafe_allow_html=True)
                if st.button("Sim, Deletar Lançamento Permanentemente"):
                    deletar_dados('lancamentos', 'id', id_real)
                    st.session_state.sucesso_msg = "Lançamento excluído com sucesso!"
                    resetar_form()
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
