import streamlit as st
import pandas as pd

st.title("📊 Ricerca TNL")

# =========================================================
# CONFIG
# =========================================================
SHEET_NAME = "TNL_TI_SRAN"   # <-- metti il nome reale del foglio

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
# FUNZIONI UTILI
# =========================================================
def columns_present(df, columns):
    """Restituisce solo le colonne effettivamente presenti nel dataframe."""
    return [col for col in columns if col in df.columns]

def section_has_data(row_df, columns):
    """Verifica se almeno una delle colonne della sezione contiene un valore utile."""
    existing = columns_present(row_df, columns)
    if not existing:
        return False

    temp = row_df[existing].copy()

    # converte tutto in stringa, toglie spazi e NaN
    temp = temp.fillna("").astype(str).apply(lambda col: col.str.strip())

    # se esiste almeno una cella valorizzata
    return (temp != "").any().any()

def render_section(title, row_df, columns):
    """Mostra la sezione solo se ci sono dati."""
    if section_has_data(row_df, columns):
        st.subheader(title)
        existing = columns_present(row_df, columns)
        section_df = row_df[existing].T.reset_index()
        section_df.columns = ["Campo", "Valore"]
        st.dataframe(section_df, use_container_width=True, hide_index=True)

# =========================================================
# CARICAMENTO DATI
# =========================================================
if uploaded_files:

    df_list = []

    for file in uploaded_files:
        try:
            df = pd.read_excel(file, sheet_name=SHEET_NAME)

            # elimina righe completamente vuote
            df = df.dropna(how="all")

            # elimina colonne unnamed
            df = df.loc[:, ~df.columns.astype(str).str.contains("^Unnamed", case=False)]

            df["source_file"] = file.name
            df_list.append(df)

        except Exception:
            continue

    if not df_list:
        st.error("❌ Nessun file valido (controlla nome foglio o struttura file)")
        st.stop()

    full_df = pd.concat(df_list, ignore_index=True)

    st.success(f"✅ Caricati {len(uploaded_files)} file")
    st.write(f"Totale righe utili: {len(full_df)}")

    # DEBUG FACOLTATIVO
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

    # -----------------------------
    # FILTRO MRBTS
    # -----------------------------
    # Sostituisci qui il nome reale colonna MRBTS se lo conosci
    POSSIBLE_MRBTS_COLS = ["MRBTS", "MRBTS_ID", "MeContext", "ManagedElement"]

    if search_mrbts:
        possible_cols = columns_present(filtered_df, POSSIBLE_MRBTS_COLS)

        if possible_cols:
            mask = False
            for col in possible_cols:
                mask = mask | filtered_df[col].astype(str).str.contains(search_mrbts, case=False, na=False)
            filtered_df = filtered_df[mask]
        else:
            # fallback su ricerca globale
            filtered_df = filtered_df[
                filtered_df.astype(str).apply(
                    lambda row: row.str.contains(search_mrbts, case=False).any(),
                    axis=1
                )
            ]

    # -----------------------------
    # FILTRO SITO
    # -----------------------------
    POSSIBLE_SITO_COLS = ["SITO", "Site", "SiteName", "NOME_LOCALITA", "NOME"]

    if search_sito:
        possible_cols = columns_present(filtered_df, POSSIBLE_SITO_COLS)

        if possible_cols:
            mask = False
            for col in possible_cols:
                mask = mask | filtered_df[col].astype(str).str.contains(search_sito, case=False, na=False)
            filtered_df = filtered_df[mask]
        else:
            filtered_df = filtered_df[
                filtered_df.astype(str).apply(
                    lambda row: row.str.contains(search_sito, case=False).any(),
                    axis=1
                )
            ]

    # -----------------------------
    # FILTRO TESTO LIBERO
    # -----------------------------
    if search_free:
        filtered_df = filtered_df[
            filtered_df.astype(str).apply(
                lambda row: row.str.contains(search_free, case=False).any(),
                axis=1
            )
        ]

    st.write(f"Risultati trovati: {len(filtered_df)}")

    if len(filtered_df) == 0:
        st.warning("Nessun risultato trovato")
        st.stop()

    # =========================================================
    # LISTA RISULTATI
    # =========================================================
    st.subheader("📋 Risultati")

    # colonne sintetiche da adattare
    preview_cols_candidates = [
        "MRBTS", "MRBTS_ID", "MeContext",
        "SITO", "Site", "SiteName", "NOME_LOCALITA", "NOME",
        "source_file"
    ]

    preview_cols = columns_present(filtered_df, preview_cols_candidates)

    if preview_cols:
        st.dataframe(filtered_df[preview_cols], use_container_width=True)
    else:
        st.dataframe(filtered_df, use_container_width=True)

    # selezione record
    selected_index = st.selectbox(
        "Seleziona la riga da dettagliare",
        options=filtered_df.index.tolist(),
        format_func=lambda x: f"Riga {x}"
    )

    selected_row = filtered_df.loc[[selected_index]]

    st.divider()

    # =========================================================
    # SEZIONI DETTAGLIO
    # =========================================================

    # -----------------------------
    # ANAGRAFICA
    # -----------------------------
    anagrafica_cols = [
        "MRBTS", "MRBTS_ID", "MeContext",
        "SITO", "Site", "SiteName",
        "NOME", "Name", "NOME_LOCALITA",
        "source_file"
    ]

    # -----------------------------
    # DETTAGLIO 4G
    # -----------------------------
    dettaglio_4g_cols = [
        "LTE", "4G", "LTE_IP", "LTE_PORT", "LTE_VLAN",
        "45G_Traffic", "InterfaceIPv4", "AddressIPv4"
    ]

    # -----------------------------
    # DETTAGLIO 5G
    # -----------------------------
    dettaglio_5g_cols = [
        "NR", "5G", "5G_IP", "5G_PORT", "5G_VLAN",
        "Node_Internal_F1", "NRDU", "NRCUCP", "4G5G_Traffic"
    ]

    # -----------------------------
    # DETTAGLIO 2G
    # -----------------------------
    dettaglio_2g_cols = [
        "GSM", "2G", "2G_IP", "2G_PORT", "2G_VLAN"
    ]

    # -----------------------------
    # DETTAGLIO SINCRONISMO
    # -----------------------------
    dettaglio_sync_cols = [
        "Sync", "Sincronismo", "Synchronization", "NTP", "PTP", "Clock"
    ]

    # -----------------------------
    # DETTAGLIO IPSEC
    # -----------------------------
    dettaglio_ipsec_cols = [
        "IPSec", "IPSEC", "Tunnel", "Tunnel_IPSec", "Security", "VPN"
    ]

    # Render sezioni
    render_section("🧾 Anagrafica", selected_row, anagrafica_cols)
    render_section("📡 Dettaglio 4G", selected_row, dettaglio_4g_cols)
    render_section("🛰️ Dettaglio 5G", selected_row, dettaglio_5g_cols)
    render_section("📞 Dettaglio 2G", selected_row, dettaglio_2g_cols)
    render_section("⏱️ Dettaglio Sincronismo", selected_row, dettaglio_sync_cols)
    render_section("🔐 Dettaglio IPSec", selected_row, dettaglio_ipsec_cols)
