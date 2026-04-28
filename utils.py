"""
Modulo: utils.py
Responsabilidade: helpers usados por varias paginas — extracao de strings
e gerenciamento de chave de form para forcar reset de widgets.

Status: ativo (preenchido na Etapa D, passo D.5).

Para usar:
    from utils import extrair_item_evento, resetar_form

Notas:
- extrair_item_evento e funcao pura (sem efeitos colaterais).
- resetar_form NAO e pura — mexe em st.session_state.form_key. Esta aqui
  porque e um helper de UI generico usado em quase todas as paginas. O
  contrato e: incrementar a chave de form, fazendo o Streamlit redesenhar
  todos os widgets cujas keys dependem dessa chave (com isso, eles "esquecem"
  o estado anterior — util apos submit de form).
"""

import streamlit as st


def extrair_item_evento(desc, nome_evento):
    prefix = f"[{nome_evento}] "
    if isinstance(desc, str):
        if desc.startswith(prefix):
            s = desc[len(prefix):]
            return s.split(" - ")[0].strip()
    return desc


def resetar_form():
    st.session_state.form_key += 1
