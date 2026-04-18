"""
styles.py — CSS global injetado no Streamlit para padronização visual.
"""
import streamlit as st


def inject_styles() -> None:
    st.markdown("""
    <style>
    /* ── Botões primários: azul ──────────────────────────────────────────
       Streamlit renderiza form_submit_button[type=primary] e st.button
       com a classe .st-emotion-cache-* variável. O seletor mais estável
       é pelo atributo data-testid + cor de fundo via !important            */

    /* Todos os botões base */
    .stButton > button,
    .stFormSubmitButton > button {
        border-radius: 6px !important;
        font-weight: 600 !important;
        transition: background-color 0.2s ease, box-shadow 0.2s ease !important;
    }

    /* Botão primário — fundo azul */
    .stButton > button[data-testid="baseButton-primary"],
    .stFormSubmitButton > button[data-testid="baseButton-primary"] {
        background-color: #1a73e8 !important;
        border: 1px solid #1a73e8 !important;
        color: #ffffff !important;
    }

    .stButton > button[data-testid="baseButton-primary"]:hover,
    .stFormSubmitButton > button[data-testid="baseButton-primary"]:hover {
        background-color: #1558b0 !important;
        border-color: #1558b0 !important;
        box-shadow: 0 2px 8px rgba(26,115,232,0.4) !important;
    }

    .stButton > button[data-testid="baseButton-primary"]:active,
    .stFormSubmitButton > button[data-testid="baseButton-primary"]:active {
        background-color: #0d47a1 !important;
        border-color: #0d47a1 !important;
    }

    /* Fallback: qualquer botão vermelho/coral → força azul
       (cobre variações de versão do Streamlit)                             */
    .stButton > button[style*="background-color: rgb(255"],
    .stFormSubmitButton > button[style*="background-color: rgb(255"] {
        background-color: #1a73e8 !important;
        border-color: #1a73e8 !important;
        color: #ffffff !important;
    }

    /* ── Botões secundários: cinza neutro ──────────────────────────────── */
    .stButton > button[data-testid="baseButton-secondary"],
    .stFormSubmitButton > button[data-testid="baseButton-secondary"] {
        border-color: #5f6368 !important;
        color: #3c4043 !important;
        background-color: transparent !important;
    }
    .stButton > button[data-testid="baseButton-secondary"]:hover,
    .stFormSubmitButton > button[data-testid="baseButton-secondary"]:hover {
        border-color: #1a73e8 !important;
        color: #1a73e8 !important;
        background-color: #e8f0fe !important;
    }
    </style>
    """, unsafe_allow_html=True)


def inject_styles_theme_override() -> None:
    """
    Alternativa via theme config — use no config.toml do Streamlit.
    Adicione ao arquivo .streamlit/config.toml:

    [theme]
    primaryColor = "#1a73e8"
    """
    pass
