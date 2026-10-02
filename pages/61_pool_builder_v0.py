import io
import re

import pandas as pd
import streamlit as st


# ==========================================================
# CONFIGURAZIONE PAGINA
# ==========================================================

st.set_page_config(
    page_title="MSC Pool Builder",
    layout="wide",
)

st.title("MSC Pool Builder")
st.caption(
    "Analisi delle tabelle BSC e MSC copiate dal foglio TIM BSC del file LLD."
)


# ==========================================================
# INIZIALIZZAZIONE SESSION STATE
# ==========================================================

DEFAULT_STATE = {
    "analysis_done": False,
    "bsc_text": "",
    "msc_text": "",
    "bsc_info": None,
    "msc_df": None,
    "selected_msc": [],
}


for key, default_value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = default_value


# ==========================================================
# FUNZIONI GENERALI
# ==========================================================

def clean_value(value):
    """
    Restituisce una stringa pulita.
    """

    if value is None:
        return ""

    value = str(value).strip()

    if value.lower() == "nan":
        return ""

    return value


def safe_get(row, index):
    """
    Legge una colonna senza generare IndexError.
    """

    if index < len(row):
        return clean_value(row[index])

    return ""


def normalize_spc(value):
    """
    Mantiene il formato SPC/DPC come stringa.

    Esempio:
    3-1085
    3-6423
    """

    return clean_value(value)


def looks_like_ip(value):
    """
    Controllo semplice del formato IPv4.
    """

    value = clean_value(value)

    return bool(
        re.fullmatch(
            r"(?:\d{1,3}\.){3}\d{1,3}",
            value,
        )
    )


def looks_like_epid(value):
    """
    Riconosce gli EPID del tipo BBG60A3 / BBG60B3.

    La regola non è limitata a BBG, così può funzionare
    anche con altri BSC.
    """

    value = clean_value(value).upper()

    return bool(
        re.fullmatch(
            r"B[A-Z0-9]+[AB]\d+",
            value,
        )
    )


def looks_like_msc(value):
    """
    Riconosce nomi MSC come:

    VTO30U
    VMI30U
    VRM30U
    VPI20U
    VNA40U
    """

    value = clean_value(value).upper()

    return bool(
        re.fullmatch(
            r"V[A-Z]{2}\d+[A-Z]",
            value,
        )
    )


def split_tabular_text(text):
    """
    Divide il testo copiato da Excel in righe e colonne,
    mantenendo anche le celle vuote intermedie.
    """

    rows = []

    for raw_line in text.splitlines():

        if not raw_line.strip():
            continue

        columns = [
            clean_value(column)
            for column in raw_line.rstrip("\r\n").split("\t")
        ]

        if any(columns):
            rows.append(columns)

    return rows


# ==========================================================
# PARSER BSC
# ==========================================================

def parse_bsc(text):
    """
    Estrae il blocco BSC copiato dal foglio TIM BSC.

    Struttura attesa:

    Riga A:
    BSC, SPID, SPC, EPID_A, VIF, IP locale A, subnet, porta

    Riga intermedia:
    EPID vuoto, eventuale altra VIF/IP

    Riga B:
    colonne iniziali vuote, EPID_B, VIF, IP locale B, subnet, porta

    Il parser cerca i valori in base alla struttura delle righe
    e non dipende dal nome specifico BBG60D.
    """

    rows = split_tabular_text(text)

    if not rows:
        return None

    first_row = None
    first_row_index = None

    # Cerca la riga principale BSC:
    # BSC, SPID, SPC, EPID, VIF, IP, subnet, porta.
    for index, row in enumerate(rows):

        bsc = safe_get(row, 0)
        spid = safe_get(row, 1)
        spc = safe_get(row, 2)
        epid = safe_get(row, 3)
        local_ip = safe_get(row, 5)

        if (
            bsc
            and spid
            and "-" in spc
            and looks_like_epid(epid)
            and looks_like_ip(local_ip)
        ):
            first_row = row
            first_row_index = index
            break

    if first_row is None:
        return None

    info = {
        "BSC": safe_get(first_row, 0),
        "SPID": safe_get(first_row, 1),
        "SPC": normalize_spc(safe_get(first_row, 2)),
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

    # Cerca la seconda riga fisica BSC, dopo la prima.
    for row in rows[first_row_index + 1:]:

        epid = safe_get(row, 3)
        local_ip = safe_get(row, 5)

        if (
            looks_like_epid(epid)
            and epid != info["EPID_A"]
            and looks_like_ip(local_ip)
        ):
            info["EPID_B"] = epid
            info["VIF_B"] = safe_get(row, 4)
            info["IP_B"] = local_ip
            info["SUBNET_B"] = safe_get(row, 6)
            info["PORT_B"] = safe_get(row, 7)
            break

    return info


# ==========================================================
# PARSER MSC
# ==========================================================

MSC_COLUMNS = [
    "MSC",
    "SPID",
    "DPC",
    "EPID_A",
    "SAID_A",
    "REMOTE_IP_A1",
    "REMOTE_IP_A2",
    "RPN_A",
    "PRIO_A",
    "EPID_B",
    "SAID_B",
    "REMOTE_IP_B1",
    "REMOTE_IP_B2",
    "RPN_B",
    "PRIO_B",
    "CNID",
    "NRI",
    "CAP",
    "MSCNRILENGTH",
]


def parse_msc(text):
    """
    Legge la tabella MSC copiata da Excel.

    Ogni MSC è formato da due righe fisiche:

    Prima riga:
    MSC, SPID, DPC, EPID_A, SAID_A, IP_A1, IP_A2,
    RPN_A, PRIO_A, CNID, NRI, CAP, MSCNRILENGTH

    Seconda riga:
    prime colonne vuote, EPID_B, SAID_B, IP_B1, IP_B2,
    RPN_B, PRIO_B

    Le due righe vengono unite in un solo record logico.
    """

    excel_rows = split_tabular_text(text)

    records = []
    current_record = None

    for row in excel_rows:

        first_column = safe_get(row, 0)

        # --------------------------------------------------
        # NUOVO RECORD MSC
        # --------------------------------------------------

        if looks_like_msc(first_column):

            if current_record is not None:
                records.append(current_record)

            current_record = {
                "MSC": safe_get(row, 0),
                "SPID": safe_get(row, 1),
                "DPC": normalize_spc(safe_get(row, 2)),
                "EPID_A": safe_get(row, 3),
                "SAID_A": safe_get(row, 4),
                "REMOTE_IP_A1": safe_get(row, 5),
                "REMOTE_IP_A2": safe_get(row, 6),
                "RPN_A": safe_get(row, 7),
                "PRIO_A": safe_get(row, 8),
                "EPID_B": "",
                "SAID_B": "",
                "REMOTE_IP_B1": "",
                "REMOTE_IP_B2": "",
                "RPN_B": "",
                "PRIO_B": "",
                "CNID": safe_get(row, 9),
                "NRI": safe_get(row, 10),
                "CAP": safe_get(row, 11),
                "MSCNRILENGTH": safe_get(row, 12),
            }

            continue

        # --------------------------------------------------
        # SECONDA RIGA DELLO STESSO MSC
        # --------------------------------------------------

        if current_record is None:
            continue

        epid_candidate = safe_get(row, 3)
        said_candidate = safe_get(row, 4)
        remote_ip_1 = safe_get(row, 5)
        remote_ip_2 = safe_get(row, 6)

        is_second_sctp_row = (
            looks_like_epid(epid_candidate)
            and said_candidate
            and looks_like_ip(remote_ip_1)
            and looks_like_ip(remote_ip_2)
        )

        if is_second_sctp_row:

            current_record["EPID_B"] = epid_candidate
            current_record["SAID_B"] = said_candidate
            current_record["REMOTE_IP_B1"] = remote_ip_1
            current_record["REMOTE_IP_B2"] = remote_ip_2
            current_record["RPN_B"] = safe_get(row, 7)
            current_record["PRIO_B"] = safe_get(row, 8)

    # Aggiunge l'ultimo record rimasto aperto.
    if current_record is not None:
        records.append(current_record)

    return pd.DataFrame(
        records,
        columns=MSC_COLUMNS,
    )


# ==========================================================
# VALIDAZIONE
# ==========================================================

def validate_bsc_info(bsc_info):
    """
    Restituisce un elenco di anomalie BSC.
    """

    issues = []

    if not bsc_info:
        return ["Tabella BSC non riconosciuta."]

    required_fields = [
        "BSC",
        "SPID",
        "SPC",
        "EPID_A",
        "IP_A",
        "EPID_B",
        "IP_B",
    ]

    for field in required_fields:
        if not clean_value(bsc_info.get(field)):
            issues.append(
                f"Campo BSC mancante: {field}"
            )

    return issues


def validate_msc_df(msc_df):
    """
    Restituisce un elenco di anomalie MSC.
    """

    issues = []

    if msc_df is None or msc_df.empty:
        return ["Tabella MSC non riconosciuta."]

    duplicate_msc = (
        msc_df["MSC"]
        .value_counts()
        .loc[lambda values: values > 1]
        .index
        .tolist()
    )

    if duplicate_msc:
        issues.append(
            "MSC duplicati: "
            + ", ".join(duplicate_msc)
        )

    required_fields = [
        "MSC",
        "DPC",
        "EPID_A",
        "SAID_A",
        "REMOTE_IP_A1",
        "REMOTE_IP_A2",
        "EPID_B",
        "SAID_B",
        "REMOTE_IP_B1",
        "REMOTE_IP_B2",
        "CNID",
        "NRI",
        "CAP",
    ]

    for row_index, row in msc_df.iterrows():

        msc_name = clean_value(
            row.get("MSC")
        ) or f"riga {row_index + 1}"

        missing_fields = [
            field
            for field in required_fields
            if not clean_value(row.get(field))
        ]

        if missing_fields:
            issues.append(
                f"{msc_name}: campi mancanti "
                + ", ".join(missing_fields)
            )

    return issues


# ==========================================================
# CALLBACK E 
