"""
Modulo: paginas/clientes.py
Responsabilidade: pagina "Gestao de Clientes" com 4 sub-abas:
- Novo Contrato: cadastro de aluno com modalidades dinamicas
- Lista de Clientes: tabela com status formatado
- Editar Contrato: edicao de aluno ATIVO
- Inativar / Reativar: inativacao com checagem de conflito de datas
  + painel de reativacao com st.expander por aluno inativo

Status: ativo (preenchido na Etapa D, passo D.8).

Para usar:
    from paginas import clientes as pg_clientes
    # ...
    elif menu == "👤 Gestão de Clientes":
        pg_clientes.render()
"""

import json
from datetime import date, datetime

import streamlit as st
import pandas as pd

from db import buscar_dados, inserir_dados, atualizar_dados
from utils import resetar_form


def render():
    fk = st.session_state.form_key

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
                # E.4/E.3: pago_ate ancorado no ultimo dia do mes anterior ao corrente.
                # Assim o cliente entra "devendo" o mes corrente, que sera quitado
                # no primeiro pagamento.
                hoje_ts = pd.Timestamp(date.today())
                venc = (hoje_ts.replace(day=1) - pd.DateOffset(days=1)).strftime('%Y-%m-%d')
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
        df_alunos = buscar_dados('alunos', select='id, nome, planos, valor_total, ativo, data_cadastro, data_cancelamento, data_ultima_ativacao, pago_ate')
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

            # E.4: coluna "Pago até" com indicador visual de status
            hoje_dt = pd.Timestamp(date.today())

            def format_pago_ate(x):
                pa = x.get('pago_ate')
                if pa is None or (isinstance(pa, str) and pa.strip() == '') or pd.isna(pa):
                    return "—"
                try:
                    pa_dt = pd.to_datetime(pa)
                    pa_fmt = pa_dt.strftime('%d/%m/%Y')
                    if pa_dt >= hoje_dt:
                        return f"🟢 {pa_fmt}"
                    else:
                        return f"🔴 {pa_fmt}"
                except:
                    return str(pa)

            df_v['Pago até'] = df_v.apply(format_pago_ate, axis=1)

            st.caption("**Legenda:** 🟢 Mensalidade regular (em dia)   🔴 Mensalidade atrasada")

            st.dataframe(df_v[['nome', 'Serviços Contratados', 'valor_total', 'Status Atual', 'Pago até']].rename(columns={'nome':'Nome do Cliente', 'valor_total':'Cota Mensal (R$)'}), use_container_width=True)

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
                            # P.1: NAO apagamos data_cancelamento na reativacao.
                            # A coluna preserva o historico do ultimo cancelamento;
                            # data_ultima_ativacao marca quando o aluno voltou.
                            # A logica de Pagamentos usa essas duas datas pra saber
                            # em quais meses o aluno esteve ativo.
                            atualizar_dados('alunos', {
                                'ativo': 1,
                                'data_ultima_ativacao': str(data_reativacao),
                                'planos': json.dumps(planos_r, ensure_ascii=False),
                                'valor_total': total_r
                            }, 'id', int(row['id']))
                            st.session_state.sucesso_msg = f"Cliente {row['nome']} reativado com sucesso! Bem-vindo de volta!"
                            resetar_form()
                            st.rerun()
        else:
            st.info("Não há clientes inativos aguardando reativação no momento.")
