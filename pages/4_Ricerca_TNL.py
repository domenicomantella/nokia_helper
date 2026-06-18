import streamlit as st
import pandas as pd

st.title("📊 Ricerca TNL")

# =========================================================
# CONFIG
# =========================================================
SHEET_NAME = "TNL_TI_SRAN"

st.warning("""
📌 ISTRUZIONI:
- Caricare file Excel aggiornati dalla cartella Teams
- Usare sempre i file ufficiali

⚠️ Caricare solo file corretti
""")

st.caption(f"📄 Foglio utilizzato: {SHEET_NAME}")

# =========================================================
# UPLOAD FILE
# =========================================================
uploaded_files = st.file_uploader(
    "📤 Carica file Excel",
    type=["xlsx"],
    accept_multiple_files=True
)

# =========================================================
# FUNZIONI
# =========================================================
def section_has_data(df, cols):
    valid = [c for c in cols if c in df.columns]
    if not valid:
        return False
    temp = df[valid].fillna("").astype(str)
    return (temp != "").any().any()


def render_section(title, df, cols):
    valid = [c for c in cols if c in df.columns]

    if section_has_data(df, cols):
        st.subheader(title)
        out = df[valid].T.reset_index()
        out.columns = ["Campo", "Valore"]
        st.dataframe(out, use_container_width=True, hide_index=True)


# =========================================================
# CARICAMENTO DATI
# =========================================================
if uploaded_files:

    df_list = []

    for file in uploaded_files:
        try:
            df = pd.read_excel(file, sheet_name=SHEET_NAME, header=[0, 1])

