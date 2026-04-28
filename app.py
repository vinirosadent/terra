import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import json
import base64
import os
from db import buscar_dados, inserir_dados, atualizar_dados, deletar_dados
from auth import inicializar_session_state_auth, mostrar_tela_login, fazer_logout
from utils import extrair_item_evento, resetar_form
from paginas import log as pg_log
from paginas import configuracoes as pg_configuracoes
from paginas import clientes as pg_clientes
from paginas import eventos as pg_eventos

# --- CONFIGURAÇÃO DA PÁGINA E ESTILIZAÇÃO ---
st.set_page_config(page_title="App da Terra | Gestão", page_icon="🌿", layout="wide")

# CSS global extraido para styles.py na Etapa D.2 do refactor.
# Conteudo do CSS preservado byte-a-byte.
from styles import aplicar_estilo_global
aplicar_estilo_global()

# --- GERENCIAMENTO DE ESTADO (LOGIN E FORMS) ---
if "form_key" not in st.session_state:
    st.session_state.form_key = 0

inicializar_session_state_auth()


# ==========================================
# 0. TELA DE LOGIN E AUTENTICAÇÃO (Supabase Auth — Etapa B)
# ==========================================
if not st.session_state.logged_in:
    mostrar_tela_login()

# Se estiver logado, exibe todo o sistema:
else:
    if "sucesso_msg" in st.session_state:
        st.success(st.session_state.sucesso_msg)
        del st.session_state.sucesso_msg
    
    fk = st.session_state.form_key 

    # --- MENU LATERAL ---
    with st.sidebar:
        if os.path.exists("logo.jpeg"):
            st.image("logo.jpeg", use_container_width=True)
        else:
            st.title("🌿 App da Terra")
            
        st.markdown(f"**Logado como:** {st.session_state.user}")
            
        st.markdown("---")
        menu = st.radio("Módulos", [
            "📈 Inteligência (BI)", 
            "💰 Recebíveis", 
            "💸 Operações (Caixa)", 
            "📅 Gestão de Eventos",
            "🎯 Orçamento & Metas",
            "👤 Gestão de Clientes",
            "⚙️ Configurações",
            "📜 Log de Lançamentos"
        ])
        
        st.markdown("<br>" * 10, unsafe_allow_html=True)
        st.markdown("---")
        if st.button("Sair (Logout)", key="btn_logout"):
            fazer_logout()
            st.rerun()

    # ==========================================
    # 1. INTELIGÊNCIA (BI)
    # ==========================================
    if menu == "📈 Inteligência (BI)":
        st.title("📈 Dashboard Gerencial (BI)")
        
        df_lanc = buscar_dados('lancamentos')
        df_alunos = buscar_dados('alunos')
        df_orc = buscar_dados('orcamentos')
        df_cats = buscar_dados('categorias_saida')
        
        if df_lanc.empty:
            st.info("Nenhum lançamento financeiro registrado. Registre operações para visualizar a Dashboard.")
        else:
            st.markdown("### Configurações de Análise")
            incluir_eventos = st.toggle("🎉 Incluir Receitas e Despesas de EVENTOS nos gráficos", value=False)
            
            if not incluir_eventos:
                df_lanc = df_lanc[df_lanc['evento_id'].isna() | (df_lanc['evento_id'] == "")]
                
            df_lanc['data'] = pd.to_datetime(df_lanc['data'])
            df_alunos['data_cadastro'] = pd.to_datetime(df_alunos['data_cadastro'], errors='coerce')
            df_alunos['data_cancelamento'] = pd.to_datetime(df_alunos['data_cancelamento'], errors='coerce')
            
            c_v1, c_v2 = st.columns(2)
            agregacao = c_v1.radio("Agrupar dados por:", ["Mensal", "Trimestral", "Anual"], horizontal=True)
            
            if agregacao == "Mensal":
                df_lanc['Periodo'] = df_lanc['data'].dt.strftime('%Y-%m')
                df_alunos['Periodo_Cad'] = df_alunos['data_cadastro'].dt.strftime('%Y-%m')
                df_alunos['Periodo_Canc'] = df_alunos['data_cancelamento'].dt.strftime('%Y-%m')
            elif agregacao == "Trimestral":
                df_lanc['Periodo'] = df_lanc['data'].dt.to_period('Q').astype(str)
                df_alunos['Periodo_Cad'] = df_alunos['data_cadastro'].dt.to_period('Q').astype(str)
                df_alunos['Periodo_Canc'] = df_alunos['data_cancelamento'].dt.to_period('Q').astype(str)
            else: 
                df_lanc['Periodo'] = df_lanc['data'].dt.strftime('%Y')
                df_alunos['Periodo_Cad'] = df_alunos['data_cadastro'].dt.strftime('%Y')
                df_alunos['Periodo_Canc'] = df_alunos['data_cancelamento'].dt.strftime('%Y')
                
            periodos_disp = sorted(df_lanc['Periodo'].unique().tolist(), reverse=True)
            periodo_sel = c_v2.selectbox("Selecione o Período para análise detalhada:", ["Todos"] + periodos_disp)
            
            df_f = df_lanc.copy()
            if periodo_sel != "Todos":
                df_f = df_f[df_f['Periodo'] == periodo_sel]
            
            receita_bruta = df_f[df_f['tipo'] == 'Entrada']['valor_bruto'].sum()
            impostos = df_f['valor_imposto'].sum()
            receita_liq = df_f[df_f['tipo'] == 'Entrada']['valor_liquido'].sum()
            despesa = df_f[df_f['tipo'] == 'Saida']['valor_liquido'].sum()
            lucro = receita_liq - despesa
            margem = (lucro / receita_liq * 100) if receita_liq > 0 else 0
            
            if periodo_sel != "Todos":
                cli_ativos = len(df_alunos[(df_alunos['Periodo_Cad'] <= periodo_sel) & ((df_alunos['ativo'] == 1) | (df_alunos['Periodo_Canc'] > periodo_sel))])
                novos_cli = len(df_alunos[df_alunos['Periodo_Cad'] == periodo_sel])
                canc_cli = len(df_alunos[df_alunos['Periodo_Canc'] == periodo_sel])
            else:
                cli_ativos = len(df_alunos[df_alunos['ativo'] == 1])
                novos_cli = len(df_alunos[df_alunos['data_cadastro'].notnull()])
                canc_cli = len(df_alunos[df_alunos['data_cancelamento'].notnull()])
                
            cresc_liq = novos_cli - canc_cli
            
            st.markdown("---")
            st.subheader("DRE Simplificado")
            cc1, cc2, cc3, cc4, cc5 = st.columns(5)
            cc1.metric("Receita Bruta", f"R$ {receita_bruta:,.2f}")
            cc2.metric("Impostos/Taxas", f"R$ {impostos:,.2f}", "Retido", delta_color="inverse")
            cc3.metric("Receita Líquida", f"R$ {receita_liq:,.2f}")
            cc4.metric("Despesas", f"R$ {despesa:,.2f}")
            cc5.metric("Lucro Real", f"R$ {lucro:,.2f}", f"{margem:.1f}% Margem")
            
            st.markdown("---")
            st.subheader("Indicadores Operacionais (Clientes)")
            cx1, cx2, cx3, cx4 = st.columns(4)
            cx1.metric("Clientes Ativos", cli_ativos)
            cx2.metric("Novos Clientes", novos_cli)
            cx3.metric("Cancelamentos", canc_cli)
            cx4.metric("Crescimento Líquido", cresc_liq)

            st.markdown("---")

            row1_1, row1_2 = st.columns(2)
            with row1_1:
                st.subheader("A. Receita, Despesa e Lucro")
                tipo_gA = st.radio("Visualização (A):", ["Linhas", "Barras"], horizontal=True, key="ga_rad")
                df_gA_r = df_lanc[df_lanc['tipo'] == 'Entrada'].groupby('Periodo')['valor_liquido'].sum().reset_index().rename(columns={'valor_liquido': 'Receita'})
                df_gA_d = df_lanc[df_lanc['tipo'] == 'Saida'].groupby('Periodo')['valor_liquido'].sum().reset_index().rename(columns={'valor_liquido': 'Despesa'})
                df_gA = pd.merge(df_gA_r, df_gA_d, on='Periodo', how='outer').fillna(0).sort_values('Periodo')
                df_gA['Lucro'] = df_gA['Receita'] - df_gA['Despesa']
                
                fig_gA = go.Figure()
                if tipo_gA == "Linhas":
                    fig_gA.add_trace(go.Scatter(x=df_gA['Periodo'], y=df_gA['Receita'], name='Receita', marker_color='#2E7D32', mode='lines+markers'))
                    fig_gA.add_trace(go.Scatter(x=df_gA['Periodo'], y=df_gA['Despesa'], name='Despesa', marker_color='#d32f2f', mode='lines+markers'))
                    fig_gA.add_trace(go.Scatter(x=df_gA['Periodo'], y=df_gA['Lucro'], name='Lucro', marker_color='#0288d1', mode='lines+markers'))
                else:
                    fig_gA.add_trace(go.Bar(x=df_gA['Periodo'], y=df_gA['Receita'], name='Receita', marker_color='#2E7D32'))
                    fig_gA.add_trace(go.Bar(x=df_gA['Periodo'], y=df_gA['Despesa'], name='Despesa', marker_color='#d32f2f'))
                    fig_gA.add_trace(go.Bar(x=df_gA['Periodo'], y=df_gA['Lucro'], name='Lucro', marker_color='#0288d1'))
                    fig_gA.update_layout(barmode='group')
                fig_gA.update_layout(template='plotly_white', hovermode="x unified")
                st.plotly_chart(fig_gA, use_container_width=True)

            with row1_2:
                st.subheader("G. Orçado vs Realizado")
                tipo_gG = st.radio("Comparar (G):", ["Despesas", "Receitas"], horizontal=True, key="gg_rad")
                if df_orc.empty:
                    st.info("Cadastre orçamentos mensais para visualizar a comparação.")
                else:
                    if tipo_gG == "Despesas":
                        df_real = df_lanc[df_lanc['tipo'] == 'Saida'].copy()
                        df_real['mes'] = df_real['data'].dt.strftime('%Y-%m')
                        df_real = df_real.groupby('mes')['valor_liquido'].sum().reset_index()
                        df_o = df_orc[df_orc['tipo'] == 'Despesa'].groupby('mes')['valor'].sum().reset_index()
                    else:
                        df_real = df_lanc[df_lanc['tipo'] == 'Entrada'].copy()
                        df_real['mes'] = df_real['data'].dt.strftime('%Y-%m')
                        df_real = df_real.groupby('mes')['valor_liquido'].sum().reset_index()
                        df_o = df_orc[df_orc['tipo'] == 'Receita'].groupby('mes')['valor'].sum().reset_index()
                    
                    df_real = df_real.rename(columns={'valor_liquido': 'Realizado'})
                    df_o = df_o.rename(columns={'valor': 'Orçado'})
                    df_comp = pd.merge(df_o, df_real, on='mes', how='outer').fillna(0).sort_values('mes')
                    
                    fig_gG = go.Figure()
                    fig_gG.add_trace(go.Bar(x=df_comp['mes'], y=df_comp['Orçado'], name='Orçado', marker_color='#a6a6a6'))
                    fig_gG.add_trace(go.Bar(x=df_comp['mes'], y=df_comp['Realizado'], name='Realizado', marker_color='#0288d1'))
                    fig_gG.update_layout(barmode='group', template='plotly_white', hovermode="x unified")
                    st.plotly_chart(fig_gG, use_container_width=True)

            st.markdown("---")

            row2_1, row2_2 = st.columns(2)
            with row2_1:
                st.subheader("B. Receita por Serviço")
                tipo_gB = st.radio("Visualização (B):", ["Donut", "Barras"], horizontal=True, key="gb_rad")
                df_gB = df_f[df_f['tipo'] == 'Entrada']
                if not df_gB.empty:
                    df_gB_exp = df_gB.assign(categoria=df_gB['categoria'].str.split(', ')).explode('categoria')
                    df_gB_agg = df_gB_exp.groupby('categoria')['valor_liquido'].sum().reset_index()
                    if tipo_gB == "Donut": fig_gB = px.pie(df_gB_agg, values='valor_liquido', names='categoria', hole=0.5, template='plotly_white')
                    else: fig_gB = px.bar(df_gB_agg, x='categoria', y='valor_liquido', color='categoria', template='plotly_white')
                    st.plotly_chart(fig_gB, use_container_width=True)
                else:
                    st.write("Sem receitas no período.")

            with row2_2:
                st.subheader("C. Despesas por Categoria")
                tipo_gC = st.radio("Visualização (C):", ["Donut", "Barras"], horizontal=True, key="gc_rad")
                df_gC = df_f[df_f['tipo'] == 'Saida']
                if not df_gC.empty:
                    df_gC_agg = df_gC.groupby('categoria')['valor_liquido'].sum().reset_index()
                    if tipo_gC == "Donut": fig_gC = px.pie(df_gC_agg, values='valor_liquido', names='categoria', hole=0.5, template='plotly_white', color_discrete_sequence=px.colors.sequential.Reds)
                    else: fig_gC = px.bar(df_gC_agg, x='categoria', y='valor_liquido', color='categoria', template='plotly_white')
                    st.plotly_chart(fig_gC, use_container_width=True)
                else:
                    st.write("Sem despesas no período.")

            st.markdown("---")

            row3_1, row3_2 = st.columns(2)
            with row3_1:
                st.subheader("D. Custos Fixos vs Variáveis")
                tipo_gD = st.radio("Visualização (D):", ["Pizza", "Barras"], horizontal=True, key="gd_rad")
                df_gC = df_f[df_f['tipo'] == 'Saida']
                if not df_gC.empty and not df_cats.empty:
                    df_gD_merged = pd.merge(df_gC, df_cats, left_on='categoria', right_on='nome', how='left')
                    df_gD_merged['tipo_custo'] = df_gD_merged['tipo_custo'].fillna('Outros')
                    df_gD_agg = df_gD_merged.groupby('tipo_custo')['valor_liquido'].sum().reset_index()
                    if tipo_gD == "Pizza": fig_gD = px.pie(df_gD_agg, values='valor_liquido', names='tipo_custo', template='plotly_white', color_discrete_map={'Fixo': '#424242', 'Variável': '#fbc02d', 'Outros': '#0288d1'})
                    else: fig_gD = px.bar(df_gD_agg, x='tipo_custo', y='valor_liquido', color='tipo_custo', template='plotly_white', color_discrete_map={'Fixo': '#424242', 'Variável': '#fbc02d', 'Outros': '#0288d1'})
                    st.plotly_chart(fig_gD, use_container_width=True)
                else:
                    st.write("Sem despesas cadastradas.")

            with row3_2:
                st.subheader("E & F. Fluxo de Clientes")
                tipo_gF = st.radio("Visualização (E/F):", ["Barras (Novos vs Cancelados)", "Linhas (Clientes Ativos)"], horizontal=True, key="gf_rad")
                df_cad = df_alunos[df_alunos['data_cadastro'].notnull()].copy()
                ent_cli = df_cad.groupby('Periodo_Cad').size().reset_index(name='Novos').rename(columns={'Periodo_Cad':'Periodo'})
                df_canc = df_alunos[df_alunos['data_cancelamento'].notnull()].copy()
                sai_cli = df_canc.groupby('Periodo_Canc').size().reset_index(name='Cancelados').rename(columns={'Periodo_Canc':'Periodo'})
                df_cli_fluxo = pd.merge(ent_cli, sai_cli, on='Periodo', how='outer').fillna(0).sort_values('Periodo')
                
                if not df_cli_fluxo.empty:
                    if tipo_gF == "Barras (Novos vs Cancelados)":
                        fig_gF = go.Figure()
                        fig_gF.add_trace(go.Bar(x=df_cli_fluxo['Periodo'], y=df_cli_fluxo['Novos'], name='Novos Clientes', marker_color='#2E7D32'))
                        fig_gF.add_trace(go.Bar(x=df_cli_fluxo['Periodo'], y=df_cli_fluxo['Cancelados'], name='Cancelados', marker_color='#d32f2f'))
                        fig_gF.update_layout(barmode='group', template='plotly_white', hovermode="x unified")
                        st.plotly_chart(fig_gF, use_container_width=True)
                    else:
                        periodos_unicos = sorted(df_cli_fluxo['Periodo'].unique().tolist())
                        ativos_hist = []
                        for p in periodos_unicos:
                            ativos_n = len(df_alunos[(df_alunos['Periodo_Cad'] <= p) & ((df_alunos['ativo'] == 1) | (df_alunos['Periodo_Canc'] > p))])
                            ativos_hist.append({'Periodo': p, 'Ativos': ativos_n})
                        df_ativos_hist = pd.DataFrame(ativos_hist)
                        fig_gF = px.line(df_ativos_hist, x='Periodo', y='Ativos', markers=True, template='plotly_white')
                        fig_gF.update_traces(line_color='#0288d1')
                        fig_gF.update_layout(hovermode="x unified")
                        st.plotly_chart(fig_gF, use_container_width=True)
                else:
                    st.write("Sem histórico de clientes.")

    # ==========================================
    # 2. RECEBÍVEIS & INADIMPLÊNCIA
    # ==========================================
    elif menu == "💰 Recebíveis":
        st.title("💰 Gestão de Contas a Receber (Vencimento Dia 20)")
        
        hoje = pd.to_datetime(date.today())
        vencimento_mes_atual = pd.to_datetime(f"{hoje.year}-{hoje.month:02d}-20")
        df_alunos = buscar_dados('alunos', eq={'ativo': 1})
        
        if not df_alunos.empty:
            df_alunos['pago_ate'] = pd.to_datetime(df_alunos['pago_ate'], errors='coerce')
            df_alunos['Status Pagamento'] = df_alunos['pago_ate'].apply(lambda x: '🟢 Em Dia (Coberto)' if pd.notnull(x) and x >= vencimento_mes_atual else '🔴 Pendente / Atrasado')
            df_pagos = df_alunos[df_alunos['Status Pagamento'] == '🟢 Em Dia (Coberto)']
            df_pendentes = df_alunos[df_alunos['Status Pagamento'] == '🔴 Pendente / Atrasado']
            
            expectativa = df_alunos['valor_total'].sum()
            recebido = df_pagos['valor_total'].sum()
            pendente = expectativa - recebido
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Faturação Prevista (Mês)", f"R$ {expectativa:,.2f}")
            c2.metric("Já Coberto/Pago", f"R$ {recebido:,.2f}")
            c3.metric("Pendente (Risco)", f"R$ {pendente:,.2f}")
            
            progresso = min(recebido / expectativa, 1.0) if expectativa > 0 else 0.0
            st.progress(progresso)
            
            aba_receb = st.radio("Filtrar Visão:", ["🔴 Atrasados/Pendentes", "🟢 Pagos/Cobertos"], horizontal=True, key=f"r_rec_{fk}")
            if aba_receb == "🔴 Atrasados/Pendentes":
                st.dataframe(df_pendentes[['nome', 'valor_total']].rename(columns={"nome": "Cliente", "valor_total": "Valor (R$)"}), use_container_width=True)
            else:
                df_g = df_pagos[['nome', 'pago_ate']].copy()
                df_g['pago_ate'] = df_g['pago_ate'].dt.strftime('%d/%m/%Y')
                st.dataframe(df_g.rename(columns={"nome": "Cliente", "pago_ate": "Coberto Até"}), use_container_width=True)

    # ==========================================
    # 3. OPERAÇÕES (CAIXA GERAL)
    # ==========================================
    elif menu == "💸 Operações (Caixa)":
        st.title("💸 Registro de Operações (Caixa Geral)")
        
        movimento = st.radio("Natureza da Operação", ["ENTRADA", "SAÍDA"], horizontal=True, key=f"mov_{fk}")
        st.markdown("---")
        
        if movimento == "ENTRADA":
            df_alunos = buscar_dados('alunos', eq={'ativo': 1}, order='nome')
            df_impostos = buscar_dados('impostos', order='nome')
            df_eventos = buscar_dados('eventos', in_col='status', in_vals=['Aberto', 'Planejamento'], order='nome')
            
            aluno_nomes = ["Pessoa Externa / Avulso"] + df_alunos['nome'].tolist() if not df_alunos.empty else ["Pessoa Externa / Avulso"]
            imposto_nomes = df_impostos['nome'].tolist() if not df_impostos.empty else []
            evento_nomes = ["Nenhum"] + df_eventos['nome'].tolist() if not df_eventos.empty else ["Nenhum"]
            
            c1, c2 = st.columns(2)
            with c1:
                data_op = st.date_input("Data do Recebimento", value=date.today(), format="DD/MM/YYYY", key=f"d_e_{fk}")
                aluno_sel = st.selectbox("Cliente / Origem *", ["Selecione..."] + aluno_nomes, key=f"al_e_{fk}")
                evento_sel = st.selectbox("Vincular a Evento?", evento_nomes, key=f"ev_e_{fk}")
                
                valor_mensal = 0.0
                desc_sugerida = ""
                al_id_str = "0"
                if aluno_sel not in ["Selecione...", "Pessoa Externa / Avulso"]:
                    dados_al = df_alunos[df_alunos['nome'] == aluno_sel].iloc[0]
                    al_id_str = str(dados_al['id'])
                    valor_mensal = float(dados_al['valor_total'])
                    try:
                        planos = json.loads(dados_al['planos'])
                        desc_sugerida = ", ".join([p['modalidade'] for p in planos])
                    except: desc_sugerida = "Mensalidade"
                        
                qtd_meses = st.number_input("Pagamento cobre quantos meses? (Pacote)", min_value=1, value=1, step=1, key=f"meses_{fk}")
                impostos_sel = st.multiselect("Impostos/Taxas Aplicáveis", imposto_nomes, key=f"imp_e_{fk}")

            with c2:
                metodo = st.radio("Método", ["PIX", "Dinheiro", "Cartão"], horizontal=True, key=f"met_e_{fk}")
                valor_sug_total = valor_mensal * qtd_meses if valor_mensal > 0 else None
                valor_cobrado = st.number_input("Valor Bruto Recebido (R$) *", min_value=0.0, value=valor_sug_total, format="%.2f", key=f"v_c_{al_id_str}_{qtd_meses}_{fk}")
                
                v_liq = 0.0
                v_imp = 0.0
                if valor_cobrado is not None:
                    aliq_total = sum([df_impostos[df_impostos['nome'] == i]['aliquota'].iloc[0] for i in impostos_sel]) if impostos_sel else 0.0
                    v_imp = valor_cobrado * (aliq_total / 100)
                    v_liq = valor_cobrado - v_imp
                    st.info(f"**Líquido Retido: R$ {v_liq:.2f}** | Taxas Descontadas: R$ {v_imp:.2f}")
                
                justificativa = ""
                if aluno_sel not in ["Selecione...", "Pessoa Externa / Avulso"] and valor_cobrado is not None and valor_sug_total is not None and valor_cobrado != valor_sug_total:
                    st.warning(f"⚠️ O contrato prevê R$ {valor_sug_total:.2f}. Justificativa obrigatória:")
                    justificativa = st.text_input("Motivo da alteração de valor *", key=f"just_{fk}")
                else:
                    justificativa = st.text_input("Observação / Recibo", key=f"obs_{fk}")

            if st.button("Confirmar Entrada", type="primary"):
                if aluno_sel == "Selecione..." or valor_cobrado is None:
                    st.error("Selecione a Origem e preencha o valor!")
                elif aluno_sel != "Pessoa Externa / Avulso" and valor_cobrado != valor_sug_total and justificativa.strip() == "":
                    st.error("Justificativa obrigatória para alteração do valor contratual!")
                else:
                    aluno_id_val = None
                    ev_id_val = None
                    if evento_sel != "Nenhum": 
                        ev_id_val = int(df_eventos[df_eventos['nome'] == evento_sel]['id'].iloc[0])
                        
                    if aluno_sel != "Pessoa Externa / Avulso":
                        aluno_data = df_alunos[df_alunos['nome'] == aluno_sel].iloc[0]
                        aluno_id_val = int(aluno_data['id'])
                        pago_ate_atual = pd.to_datetime(aluno_data['pago_ate']) if pd.notnull(aluno_data['pago_ate']) else pd.to_datetime(f"{date.today().year}-{date.today().month:02d}-20")
                        if pago_ate_atual < pd.to_datetime(f"{date.today().year}-{date.today().month:02d}-20"): pago_ate_atual = pd.to_datetime(f"{date.today().year}-{date.today().month:02d}-20")
                        novo_pago_ate = pago_ate_atual + pd.DateOffset(months=qtd_meses)
                        atualizar_dados('alunos', {'pago_ate': novo_pago_ate.strftime('%Y-%m-%d')}, 'id', aluno_id_val)
                    
                    imp_str = ", ".join(impostos_sel)
                    desc_final = f"{desc_sugerida} ({qtd_meses}x)" if aluno_sel != "Pessoa Externa / Avulso" else "Entrada Avulsa"
                    cat_final = "Eventos" if ev_id_val else desc_sugerida
                    
                    inserir_dados('lancamentos', {
                        'data': str(data_op), 'valor_bruto': valor_cobrado, 'valor_imposto': v_imp, 
                        'valor_liquido': v_liq, 'tipo': 'Entrada', 'metodo_pagamento': metodo, 
                        'aluno_id': aluno_id_val, 'evento_id': ev_id_val, 'categoria': cat_final, 
                        'descricao': justificativa, 'operacao': 'A Vista', 'impostos_aplicados': imp_str
                    })
                    
                    st.session_state.sucesso_msg = "Pagamento Registrado no Caixa Geral com sucesso!"
                    resetar_form()
                    st.rerun()

        elif movimento == "SAÍDA":
            df_cat = buscar_dados('categorias_saida', order='nome')
            df_eventos = buscar_dados('eventos', in_col='status', in_vals=['Aberto', 'Planejamento'], order='nome')
            cats = df_cat['nome'].tolist() if not df_cat.empty else []
            evento_nomes = ["Nenhum"] + df_eventos['nome'].tolist() if not df_eventos.empty else ["Nenhum"]
            
            c1, c2 = st.columns(2)
            with c1:
                data_op = st.date_input("Data da Despesa", value=date.today(), format="DD/MM/YYYY", key=f"d_s_{fk}")
                categoria = st.selectbox("Centro de Custo *", ["Selecione..."] + cats, key=f"cat_s_{fk}")
                evento_sel = st.selectbox("Vincular a Evento?", evento_nomes, key=f"ev_s_{fk}")
                desc = st.text_input("Fornecedor / Descrição", key=f"desc_s_{fk}")
                
            with c2:
                metodo = st.radio("Método", ["PIX", "Dinheiro", "Cartão"], horizontal=True, key=f"met2_s_{fk}")
                valor = st.number_input("Valor Pago (R$) *", min_value=0.0, value=None, format="%.2f", key=f"val2_s_{fk}")
                
            if st.button("Confirmar Saída", type="primary"):
                if categoria != "Selecione..." and valor is not None and valor > 0:
                    ev_id_val = int(df_eventos[df_eventos['nome'] == evento_sel]['id'].iloc[0]) if evento_sel != "Nenhum" else None
                    
                    inserir_dados('lancamentos', {
                        'data': str(data_op), 'valor_bruto': valor, 'valor_imposto': 0, 
                        'valor_liquido': valor, 'tipo': 'Saida', 'metodo_pagamento': metodo, 
                        'evento_id': ev_id_val, 'categoria': categoria, 'descricao': desc, 
                        'operacao': 'A Vista', 'impostos_aplicados': ''
                    })
                    st.session_state.sucesso_msg = "Despesa registrada no fluxo geral com sucesso!"
                    resetar_form()
                    st.rerun()
                else:
                    st.error("Preencha Centro de Custo e um Valor válido.")

    # ==========================================
    # 4. GESTÃO DE EVENTOS
    # ==========================================
    elif menu == "📅 Gestão de Eventos":
        pg_eventos.render()

    # ==========================================
    # 5. ORÇAMENTO & METAS
    # ==========================================
    elif menu == "🎯 Orçamento & Metas":
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

    # ==========================================
    # 6. GESTÃO DE CLIENTES
    # ==========================================
    elif menu == "👤 Gestão de Clientes":
        pg_clientes.render()

    # ==========================================
    # 7. CONFIGURAÇÕES BASE DO SISTEMA
    # ==========================================
    elif menu == "⚙️ Configurações":
        pg_configuracoes.render()

    # ==========================================
    # 8. LOG DE LANÇAMENTOS (O "DIÁRIO")
    # ==========================================
    elif menu == "📜 Log de Lançamentos":
        pg_log.render()
