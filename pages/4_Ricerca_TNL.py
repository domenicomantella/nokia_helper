import streamlit as st
import pandas as pd

st.title("📊 Ricerca TNL")

# --- CONFIG ---
SHEET_NAME = "TNL_TI_SRAN"   # 🔹 metti qui il tuo foglio reale

# --- AVVISO OPERATIVO ---
st.warning("""
📌 ISTRUZIONI:
- I file devono essere presi dalla cartella Teams ufficiale
- Si consiglia di usare "Aggiungi collegamento a OneDrive"
- Assicurarsi di avere file aggiornati prima del caricamento

⚠️ Carica solo i file Excel corretti
""")

st.caption(f"📄 Foglio utilizzato: {SHEET_NAME}")

# =========================================================
# UPLOAD FILE
# =========================================================

uploaded_files = st.file_uploader(
    "📤 Carica file Excel Trasporti",
    type=["xlsx"],
    accept_multiple_files=True
)

# =========================================================
# CARICAMENTO DATI
# =========================================================

if uploaded_files:

    df_list = []

    for file in uploaded_files:
        try:
            df = pd.read_excel(file, sheet_name=SHEET_NAME)
            df["source_file"] = file.name
            df_list.append(df)
        except:
            continue

    if not df_list:
        st.error("❌ Nessun file valido (controlla il nome foglio)")
        st.stop()

    full_df = pd.concat(df_list, ignore_index=True)

    st.success(f"✅ Caricati {len(uploaded_files)} file")
    st.write(f"Totale righe: {len(full_df)}")

    # =========================================================
    # RICERCA
    # =========================================================

    search = st.text_input("🔎 Cerca (sito, nodo, IP, porta...)")

    if search:
        result = full_df[
            full_df.astype(str).apply(
                lambda row: row.str.contains(search, case=False).any(),
                axis=1
            )
        ]

        st.write(f"Risultati trovati: {len(result)}")
        st.dataframe(result)

    else:
        st.dataframe(full_df)
