import io
import re

import pandas as pd
import streamlit as st


# ==========================================================
# CONFIGURAZIONE PAGINA
# ==========================================================

st.set_page_config(
    page_title="MSC Pool Builder",
    page_icon="🧩",
    layout="wide",
)

st.title("MSC Pool Builder")

st.caption(
    "Generazione dello script BSC per l'aggiunta "
    "delle destinazioni MSC selezionate."
)


# ==========================================================
# SESSION STATE
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
# UTILITÀ
# ==========================================================

def clean_value(value):
    """
    Converte il valore in stringa e rimuove
    spazi o valori NaN.
    """

    if value is None:
        return ""

    value = str(value).strip()

    if value.lower() == "nan":
        return ""

    return value


def safe_get(row, index):
    """
    Legge una posizione della riga senza generare IndexError.
    """

    if index < len(row):
        return clean_value(row[index])

    return ""


def looks_like_ip(value):
    """
    Riconoscimento semplice di un indirizzo IPv4.
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
    Riconosce EPID del tipo:

    BBG60A3
    BBG60B3

    mantenendo la regola abbastanza generica
    per altri nomi BSC.
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
    Riconosce MSC del tipo:

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
    Divide il testo copiato da Excel in righe e colonne
    mantenendo le celle vuote intermedie.
    """

    rows = []

    for raw_line in text.splitlines():

        if not raw_line.strip():
            continue

        columns = [
            clean_value(column)
            for column in raw_line.rstrip(
                "\r\n"
            ).split("\t")
        ]

        if any(columns):
            rows.append(columns)

    return rows


def format_nri(value):
    """
    Converte:

    76,77,78,11,12,13,116

    in:

    76&77&78&11&12&13&116
    """

    value = clean_value(value)

    nri_values = [
        item.strip()
        for item in re.split(
            r"[,;&\s]+",
            value,
        )
        if item.strip()
    ]

    return "&".join(nri_values)


def format_release(value):
    """
    Uniforma il testo release per l'intestazione.
    """

    value = clean_value(value)

    if not value:
        return ""

    if value.lower().startswith("release"):
        return value

    return f"Release {value}"


# ==========================================================
# PARSER BSC
# ==========================================================

def parse_bsc(text):
    """
    Estrae il blocco BSC copiato dal foglio TIM BSC.
    """

    rows = split_tabular_text(text)

    if not rows:
        return None

    first_row = None
    first_row_index = None

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
    Unisce le due righe fisiche di ogni MSC
    in un singolo record logico.
    """

    excel_rows = split_tabular_text(text)

    records = []
    current_record = None

    for row in excel_rows:

        first_column = safe_get(row, 0)

        # Nuovo MSC
        if looks_like_msc(first_column):

            if current_record is not None:
                records.append(current_record)

            current_record = {
                "MSC": safe_get(row, 0),
                "SPID": safe_get(row, 1),
                "DPC": safe_get(row, 2),
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
                "MSCNRILENGTH": safe_get(
                    row,
                    12,
                ),
            }

            continue

        # Secondo ramo SCTP del record corrente
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

            current_record["EPID_B"] = (
                epid_candidate
            )

            current_record["SAID_B"] = (
                said_candidate
            )

            current_record["REMOTE_IP_B1"] = (
                remote_ip_1
            )

            current_record["REMOTE_IP_B2"] = (
                remote_ip_2
            )

            current_record["RPN_B"] = safe_get(
                row,
                7,
            )

            current_record["PRIO_B"] = safe_get(
                row,
                8,
            )

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
    Controlla i campi BSC indispensabili.
    """

    if not bsc_info:

        return [
            "Tabella BSC non riconosciuta."
        ]

    issues = []

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

        if not clean_value(
            bsc_info.get(field)
        ):

            issues.append(
                f"Campo BSC mancante: {field}"
            )

    return issues


def validate_msc_df(msc_df):
    """
    Controlla che i record MSC contengano
    entrambi i rami SCTP e i dati comuni.
    """

    if msc_df is None or msc_df.empty:

        return [
            "Tabella MSC non riconosciuta."
        ]

    issues = []

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
        "RPN_A",
        "RPN_B",
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
            if not clean_value(
                row.get(field)
            )
        ]

        if missing_fields:

            issues.append(
                f"{msc_name}: campi mancanti "
                + ", ".join(missing_fields)
            )

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

    return issues


# ==========================================================
# GENERAZIONE SCRIPT
# ==========================================================

def append_section(
    output,
    separator,
    title,
):
    """
    Aggiunge un'intestazione di sezione.
    """

    output.append(f" !{separator}!")
    output.append(f" !*** {title} ***!")
    output.append(f" !{separator}!")


def generate_bsc_script(
    bsc_info,
    selected_df,
    release="25.Q4",
    company_group="[MR]",
):
    """
    Genera lo script completo BSC per tutti
    gli MSC selezionati.

    L'ordine delle sezioni replica il template
    operativo precedentemente analizzato.
    """

    lines = []

    bsc_name = clean_value(
        bsc_info.get("BSC")
    )

    epid_a = clean_value(
        bsc_info.get("EPID_A")
    )

    epid_b = clean_value(
        bsc_info.get("EPID_B")
    )

    local_ip_a = clean_value(
        bsc_info.get("IP_A")
    )

    local_ip_b = clean_value(
        bsc_info.get("IP_B")
    )

    # ------------------------------------------------------
    # DATI DI CENTRALE
    # ------------------------------------------------------

    lines.extend(
        [
            " !=============================================================!",
            " !                 *** DATI DI CENTRALE ***                    !",
            " !=============================================================!",
            f" ! CENTRALE       : {bsc_name:<43}!",
            " ! TIPOLOGIA      : BSC/EVO Controller 8230 R2    Rete  GSM/2G !",
            f" ! RELEASE        : {format_release(release):<43}!",
            f" ! SOCIETA-GRUPPO : {company_group:<43}!",
            " ! PREPARATO      :                                            !",
            " ! APPROVATO      :                                            !",
            " ! TELEFONO       :                                            !",
            " ! DATA FILE      :                                            !",
            " ! DATA PRINT     :                                            !",
            " ! INPUT          :                                            !",
            " ! COD ATTIVITA   :                                            !",
            " ! NOME FILE      : AoIP_Add-Node_a.Bsc                        !",
            " ! REVISIONE FILE : A                                          !",
            " ! COMMISSIONE    :                                            !",
            " ! TELEFONO REP   :                                            !",
            " ! VERIFICATO     :                                            !",
            " ! TELEFONO VER   :                                            !",
            " !=============================================================!",
            " ! NOTE           : Aggiunta nodi Core in Pool A Over IP       !",
            " !                  per BSC EvoC8230                           !",
            " !=============================================================!",
            "!CCITT7 SIGNALLING;",
        ]
    )

    # ------------------------------------------------------
    # MSC DEFINITION
    # ------------------------------------------------------

    append_section(
        lines,
        "-----------------------------",
        "MSC definition in Bsc",
    )

    lines.append(
        "     rrmbp:msc=all;"
    )

    lines.append(
        "     rltdp:msc=all;"
    )

    for _, row in selected_df.iterrows():

        msc = clean_value(row["MSC"])
        dpc = clean_value(row["DPC"])
        cnid = clean_value(row["CNID"])

        lines.append(
            f"     RRMBI:MSC={msc}, "
            f"SP={dpc}, "
            f"CNID={cnid};"
            f"    !* MSC Server - {msc}!"
        )

    lines.append(
        "     rrmbp:msc=all;"
    )

    lines.append(
        "     rltdp:msc=all;"
    )

    # ------------------------------------------------------
    # NRI
    # ------------------------------------------------------

    append_section(
        lines,
        "-----------------------------------",
        "Define NRI Value and Lenght",
    )

    lines.append(
        "     rrnrp:msc=all;"
    )

    lines.append(
        "     rrnlp;"
    )

    for _, row in selected_df.iterrows():

        msc = clean_value(row["MSC"])
        nri = format_nri(row["NRI"])

        lines.append(
            f"     RRNRI:MSC={msc}, "
            f"NRI={nri};"
            f"    !* MSC Server - {msc}!"
        )

    lines.append(
        "     rrnrp:msc=all;"
    )

    lines.append(
        "     rrnlp;"
    )

    # ------------------------------------------------------
    # C7 SIGNALLING POINT
    # ------------------------------------------------------

    append_section(
        lines,
        "----------------------------------------------------",
        "C7 Signalling Point in the different Network",
    )

    lines.append(
        "     c7spp:sp=all;"
    )

    for _, row in selected_df.iterrows():

        msc = clean_value(row["MSC"])
        dpc = clean_value(row["DPC"])

        lines.append(
            f"     C7SPI:SP={dpc}, "
            f"NET=BOTH, PREF=IP, LMSG;"
            f"    !* MSC Server - {msc}!"
        )

        lines.append(
            f"     C7PNC:SP={dpc}, "
            f"SPID={msc};"
        )

    lines.append(
        "     c7spp:sp=all;"
    )

    # ------------------------------------------------------
    # SCCP NETWORK BROADCAST
    # ------------------------------------------------------

    append_section(
        lines,
        "-----------------------------------------------",
        "C7 SCCP Network Broadcast Status Change",
    )

    lines.append(
        "     c7ltp:ls=all;"
    )

    lines.append(
        "     c7rsp:dest=all;"
    )

    lines.append(
        "     c7ncp:sp=all,ssn=all;"
    )

    for _, row in selected_df.iterrows():

        msc = clean_value(row["MSC"])
        dpc = clean_value(row["DPC"])

        lines.append(
            f"     C7NPI:SP={dpc};"
            f"            !* MSC Server - {msc}!"
        )

        lines.append(
            f"     C7NPC:SP={dpc}, MSG=1;"
        )

        lines.append(
            f"     C7NSI:SP={dpc}, SSN=254;"
        )

    lines.append(
        "     c7ltp:ls=all;"
    )

    lines.append(
        "     c7rsp:dest=all;"
    )

    lines.append(
        "     c7ncp:sp=all,ssn=all;"
    )

    # ------------------------------------------------------
    # SIGTRAN COMMENT
    # ------------------------------------------------------

    lines.extend(
        [
            " !---------------------------------------------------------------!",
            " !   Sigtran Connection for signalling trasport                  !",
            " !---------------------------------------------------------------!",
        ]
    )

    # ------------------------------------------------------
    # SCTP ASSOCIATIONS
    # ------------------------------------------------------

    append_section(
        lines,
        "------------------------------------------------------------------",
        "Create SCTP Associations towards MSC Pool",
    )

    for _, row in selected_df.iterrows():

        msc = clean_value(row["MSC"])

        said_a = clean_value(
            row["SAID_A"]
        )

        said_b = clean_value(
            row["SAID_B"]
        )

        remote_a1 = clean_value(
            row["REMOTE_IP_A1"]
        )

        remote_a2 = clean_value(
            row["REMOTE_IP_A2"]
        )

        remote_b1 = clean_value(
            row["REMOTE_IP_B1"]
        )

        remote_b2 = clean_value(
            row["REMOTE_IP_B2"]
        )

        rpn_a = clean_value(
            row["RPN_A"]
        )

        rpn_b = clean_value(
            row["RPN_B"]
        )

        lines.append(
            f"     IHADI:SAID={said_a}, "
            f"EPID={epid_a}, "
            f'RIP="{remote_a1}"&"{remote_a2}", '
            f"SCTPCP, RPN={rpn_a};"
        )

        lines.append(
            f"     IHADI:SAID={said_b}, "
            f"EPID={epid_b}, "
            f'RIP="{remote_b1}"&"{remote_b2}", '
            f"SCTPCP, RPN={rpn_b};"
        )

        lines.append(
            f"     IHAPC:SAID={said_a}, "
            f'PLIP="{local_ip_a}", '
            f'PRIP="{remote_a1}";'
        )

        lines.append(
            f"     IHAPC:SAID={said_b}, "
            f'PLIP="{local_ip_b}", '
            f'PRIP="{remote_b1}";'
        )

    lines.append(
        "     ihclp:epid=all,said=all;"
    )

    lines.append(
        "     ihalp:epid=all;"
    )

    # ------------------------------------------------------
    # C7 SIGNALLING POINT CHANGE
    # ------------------------------------------------------

    append_section(
        lines,
        "----------------------------------",
        "C7 Signalling Point Change",
    )

    lines.append(
        "     c7spp:sp=all;"
    )

    for _, row in selected_df.iterrows():

        msc = clean_value(row["MSC"])
        dpc = clean_value(row["DPC"])

        lines.append(
            f"     C7SPC:SP={dpc}, "
            f"NET=BOTH, PREF=IP;"
            f"    !* MSC Server - {msc}!"
        )

    # ------------------------------------------------------
    # M3UA ROUTING SPECIFICATION
    # ------------------------------------------------------

    append_section(
        lines,
        "---------------------------------------------",
        "M3UA, Routing Specification, Initiate",
    )

    lines.append(
        "     m3rsp:dest=all;"
    )

    for _, row in selected_df.iterrows():

        dpc = clean_value(row["DPC"])
        said_a = clean_value(row["SAID_A"])
        said_b = clean_value(row["SAID_B"])
        prio_a = clean_value(row["PRIO_A"])
        prio_b = clean_value(row["PRIO_B"])

        lines.append(
            f"     M3RSI:DEST={dpc}, "
            f"SAID={said_a}, "
            f"PRIO={prio_a};"
        )

        lines.append(
            f"     M3RSI:DEST={dpc}, "
            f"SAID={said_b}, "
            f"PRIO={prio_b};"
        )

    # ------------------------------------------------------
    # SCTP ASSOCIATION STATE
    # ------------------------------------------------------

    append_section(
        lines,
        "----------------------------------------------------",
        "IP Transport, SCTP Association State, Change",
    )

    for _, row in selected_df.iterrows():

        said_a = clean_value(row["SAID_A"])
        said_b = clean_value(row["SAID_B"])

        lines.append(
            f"     IHASC:SAID={said_a}, "
            "PROC=ESTB, USER=M3UA, SCTPCP;"
        )

        lines.append(
            f"     IHASC:SAID={said_b}, "
            "PROC=ESTB, USER=M3UA, SCTPCP;"
        )

    # ------------------------------------------------------
    # M3UA ROUTING ACTIVATION
    # ------------------------------------------------------

    append_section(
        lines,
        "------------------------------------------",
        "M3UA, Routing Activation, Initiate",
    )

    for _, row in selected_df.iterrows():

        dpc = clean_value(row["DPC"])
        said_a = clean_value(row["SAID_A"])
        said_b = clean_value(row["SAID_B"])

        lines.append(
            f"     M3RAI:DEST={dpc}, "
            f"SAID={said_a};"
        )

        lines.append(
            f"     M3RAI:DEST={dpc}, "
            f"SAID={said_b};"
        )

    # ------------------------------------------------------
    # M3UA ASSOCIATION STATE
    # ------------------------------------------------------

    append_section(
        lines,
        "---------------------------------------",
        "M3UA, Association State, Change",
    )

    for _, row in selected_df.iterrows():

        said_a = clean_value(row["SAID_A"])
        said_b = clean_value(row["SAID_B"])

        lines.append(
            f"     M3ASC:SAID={said_a}, "
            "PROC=ACT;"
        )

        lines.append(
            f"     M3ASC:SAID={said_b}, "
            "PROC=ACT;"
        )

    # ------------------------------------------------------
    # TRAFFIC DISTRIBUTION
    # ------------------------------------------------------

    append_section(
        lines,
        "-----------------------------------------------------------------",
        "Radio Control Cell, MSC Traffic Distribution Data, Change",
    )

    lines.append(
        "     rltdp:msc=all;"
    )

    for _, row in selected_df.iterrows():

        msc = clean_value(row["MSC"])
        cap = clean_value(row["CAP"])

        lines.append(
            f"     RLTDC:MSC={msc}, "
            f"MODE=ACTIVE, "
            f"CAP={cap}, "
            "PART=100, RAND=219;"
        )

    lines.append(
        "     rltdp:msc=all;"
    )

    return "\n".join(lines) + "\n"


# ==========================================================
# CALLBACK
# ==========================================================

def run_analysis():
    """
    Esegue il parsing e salva i risultati
    nella sessione Streamlit.
    """

    bsc_text = st.session_state.get(
        "bsc_input_widget",
        "",
    )

    msc_text = st.session_state.get(
        "msc_input_widget",
        "",
    )

    st.session_state["bsc_text"] = bsc_text
    st.session_state["msc_text"] = msc_text

    bsc_info = parse_bsc(bsc_text)
    msc_df = parse_msc(msc_text)

    st.session_state["bsc_info"] = bsc_info
    st.session_state["msc_df"] = msc_df
    st.session_state["analysis_done"] = True

    if msc_df is not None and not msc_df.empty:

        st.session_state["selected_msc"] = (
            msc_df["MSC"].tolist()
        )

    else:

        st.session_state["selected_msc"] = []


def edit_input():
    """
    Torna agli input mantenendo i testi.
    """

    st.session_state["analysis_done"] = False


def reset_all():
    """
    Cancella completamente la sessione.
    """

    for key, default_value in DEFAULT_STATE.items():

        st.session_state[key] = default_value

    st.session_state["bsc_input_widget"] = ""
    st.session_state["msc_input_widget"] = ""


# ==========================================================
# INPUT
# ==========================================================

if not st.session_state["analysis_done"]:

    st.subheader("1. Inserimento dati")

    st.info(
        "Copia dal foglio TIM BSC del LLD il blocco BSC "
        "e il blocco MSC, includendo le intestazioni."
    )

    tab_bsc, tab_msc = st.tabs(
        [
            "Tabella BSC",
            "Tabella MSC",
        ]
    )

    with tab_bsc:

        st.text_area(
            "Incolla la tabella BSC",
            value=st.session_state["bsc_text"],
            height=260,
            key="bsc_input_widget",
        )

    with tab_msc:

        st.text_area(
            "Incolla la tabella MSC",
            value=st.session_state["msc_text"],
            height=430,
            key="msc_input_widget",
        )

    button_col_1, button_col_2 = st.columns(
        [3, 1]
    )

    with button_col_1:

        st.button(
            "Analizza tabelle",
            type="primary",
            use_container_width=True,
            on_click=run_analysis,
        )

    with button_col_2:

        st.button(
            "Azzera",
            use_container_width=True,
            on_click=reset_all,
        )


# ==========================================================
# RISULTATI E GENERAZIONE
# ==========================================================

else:

    bsc_info = st.session_state["bsc_info"]
    msc_df = st.session_state["msc_df"]

    st.subheader("2. Risultati analisi")

    top_col_1, top_col_2, top_col_3 = st.columns(
        [3, 1, 1]
    )

    with top_col_1:

        st.success(
            "Analisi memorizzata nella sessione."
        )

    with top_col_2:

        st.button(
            "Modifica dati",
            use_container_width=True,
            on_click=edit_input,
        )

    with top_col_3:

        st.button(
            "Nuova analisi",
            use_container_width=True,
            on_click=reset_all,
        )

    bsc_issues = validate_bsc_info(
        bsc_info
    )

    msc_issues = validate_msc_df(
        msc_df
    )

    # ------------------------------------------------------
    # BSC
    # ------------------------------------------------------

    st.markdown("### BSC")

    if bsc_info:

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "BSC",
            bsc_info.get("BSC", ""),
        )

        c2.metric(
            "SPID",
            bsc_info.get("SPID", ""),
        )

        c3.metric(
            "SPC",
            bsc_info.get("SPC", ""),
        )

        c4.metric(
            "EPID",
            (
                f"{bsc_info.get('EPID_A', '')} / "
                f"{bsc_info.get('EPID_B', '')}"
            ),
        )

        bsc_display_df = pd.DataFrame(
            [
                {
                    "Lato": "A",
                    "EPID": bsc_info.get(
                        "EPID_A",
                        "",
                    ),
                    "VIF": bsc_info.get(
                        "VIF_A",
                        "",
                    ),
                    "Local IP": bsc_info.get(
                        "IP_A",
                        "",
                    ),
                    "Porta": bsc_info.get(
                        "PORT_A",
                        "",
                    ),
                },
                {
                    "Lato": "B",
                    "EPID": bsc_info.get(
                        "EPID_B",
                        "",
                    ),
                    "VIF": bsc_info.get(
                        "VIF_B",
                        "",
                    ),
                    "Local IP": bsc_info.get(
                        "IP_B",
                        "",
                    ),
                    "Porta": bsc_info.get(
                        "PORT_B",
                        "",
                    ),
                },
            ]
        )

        st.dataframe(
            bsc_display_df,
            use_container_width=True,
            hide_index=True,
        )

    # ------------------------------------------------------
    # MSC
    # ------------------------------------------------------

    st.markdown("### MSC")

    if msc_df is not None and not msc_df.empty:

        available_msc = (
            msc_df["MSC"]
            .dropna()
            .astype(str)
            .tolist()
        )

        valid_previous_selection = [
            msc
            for msc in st.session_state[
                "selected_msc"
            ]
            if msc in available_msc
        ]

        st.session_state[
            "selected_msc"
        ] = valid_previous_selection

        selected_msc = st.multiselect(
            "MSC da includere nello script",
            options=available_msc,
            key="selected_msc",
        )

        selected_df = msc_df[
            msc_df["MSC"].isin(
                selected_msc
            )
        ].copy()

        m1, m2 = st.columns(2)

        m1.metric(
            "MSC disponibili",
            len(msc_df),
        )

        m2.metric(
            "MSC selezionati",
            len(selected_df),
        )

        preview_columns = [
            "MSC",
            "DPC",
            "EPID_A",
            "SAID_A",
            "EPID_B",
            "SAID_B",
            "CNID",
            "NRI",
            "CAP",
        ]

        st.dataframe(
            selected_df[preview_columns],
            use_container_width=True,
            hide_index=True,
        )

        # --------------------------------------------------
        # PARAMETRI GENERAZIONE
        # --------------------------------------------------

        st.markdown(
            "### 3. Generazione script"
        )

        generation_col_1, generation_col_2 = (
            st.columns(2)
        )

        with generation_col_1:

            release = st.text_input(
                "Release",
                value="25.Q4",
            )

        with generation_col_2:

            company_group = st.text_input(
                "Società / Gruppo",
                value="[MR]",
            )

        blocking_issues = (
            bsc_issues + msc_issues
        )

        if selected_df.empty:

            st.warning(
                "Seleziona almeno un MSC."
            )

        elif blocking_issues:

            st.error(
                "Lo script non può essere generato "
                "perché sono presenti dati mancanti."
            )

            with st.expander(
                "Visualizza anomalie",
                expanded=True,
            ):

                for issue in blocking_issues:
                    st.warning(issue)

        else:

            generated_script = (
                generate_bsc_script(
                    bsc_info=bsc_info,
                    selected_df=selected_df,
                    release=release,
                    company_group=company_group,
                )
            )

            output_file_name = (
                f"{bsc_info.get('BSC', 'BSC')}"
                "_MSC_POOL_ADD.txt"
            )

            st.download_button(
                "Scarica script BSC",
                data=generated_script.encode(
                    "utf-8"
                ),
                file_name=output_file_name,
                mime="text/plain",
                type="primary",
                use_container_width=True,
            )

            with st.expander(
                "Anteprima script",
                expanded=True,
            ):

                st.text_area(
                    "Script generato",
                    value=generated_script,
                    height=700,
                )

    else:

        st.error(
            "Tabella MSC non riconosciuta."
        )
