"""
Modulo: db.py
Responsabilidade: cliente Supabase e funcoes wrapper de query.
Status: ativo (preenchido na Etapa D, passo D.3).

Para usar:
    from db import init_connection, buscar_dados, inserir_dados, atualizar_dados, deletar_dados

Cada wrapper chama init_connection() internamente. init_connection() ja cacheia
o cliente em st.session_state.supabase_client, entao o overhead e desprezivel
(1 lookup em dict por chamada).

NAO ALTERAR o corpo de init_connection() sem aprovacao explicita: a logica de
defesa de JWT (set_session no caso do cliente ser recriado apos rerun pesado)
foi adicionada na Etapa C e e CRITICA para RLS funcionar corretamente.
"""

import streamlit as st
import pandas as pd
from supabase import create_client, Client


def init_connection() -> Client:
    """Cliente Supabase por sessao (sem @st.cache_resource).

    O Supabase mantem estado de auth (JWT) interno apos sign_in_with_password.
    Compartilhar entre sessoes via cache_resource causaria bugs de auth.
    Mantemos uma instancia por sessao via st.session_state.

    Defesa para RLS (Etapa C): se a sessao do Streamlit ja tem tokens
    guardados de um login anterior mas o cliente foi descartado (rerun
    pesado, inatividade), restauramos o JWT antes de retornar. Sem isso,
    RLS bloquearia queries silenciosamente em cenarios de borda.
    """
    if "supabase_client" not in st.session_state:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        st.session_state.supabase_client = create_client(url, key)

        # Restaura sessao autenticada se ja havia login ativo nesta aba
        access_token = st.session_state.get("access_token", "")
        refresh_token = st.session_state.get("refresh_token", "")
        if access_token and refresh_token:
            try:
                st.session_state.supabase_client.auth.set_session(
                    access_token, refresh_token
                )
            except Exception:
                # Token expirado ou invalido: derruba o login local
                # e o usuario sera redirecionado para a tela de login
                st.session_state.logged_in = False
                st.session_state.access_token = ""
                st.session_state.refresh_token = ""

    return st.session_state.supabase_client


def buscar_dados(tabela, select="*", eq=None, order=None, order_desc=False, in_col=None, in_vals=None):
    supabase = init_connection()
    query = supabase.table(tabela).select(select)
    if eq:
        for k, v in eq.items():
            query = query.eq(k, v)
    if in_col and in_vals:
        query = query.in_(in_col, in_vals)
    if order:
        query = query.order(order, desc=order_desc)

    response = query.execute()
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()


def inserir_dados(tabela, dados):
    supabase = init_connection()
    supabase.table(tabela).insert(dados).execute()


def atualizar_dados(tabela, dados, eq_col, eq_val):
    supabase = init_connection()
    supabase.table(tabela).update(dados).eq(eq_col, eq_val).execute()


def deletar_dados(tabela, eq_col, eq_val):
    supabase = init_connection()
    supabase.table(tabela).delete().eq(eq_col, eq_val).execute()
