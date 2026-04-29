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
from paginas import orcamento as pg_orcamento
from paginas import operacoes as pg_operacoes
from paginas import recebiveis as pg_recebiveis

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
        pg_recebiveis.render()

    # ==========================================
    # 3. OPERAÇÕES (CAIXA GERAL)
    # ==========================================
    elif menu == "💸 Operações (Caixa)":
        pg_operacoes.render()

    # ==========================================
    # 4. GESTÃO DE EVENTOS
    # ==========================================
    elif menu == "📅 Gestão de Eventos":
        pg_eventos.render()

    # ==========================================
    # 5. ORÇAMENTO & METAS
    # ==========================================
    elif menu == "🎯 Orçamento & Metas":
        pg_orcamento.render()

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
