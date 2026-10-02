import io
import re
import zipfile

import msoffcrypto
import olefile
import pandas as pd
import streamlit as st


# ==========================================================
# CONFIGURAZIONE PAGINA
# ==========================================================

st.set_page_config(
    page_title="LLD Auto Reader",
    page_icon="🔎",
    layout="wide",
)

st.title("LLD Auto Reader")
st.caption(
    "Pagina sperimentale per leggere automaticamente il foglio TIM BSC "
    "da un file LLD, senza modificare il Pool Builder stabile."
)


# ==========================================================
# COSTANTI E SESSION STATE
# ==========================================================

STATE_DEFAULTS = {
    "auto_analysis_done": False,
    "auto_read_method": "",
    "auto_error": "",
    "auto_sheet_names": [],
    "auto_bsc_info": None,
    "auto_bsc_preview": None,
    "auto_tim_bsc_shape": None,
    "auto_decrypted_bytes": None,
    "auto_source_signature": "",
}

for state_key, default_value in STATE_DEFAULTS.items():
    if state_key not in st.session_state:
        st.session_state[state_key] = default_value


# ==========================================================
# FUNZIONI GENERALI
# ==========================================================

def clean_value(value):
    """Converte un valore Excel in una stringa pulita."""
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass

    value = str(value).strip()
    return "" if value.lower() == "nan" else value


def safe_get(row, index):
    """Legge una posizione di una Series/lista senza generare IndexError."""
    try:
        if hasattr(row, "iloc"):
            return clean_value(row.iloc[index])
        return clean_value(row[index])
    except (IndexError, KeyError, TypeError):
        return ""


def looks_like_ip(value):
    """Riconosce sintatticamente un indirizzo IPv4."""
    return bool(
        re.fullmatch(
            r"(?:\d{1,3}\.){3}\d{1,3}",
            clean_value(value),
        )
    )


def looks_like_spc(value):
    """Riconosce uno SPC nel formato numero-numero, ad esempio 3-1085."""
    return bool(
        re.fullmatch(
            r"\d+-\d+",
            clean_value(value),
        )
    )


def looks_like_epid(value):
    """Riconosce EPID del tipo BBG60A3 / BBG60B3."""
    return bool(
        re.fullmatch(
            r"B[A-Z0-9]+[AB]\d+",
            clean_value(value).upper(),
        )
    )


def detect_container_type(file_bytes):
    """Rileva il contenitore dai byte iniziali."""
    if file_bytes.startswith(b"PK"):
        return "XLSX / ZIP OOXML"

    if file_bytes.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "OLE2 Compound Document"

    return "Formato non riconosciuto"


def is_valid_zip(file_bytes):
    """Verifica che i byte rappresentino un archivio ZIP leggibile."""
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as archive:
            archive.namelist()
        return True
    except (zipfile.BadZipFile, OSError, ValueError):
        return False


# ==========================================================
# DIAGNOSTICA OLE
# ==========================================================

def inspect_ole_streams(file_bytes):
    """Restituisce l'elenco degli stream presenti in un contenitore OLE."""
    source = io.BytesIO(file_bytes)

    try:
        if not olefile.isOleFile(source):
            return []

        source.seek(0)
        with olefile.OleFileIO(source) as ole:
            return ["/".join(parts) for parts in ole.listdir()]
    except Exception:
        return []


def stream_present(stream_names, target):
    """Controlla un nome stream anche quando è dentro un percorso OLE."""
    target_lower = target.lower()
    return any(
        stream_name.lower() == target_lower
        or stream_name.lower().endswith("/" + target_lower)
        for stream_name in stream_names
    )


def detect_protection_indicators(stream_names):
    """Restituisce gli indicatori di cifratura/DRM trovati negli stream."""
    indicators = []

    for label in (
        "EncryptedPackage",
        "DRMEncryptedDataSpace",
        "DRMEncryptedTransform",
        "LabelInfo",
    ):
        if any(label.lower() in name.lower() for name in stream_names):
            indicators.append(label)

    return indicators


# ==========================================================
# LETTURA E DECIFRATURA WORKBOOK
# ==========================================================

def decrypt_with_password(file_bytes, password):
    """
    Decifra in memoria un documento Office compatibile con msoffcrypto.
    Funziona per cifrature supportate dalla libreria e non aggira DRM
    basato sull'identità aziendale.
    """
    if not password:
        raise ValueError(
            "Il documento contiene EncryptedPackage. Inserisci una password "
            "Office solo se il file è protetto con una password conosciuta."
        )

    source = io.BytesIO(file_bytes)
    office_file = msoffcrypto.OfficeFile(source)

    if not office_file.is_encrypted():
        raise ValueError(
            "msoffcrypto riconosce il contenitore Office, ma non lo identifica "
            "come cifratura tramite password supportata."
        )

    office_file.load_key(
        password=password,
        verify_password=True,
    )

    decrypted = io.BytesIO()
    office_file.decrypt(decrypted, verify_integrity=True)
    decrypted.seek(0)
    result = decrypted.read()

    if not result:
        raise ValueError("La decifratura non ha prodotto alcun contenuto.")

    if not is_valid_zip(result):
        raise ValueError(
            "La decifratura ha prodotto dati, ma non un workbook XLSX valido."
        )

    return result


def read_all_sheets(file_bytes, password=""):
    """
    Legge tutti i fogli e restituisce:
    sheets, metodo_di_lettura, eventuali_byte_decifrati.
    """
    container_type = detect_container_type(file_bytes)

    if container_type == "XLSX / ZIP OOXML":
        sheets = pd.read_excel(
            io.BytesIO(file_bytes),
            sheet_name=None,
            header=None,
            engine="openpyxl",
        )
        return sheets, "XLSX standard letto con openpyxl", None

    if container_type != "OLE2 Compound Document":
        raise ValueError("Il file caricato non è un contenitore Excel riconosciuto.")

    streams = inspect_ole_streams(file_bytes)

    if stream_present(streams, "EncryptedPackage"):
        decrypted_bytes = decrypt_with_password(file_bytes, password)
        sheets = pd.read_excel(
            io.BytesIO(decrypted_bytes),
            sheet_name=None,
            header=None,
            engine="openpyxl",
        )
        return (
            sheets,
            "Pacchetto Office decifrato in memoria con msoffcrypto",
            decrypted_bytes,
        )

    # Se non c'è EncryptedPackage, prova il vecchio formato BIFF .xls.
    sheets = pd.read_excel(
        io.BytesIO(file_bytes),
        sheet_name=None,
        header=None,
        engine="xlrd",
    )
    return sheets, "XLS legacy letto con xlrd", None


# ==========================================================
# RICERCA FOGLIO TIM BSC
# ==========================================================

def normalize_sheet_name(value):
    return re.sub(r"\s+", " ", clean_value(value)).strip().upper()


def find_tim_bsc_sheet(sheets):
    """Trova il foglio TIM BSC ignorando maiuscole e spazi multipli."""
    for sheet_name, dataframe in sheets.items():
        if normalize_sheet_name(sheet_name) == "TIM BSC":
            return sheet_name, dataframe
    return None, None


# ==========================================================
# ESTRAZIONE BLOCCO BSC
# ==========================================================

def find_bsc_network_header(df):
    """
    Cerca l'intestazione del blocco con BSC, SPID, SPC, EPID e Local IP.
    La ricerca evita di dipendere dal numero fisso di riga del template.
    """
    for row_index in range(len(df)):
        values = [clean_value(value) for value in df.iloc[row_index].tolist()]
        row_text = " ".join(values).upper()

        if all(
            token in row_text
            for token in ("SPID", "SPC", "EPID", "LOCAL IP")
        ):
            return row_index

    return None


def extract_bsc_block(df):
    """Estrae i due rami locali A/B dal blocco BSC del foglio TIM BSC."""
    header_row = find_bsc_network_header(df)

    if header_row is None:
        return None, None

    search_end = min(header_row + 20, len(df))
    first_row = None
    first_index = None

    for row_index in range(header_row + 1, search_end):
        row = df.iloc[row_index]

        if (
            safe_get(row, 0)
            and safe_get(row, 1)
            and looks_like_spc(safe_get(row, 2))
            and looks_like_epid(safe_get(row, 3))
            and looks_like_ip(safe_get(row, 5))
        ):
            first_row = row
            first_index = row_index
            break

    if first_row is None:
        return None, None

    result = {
        "BSC": safe_get(first_row, 0),
        "SPID": safe_get(first_row, 1),
        "SPC": safe_get(first_row, 2),
        "EPID_A": safe_get(first_row, 3),
        "VIF_A": safe_get(first_row, 4),
        "IP_A": safe_get(first_row, 5),
        "SUBNET_A": safe_get(first_row, 6),
        "PORT_A": safe_get(first_row, 7),
        "EPID_B": "",
        "VIF_B": "",
        "IP_B": "",
        "SUBNET_B": "",
        "PORT_B": "",
    }

    for row_index in range(first_index + 1, search_end):
        row = df.iloc[row_index]
        epid = safe_get(row, 3)
        local_ip = safe_get(row, 5)

        if (
            looks_like_epid(epid)
            and epid != result["EPID_A"]
            and looks_like_ip(local_ip)
        ):
            result["EPID_B"] = epid
            result["VIF_B"] = safe_get(row, 4)
            result["IP_B"] = local_ip
            result["SUBNET_B"] = safe_get(row, 6)
            result["PORT_B"] = safe_get(row, 7)
            break

    preview_start = max(header_row - 1, 0)
    preview_end = min(search_end, len(df))
    preview = df.iloc[preview_start:preview_end].copy()
    preview.insert(0, "Riga dataframe", preview.index)
    preview.reset_index(drop=True, inplace=True)

    return result, preview


def validate_bsc(bsc_info):
    if not bsc_info:
        return ["Blocco BSC non trovato."]

    required = ["BSC", "SPID", "SPC", "EPID_A", "IP_A", "EPID_B", "IP_B"]
    return [
        f"Campo mancante: {field}"
        for field in required
        if not clean_value(bsc_info.get(field))
    ]


# ==========================================================
# RESET SESSIONE
# ==========================================================

def reset_results():
    for key, default_value in STATE_DEFAULTS.items():
        st.session_state[key] = default_value


# ==========================================================
# INTERFACCIA
# ==========================================================

uploaded_file = st.file_uploader(
    "Carica il file LLD",
    type=["xlsx", "xls", "xlsm"],
    help=(
        "La pagina prova XLSX standard, XLS legacy e pacchetti Office "
        "cifrati tramite password supportata."
    ),
)

if uploaded_file is None:
    st.info("Carica un file LLD per iniziare.")
    st.stop()

file_bytes = uploaded_file.getvalue()
container_type = detect_container_type(file_bytes)
ole_streams = (
    inspect_ole_streams(file_bytes)
    if container_type == "OLE2 Compound Document"
    else []
)
protection_indicators = detect_protection_indicators(ole_streams)
encrypted_package_present = stream_present(ole_streams, "EncryptedPackage")

st.markdown("### File caricato")
col_1, col_2, col_3 = st.columns(3)
col_1.metric("Nome", uploaded_file.name)
col_2.metric("Dimensione", f"{len(file_bytes):,} byte")
col_3.metric("Contenitore", container_type)

if encrypted_package_present:
    st.warning("È presente lo stream EncryptedPackage.")

if any(
    item in protection_indicators
    for item in ("DRMEncryptedDataSpace", "DRMEncryptedTransform", "LabelInfo")
):
    st.warning(
        "Il contenitore presenta indicatori DRM/LabelInfo. Se la protezione "
        "dipende dall'identità aziendale, una password Office potrebbe non "
        "essere sufficiente per aprire il documento nell'app Cloud."
    )

with st.expander("Diagnostica contenitore", expanded=False):
    st.write("Primi 64 byte:")
    st.code(repr(file_bytes[:64]))

    if ole_streams:
        st.write("Stream OLE:")
        st.code("\n".join(ole_streams))

password = ""
if encrypted_package_present:
    password = st.text_input(
        "Password Office, se prevista",
        type="password",
        help="La password viene usata solo in memoria e non viene salvata.",
    )

button_col_1, button_col_2 = st.columns([3, 1])
with button_col_1:
    analyze_clicked = st.button(
        "Leggi automaticamente il LLD",
        type="primary",
        use_container_width=True,
    )
with button_col_2:
    st.button(
        "Azzera risultati",
        use_container_width=True,
        on_click=reset_results,
    )

if analyze_clicked:
    reset_results()

    try:
        with st.spinner("Apertura e analisi del workbook..."):
            sheets, read_method, decrypted_bytes = read_all_sheets(
                file_bytes=file_bytes,
                password=password,
            )

            sheet_name, tim_bsc_df = find_tim_bsc_sheet(sheets)
            if tim_bsc_df is None:
                raise ValueError(
                    "Workbook aperto, ma il foglio TIM BSC non è stato trovato. "
                    f"Fogli disponibili: {', '.join(map(str, sheets.keys()))}"
                )

            bsc_info, bsc_preview = extract_bsc_block(tim_bsc_df)
            if bsc_info is None:
                raise ValueError(
                    "Foglio TIM BSC letto, ma il blocco BSC network non è stato trovato."
                )

            st.session_state["auto_analysis_done"] = True
            st.session_state["auto_read_method"] = read_method
            st.session_state["auto_sheet_names"] = list(sheets.keys())
            st.session_state["auto_bsc_info"] = bsc_info
            st.session_state["auto_bsc_preview"] = bsc_preview
            st.session_state["auto_tim_bsc_shape"] = tuple(tim_bsc_df.shape)
            st.session_state["auto_decrypted_bytes"] = decrypted_bytes
            st.session_state["auto_source_signature"] = repr(file_bytes[:16])

    except Exception as error:
        error_type = type(error).__name__
        error_message = str(error).strip() or "Errore senza descrizione."
        st.session_state["auto_error"] = f"{error_type}: {error_message}"

if st.session_state["auto_error"]:
    st.error("Il file non è stato aperto automaticamente.")
    st.code(st.session_state["auto_error"])

    if protection_indicators:
        st.info(
            "La diagnostica mostra una protezione Office. msoffcrypto gestisce "
            "cifrature supportate tramite password o chiavi compatibili, ma non "
            "fornisce automaticamente l'identità aziendale usata da Excel desktop."
        )

if st.session_state["auto_analysis_done"]:
    bsc_info = st.session_state["auto_bsc_info"]
    bsc_preview = st.session_state["auto_bsc_preview"]

    st.success("Workbook aperto e blocco BSC individuato.")
    st.write("**Metodo di lettura:**", st.session_state["auto_read_method"])
    st.write("**Dimensione foglio TIM BSC:**", st.session_state["auto_tim_bsc_shape"])

    with st.expander("Fogli trovati", expanded=False):
        for name in st.session_state["auto_sheet_names"]:
            st.write(f"- {name}")

    st.markdown("### Blocco BSC rilevato")
    metric_1, metric_2, metric_3 = st.columns(3)
    metric_1.metric("BSC", bsc_info.get("BSC", ""))
    metric_2.metric("SPID", bsc_info.get("SPID", ""))
    metric_3.metric("SPC", bsc_info.get("SPC", ""))

    bsc_table = pd.DataFrame(
        [
            {
                "Lato": "A",
                "EPID": bsc_info.get("EPID_A", ""),
                "VIF": bsc_info.get("VIF_A", ""),
                "Local IP": bsc_info.get("IP_A", ""),
                "Subnet": bsc_info.get("SUBNET_A", ""),
                "Porta": bsc_info.get("PORT_A", ""),
            },
            {
                "Lato": "B",
                "EPID": bsc_info.get("EPID_B", ""),
                "VIF": bsc_info.get("VIF_B", ""),
                "Local IP": bsc_info.get("IP_B", ""),
                "Subnet": bsc_info.get("SUBNET_B", ""),
                "Porta": bsc_info.get("PORT_B", ""),
            },
        ]
    )

    st.dataframe(bsc_table, use_container_width=True, hide_index=True)

    issues = validate_bsc(bsc_info)
    if issues:
        with st.expander("Anomalie BSC", expanded=True):
            for issue in issues:
                st.warning(issue)

    with st.expander("Righe originali intorno al blocco BSC", expanded=False):
        st.dataframe(bsc_preview, use_container_width=True, hide_index=True)

    decrypted_bytes = st.session_state["auto_decrypted_bytes"]
    if decrypted_bytes:
        st.download_button(
            "Scarica copia XLSX decifrata",
            data=decrypted_bytes,
            file_name="LLD_decrypted.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            use_container_width=True,
        )
