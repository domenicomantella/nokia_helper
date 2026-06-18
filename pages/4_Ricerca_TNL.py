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
# LABEL MAP (nomi belli in UI)
# =========================================================
LABEL_MAP = {
    # -------------------------
    # ANAGRAFICA
    # -------------------------
    "SiteMainPar - eNB id": "MRBTS Id",
    "SiteMainPar - BTS Name": "Sito",
    "SiteMainPar - eNB Name": "Nome",
    "source_file": "File sorgente",

    # -------------------------
    # 4G
    # -------------------------
    "VLAN#2 M-plane (IVIF) - SRAN VLAN network interface #2 IP@": "Indirizzo IP O&M",
    "IPRT - DCN Gateway 2": "Indirizzo IP Def GTW",
    "VLAN#2 M-plane (IVIF) - SRAN VLAN id#2 for M-Plane": "VLAN O&M",
    "4G VLAN#1 U/C/S-plane (IVIF) - 4G VLAN network interface #1 IP@": "Indirizzo IP 45G",
    "IPRT - 4G U/C Gateway 1": "Indirizzo IP Def GTW 45G",
    "4G VLAN#1 U/C/S-plane (IVIF) - 4G VLAN id#1 for U/C/S-Plane": "VLAN UserPlane 45G",

    # -------------------------
    # 5G
    # -------------------------
    "5G VLAN#1 U/C/S-plane (IVIF) - 5G VLAN network interface #1 IP@": "Indirizzo IP 45G",
    "IPRT - 5G U/C Gateway 1": "Indirizzo IP Def GTW 45G",
    "5G VLAN#1 U/C/S-plane (IVIF) - 5G VLAN id#1 for U/C/S-Plane": "VLAN UserPlane 45G",

    # -------------------------
    # 2G
    # -------------------------
    "2G VLAN#4 U/C-plane (IVIF) - 2G VLAN id#4 for U/C-Plane": "VLAN 2G U/C",
    "2G VLAN#5 omusig  (IVIF) - 2G VLAN id#5 for omusig-Plane": "VLAN 2G omusig",

    # -------------------------
    # SINCRONISMO
    # -------------------------
    "Features - Sync Type": "Tipo sincronismo",
    "INTP - TP5000 IP address": "TP5000 IP address",

    # -------------------------
    # IPSEC
    # -------------------------
    "IPSECC - SEC-Gw IP@": "SEC-Gw IP",
    "IPSECC - CA Server IP address": "CA Server IP",
    "IPSECC - CA Name": "CA Name"
}

# =========================================================
# FUNZIONI
# =========================================================
def section_has_data(df, cols):
    valid = [c for c in cols if c in df.columns]
    if not valid:
        return False

    temp = df[valid].fillna("").astype(str).apply(lambda col: col.str.strip())
    return (temp != "").any().any()


def render_section(title, df, cols):
    valid = [c for c in cols if c in df.columns]

    if section_has_data(df, cols):
        st.subheader(title)

        out = df[valid].T.reset_index()
        out.columns = ["Campo", "Valore"]

        out["Campo"] = out["Campo"].apply(lambda x: LABEL_MAP.get(x, x))

        st.dataframe(out, use_container_width=True, hide_index=True)

# =========================================================
# CARICAMENTO DATI
# =========================================================
if uploaded_files:

    df_list = []

    for file in uploaded_files:
        try:
            df = pd.read_excel(file, sheet_name=SHEET_NAME, header=[0, 1])

            # Flatten colonne multiheader
            df.columns = [
                f"{str(c[0]).strip()} - {str(c[1]).strip()}"
                for c in df.columns
            ]

            # Rimuove la prima riga descrittiva sotto l'intestazione
            df = df.iloc[1:]

            # Elimina righe completamente vuote
            df = df.dropna(how="all")

            # Elimina colonne unnamed
            df = df.loc[:, ~df.columns.str.contains("Unnamed", case=False)]

            # Aggiunge file sorgente
            df["source_file"] = file.name

            df_list.append(df)

        except Exception as e:
            st.error(f"Errore file {file.name}: {e}")

    if not df_list:
        st.error("❌ Nessun file valido")
        st.stop()

    full_df = pd.concat(df_list, ignore_index=True)

    # Converte tutto in stringa
    full_df = full_df.astype(str)

    # =========================================================
    # FIX .0 SOLO SU VALORI INTERI LETTI COME FLOAT
    # Es: 123456.0 -> 123456
    # NON tocca IP tipo 10.0.0.1
    # =========================================================
    full_df = full_df.replace(r"^(-?\d+)\.0$", r"\1", regex=True)

    st.success(f"✅ File caricati: {len(uploaded_files)}")
    st.write(f"Totale righe: {len(full_df)}")

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
            filtered_df.apply(
                lambda r: r.str.contains(search_mrbts, case=False, regex=False).any(),
                axis=1
            )
        ]

    if search_sito:
        filtered_df = filtered_df[
            filtered_df.apply(
                lambda r: r.str.contains(search_sito, case=False, regex=False).any(),
                axis=1
            )
        ]

    if search_free:
        filtered_df = filtered_df[
            filtered_df.apply(
                lambda r: r.str.contains(search_free, case=False, regex=False).any(),
                axis=1
            )
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
        "SiteMainPar - BTS Name",
        "SiteMainPar - eNB Name",
        "source_file"
    ]

    valid_preview = [c for c in preview_cols if c in filtered_df.columns]

    st.dataframe(
        filtered_df[valid_preview] if valid_preview else filtered_df,
        use_container_width=True
    )

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

    # -------------------------
    # ANAGRAFICA
    # -------------------------
    ANAGRAFICA = [
        "SiteMainPar - eNB id",
        "SiteMainPar - BTS Name",
        "SiteMainPar - eNB Name",
        "source_file"
    ]

    # -------------------------
    # 4G
    # -------------------------
    DET_4G = [
        "VLAN#2 M-plane (IVIF) - SRAN VLAN network interface #2 IP@",
        "IPRT - DCN Gateway 2",
        "VLAN#2 M-plane (IVIF) - SRAN VLAN id#2 for M-Plane",
        "4G VLAN#1 U/C/S-plane (IVIF) - 4G VLAN network interface #1 IP@",
        "IPRT - 4G U/C Gateway 1",
        "4G VLAN#1 U/C/S-plane (IVIF) - 4G VLAN id#1 for U/C/S-Plane"
    ]

    # -------------------------
    # 5G
    # -------------------------
    DET_5G = [
        "5G VLAN#1 U/C/S-plane (IVIF) - 5G VLAN network interface #1 IP@",
        "IPRT - 5G U/C Gateway 1",
        "5G VLAN#1 U/C/S-plane (IVIF) - 5G VLAN id#1 for U/C/S-Plane"
    ]

    # -------------------------
    # 2G
    # -------------------------
    DET_2G = [
        "2G VLAN#4 U/C-plane (IVIF) - 2G VLAN id#4 for U/C-Plane",
        "2G VLAN#5 omusig  (IVIF) - 2G VLAN id#5 for omusig-Plane"
    ]

    # -------------------------
    # SINCRONISMO
    # -------------------------
    DET_SYNC = [
        "Features - Sync Type",
        "INTP - TP5000 IP address"
    ]

    # -------------------------
    # IPSEC
    # -------------------------
    DET_IPSEC = [
        "IPSECC - SEC-Gw IP@",
        "IPSECC - CA Server IP address",
        "IPSECC - CA Name"
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
