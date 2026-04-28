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
        st.title("👤 Cadastro de Clientes e Contratos")
        df_ativ = buscar_dados('atividades_entrada')
        lista_ativ = df_ativ['nome'].tolist() if not df_ativ.empty else []
        
        aba_clientes = st.radio("Selecione a Ação:", ["➕ Novo Contrato", "📋 Lista de Clientes", "✏️ Editar Contrato", "🛑 Inativar / Reativar"], horizontal=True, key=f"rad_cli_{fk}")
        st.markdown("---")
        
        if aba_clientes == "➕ Novo Contrato":
            st.write("Adicione um cliente. As modalidades aparecem dinamicamente para você precificar.")
            nome = st.text_input("Nome Completo do Cliente", key=f"na_{fk}")
            mod_selecionadas = st.multiselect("Selecione os Serviços Contratados", lista_ativ, key=f"ma_{fk}")
            
            planos_aluno = []
            total_mensal = 0.0
            
            if mod_selecionadas:
                st.markdown("#### Ajuste de Valores Específicos do Contrato")
                for mod in mod_selecionadas:
                    val_padrao = df_ativ[df_ativ['nome'] == mod]['valor_padrao'].iloc[0]
                    val_ac = st.number_input(f"Valor cobrado por '{mod}' (Preço Padrão: R$ {val_padrao:.2f})", value=float(val_padrao), format="%.2f", key=f"v_add_{mod}_{fk}")
                    if val_ac is not None:
                        planos_aluno.append({"modalidade": mod, "valor": val_ac})
                        total_mensal += val_ac
                
                st.info(f"**Total Mensal Acordado: R$ {total_mensal:.2f}**")
                
            if st.button("Confirmar Cadastro do Cliente", type="primary"):
                if nome and planos_aluno:
                    venc = f"{date.today().year}-{date.today().month:02d}-20"
                    hoje = date.today().strftime('%Y-%m-%d')
                    
                    inserir_dados('alunos', {
                        'nome': nome, 'ativo': 1, 'planos': json.dumps(planos_aluno, ensure_ascii=False), 
                        'valor_total': total_mensal, 'pago_ate': venc, 'data_cadastro': hoje, 'data_ultima_ativacao': hoje
                    })
                    st.session_state.sucesso_msg = "Cliente cadastrado com sucesso!"
                    resetar_form()
                    st.rerun()
                else:
                    st.error("Preencha Nome e selecione os Serviços para prosseguir.")

        elif aba_clientes == "📋 Lista de Clientes":
            df_alunos = buscar_dados('alunos', select='id, nome, planos, valor_total, ativo, data_cadastro, data_cancelamento, data_ultima_ativacao')
            if not df_alunos.empty:
                def format_p(p):
                    try: return " + ".join([f"{x['modalidade']}" for x in json.loads(p)])
                    except: return ""
                df_v = df_alunos.copy()
                df_v['Serviços Contratados'] = df_v['planos'].apply(format_p)
                
                def format_status(x):
                    if x['ativo'] == 1:
                        d_inicio = x['data_ultima_ativacao'] if pd.notnull(x['data_ultima_ativacao']) and str(x['data_ultima_ativacao']).strip() != '' else x['data_cadastro']
                        try: d_inicio = datetime.strptime(d_inicio, '%Y-%m-%d').strftime('%d/%m/%Y')
                        except: pass
                        return f"Ativo desde {d_inicio}"
                    else:
                        d_fim = x['data_cancelamento']
                        try: d_fim = datetime.strptime(d_fim, '%Y-%m-%d').strftime('%d/%m/%Y')
                        except: pass
                        return f"Inativo desde {d_fim}"
                        
                df_v['Status Atual'] = df_v.apply(format_status, axis=1)
                
                st.dataframe(df_v[['nome', 'Serviços Contratados', 'valor_total', 'Status Atual']].rename(columns={'nome':'Nome do Cliente', 'valor_total':'Cota Mensal (R$)'}), use_container_width=True)

        elif aba_clientes == "✏️ Editar Contrato":
            df_ativos = buscar_dados('alunos', eq={'ativo': 1}, order='nome')
            if not df_ativos.empty:
                aluno_ed = st.selectbox("Selecione o Cliente ATIVO para Editar o Contrato", df_ativos['nome'].tolist(), key=f"sel_ed_cli_{fk}")
                d_aluno = df_ativos[df_ativos['nome'] == aluno_ed].iloc[0]
                al_id = d_aluno['id']
                
                e_nome = st.text_input("Nome do Cliente", value=d_aluno['nome'], key=f"en_{al_id}_{fk}")
                try: ativ_atuais = [p['modalidade'] for p in json.loads(d_aluno['planos'])]
                except: ativ_atuais = []
                
                e_mods = st.multiselect("Serviços Contratados", lista_ativ, default=[a for a in ativ_atuais if a in lista_ativ], key=f"em_{al_id}_{fk}")
                
                planos_ed = []
                total_ed = 0.0
                if e_mods:
                    st.markdown("#### Ajuste de Valores Específicos do Contrato")
                    for mod in e_mods:
                        val_atual = df_ativ[df_ativ['nome'] == mod]['valor_padrao'].iloc[0]
                        try:
                            for p in json.loads(d_aluno['planos']):
                                if p['modalidade'] == mod: val_atual = p['valor']
                        except: pass
                        
                        v_ac = st.number_input(f"Valor cobrado por '{mod}'", value=float(val_atual), format="%.2f", key=f"ve_{mod}_{al_id}_{fk}")
                        if v_ac is not None:
                            planos_ed.append({"modalidade": mod, "valor": v_ac})
                            total_ed += v_ac
                    
                    st.info(f"**Novo Total Mensal do Contrato: R$ {total_ed:.2f}**")
                
                data_efetiva = st.date_input("Alteração Efetiva a partir de", value=date.today(), format="DD/MM/YYYY", key=f"dt_efetiva_{fk}")
                
                if st.button("Salvar Alterações do Contrato", type="primary"):
                    atualizar_dados('alunos', {'nome': e_nome, 'planos': json.dumps(planos_ed, ensure_ascii=False), 'valor_total': total_ed}, 'id', int(d_aluno['id']))
                    st.session_state.sucesso_msg = f"Contrato atualizado com sucesso! Novo valor efetivo a partir de {data_efetiva.strftime('%d/%m/%Y')}."
                    resetar_form()
                    st.rerun()
            else:
                st.info("Nenhum cliente ativo para editar.")

        elif aba_clientes == "🛑 Inativar / Reativar":
            st.markdown("### 🛑 Inativar Cliente Ativo")
            df_ativos_in = buscar_dados('alunos', eq={'ativo': 1}, order='nome')
            if not df_ativos_in.empty:
                with st.form("f_inativar"):
                    a_inativar = st.selectbox("Selecione o Cliente para inativar:", df_ativos_in['nome'].tolist())
                    data_inativacao = st.date_input("Data Oficial do Cancelamento/Saída", value=date.today(), format="DD/MM/YYYY")
                    
                    st.markdown('<div class="btn-danger">', unsafe_allow_html=True)
                    submit_ina = st.form_submit_button("Confirmar Inativação")
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    if submit_ina:
                        aluno_id_stat = int(df_ativos_in[df_ativos_in['nome'] == a_inativar]['id'].iloc[0])
                        
                        df_l = buscar_dados('lancamentos', eq={'aluno_id': aluno_id_stat, 'tipo': 'Entrada'})
                        if not df_l.empty:
                            df_conflito = df_l[df_l['data'] > str(data_inativacao)][['id', 'data', 'valor_liquido', 'descricao']]
                        else:
                            df_conflito = pd.DataFrame()
                        
                        if not df_conflito.empty:
                            st.error(f"⚠️ CONFLITO DE DATAS: Não é possível inativar o cliente em {data_inativacao.strftime('%d/%m/%Y')}.")
                            st.write("O sistema encontrou pagamentos registrados no Caixa GERAL **após** esta data. Exclua os lançamentos futuros antes de inativar com esta data retroativa.")
                            st.dataframe(df_conflito.rename(columns={'data': 'Data do Pagamento', 'valor_liquido': 'Valor Líquido (R$)', 'descricao': 'Descrição'}))
                        else:
                            atualizar_dados('alunos', {'ativo': 0, 'data_cancelamento': str(data_inativacao)}, 'id', aluno_id_stat)
                            st.session_state.sucesso_msg = f"Cliente {a_inativar} inativado com sucesso!"
                            resetar_form()
                            st.rerun()
            else:
                st.info("Todos os clientes já estão inativos.")

            st.markdown("---")
            st.markdown("### ♻️ Clientes Inativos (Painel de Reativação)")
            df_inativos = buscar_dados('alunos', eq={'ativo': 0}, order='nome')
            
            if not df_inativos.empty:
                for idx, row in df_inativos.iterrows():
                    d_canc = row['data_cancelamento']
                    try: d_canc = datetime.strptime(d_canc, '%Y-%m-%d').strftime('%d/%m/%Y')
                    except: pass
                    
                    with st.expander(f"👤 {row['nome']} (Inativo desde {d_canc})"):
                        data_reativacao = st.date_input("Data de Reativação (Início do Novo Ciclo)", value=date.today(), format="DD/MM/YYYY", key=f"d_rea_{row['id']}_{fk}")
                        
                        r_mods = st.multiselect("Selecione os Serviços Contratados agora", lista_ativ, key=f"rm_{row['id']}_{fk}")
                        planos_r = []
                        total_r = 0.0
                        
                        if r_mods:
                            st.write("Ajuste os valores contratuais para o novo ciclo:")
                            for mod in r_mods:
                                val_padrao = df_ativ[df_ativ['nome'] == mod]['valor_padrao'].iloc[0]
                                v_ac = st.number_input(f"Valor cobrado por '{mod}'", value=float(val_padrao), format="%.2f", key=f"vr_{mod}_{row['id']}_{fk}")
                                if v_ac is not None:
                                    planos_r.append({"modalidade": mod, "valor": v_ac})
                                    total_r += v_ac
                            st.info(f"**Novo Total Mensal Acordado: R$ {total_r:.2f}**")
                        
                        if st.button(f"Confirmar Reativação de {row['nome']}", type="primary", key=f"btn_rea_{row['id']}_{fk}"):
                            if not planos_r:
                                st.error("Selecione ao menos um serviço para reativar o contrato.")
                            else:
                                atualizar_dados('alunos', {
                                    'ativo': 1, 
                                    'data_cancelamento': "", 
                                    'data_ultima_ativacao': str(data_reativacao), 
                                    'planos': json.dumps(planos_r, ensure_ascii=False), 
                                    'valor_total': total_r
                                }, 'id', int(row['id']))
                                st.session_state.sucesso_msg = f"Cliente {row['nome']} reativado com sucesso! Bem-vindo de volta!"
                                resetar_form()
                                st.rerun()
            else:
                st.info("Não há clientes inativos aguardando reativação no momento.")

    # ==========================================
    # 7. CONFIGURAÇÕES BASE DO SISTEMA
    # ==========================================
    elif menu == "⚙️ Configurações":
        st.title("⚙️ Cadastros e Configurações")
        
        aba_config = st.radio("Selecione a Configuração:", ["Serviços / Modalidades", "Centros de Custo", "Impostos / Taxas", "Segurança (Login)"], horizontal=True, key=f"rad_conf_{fk}")
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
                    
        # === DESATIVADO Etapa B: troca de senha agora gerenciada pelo Supabase Auth Dashboard ===
        # elif aba_config == "Segurança (Login)":
        #     st.subheader("Alterar Credenciais de Acesso")
        #     st.write("Atualize o utilizador e a senha para aceder ao sistema. Em caso de perda, deverá contactar o administrador da base de dados (Supabase).")
        #
        #     with st.form("f_seguranca"):
        #         n_user = st.text_input("Novo Nome de Usuário", placeholder="Digite o novo login")
        #         n_pwd = st.text_input("Nova Senha", type="password", placeholder="Digite a nova senha segura")
        #
        #         if st.form_submit_button("Salvar Novas Credenciais", type="primary"):
        #             if n_user.strip() != "" and n_pwd.strip() != "":
        #                 atualizar_dados('perfil_acesso', {'usuario': n_user, 'senha': n_pwd}, 'id', 1)
        #                 st.session_state.user = n_user
        #                 st.session_state.sucesso_msg = "Credenciais atualizadas com sucesso! Utilize-as no seu próximo login."
        #                 resetar_form()
        #                 st.rerun()
        #             else:
        #                 st.error("Por favor, preencha os dois campos.")

    # ==========================================
    # 8. LOG DE LANÇAMENTOS (O "DIÁRIO")
    # ==========================================
    elif menu == "📜 Log de Lançamentos":
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
