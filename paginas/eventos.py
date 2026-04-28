"""
Modulo: paginas/eventos.py
Responsabilidade: pagina "Gestao de Eventos" — funil de 4 etapas:
- 1. Planejamento (Criar & Orcar): cria evento + monta orcamento de receitas/despesas
- 2. Evento Aberto (Live): 2 colunas — esquerda registra inscricoes/despesas,
  direita mostra resumo em tempo real + ajustes
- 3. Reconciliacao & Fechar: comparativo orcado vs realizado + lancamento
  esquecido + botao de encerramento
- 4. Relatorio (SOA): metricas de variancia + grafico plotly + tabela
  de detalhamento + geracao de HTML/PDF pra download (base64)

Status: ativo (preenchido na Etapa D, passo D.9).

Para usar:
    from paginas import eventos as pg_eventos
    # ...
    elif menu == "📅 Gestão de Eventos":
        pg_eventos.render()
"""

import base64
from datetime import date

import streamlit as st
import pandas as pd
import plotly.express as px

from db import buscar_dados, inserir_dados, atualizar_dados, deletar_dados
from utils import extrair_item_evento, resetar_form


def render():
    fk = st.session_state.form_key

    st.title("📅 Funil de Projetos e Eventos")
    st.write("Gerencie eventos em estágios: Planejamento, Aberto (Live), Fechamento e Relatórios (SOA).")

    etapa_evento = st.radio("Selecione a Fase do Evento:",
                            ["1. Planejamento (Criar & Orçar)", "2. Evento Aberto (Live)", "3. Reconciliação & Fechar", "4. Relatório (SOA)"],
                            horizontal=True, key=f"rad_ev_etapa_{fk}")
    st.markdown("---")

    df_ev_todos = buscar_dados('eventos', order='id', order_desc=True)
    if df_ev_todos.empty:
        df_ev_todos = pd.DataFrame(columns=['id', 'nome', 'descricao', 'data_evento', 'meta_publico', 'status'])

    # --- ETAPA 1: PLANEJAMENTO ---
    if etapa_evento == "1. Planejamento (Criar & Orçar)":
        st.subheader("A. Novo Evento")
        with st.form("f_add_ev"):
            c1, c2 = st.columns(2)
            n_ev = c1.text_input("Nome do Evento (Ex: Trilha de Verão)", key=f"n_ev_{fk}")
            d_ev = c2.date_input("Data Prevista do Evento", value=date.today(), format="DD/MM/YYYY", key=f"d_ev_{fk}")

            c3, c4 = st.columns([1, 3])
            m_pub = c3.number_input("Meta de Público", min_value=1, value=30, step=1, key=f"m_pub_{fk}")
            desc_ev = c4.text_input("Descrição Curta (máx 10 palavras)", key=f"desc_ev_{fk}")

            if st.form_submit_button("Criar Evento (Inicia no Planejamento)", type="primary"):
                if n_ev:
                    inserir_dados('eventos', {'nome': n_ev, 'descricao': desc_ev, 'data_evento': str(d_ev), 'meta_publico': m_pub, 'status': 'Planejamento'})
                    st.session_state.sucesso_msg = "Evento criado! Agora construa o orçamento abaixo."
                    resetar_form()
                    st.rerun()
                else: st.error("Digite o nome do evento.")

        st.markdown("---")
        st.subheader("B. Construir Orçamento")
        evs_plan = df_ev_todos[df_ev_todos['status'] == 'Planejamento']
        if not evs_plan.empty:
            ev_sel_plan = st.selectbox("Selecione o Evento para Planejar:", evs_plan['nome'].tolist(), key=f"ev_sel_plan_{fk}")
            ev_dados_plan = evs_plan[evs_plan['nome'] == ev_sel_plan].iloc[0]
            ev_id_plan = int(ev_dados_plan['id'])

            df_orc_ev = buscar_dados('orcamento_eventos', eq={'evento_id': ev_id_plan})

            with st.form("f_add_orc_ev"):
                c1, c2, c3 = st.columns([1, 2, 1])
                tipo_orc_ev = c1.selectbox("Natureza", ["Despesa Esperada", "Receita Esperada"])
                desc_orc_ev = c2.text_input("Descrição do Item (Ex: Ônibus, Ingressos)")
                val_orc_ev = c3.number_input("Valor Projetado (R$)", min_value=0.0, value=None, format="%.2f")

                if st.form_submit_button("Adicionar Linha ao Orçamento", type="primary"):
                    if desc_orc_ev and val_orc_ev is not None:
                        tipo_db = "Receita" if tipo_orc_ev == "Receita Esperada" else "Despesa"
                        inserir_dados('orcamento_eventos', {'evento_id': ev_id_plan, 'tipo': tipo_db, 'descricao': desc_orc_ev, 'valor': val_orc_ev})
                        st.rerun()

            if not df_orc_ev.empty:
                st.dataframe(df_orc_ev[['tipo', 'descricao', 'valor']].rename(columns={'tipo':'Natureza', 'descricao':'Descrição', 'valor':'Valor (R$)'}), use_container_width=True)

                rec_proj = df_orc_ev[df_orc_ev['tipo'] == 'Receita']['valor'].sum()
                desp_proj = df_orc_ev[df_orc_ev['tipo'] == 'Despesa']['valor'].sum()
                st.info(f"**Projeção Atual:** Custo: R$ {desp_proj:.2f} | Receita: R$ {rec_proj:.2f} | Lucro Projetado: R$ {rec_proj - desp_proj:.2f}")

            st.markdown("---")
            if st.button("🚀 Abrir Evento (Go Live!)", type="primary", use_container_width=True):
                atualizar_dados('eventos', {'status': 'Aberto'}, 'id', ev_id_plan)
                st.session_state.sucesso_msg = f"O evento '{ev_sel_plan}' agora está Aberto e pronto para receber inscrições e lançamentos reais!"
                resetar_form()
                st.rerun()
        else:
            st.info("Nenhum evento no estágio de planejamento.")

    elif etapa_evento == "2. Evento Aberto (Live)":
        evs_abertos = df_ev_todos[df_ev_todos['status'] == 'Aberto']
        if not evs_abertos.empty:
            ev_sel_live = st.selectbox("Gerenciando o Evento Aberto:", evs_abertos['nome'].tolist(), key=f"ev_sel_live_{fk}")
            ev_dados_live = evs_abertos[evs_abertos['nome'] == ev_sel_live].iloc[0]
            ev_id_live = int(ev_dados_live['id'])

            st.markdown(f"**Data Prevista:** {ev_dados_live['data_evento']} | **Descrição:** {ev_dados_live['descricao']}")

            col_live_1, col_live_2 = st.columns(2)

            with col_live_1:
                st.subheader("Receber Inscrição (Entrada)")
                st.write("*O valor vai imediatamente para o Caixa Geral.*")
                df_alunos = buscar_dados('alunos', eq={'ativo': 1}, order='nome')
                df_impostos = buscar_dados('impostos', order='nome')

                st.markdown("<div style='background-color:#f8f9fa; padding:15px; border-radius:8px;'>", unsafe_allow_html=True)
                tipo_inscrito = st.radio("Origem da Inscrição:", ["Aluno (Interno)", "Convidado (Externo)"], horizontal=True, key=f"r_insc_live_{fk}")
                if tipo_inscrito == "Aluno (Interno)":
                    aluno_nome_sel = st.selectbox("Selecione o Aluno", df_alunos['nome'].tolist() if not df_alunos.empty else ["Nenhum aluno cadastrado"], key=f"s_aln_{fk}")
                    nome_ext_insc = ""
                else:
                    nome_ext_insc = st.text_input("Nome do Convidado Livre", key=f"t_ext_{fk}")
                    aluno_nome_sel = ""

                c3, c4 = st.columns(2)
                valor_insc = c3.number_input("Valor Pago Bruto (R$)", min_value=0.0, value=None, format="%.2f", key=f"v_insc_{fk}")
                metodo_insc = c4.radio("Forma de Pagto", ["PIX", "Dinheiro", "Cartão"], horizontal=True, key=f"m_insc_{fk}")

                aplicar_imposto = st.checkbox("Aplicar Impostos/Taxas?", value=False, key=f"c_imp_{fk}")
                impostos_sel = []
                if aplicar_imposto and not df_impostos.empty:
                    impostos_sel = st.multiselect("Selecione os Impostos", df_impostos['nome'].tolist(), key=f"ms_imp_{fk}")

                if st.button("Confirmar Inscrição no Caixa", type="primary", use_container_width=True):
                    if valor_insc is None: st.error("Preencha o valor.")
                    elif tipo_inscrito == "Convidado (Externo)" and not nome_ext_insc: st.error("Digite o nome do convidado.")
                    else:
                        aliq_total = sum([df_impostos[df_impostos['nome'] == i]['aliquota'].iloc[0] for i in impostos_sel]) if aplicar_imposto and impostos_sel else 0.0
                        v_imp = valor_insc * (aliq_total / 100)
                        v_liq = valor_insc - v_imp
                        imp_str = ", ".join(impostos_sel) if impostos_sel else ""

                        aluno_id_insc = int(df_alunos[df_alunos['nome'] == aluno_nome_sel]['id'].iloc[0]) if tipo_inscrito == "Aluno (Interno)" else None
                        desc_caixa = f"Inscrição: {aluno_nome_sel}" if tipo_inscrito == "Aluno (Interno)" else f"Inscrição: {nome_ext_insc}"

                        inserir_dados('lancamentos', {
                            'data': str(date.today()), 'valor_bruto': valor_insc, 'valor_imposto': v_imp,
                            'valor_liquido': v_liq, 'tipo': 'Entrada', 'metodo_pagamento': metodo_insc,
                            'aluno_id': aluno_id_insc, 'evento_id': ev_id_live, 'categoria': 'Inscrição Evento',
                            'descricao': desc_caixa, 'operacao': 'A Vista', 'impostos_aplicados': imp_str
                        })
                        st.session_state.sucesso_msg = f"Inscrição confirmada! Líquido retido: R$ {v_liq:.2f} (Imposto retido: R$ {v_imp:.2f})"
                        resetar_form()
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

                st.markdown("---")
                st.subheader("Registrar Gasto de Preparação (Saída)")

                df_orc_desp = buscar_dados('orcamento_eventos', eq={'evento_id': ev_id_live, 'tipo': 'Despesa'})
                cat_options = df_orc_desp['descricao'].tolist() if not df_orc_desp.empty else []
                cat_options.append("Outro (Nova Categoria)")

                st.markdown("<div style='background-color:#fef2f2; padding:15px; border-radius:8px;'>", unsafe_allow_html=True)
                d_desp = st.date_input("Data do Gasto", value=date.today(), format="DD/MM/YYYY", key=f"dt_desp_{fk}")
                cat_desp = st.selectbox("Categoria (Orçada ou Nova)", cat_options, key=f"cat_desp_{fk}")

                desc_nova = ""
                if cat_desp == "Outro (Nova Categoria)":
                    desc_nova = st.text_input("Nome do novo item/gasto", key=f"dn_desp_{fk}")

                cx1, cx2 = st.columns(2)
                val_desp = cx1.number_input("Valor Gasto (R$)", min_value=0.01, format="%.2f", key=f"vd_desp_{fk}")
                met_desp = cx2.selectbox("Método", ["PIX", "Cartão", "Dinheiro"], key=f"md_desp_{fk}")
                nota_desp = st.text_input("Fornecedor / Observação", key=f"nd_desp_{fk}")

                if st.button("Lançar Despesa do Evento", type="primary", use_container_width=True):
                    if val_desp > 0:
                        cat_final = desc_nova if cat_desp == "Outro (Nova Categoria)" else cat_desp
                        if cat_final.strip() == "":
                            st.error("Informe o nome do item/gasto.")
                        else:
                            inserir_dados('lancamentos', {
                                'data': str(d_desp), 'valor_bruto': val_desp, 'valor_imposto': 0,
                                'valor_liquido': val_desp, 'tipo': 'Saida', 'metodo_pagamento': met_desp,
                                'evento_id': ev_id_live, 'categoria': 'Eventos Gerais', 'descricao': f"[{ev_sel_live}] {cat_final} - {nota_desp}",
                                'operacao': 'A Vista'
                            })
                            st.session_state.sucesso_msg = "Despesa registrada no Caixa Geral e vinculada ao evento!"
                            resetar_form()
                            st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

            with col_live_2:
                st.subheader("Resumo em Tempo Real")

                df_l_live = buscar_dados('lancamentos', eq={'evento_id': ev_id_live}, order='id', order_desc=True)
                if not df_l_live.empty:
                    df_a_live = buscar_dados('alunos', select='id, nome')
                    if not df_a_live.empty:
                        df_lanc_live = pd.merge(df_l_live, df_a_live, left_on='aluno_id', right_on='id', how='left', suffixes=('', '_aluno'))
                    else:
                        df_lanc_live = df_l_live.copy()
                        df_lanc_live['nome'] = None

                    def build_desc(row):
                        if pd.notnull(row.get('nome')):
                            return f"Inscrição: {row['nome']}"
                        return row['descricao']

                    df_lanc_live['Descricao'] = df_lanc_live.apply(build_desc, axis=1)
                    df_lanc_live = df_lanc_live.rename(columns={'data': 'Data', 'tipo': 'Tipo', 'valor_bruto': 'Bruto', 'valor_liquido': 'Liquido', 'metodo_pagamento': 'Metodo'})

                    df_entradas = df_lanc_live[df_lanc_live['Tipo'] == 'Entrada']
                    df_saidas = df_lanc_live[df_lanc_live['Tipo'] == 'Saida'].copy()

                    tot_arrecadado_bruto = df_entradas['Bruto'].sum()
                    tot_impostos_retidos = df_entradas['valor_imposto'].sum()
                    tot_gasto = df_saidas['Liquido'].sum() + tot_impostos_retidos

                    st.success(f"📈 Total Arrecadado (Bruto): R$ {tot_arrecadado_bruto:.2f}")
                    st.dataframe(df_entradas[['Data', 'Descricao', 'Bruto']].rename(columns={'Bruto': 'Valor Entrada (R$)'}), use_container_width=True)

                    st.error(f"📉 Total Gasto Até Agora: R$ {tot_gasto:.2f}")

                    df_orc_live = buscar_dados('orcamento_eventos', eq={'evento_id': ev_id_live, 'tipo': 'Despesa'})
                    if not df_saidas.empty:
                        df_saidas['Categoria'] = df_saidas['Descricao'].apply(lambda x: extrair_item_evento(x, ev_sel_live))
                        df_saidas_agg = df_saidas.groupby('Categoria')['Liquido'].sum().reset_index()
                    else:
                        df_saidas_agg = pd.DataFrame(columns=['Categoria', 'Liquido'])

                    df_comp_saidas = pd.merge(df_saidas_agg, df_orc_live, left_on='Categoria', right_on='descricao', how='outer').fillna(0)
                    df_comp_saidas['Categoria'] = df_comp_saidas['Categoria'].replace(0, pd.NA).fillna(df_comp_saidas['descricao'])
                    df_comp_saidas = df_comp_saidas[['Categoria', 'valor', 'Liquido']].rename(columns={'valor': 'Orçamento (R$)', 'Liquido': 'Valor Saída (R$)'})

                    if tot_impostos_retidos > 0:
                        df_comp_saidas = pd.concat([df_comp_saidas, pd.DataFrame([{'Categoria': 'Impostos/Taxas Retidas', 'Orçamento (R$)': 0.0, 'Valor Saída (R$)': tot_impostos_retidos}])], ignore_index=True)

                    st.dataframe(df_comp_saidas, use_container_width=True)

                    st.markdown("---")
                    st.markdown("#### ✏️ Ajustar Lançamentos Realizados")

                    c_filtro1, c_filtro2 = st.columns(2)
                    f_tipo = c_filtro1.radio("Filtrar por:", ["Todos", "Entrada", "Saída"], horizontal=True, key=f"f_tipo_{fk}")
                    f_texto = c_filtro2.text_input("Buscar por descrição ou nome:", key=f"f_texto_{fk}")

                    df_filtro = df_lanc_live.copy()
                    if f_tipo == "Entrada":
                        df_filtro = df_filtro[df_filtro['Tipo'] == 'Entrada']
                    elif f_tipo == "Saída":
                        df_filtro = df_filtro[df_filtro['Tipo'] == 'Saida']

                    if f_texto:
                        df_filtro = df_filtro[df_filtro['Descricao'].str.contains(f_texto, case=False, na=False)]

                    if not df_filtro.empty:
                        lanc_options = df_filtro['id'].astype(str) + " - " + df_filtro['Data'] + " - " + df_filtro['Descricao'] + " (R$ " + df_filtro['Liquido'].astype(str) + ")"
                        lanc_sel = st.selectbox("Selecione o lançamento que deseja editar/remover:", ["Selecione..."] + lanc_options.tolist(), key=f"sel_adj_live_{fk}")

                        if lanc_sel != "Selecione...":
                            l_id = int(lanc_sel.split(" - ")[0])
                            l_dados = df_lanc_live[df_lanc_live['id'] == l_id].iloc[0]

                            c_adj1, c_adj2 = st.columns(2)
                            novo_valor = c_adj1.number_input("Novo Valor (R$)", value=float(l_dados['Bruto'] if l_dados['Tipo'] == 'Entrada' else l_dados['Liquido']), format="%.2f", key=f"nv_{fk}")
                            nova_data = c_adj2.date_input("Nova Data", value=pd.to_datetime(l_dados['Data']), format="DD/MM/YYYY", key=f"nd_{fk}")

                            c_btn1, c_btn2 = st.columns(2)
                            if c_btn1.button("Salvar Alteração", type="primary", use_container_width=True):
                                atualizar_dados('lancamentos', {'valor_bruto': novo_valor, 'valor_liquido': novo_valor, 'valor_imposto': 0, 'impostos_aplicados': '', 'data': str(nova_data)}, 'id', l_id)
                                st.session_state.sucesso_msg = "Lançamento atualizado com sucesso!"
                                resetar_form()
                                st.rerun()

                            st.markdown('<div class="btn-danger">', unsafe_allow_html=True)
                            if st.button("Remover Lançamento", use_container_width=True):
                                deletar_dados('lancamentos', 'id', l_id)
                                st.session_state.sucesso_msg = "Lançamento excluído permanentemente!"
                                resetar_form()
                                st.rerun()
                            st.markdown('</div>', unsafe_allow_html=True)
                    else:
                        st.info("Nenhum lançamento encontrado com estes filtros.")
                else:
                    st.info("Nenhuma movimentação real registrada no caixa para este evento ainda.")

        else:
            st.info("Nenhum evento 'Aberto' (Live) no momento.")

    elif etapa_evento == "3. Reconciliação & Fechar":
        evs_abertos = df_ev_todos[df_ev_todos['status'] == 'Aberto']
        if not evs_abertos.empty:
            ev_sel_close = st.selectbox("Selecione o Evento para Fechar as Contas:", evs_abertos['nome'].tolist(), key=f"ev_sel_close_{fk}")
            ev_id_close = int(evs_abertos[evs_abertos['nome'] == ev_sel_close]['id'].iloc[0])

            st.warning("🔒 **Aviso:** Verifique os gastos e entradas. Adicione qualquer item pendente ou esquecido, e depois encerre o evento.")

            df_orc_close = buscar_dados('orcamento_eventos', eq={'evento_id': ev_id_close})
            df_lanc_close = buscar_dados('lancamentos', eq={'evento_id': ev_id_close})

            st.markdown("### Comparativo (Orçado vs Realizado até o momento)")

            linhas_recon = []

            tot_imposto = df_lanc_close[df_lanc_close['tipo'] == 'Entrada']['valor_imposto'].sum() if not df_lanc_close.empty else 0.0

            df_lanc_saida = df_lanc_close[df_lanc_close['tipo'] == 'Saida'].copy()
            if not df_lanc_saida.empty:
                df_lanc_saida['Item'] = df_lanc_saida['descricao'].apply(lambda x: extrair_item_evento(x, ev_sel_close))
            else:
                df_lanc_saida = pd.DataFrame(columns=['Item', 'valor_liquido'])

            itens_desp = set(df_orc_close[df_orc_close['tipo'] == 'Despesa']['descricao'].tolist() + df_lanc_saida['Item'].tolist())
            for item in itens_desp:
                val_o = df_orc_close[(df_orc_close['tipo'] == 'Despesa') & (df_orc_close['descricao'] == item)]['valor'].sum()
                val_r = df_lanc_saida[df_lanc_saida['Item'] == item]['valor_liquido'].sum() if not df_lanc_saida.empty else 0.0
                linhas_recon.append({"Natureza": "Despesa", "Categoria / Item": item, "Orçado (R$)": val_o, "Realizado (R$)": val_r, "Diferença (R$)": val_o - val_r})

            if tot_imposto > 0:
                linhas_recon.append({"Natureza": "Despesa", "Categoria / Item": "Impostos/Taxas Retidas", "Orçado (R$)": 0.0, "Realizado (R$)": tot_imposto, "Diferença (R$)": 0.0 - tot_imposto})

            val_rec_o = df_orc_close[df_orc_close['tipo'] == 'Receita']['valor'].sum()
            ent_real = df_lanc_close[df_lanc_close['tipo'] == 'Entrada']['valor_bruto'].sum() if not df_lanc_close.empty else 0.0
            linhas_recon.append({"Natureza": "Receita", "Categoria / Item": "Total de Entradas (Inscrições/Bruto)", "Orçado (R$)": val_rec_o, "Realizado (R$)": ent_real, "Diferença (R$)": ent_real - val_rec_o})

            df_recon_table = pd.DataFrame(linhas_recon).sort_values('Natureza', ascending=False)
            st.dataframe(df_recon_table, use_container_width=True)

            total_real = (df_lanc_saida['valor_liquido'].sum() if not df_lanc_saida.empty else 0) + tot_imposto
            st.write(f"**Soma de Todos os Gastos Lançados no 'Live' até o momento:** R$ {total_real:.2f}")

            st.markdown("---")
            st.markdown("### Adicionar Lançamento Esquecido")
            st.write("Adicione despesas finais ou ingressos vendidos de última hora.")

            st.markdown("<div style='background-color:#f1f3f5; padding:15px; border-radius:8px;'>", unsafe_allow_html=True)
            tipo_mov = st.radio("Tipo de Movimento", ["Entrada (Receita)", "Saída (Despesa)"], horizontal=True, key=f"t_mov_{fk}")

            df_alunos = buscar_dados('alunos', eq={'ativo': 1}, order='nome')

            if tipo_mov == "Entrada (Receita)":
                tipo_inscrito_f = st.radio("Origem da Inscrição:", ["Aluno (Interno)", "Convidado (Externo)"], horizontal=True, key=f"t_insc_f_{fk}")
                if tipo_inscrito_f == "Aluno (Interno)":
                    aluno_nome_f = st.selectbox("Selecione o Aluno", df_alunos['nome'].tolist() if not df_alunos.empty else ["Nenhum aluno cadastrado"], key=f"a_nm_f_{fk}")
                    desc_adj = f"Inscrição: {aluno_nome_f}"
                else:
                    nome_ext_f = st.text_input("Nome do Convidado Livre", key=f"n_ext_f_{fk}")
                    desc_adj = f"Inscrição: {nome_ext_f}"
            else:
                cat_options = df_orc_close[df_orc_close['tipo'] == 'Despesa']['descricao'].tolist()
                cat_options.append("Outro (Nova Categoria)")
                cat_desp_f = st.selectbox("Categoria", cat_options, key=f"c_dsp_f_{fk}")
                if cat_desp_f == "Outro (Nova Categoria)":
                    desc_nova_f = st.text_input("Nome do novo item", key=f"d_nv_f_{fk}")
                    cat_final_f = desc_nova_f
                else:
                    cat_final_f = cat_desp_f

                nota_desp_f = st.text_input("Fornecedor / Obs", key=f"n_dsp_f_{fk}")
                desc_adj = f"[{ev_sel_close}] {cat_final_f} - {nota_desp_f}"

            c_adj1, c_adj2 = st.columns(2)
            v_adj = c_adj1.number_input("Valor Bruto/Líquido (R$)", min_value=0.01, value=0.01, format="%.2f", key=f"v_adj_{fk}")
            met_adj = c_adj2.selectbox("Método de Pagamento", ["PIX", "Dinheiro", "Cartão"], key=f"m_adj_{fk}")

            if st.button("Inserir Lançamento no Caixa e Atualizar", type="primary"):
                if tipo_mov == "Entrada (Receita)" and tipo_inscrito_f == "Convidado (Externo)" and not nome_ext_f:
                    st.error("Digite o nome do convidado.")
                elif tipo_mov == "Saída (Despesa)" and cat_desp_f == "Outro (Nova Categoria)" and not desc_nova_f:
                    st.error("Digite o nome do item.")
                else:
                    aluno_id_val = int(df_alunos[df_alunos['nome'] == aluno_nome_f]['id'].iloc[0]) if (tipo_mov == "Entrada (Receita)" and tipo_inscrito_f == "Aluno (Interno)") else None
                    tipo_db = "Saida" if tipo_mov == "Saída (Despesa)" else "Entrada"
                    cat_db = "Eventos Gerais" if tipo_db == "Saida" else "Inscrição Evento"

                    inserir_dados('lancamentos', {
                        'data': str(date.today()), 'valor_bruto': v_adj, 'valor_imposto': 0,
                        'valor_liquido': v_adj, 'tipo': tipo_db, 'metodo_pagamento': met_adj,
                        'aluno_id': aluno_id_val, 'evento_id': ev_id_close, 'categoria': cat_db,
                        'descricao': desc_adj, 'operacao': 'A Vista'
                    })
                    st.session_state.sucesso_msg = "Lançamento inserido! A tabela acima foi atualizada."
                    resetar_form()
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("---")
            if st.button("🔒 Finalizar Reconciliação e Encerrar Evento", use_container_width=True, type="primary"):
                atualizar_dados('eventos', {'status': 'Encerrado'}, 'id', ev_id_close)
                st.session_state.sucesso_msg = "Evento encerrado com sucesso! Veja o resultado final em Relatório (SOA)."
                resetar_form()
                st.rerun()
        else:
            st.info("Nenhum evento 'Aberto' para fechar.")

    elif etapa_evento == "4. Relatório (SOA)":
        evs_encerrados = df_ev_todos[df_ev_todos['status'] == 'Encerrado']
        if not evs_encerrados.empty:
            ev_sel_soa = st.selectbox("Selecione o Evento Concluído:", evs_encerrados['nome'].tolist(), key=f"ev_sel_soa_{fk}")
            ev_id_soa = int(evs_encerrados[evs_encerrados['nome'] == ev_sel_soa]['id'].iloc[0])

            df_lanc_ev = buscar_dados('lancamentos', eq={'evento_id': ev_id_soa})
            ent_real = df_lanc_ev[df_lanc_ev['tipo'] == 'Entrada']['valor_bruto'].sum() if not df_lanc_ev.empty else 0.0
            tot_imposto = df_lanc_ev[df_lanc_ev['tipo'] == 'Entrada']['valor_imposto'].sum() if not df_lanc_ev.empty else 0.0
            sai_real = (df_lanc_ev[df_lanc_ev['tipo'] == 'Saida']['valor_liquido'].sum() if not df_lanc_ev.empty else 0.0) + tot_imposto
            lucro_real = ent_real - sai_real
            margem_real = (lucro_real / ent_real * 100) if ent_real > 0 else 0.0

            df_orc_ev_d = buscar_dados('orcamento_eventos', eq={'evento_id': ev_id_soa})
            ent_proj = df_orc_ev_d[df_orc_ev_d['tipo'] == 'Receita']['valor'].sum() if not df_orc_ev_d.empty else 0.0
            sai_proj = df_orc_ev_d[df_orc_ev_d['tipo'] == 'Despesa']['valor'].sum() if not df_orc_ev_d.empty else 0.0
            lucro_proj = ent_proj - sai_proj

            st.markdown("### Resumo Executivo (Variância)")
            c1, c2, c3 = st.columns(3)
            c1.metric("Receita Arrecadada (Bruta)", f"R$ {ent_real:,.2f}", f"{ent_real - ent_proj:,.2f} vs Orçado")
            c2.metric("Custo Final", f"R$ {sai_real:,.2f}", f"{sai_real - sai_proj:,.2f} vs Orçado", delta_color="inverse")
            c3.metric("Lucro Líquido", f"R$ {lucro_real:,.2f}", f"Margem: {margem_real:.1f}%")

            df_desvio = pd.DataFrame({
                "Métrica": ["Receitas", "Receitas", "Despesas", "Despesas"],
                "Tipo": ["Orçado", "Realizado", "Orçado", "Realizado"],
                "Valor": [ent_proj, ent_real, sai_proj, sai_real]
            })
            fig_desvio = px.bar(df_desvio, x="Métrica", y="Valor", color="Tipo", barmode="group", template="plotly_white",
                                color_discrete_map={"Orçado": "#a6a6a6", "Realizado": "#2E7D32"})
            st.plotly_chart(fig_desvio, use_container_width=True)

            st.markdown("---")
            st.markdown("### Detalhamento Financeiro (Orçado vs Realizado)")
            linhas_soa = []

            df_lanc_saida = df_lanc_ev[df_lanc_ev['tipo'] == 'Saida'].copy()
            if not df_lanc_saida.empty:
                df_lanc_saida['Item'] = df_lanc_saida['descricao'].apply(lambda x: extrair_item_evento(x, ev_sel_soa))
            else:
                df_lanc_saida = pd.DataFrame(columns=['Item', 'valor_liquido'])

            itens_desp = set(df_orc_ev_d[df_orc_ev_d['tipo'] == 'Despesa']['descricao'].tolist() + df_lanc_saida['Item'].tolist())
            for item in itens_desp:
                val_o = df_orc_ev_d[(df_orc_ev_d['tipo'] == 'Despesa') & (df_orc_ev_d['descricao'] == item)]['valor'].sum()
                val_r = df_lanc_saida[df_lanc_saida['Item'] == item]['valor_liquido'].sum() if not df_lanc_saida.empty else 0.0
                linhas_soa.append({"Natureza": "Despesa", "Categoria / Item": item, "Orçado (R$)": val_o, "Realizado (R$)": val_r, "Diferença (R$)": val_o - val_r})

            if tot_imposto > 0:
                linhas_soa.append({"Natureza": "Despesa", "Categoria / Item": "Impostos/Taxas Retidas", "Orçado (R$)": 0.0, "Realizado (R$)": tot_imposto, "Diferença (R$)": 0.0 - tot_imposto})

            val_rec_o = df_orc_ev_d[df_orc_ev_d['tipo'] == 'Receita']['valor'].sum()
            linhas_soa.append({"Natureza": "Receita", "Categoria / Item": "Total de Entradas (Inscrições/Bruto)", "Orçado (R$)": val_rec_o, "Realizado (R$)": ent_real, "Diferença (R$)": ent_real - val_rec_o})

            df_detalhe_soa = pd.DataFrame(linhas_soa).sort_values('Natureza', ascending=False)
            st.dataframe(df_detalhe_soa, use_container_width=True)

            st.markdown("---")
            html_soa = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; color: #333; }}
                    h1 {{ color: #2c3e50; border-bottom: 2px solid #2E7D32; padding-bottom: 10px; }}
                    .box {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
                    th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
                    th {{ background-color: #2E7D32; color: white; }}
                    .verde {{ color: #2E7D32; font-weight: bold; }}
                    .vermelho {{ color: #d32f2f; font-weight: bold; }}
                </style>
            </head>
            <body>
                <h1>Statement of Accounts (SOA) - {ev_sel_soa}</h1>
                <p><strong>Data de Emissão:</strong> {date.today().strftime('%d/%m/%Y')}</p>
                <div class="box">
                    <h3>Resumo Financeiro (Orçado vs Realizado)</h3>
                    <table>
                        <tr><th>Métrica</th><th>Orçamento Projetado</th><th>Execução Real</th><th>Variância</th></tr>
                        <tr><td>Receitas</td><td>R$ {ent_proj:.2f}</td><td>R$ {ent_real:.2f}</td><td>R$ {ent_real - ent_proj:.2f}</td></tr>
                        <tr><td>Despesas</td><td>R$ {sai_proj:.2f}</td><td>R$ {sai_real:.2f}</td><td>R$ {sai_real - sai_proj:.2f}</td></tr>
                        <tr><td><strong>LUCRO LÍQUIDO</strong></td><td><strong>R$ {lucro_proj:.2f}</strong></td><td><strong class="verde">R$ {lucro_real:.2f}</strong></td><td><strong>R$ {lucro_real - lucro_proj:.2f}</strong></td></tr>
                    </table>
                    <p><strong>Margem de Lucro Final Alcançada:</strong> {margem_real:.1f}%</p>
                </div>
            </body>
            </html>
            """
            b64 = base64.b64encode(html_soa.encode()).decode()
            href = f'<a href="data:text/html;base64,{b64}" download="SOA_{ev_sel_soa.replace(" ", "_")}.html"><button style="background-color:#2E7D32; color:white; padding:10px 20px; border:none; border-radius:5px; cursor:pointer; font-weight:bold;">📄 Baixar Relatório (SOA) em PDF</button></a>'
            st.markdown(href, unsafe_allow_html=True)
            st.caption("*Dica: Ao abrir o arquivo baixado no navegador, aperte Ctrl+P e escolha 'Salvar como PDF'.*")

            st.markdown("---")
            if st.button("⚠️ Reabrir Evento (Devolver para Fase 'Live')", help="Caso tenha fechado sem querer e precise editar despesas ou inscrições.", type="primary"):
                atualizar_dados('eventos', {'status': 'Aberto'}, 'id', ev_id_soa)
                st.session_state.sucesso_msg = "Evento reaberto! Você pode fazer novos lançamentos na aba 'Evento Aberto (Live)'."
                resetar_form()
                st.rerun()

        else:
            st.info("Nenhum evento encerrado para gerar prestação de contas.")
