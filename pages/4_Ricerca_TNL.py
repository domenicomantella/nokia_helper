import streamlit as st
import pandas as pd
import os

st.title("📊 Ricerca Trasporti")

# --- CONFIG ---
PATTERN = "TRASPORTO"       # stringa presente nei nomi file
SHEET_NAME = "ip_NO"        # nome foglio fisso

# --- SCELTA MODALITÀ ---
mode = st.radio(
    "Sorgente dati",
    ["Cartella Teams", "Upload manuale"]
)

# =========================================================
# MODALITÀ 1: CARTELLA TEAMS
# =========================================================
if mode == "Cartella Teams":

    st.warning("""
    📌 ISTRUZIONI:
    - Vai su Teams
    - Apri la cartella Trasporti
    - Clicca "Aggiungi collegamento a OneDrive"
    - Copia il percorso da Esplora Risorse
    """)

    folder_path = st.text_input("📁 Percorso cartella")

    if folder_path:

        if not os.path.exists(folder_path):
            st.error("❌ Percorso non valido")
            st.stop()

        st.success("✅ Cartella trovata")

        st.caption(f"📄 Foglio utilizzato: {SHEET_NAME}")

        # --- CARICAMENTO DATI ---
        @st.cache_data
        def load_data(folder_path):

            df_list = []

            for file in os.listdir(folder_path):
                if file.endswith(".xlsx") and PATTERN.lower() in file.lower():

                    file_path = os.path.join(folder_path, file)

                    try:
                        df = pd.read_excel(file_path, sheet_name=SHEET_NAME)
                        df["source_file"] = file
                        df_list.append(df)

                    except:
                        continue

            if df_list:
                return pd.concat(df_list, ignore_index=True)
            else:
                return None

        full_df = load_data(folder_path)

        if full_df is None:
            st.error("❌ Nessun file valido trovato")
            st.stop()

        st.success(f"✅ Dati caricati: {len(full_df)} righe")

        # --- RICERCA BASE ---
        search = st.text_input("🔎 Cerca (sito, nodo, IP, ... )")

        if search:
            result = full_df[
                full_df.astype(str).apply(
                    lambda row: row.str.contains(search, case=False).any(),
                    axis=1
                )
            ]

            st.write(f"Risultati trovati: {len(result)}")
            st.dataframe(result)

# =========================================================
# MODALITÀ 2: UPLOAD MANUALE
# =========================================================
elif mode == "Upload manuale":

    uploaded_files = st.file_uploader(
        "Carica file Excel",
        type=["xlsx"],
        accept_multiple_files=True
    )

    if uploaded_files:

        df_list = []

        for file in uploaded_files:
            try:
                df = pd.read_excel(file, sheet_name=SHEET_NAME)
                df["source_file"] = file.name
                df_list.append(df)
            except:
                continue

        if df_list:
            full_df = pd.concat(df_list, ignore_index=True)

            st.success(f"✅ Caricati {len(uploaded_files)} file")
            st.dataframe(full_df)

        else:
            st.error("❌ Nessun file valido")
