"""
Modulo: styles.py
Responsabilidade: CSS global do app (paleta, fontes, botoes).
Status: ativo (preenchido na Etapa D, passo D.2).

Para usar:
    from styles import aplicar_estilo_global
    aplicar_estilo_global()

Deve ser chamado UMA vez no app.py logo apos st.set_page_config(),
antes de qualquer outro st.markdown ou widget.
"""

import streamlit as st


def aplicar_estilo_global() -> None:
    """Injeta o bloco CSS global do app.

    Conteudo identico ao bloco que vivia inline no app.py antes do refactor
    da Etapa D. NAO ALTERAR sem aprovacao explicita: este CSS foi calibrado
    no MVP e qualquer mudanca quebra a harmonia visual (PRIORIDADE 0).
    """
    st.markdown("""
    <style>
        html, body, [class*="css"] { font-family: 'Arial', sans-serif !important; }

        /* TRATOR CSS: Pega botões normais E botões de formulário */
        button[kind="primary"],
        button[kind="primaryFormSubmit"] {
            background-color: #2E7D32 !important;
            border-color: #2E7D32 !important;
            color: white !important;
            border-radius: 6px !important;
            font-weight: bold !important;
            width: 100% !important;
        }

        button[kind="primary"]:hover,
        button[kind="primaryFormSubmit"]:hover {
            background-color: #1B5E20 !important;
            border-color: #1B5E20 !important;
            color: white !important !important;
        }

        /* Botões secundários normais (para não piscarem vermelho ao passar o mouse) */
        button[kind="secondary"]:hover,
        button[kind="secondaryFormSubmit"]:hover {
            border-color: #2E7D32 !important;
            color: #2E7D32 !important;
        }

        /* Botões de Perigo (Vermelhos da classe btn-danger) */
        .btn-danger button {
            background-color: #d32f2f !important;
            border-color: #d32f2f !important;
            color: white !important;
            border-radius: 6px !important;
            font-weight: bold !important;
        }
        .btn-danger button:hover {
            background-color: #b71c1c !important;
            border-color: #b71c1c !important;
        }

        thead tr th:first-child {display:none}
        tbody th {display:none}
        .login-box { max-width: 400px; margin: 0 auto; padding: 30px; background-color: #f9f9f9; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); text-align: center; }
    </style>
""", unsafe_allow_html=True)
