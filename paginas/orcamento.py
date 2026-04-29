"""
Modulo: paginas/orcamento.py
Responsabilidade: pagina "Orcamento & Metas" com 3 secoes:
- Lancamento Mensal Especifico: form pra cadastrar/atualizar 1 mes especifico
  (upsert manual: busca → se existe atualiza, se nao insere)
- Acoes em Lote (Ano Completo): replica valor pros 12 meses do ano
- Resumo Orcamentario: tabela pivotada (linha por categoria, coluna por mes)
  + balanco anual com 3 metricas

Status: ativo (preenchido na Etapa D, passo D.10).

Para usar:
    from paginas import orcamento as pg_orcamento
    # ...
    elif menu == "🎯 Orçamento & Metas":
        pg_orcamento.render()
"""

from datetime import date

import streamlit as st

from db import buscar_dados, inserir_dados, atualizar_dados


def render():
    st.title("🎯 Planejamento de Orçamentos Mensais")

    df_cat = buscar_dados('categorias_saida')
    categorias = df_cat['nome'].tolist() if not df_cat.empty else []

    ano_atual = date.today().year
    c_ano1, c_ano2 = st.columns([1, 4])
    ano_selecionado = c_ano1.selectbox("📅 Ano de Planejamento", [ano_atual - 1, ano_atual, ano_atual + 1], index=1)

    st.markdown("### ➕ Lançamento Mensal Específico")
    with st.form("f_add_orc"):
        c1, c2, c3, c4 = st.columns(4)
        tipo_orc = c1.selectbox("Tipo", ["Despesa", "Receita"])
        cat_sel = c2.selectbox("Categoria Correspondente", categorias if tipo_orc == "Despesa" else ["Academia", "Personal", "Calistenia", "Assessoria", "Inscrição Evento"])
        mes_sel = c3.selectbox("Mês", [f"{ano_selecionado}-{m:02d}" for m in range(1,13)])
        val_orc = c4.number_input("Valor Projetado (R$)", min_value=0.0, value=None, format="%.2f")

        if st.form_submit_button("Salvar Orçamento do Mês", type="primary"):
            if val_orc is not None:
                df_check = buscar_dados('orcamentos', eq={'ano': ano_selecionado, 'mes': mes_sel, 'categoria': cat_sel, 'tipo': tipo_orc})
                if not df_check.empty:
                    atualizar_dados('orcamentos', {'valor': val_orc}, 'id', int(df_check.iloc[0]['id']))
                else:
                    inserir_dados('orcamentos', {'ano': ano_selecionado, 'mes': mes_sel, 'categoria': cat_sel, 'valor': val_orc, 'tipo': tipo_orc})
                st.session_state.sucesso_msg = "Orçamento salvo com sucesso!"
                st.rerun()

    st.markdown("---")
    st.markdown("### ⚡ Ações em Lote (Ano Completo)")
    st.write("Evite trabalho repetitivo: replique um custo fixo (ex: Aluguel, Eletricidade) para todos os meses de janeiro a dezembro do ano selecionado.")
    with st.form("f_lote"):
        cl1, cl2, cl3 = st.columns(3)
        t_lote = cl1.selectbox("Tipo", ["Despesa", "Receita"], key="tlote")
        cat_lote = cl2.selectbox("Categoria", categorias if t_lote == "Despesa" else ["Academia", "Personal", "Calistenia", "Assessoria", "Inscrição Evento"], key="clote")
        v_lote = cl3.number_input("Valor Fixo Mensal (R$)", min_value=0.0, value=None, format="%.2f", key="vlote")

        if st.form_submit_button("🔄 Aplicar a Todos os 12 Meses", type="primary"):
            if v_lote is not None:
                for m in range(1, 13):
                    m_str = f"{ano_selecionado}-{m:02d}"
                    df_check_lote = buscar_dados('orcamentos', eq={'ano': ano_selecionado, 'mes': m_str, 'categoria': cat_lote, 'tipo': t_lote})
                    if not df_check_lote.empty:
                        atualizar_dados('orcamentos', {'valor': v_lote}, 'id', int(df_check_lote.iloc[0]['id']))
                    else:
                        inserir_dados('orcamentos', {'ano': ano_selecionado, 'mes': m_str, 'categoria': cat_lote, 'valor': v_lote, 'tipo': t_lote})
                st.session_state.sucesso_msg = f"Lote aplicado! R$ {v_lote:.2f} registrado para todos os meses do ano."
                st.rerun()

    st.markdown("---")
    st.subheader(f"📊 Resumo Orçamentário - {ano_selecionado}")

    df_orc_ano = buscar_dados('orcamentos', eq={'ano': ano_selecionado})

    if not df_orc_ano.empty:
        df_orc_ano['mes_curto'] = df_orc_ano['mes'].apply(lambda x: x.split('-')[1])
        df_pivot = df_orc_ano.pivot_table(index=['tipo', 'categoria'], columns='mes_curto', values='valor', aggfunc='sum').fillna(0)

        for m in range(1, 13):
            m_str = f"{m:02d}"
            if m_str not in df_pivot.columns:
                df_pivot[m_str] = 0.0

        meses_cols = [f"{m:02d}" for m in range(1, 13)]
        df_pivot = df_pivot[meses_cols]
        df_pivot['Total Anual'] = df_pivot.sum(axis=1)

        df_display = df_pivot.reset_index()
        df_display = df_display.rename(columns={'tipo': 'Natureza', 'categoria': 'Item / Categoria'})

        df_receitas = df_display[df_display['Natureza'] == 'Receita'].drop(columns=['Natureza'])
        df_despesas = df_display[df_display['Natureza'] == 'Despesa'].drop(columns=['Natureza'])

        if not df_receitas.empty:
            st.markdown("#### 🟢 Metas de Receita Projetadas")
            st.dataframe(df_receitas.style.format({c: "R$ {:.2f}" for c in meses_cols + ['Total Anual']}), use_container_width=True)

        if not df_despesas.empty:
            st.markdown("#### 🔴 Despesas Previstas")
            st.dataframe(df_despesas.style.format({c: "R$ {:.2f}" for c in meses_cols + ['Total Anual']}), use_container_width=True)

        st.markdown("#### 🧮 Balanço Anual Projetado")
        tot_rec = df_receitas['Total Anual'].sum() if not df_receitas.empty else 0.0
        tot_desp = df_despesas['Total Anual'].sum() if not df_despesas.empty else 0.0

        c_m1, c_m2, c_m3 = st.columns(3)
        c_m1.metric("Receita Total Prevista (Ano)", f"R$ {tot_rec:,.2f}")
        c_m2.metric("Despesa Total Prevista (Ano)", f"R$ {tot_desp:,.2f}", delta_color="inverse")
        c_m3.metric("Lucro Líquido Previsto (Ano)", f"R$ {tot_rec - tot_desp:,.2f}")

    else:
        st.info(f"Nenhum orçamento planejado para o ano de {ano_selecionado}. Cadastre acima para visualizar a tabela de planejamento.")
