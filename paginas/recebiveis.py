"""
Modulo: paginas/recebiveis.py
Responsabilidade: pagina "Recebiveis" — gestao de contas a receber com
vencimento dia 20. Pagina so de leitura:
- Calcula status de cada aluno ativo (em dia se pago_ate >= dia 20 do
  mes atual; pendente caso contrario)
- 3 metricas: Faturamento Previsto, Ja Coberto, Pendente
- Barra de progresso do recebimento
- Tabela filtravel: Atrasados ou Pagos

Status: ativo (preenchido na Etapa D, passo D.12).

Para usar:
    from paginas import recebiveis as pg_recebiveis
    # ...
    elif menu == "💰 Recebíveis":
        pg_recebiveis.render()
"""

from datetime import date

import streamlit as st
import pandas as pd

from db import buscar_dados


def render():
    fk = st.session_state.form_key

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
