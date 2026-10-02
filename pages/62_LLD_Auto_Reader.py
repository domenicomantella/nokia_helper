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
    "Lettura automatica del foglio TIM BSC "
    "e ricerca del blocco dati BSC."
)

st.info(
    "Questa pagina è sperimentale e separata dal Pool Builder stabile."
)


# ==========================================================
# SESSION STATE
# ==========================================================

DEFAULT_STATE = {
    "lld_analysis_done": False,
    "lld_status": "",
    "lld_error": "",
    "lld_file_type": "",
    "lld_sheet_names": [],
    "lld_tim_bsc_df": None,
    "lld_bsc_info": None,
    "lld_decrypted_bytes": None,
}


for key, default_value in DEFAULT_STATE.items():

    if key not in st.session_state:
        st.session_state[key] = default_value


# ==========================================================
# UTILITÀ GENERALI
# ==========================================================

def clean_value(value):
    """
    Converte un valore in stringa pulita.
    """

    if value is None:
        return ""

    if pd.isna(value):
        return ""

    value = str(value).strip()

    if value.lower() == "nan":
        return ""

    return value


def safe_get(row, index):
    """
    Accede in modo sicuro a una posizione della riga.
    """

    if index < len(row):
        return clean_value(row.iloc[index])

    return ""


def looks_like_ip(value):
    """
    Controllo semplice di un indirizzo IPv4.
    """

    return bool(
        re.fullmatch(
            r"(?:\d{1,3}\.){3}\d{1,3}",
            clean_value(value),
        )
    )


def looks_like_spc(value):
    """
    Riconosce uno SPC del tipo 3-1085.
    """

    return bool(
        re.fullmatch(
            r"\d+-\d+",
            clean_value(value),
        )
    )


def looks_like_epid(value):
    """
    Riconosce un EPID del tipo BBG60A3 o BBG60B3.
    """

    return bool(
        re.fullmatch(
            r"B[A-Z0-9]+[AB]\d+",
            clean_value(value).upper(),
        )
    )


def detect_container_type(file_bytes):
    """
    Rileva il tipo di contenitore dai primi byte.
    """

    if file_bytes.startswith(b"PK"):
        return "XLSX / ZIP OOXML"

    if file_bytes.startswith(
        b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    ):
        return "OLE2 Compound Document"

    return "Formato non riconosciuto"


def is_zip_bytes(file_bytes):
    """
    Verifica che il contenuto sia un archivio ZIP valido.
    """

    try:

        with zipfile.ZipFile(
            io.BytesIO(file_bytes)
        ) as archive:

            archive.testzip()

        return True

    except Exception:

        return False


# ==========================================================
# DIAGNOSTICA OLE
# ==========================================================

def inspect_ole_streams(file_bytes):
    """
    Restituisce gli stream interni del contenitore OLE.
    """

    streams = []

    try:

        buffer = io.BytesIO(file_bytes)

        if not olefile.isOleFile(buffer):
            return streams

        buffer.seek(0)

        with olefile.OleFileIO(buffer) as ole:

            streams = [
                "/".join(stream_path)
                for stream_path in ole.listdir()
            ]

    except Exception:

        return []

    return streams


def has_encrypted_package(file_bytes):
    """
    Verifica la presenza dello stream EncryptedPackage.
    """

    stream_names = inspect_ole_streams(
        file_bytes
    )

    return any(
        stream_name == "EncryptedPackage"
        or stream_name.endswith(
            "/EncryptedPackage"
        )
        for stream_name in stream_names
    )


def has_drm_streams(file_bytes):
    """
    Cerca elementi che suggeriscono protezione DRM
    o Microsoft Information Protection.
    """

    stream_names = inspect_ole_streams(
        file_bytes
    )

    indicators = (
        "DRMEncryptedDataSpace",
        "DRMEncryptedTransform",
        "LabelInfo",
    )

    return any(
        indicator.lower()
        in stream_name.lower()
        for stream_name in stream_names
        for indicator in indicators
    )


# ==========================================================
# APERTURA WORKBOOK
# ==========================================================

def decrypt_office_file(
    file_bytes,
    password,
):
    """
    Prova a decifrare un file Office cifrato
    utilizzando msoffcrypto.

    Restituisce:
    - byte decifrati;
    - tipo di cifratura rilevato.
    """

    source_buffer = io.BytesIO(
        file_bytes
    )

    office_file = msoffcrypto.OfficeFile(
        source_buffer
    )

    is_encrypted = office_file.is_encrypted()

    if not is_encrypted:

        return file_bytes, False

    if not password:

        raise ValueError(
            "Il documento risulta cifrato, "
            "ma non è stata inserita una password."
        )

    decrypted_buffer = io.BytesIO()

    office_file.load_key(
        password=password,
        verify_password=True,
    )

    office_file.decrypt(
        decrypted_buffer
    )

    decrypted_buffer.seek(0)

    decrypted_bytes = (
        decrypted_buffer.read()
    )

    if not decrypted_bytes:
        raise ValueError(
            "La decifratura non ha prodotto dati."
        )

    return decrypted_bytes, True


def read_excel_workbook(
    file_bytes,
    password="",
):
    """
    Prova ad aprire il workbook.

    Percorsi:

    1. XLSX standard
    2. XLS standard
    3. Office cifrato compatibile con msoffcrypto

    Restituisce:
    - dizionario dei fogli;
    - descrizione del metodo usato;
    - eventuali byte decifrati.
    """

    container_type = detect_container_type(
        file_bytes
    )

    # ------------------------------------------------------
    # XLSX NORMALE
    # ------------------------------------------------------

    if container_type == "XLSX / ZIP OOXML":

        workbook_buffer = io.BytesIO(
            file_bytes
        )

        sheets = pd.read_excel(
            workbook_buffer,
            sheet_name=None,
            header=None,
            engine="openpyxl",
        )

        return (
            sheets,
            "XLSX standard letto con openpyxl",
            None,
        )

    # ------------------------------------------------------
    # OLE2
    # ------------------------------------------------------

    if container_type == "OLE2 Compound Document":

        streams = inspect_ole_streams(
            file_bytes
        )

        encrypted_package = any(
            stream_name == "EncryptedPackage"
            or stream_name.endswith(
                "/EncryptedPackage"
            )
            for stream_name in streams
        )

        # --------------------------------------------------
        # OLE2 CON ENCRYPTEDPACKAGE
        # --------------------------------------------------

        if encrypted_package:

            decrypted_bytes, was_encrypted = (
                decrypt_office_file(
                    file_bytes=file_bytes,
                    password=password,
                )
            )

            if not is_zip_bytes(
                decrypted_bytes
            ):

                raise ValueError(
                    "Il pacchetto è stato elaborato, "
                    "ma il risultato non è un XLSX valido."
                )

            workbook_buffer = io.BytesIO(
                decrypted_bytes
            )

            sheets = pd.read_excel(
                workbook_buffer,
                sheet_name=None,
                header=None,
                engine="openpyxl",
            )

            method = (
                "Documento Office cifrato decifrato "
                "con msoffcrypto"
                if was_encrypted
                else "Documento Office non cifrato"
            )

            return (
                sheets,
                method,
                decrypted_bytes,
            )

        # --------------------------------------------------
        # XLS LEGACY CON WORKBOOK / BOOK
        # --------------------------------------------------

        legacy_buffer = io.BytesIO(
            file_bytes
        )

        sheets = pd.read_excel(
            legacy_buffer,
            sheet_name=None,
            header=None,
            engine="xlrd",
        )

        return (
            sheets,
            "XLS legacy letto con xlrd",
            None,
        )

    raise ValueError(
        "Il contenitore caricato non è stato riconosciuto."
    )


# ==========================================================
# RICERCA FOGLIO TIM BSC
# ==========================================================

def normalize_sheet_name(value):
    """
    Normalizza il nome di un foglio.
    """

    return re.sub(
        r"\s+",
        " ",
        clean_value(value),
    ).strip().upper()


def find_tim_bsc_sheet(sheets):
    """
    Cerca il foglio TIM BSC senza dipendere
    da maiuscole o spazi multipli.
    """

    for sheet_name, dataframe in sheets.items():

        normalized = normalize_sheet_name(
            sheet_name
        )

        if normalized == "TIM BSC":
            return sheet_name, dataframe

    return None, None


# ==========================================================
# ESTRAZIONE BLOCCO BSC
# ==========================================================

def find_bsc_header_row(df):
    """
    Cerca la riga di intestazione del blocco BSC network.

    Intestazioni attese nella stessa riga:

    BSC
    SPID (BSC)
    SPC (BSC)
    EPID
    VIF
    Local IP address
    """

    for row_index in range(len(df)):

        values = [
            clean_value(value)
            for value in df.iloc[
                row_index
            ].tolist()
        ]

        row_text = " ".join(
            values
        ).upper()

        conditions = [
            "BSC" in row_text,
            "SPID" in row_text,
            "SPC" in row_text,
            "EPID" in row_text,
            "LOCAL IP" in row_text,
        ]

        if all(conditions):
            return row_index

    return None


def extract_bsc_block(df):
    """
    Estrae il blocco BSC dal foglio TIM BSC.

    Non usa numeri di riga rigidi: trova prima
    l'intestazione e poi cerca le righe dati.
    """

    header_row = find_bsc_header_row(
        df
    )

    if header_row is None:
        return None, None

    search_end = min(
        header_row + 15,
        len(df),
    )

    first_data_row = None
    first_data_index = None

    for row_index in range(
        header_row + 1,
        search_end,
    ):

        row = df.iloc[
            row_index
        ]

        bsc = safe_get(row, 0)
        spid = safe_get(row, 1)
        spc = safe_get(row, 2)
        epid = safe_get(row, 3)
        local_ip = safe_get(row, 5)

        if (
            bsc
            and spid
            and looks_like_spc(spc)
            and looks_like_epid(epid)
            and looks_like_ip(local_ip)
        ):

            first_data_row = row
            first_data_index = row_index
            break

    if first_data_row is None:
        return None, None

    bsc_info = {
        "BSC": safe_get(
            first_data_row,
            0,
        ),
        "SPID": safe_get(
            first_data_row,
            1,
        ),
        "SPC": safe_get(
            first_data_row,
            2,
        ),
        "EPID_A": safe_get(
            first_data_row,
            3,
        ),
        "VIF_A": safe_get(
            first_data_row,
            4,
        ),
        "IP_A": safe_get(
            first_data_row,
            5,
        ),
        "SUBNET_A": safe_get(
            first_data_row,
            6,
        ),
        "PORT_A": safe_get(
            first_data_row,
            7,
        ),
        "EPID_B": "",
        "VIF_B": "",
        "IP_B": "",
        "SUBNET_B": "",
        "PORT_B": "",
    }

    for row_index in range(
        first_data_index + 1,
        search_end,
    ):

        row = df.iloc[
            row_index
        ]

        epid = safe_get(row, 3)
        local_ip = safe_get(row, 5)

        if (
        
