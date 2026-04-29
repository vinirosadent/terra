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
from paginas import bi as pg_bi

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
        pg_bi.render()

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
