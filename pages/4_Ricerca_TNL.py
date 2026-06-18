import streamlit as st
import pandas as pd
import os
import re

st.title("📊 Ricerca TNL")

# =========================================================
# CONFIG
# =========================================================
SHEET_NAME = "TNL_TI_SRAN"
BSC_MAPPING_FILE = "data/mapping_bsc.csv"

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
# LABEL MAP
# =========================================================
LABEL_MAP = {
    # ANAGRAFICA
    "SiteMainPar - eNB id": "MRBTS Id",
    "SiteMainPar - BTS Name": "Sito",
    "SiteMainPar - eNB Name": "Nome",
    "source_file": "File sorgente",

    # 4G
    "VLAN#2 M-plane (IVIF) - SRAN VLAN network interface #2 IP@": "Indirizzo IP O&M",
    "IPRT - DCN Gateway 2": "Indirizzo IP Def GTW",
    "VLAN#2 M-plane (IVIF) - SRAN VLAN id#2 for M-Plane": "VLAN O&M",
    "4G VLAN#1 U/C/S-plane (IVIF) - 4G VLAN network interface #1 IP@": "Indirizzo IP 45G",
    "IPRT - 4G U/C Gateway 1": "Indirizzo IP Def GTW 45G",
    "4G VLAN#1 U/C/S-plane (IVIF) - 4G VLAN id#1 for U/C/S-Plane": "VLAN UserPlane 45G",

    # 5G
    "5G VLAN#1 U/C/S-plane (IVIF) - 5G VLAN network interface #1 IP@": "Indirizzo IP 45G",
    "IPRT - 5G U/C Gateway 1": "Indirizzo IP Def GTW 45G",
    "5G VLAN#1 U/C/S-plane (IVIF) - 5G VLAN id#1 for U/C/S-Plane": "VLAN UserPlane 45G",

    # SINCRONISMO
    "Features - Sync Type": "Tipo Sincronismo",
    "TOP - ToP master IP@": "Indirizzo IP Time Server",

    # IPSEC
    "Addressing IPNO - 4G logical Control Plane IP@": "Indirizzo IPSec 4G",
    "Addressing IPNO - 5G logical Control Plane IP@": "Indirizzo IPSec 5G",
    "IPSECC - SEC-Gw IP@": "TEP (SecGTW)",

    # 2G
    "BSC": "BSC",
    "2G VLAN#5 omusig  (IVIF) - 2G VLAN network interface #5 IP@": "OMUSIG",
    "2G VLAN#5 omusig  (IVIF) - 2G VLAN id#5 for omusig-Plane": "Vlan GSM"
}

# =========================================================
# FUNZIONI
# =========================================================
def normalize_id(value):
    """
    Normalizza ID numerici letti da Excel/CSV:
    - 416391.0 -> 416391
    - ' 416391 ' -> 416391
    - nan / None -> ''
    """
    value = str(value).strip()

    if value.lower() in ["nan", "none", ""]:
        return ""

    # Se è un intero letto come float, rimuove .0
    if re.fullmatch(r"-?\d+\.0", value):
        value = value[:-2]

    # Rimuove eventuali spazi residui
    return value.strip()


def clean_display_value(value):
    """
    Pulisce il valore da mostrare in UI.
    """
    value = str(value).strip()

    if value.lower() in ["nan", "none"]:
        return ""

    if re.fullmatch(r"-?\d+\.0", value):
        value = value[:-2]

    return value


@st.cache_data
def load_bsc_mapping():
    try:
        if not os.path.exists(BSC_MAPPING_FILE):
            st.error(f"❌ File mapping BSC non trovato: {BSC_MAPPING_FILE}")
            return {}

        # sep=None prova a riconoscere automaticamente "," o ";"
        df_bsc = pd.read_csv(
            BSC_MAPPING_FILE,
            dtype=str,
            sep=None,
            engine="python"
        )

        # Pulisce i nomi colonna
        df_bsc.columns = df_bsc.columns.astype(str).str.strip()

        col_id = None
        col_name = None

        for col in df_bsc.columns:
            normalized_col = (
                col.lower()
                .replace(" ", "")
                .replace("_", "")
                .replace("-", "")
            )

            if "bsc" in normalized_col and "id" in normalized_col:
                col_id = col

            if "bsc" in normalized_col and ("name" in normalized_col or "nome" in normalized_col):
                col_name = col

        if not col_id or not col_name:
            st.error(
                "❌ Colonne BSC non riconosciute nel CSV. "
                "Servono una colonna tipo 'BSC Id' e una tipo 'BSC Name'."
            )

            with st.expander("🔧 Debug colonne CSV"):
                st.write(df_bsc.columns.tolist())

            return {}

        # Normalizza chiavi e valori
        df_bsc[col_id] = df_bsc[col_id].apply(normalize_id)
        df_bsc[col_name] = df_bsc[col_name].fillna("").astype(str).str.strip()

        bsc_map = dict(zip(df_bsc[col_id], df_bsc[col_name]))

        return bsc_map

    except Exception as e:
        st.error(f"Errore lettura mapping BSC: {e}")
        return {}


def find_first_existing_column(df, possible_columns):
    for col in possible_columns:
        if col in df.columns:
            return col
    return None


def section_has_data(df, cols):
    valid = [c for c in cols if c in df.columns]

    if not valid:
        return False

    temp = df[valid].fillna("").astype(str).apply(lambda col: col.str.strip())
    temp = temp.replace(["nan", "NaN", "None"], "")

    return (temp != "").any().any()


def render_section(title, df, cols):
    valid = [c for c in cols if c in df.columns]

    if section_has_data(df, cols):
        st.subheader(title)

        out = df[valid].T.reset_index()
        out.columns = ["Campo", "Valore"]

        out["Campo"] = out["Campo"].apply(lambda x: LABEL_MAP.get(x, x))
        out["Valore"] = out["Valore"].apply(clean_display_value)

        st.dataframe(out, use_container_width=True, hide_index=True)


def render_section_always(title, df, cols):
    valid = [c for c in cols if c in df.columns]

    st.subheader(title)

    if valid:
        out = df[valid].T.reset_index()
        out.columns = ["Campo", "Valore"]

        out["Campo"] = out["Campo"].apply(lambda x: LABEL_MAP.get(x, x))
        out["Valore"] = out["Valore"].apply(clean_display_value)

        st.dataframe(out, use_container_width=True, hide_index=True)
    else:
        st.info("Nessun campo disponibile per questa sezione.")


# =========================================================
# CARICAMENTO DATI
# =========================================================
if uploaded_files:

    df_list = []

    for file in uploaded_files:
        try:
            df = pd.read_excel(file, sheet_name=SHEET_NAME, header=[0, 1])

            # Flatten header multi-riga
            df.columns = [
                f"{str(c[0]).strip()} - {str(c[1]).strip()}"
                for c in df.columns
            ]

            # Rimuove la prima riga descrittiva sotto l'intestazione
            df = df.iloc[1:]

            # Elimina righe completamente vuote
            df = df.dropna(how="all")

            # Elimina colonne Unnamed
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

    # Pulisce nan testuali
    full_df = full_df.replace(["nan", "NaN", "None"], "")

    # Fix .0 solo su interi letti come float
    full_df = full_df.replace(r"^(-?\d+)\.0$", r"\1", regex=True)

    # =========================================================
    # MAPPING BSC DA CSV
    # =========================================================
    BSC_MAP = load_bsc_mapping()

    possible_bsc_cols = [
        "RNC&amp;BSC - BSCid",
        "RNC&BSC - BSCid"
    ]

    bsc_col = find_first_existing_column(full_df, possible_bsc_cols)

    if bsc_col:
        full_df["_BSC_ID_NORMALIZED"] = full_df[bsc_col].apply(normalize_id)

        full_df["BSC"] = full_df["_BSC_ID_NORMALIZED"].apply(
            lambda x: BSC_MAP.get(x, x)
        )

        # Debug utile per verificare casi tipo 416391 -> BMI70D
        with st.expander("🔧 Debug BSC mapping"):
            st.write("Colonna BSC trovata:", bsc_col)
            st.write("Esempi ID Excel:", full_df["_BSC_ID_NORMALIZED"].drop_duplicates().head(20).tolist())
            st.write("Esempi chiavi CSV:", list(BSC_MAP.keys())[:20])
    else:
        full_df["BSC"] = ""

        with st.expander("🔧 Debug BSC mapping"):
            st.warning("Colonna BSCid non trovata nel file Excel.")
            st.write("Colonne disponibili:", list(full_df.columns))

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
    ANAGRAFICA = [
        "SiteMainPar - eNB id",
        "SiteMainPar - BTS Name",
        "SiteMainPar - eNB Name",
        "source_file"
    ]

    DET_4G = [
        "VLAN#2 M-plane (IVIF) - SRAN VLAN network interface #2 IP@",
        "IPRT - DCN Gateway 2",
        "VLAN#2 M-plane (IVIF) - SRAN VLAN id#2 for M-Plane",
        "4G VLAN#1 U/C/S-plane (IVIF) - 4G VLAN network interface #1 IP@",
        "IPRT - 4G U/C Gateway 1",
        "4G VLAN#1 U/C/S-plane (IVIF) - 4G VLAN id#1 for U/C/S-Plane"
    ]

    DET_5G = [
        "5G VLAN#1 U/C/S-plane (IVIF) - 5G VLAN network interface #1 IP@",
        "IPRT - 5G U/C Gateway 1",
        "5G VLAN#1 U/C/S-plane (IVIF) - 5G VLAN id#1 for U/C/S-Plane"
    ]

    DET_SYNC = [
        "Features - Sync Type",
        "TOP - ToP master IP@"
    ]

    DET_IPSEC = [
        "Addressing IPNO - 4G logical Control Plane IP@",
        "Addressing IPNO - 5G logical Control Plane IP@",
        "IPSECC - SEC-Gw IP@"
    ]

    DET_2G = [
        "BSC",
        "2G VLAN#5 omusig  (IVIF) - 2G VLAN network interface #5 IP@",
        "2G VLAN#5 omusig  (IVIF) - 2G VLAN id#5 for omusig-Plane"
    ]

    # =========================================================
    # UI A TAB
    # =========================================================

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🧾 Anagrafica",
        "📡 4G",
        "🛰️ 5G",
        "📞 2G",
        "🔐 IPSec",
        "⏱️ Sync"
    ])

    with tab1:
        render_section("Anagrafica", row, ANAGRAFICA)

    with tab2:
        render_section("Dettaglio 4G", row, DET_4G)

    with tab3:
        render_section("Dettaglio 5G", row, DET_5G)

    with tab4:
        # 2G sempre visibile
        render_section_always("Dettaglio 2G", row, DET_2G)

    with tab5:
        render_section("IPSec", row, DET_IPSEC)

    with tab6:
        # Sync sempre visibile
        render_section_always("Sincronismo", row, DET_SYNC)

