"""
Modulo: paginas/operacoes.py
Responsabilidade: pagina "Operacoes (Caixa)" — registro de entradas
(mensalidades) e saidas (despesas) no caixa geral.

Modos:
- ENTRADA: recebimento de mensalidade com sugestao de valor pelo contrato,
  suporte a pacote multi-mes (1 pagamento cobre N meses), aplicacao de
  impostos/taxas, e atualizacao automatica de pago_ate do aluno.
- SAIDA: registro de despesa simples (centro de custo + valor + metodo).

Status: ativo (preenchido na Etapa D, passo D.11).

Para usar:
    from paginas import operacoes as pg_operacoes
    # ...
    elif menu == "💸 Operações (Caixa)":
        pg_operacoes.render()
"""

import json
from datetime import date

import streamlit as st
import pandas as pd

from db import buscar_dados, inserir_dados, atualizar_dados
from utils import resetar_form


def render():
    fk = st.session_state.form_key

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
