"""
Modulo: auth.py
Responsabilidade: tela de login, logout e inicializacao do estado de sessao
relacionado a autenticacao (Supabase Auth — Etapa B).

Status: ativo (preenchido na Etapa D, passo D.4).

Para usar:
    from auth import (
        inicializar_session_state_auth,
        mostrar_tela_login,
        fazer_logout,
    )

    # Logo no inicio do app.py:
    inicializar_session_state_auth()

    # Quando o usuario nao esta logado:
    if not st.session_state.logged_in:
        mostrar_tela_login()

    # Quando o usuario clica em Sair:
    if st.button("Sair"):
        fazer_logout()
        st.rerun()

NAO ALTERAR a logica de login/logout sem aprovacao explicita: foi calibrada
na Etapa B (migracao para Supabase Auth com bcrypt) e e o portao de entrada
do app — quebrar significa app inacessivel.
"""

import os
import streamlit as st
from db import init_connection


def inicializar_session_state_auth() -> None:
    """Cria as chaves de session_state usadas para controle de login.

    Idempotente: se as chaves ja existem (rerun do Streamlit), nao sobrescreve.
    """
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if "user" not in st.session_state:
        st.session_state.user = ""

    if "access_token" not in st.session_state:
        st.session_state.access_token = ""

    if "refresh_token" not in st.session_state:
        st.session_state.refresh_token = ""


def mostrar_tela_login() -> None:
    """Renderiza a tela de login centralizada e processa o submit do form.

    Em caso de sucesso, popula st.session_state com tokens e dispara st.rerun()
    para o app entrar no fluxo logado.
    """
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<div class='login-box'>", unsafe_allow_html=True)
        if os.path.exists("logo.jpeg"):
            st.image("logo.jpeg", use_container_width=True)
        else:
            st.markdown("<h2 style='color:#2E7D32; font-family:Arial;'>App da Terra</h2>", unsafe_allow_html=True)

        st.markdown("<h4>Acesso Restrito</h4>", unsafe_allow_html=True)

        with st.form("login_form"):
            email = st.text_input("Email", placeholder="Digite seu email")
            senha = st.text_input("Senha", type="password", placeholder="Digite sua senha")
            submit = st.form_submit_button("Entrar", type="primary", use_container_width=True)

            if submit:
                if not email or not senha:
                    st.error("❌ Preencha email e senha.")
                else:
                    try:
                        sb = init_connection()
                        response = sb.auth.sign_in_with_password({
                            "email": email,
                            "password": senha
                        })
                        if response.session and response.user:
                            st.session_state.logged_in = True
                            st.session_state.user = response.user.email or ""
                            st.session_state.access_token = response.session.access_token
                            st.session_state.refresh_token = response.session.refresh_token

                            st.rerun()
                        else:
                            st.error("❌ Email ou senha incorretos.")
                    except Exception as e:
                        msg = str(e)
                        if "Invalid login credentials" in msg or "invalid_credentials" in msg.lower():
                            st.error("❌ Email ou senha incorretos.")
                        else:
                            st.error(f"❌ Erro ao fazer login: {msg}")
        st.markdown("</div>", unsafe_allow_html=True)


def fazer_logout() -> None:
    """Invalida o JWT no servidor Supabase e limpa o session_state de auth.

    Nao chama st.rerun() — quem invocar decide quando o rerun acontece (em
    geral imediatamente apos o fazer_logout, mas mantemos a separacao por
    flexibilidade).
    """
    # Avisa o Supabase para invalidar o JWT no servidor
    try:
        sb = init_connection()
        sb.auth.sign_out()
    except Exception:
        pass

    # Limpa session_state de auth
    st.session_state.logged_in = False
    st.session_state.user = ""
    st.session_state.access_token = ""
    st.session_state.refresh_token = ""

    # Forca recriacao do cliente Supabase na proxima execucao
    if "supabase_client" in st.session_state:
        del st.session_state.supabase_client
