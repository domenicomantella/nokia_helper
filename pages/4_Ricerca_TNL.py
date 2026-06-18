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
- Usare sempre file ufficiali
""")

st.caption(f"📄 Foglio utilizzato: {SHEET_NAME}")

# =========================================================
# UPLOAD
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

            # flatten colonne
            df.columns = [
                f"{str(c[0]).strip()} - {str(c[1]).strip()}"
                for c in df.columns
            ]

            # rimuove riga descrittiva
            df = df.iloc[1:]

            # pulizia
            df = df.dropna(how="all")
            df = df.loc[:, ~df.columns.str.contains("Unnamed", case=False)]

            df["source_file"] = file.name

            df_list.append(df)

        except Exception as e:
            st.error(f"Errore file {file.name}: {e}")

    if not df_list:
        st.error("❌ Nessun file valido")
        st.stop()

    full_df = pd.concat(df_list, ignore_index=True)

    # 🔥 evita problemi di tipi
    full_df = full_df.astype(str)

    st.success(f"✅ File caricati: {len(uploaded_files)}")
    st.write(f"Totale righe: {len(full_df)}")

    # DEBUG
    with st.expander("🔧 Colonne rilevate"):
        st.write(list(full_df.columns))

    # =========================================================
    # RICERCA
    # =========================================================
    st.subheader("🔎 Ricerca")

    c1, c2, c3 = st.columns(3)

    with c1:
        search_mrbts = st.text_input("MRBTS")

    with c2:
        search_sito = st.text_input("Sito")

    with c3:
        search_free = st.text_input("Testo libero")

    filtered_df = full_df.copy()

    if search_mrbts:
        filtered_df = filtered_df[
            filtered_df.apply(lambda r: r.str.contains(search_mrbts, case=False).any(), axis=1)
        ]

    if search_sito:
        filtered_df = filtered_df[
            filtered_df.apply(lambda r: r.str.contains(search_sito, case=False).any(), axis=1)
        ]

    if search_free:
        filtered_df = filtered_df[
            filtered_df.apply(lambda r: r.str.contains(search_free, case=False).any(), axis=1)
        ]

    st.write(f"Risultati trovati: {len(filtered_df)}")

    if filtered_df.empty:
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

    st.dataframe(filtered_df[valid_preview] if valid_preview else filtered_df)

    selected_index = st.selectbox(
        "Seleziona riga",
        filtered_df.index.tolist(),
        format_func=lambda x: f"Riga {x}"
    )

    row = filtered_df.loc[[selected_index]]

    st.divider()

    # =========================================================
    # SEZIONI
    # =========================================================
    ANAGRAFICA = [
        "SiteMainPar - eNB id",
        "SiteMainPar - eNB Name",
        "SiteMainPar - BTS Name",
        "source_file"
    ]

    DET_4G = [
        "Addressing IPNO - 4G logical Control Plane IP@",
        "Addressing IPNO - 4G logical User Plane IP@"
    ]

    DET_5G = [
        "Addressing IPNO - 5G logical Control Plane IP@",
        "Addressing IPNO - 5G logical User Plane IP@"
    ]

    DET_2G = [
        "2G VLAN#4 U/C-plane (IVIF) - 2G VLAN id#4 for U/C-Plane"
    ]

    DET_SYNC = [
        "Features - Sync Type",
        "INTP - TP5000 IP address"
    ]

    DET_IPSEC = [
        "IPSECC - SEC-Gw IP@"
    ]

    # =========================================================
    # OUTPUT
    # =========================================================
    render_section("🧾 Anagrafica", row, ANAGRAFICA)
    render_section("📡 Dettaglio 4G", row, DET_4G)
    render_section("🛰️ Dettaglio 5G", row, DET_5G)
    render_section("📞 Dettaglio 2G", row, DET_2G)
    render_section("⏱️ Sincronismo", row, DET_SYNC)
    render_section("🔐 IPSec", row, DET_IPSEC)
