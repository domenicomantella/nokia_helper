import streamlit as st
import pandas as pd

st.title("📊 Ricerca TNL")

# =========================================================
# CONFIG
# =========================================================
SHEET_NAME = "TNL_TI_SRAN"

st.warning("""
📌 ISTRUZIONI:
- I file devono essere presi dalla cartella Teams ufficiale
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
# FUNZIONI UTILI
# =========================================================
def section_has_data(df, cols):
    valid_cols = [c for c in cols if c in df.columns]
    if not valid_cols:
        return False

    temp = df[valid_cols].copy()
    temp = temp.fillna("").astype(str).apply(lambda col: col.str.strip())
    return (temp != "").any().any()


def render_section(title, df, cols):
    valid_cols = [c for c in cols if c in df.columns]

    if section_has_data(df, cols):
        st.subheader(title)
        section_df = df[valid_cols].T.reset_index()
        section_df.columns = ["Campo", "Valore"]
        st.dataframe(section_df, use_container_width=True, hide_index=True)

# =========================================================
# CARICAMENTO DATI
# =========================================================
if uploaded_files:

    df_list = []

    for file in uploaded_files:
        try:
            df = pd.read_excel(file, sheet_name=SHEET_NAME, header=[0, 1])

            # 🔥 appiattisce intestazioni
            df.columns = [
                f"{str(col[0]).strip()} - {str(col[1]).strip()}"
                for col in df.columns
            ]

            # 🔥 elimina righe descrittive
            df = df.iloc[1:]

            # 🔥 elimina righe vuote
            df = df.dropna(how="all")

            # 🔥 elimina colonne inutili
            df = df.loc[:, ~df.columns.str.contains("Unnamed", case=False)]

            df["source_file"] = file.name

            df_list.append(df)

        except Exception as e:
            st.error(f"Errore file {file.name}: {e}")

    if not df_list:
        st.error("❌ Nessun file valido")
        st.stop()

    full_df = pd.concat(df_list, ignore_index=True)

    st.success(f"✅ Caricati {len(uploaded_files)} file")
    st.write(f"Totale righe utili: {len(full_df)}")

    with st.expander("🔧 Colonne rilevate"):
        st.write(list(full_df.columns))

    # =========================================================
    # RICERCA
    # =========================================================
    st.subheader("🔎 Ricerca")

    col1, col2, col3 = st.columns(3)

    with col1:
        search_mrbts = st.text_input("MRBTS")

    with col2:
        search_sito = st.text_input("Sito")

    with col3:
        search_free = st.text_input("Testo libero")

    filtered_df = full_df.copy()

    # 🔹 ricerca semplice globale
    if search_mrbts or search_sito or search_free:
        search_text = f"{search_mrbts} {search_sito} {search_free}"
        filtered_df = filtered_df[
            filtered_df.astype(str).apply(
                lambda row: row.str.contains(search_text, case=False).any(),
                axis=1
            )
        ]

    st.write(f"Risultati trovati: {len(filtered_df)}")

    if len(filtered_df) == 0:
        st.warning("Nessun risultato trovato")
        st.stop()

    # =========================================================
    # RISULTATI
    # =========================================================
    st.subheader("📋 Risultati")

    preview_cols = [
        "SiteMainPar - eNB id",
        "SiteMainPar - eNB Name",
        "SiteMainPar - BTS Name",
        "source_file"
    ]

    valid_preview = [c for c in preview_cols if c in filtered_df.columns]

    if valid_preview:
        st.dataframe(filtered_df[valid_preview], use_container_width=True)
    else:
        st.dataframe(filtered_df)

    selected_index = st.selectbox(
        "Seleziona la riga da dettagliare",
        options=filtered_df.index.tolist(),
        format_func=lambda x: f"Riga {x}"
    )

    selected_row = filtered_df.loc[[selected_index]]

    st.divider()

    # =========================================================
    # MAPPING SEZIONI
    # =========================================================

    ANAGRAFICA = [
        "SiteMainPar - eNB id",
        "SiteMainPar - eNB Name",
        "SiteMainPar - BTS Name",
        "source_file"
    ]

    DET_4G = [
        "Addressing IPNO - 4G logical Control Plane IP@",
        "Addressing IPNO - 4G logical User Plane IP@",
        "Addressing IPNO - SRAN Management Plane IP@"
    ]

    DET_5G = [
        "Addressing IPNO - 5G logical Control Plane IP@",
        "Addressing IPNO - 5G logical User Plane IP@"
    ]

    DET_2G = [
        "2G VLAN#4 U/C-plane (IVIF) - 2G VLAN id#4 for U/C-Plane",
        "2G VLAN#5 omusig  (IVIF) - 2G VLAN id#5 for omusig-Plane"
    ]

    DET_SYNC = [
        "Features - Sync Type",
        "INTP - TP5000 IP address"
    ]

    DET_IPSEC = [
        "IPSECC - SEC-Gw IP@",
        "IPSECC - CA Server IP address"
    ]

    # =========================================================
    # RENDER UI
