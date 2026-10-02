import io
import re
import zipfile

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
    "Generazione script BSC per aggiunta destinazioni MSC."
)


# ==========================================================
# COSTANTI
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


DEFAULT_STATE = {
    "analysis_done": False,
    "bsc_text": "",
    "msc_text": "",
    "bsc_info": None,
    "msc_df": None,
}


for state_key, default_value in DEFAULT_STATE.items():
    if state_key not in st.session_state:
        st.session_state[state_key] = default_value


# ==========================================================
# FUNZIONI GENERALI
# ==========================================================

def clean_value(value):
    if value is None:
        return ""

    value = str(value).strip()

    if value.lower() == "nan":
        return ""

    return value


def safe_get(row, index):
    if index < len(row):
        return clean_value(row[index])

    return ""


def looks_like_ip(value):
    return bool(
        re.fullmatch(
            r"(?:\d{1,3}\.){3}\d{1,3}",
            clean_value(value),
        )
    )


def looks_like_epid(value):
    return bool(
        re.fullmatch(
            r"B[A-Z0-9]+[AB]\d+",
            clean_value(value).upper(),
        )
    )


def looks_like_msc(value):
    return bool(
        re.fullmatch(
            r"V[A-Z]{2}\d+[A-Z]",
            clean_value(value).upper(),
        )
    )


def split_tabular_text(text):
    """
    Divide il contenuto copiato da Excel utilizzando
    le tabulazioni e conserva le celle vuote intermedie.
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


def format_nri(value):
    """
    76,77,78,11,12,13,116
    diventa
    76&77&78&11&12&13&116
    """

    values = [
        item.strip()
        for item in re.split(
            r"[,;&\s]+",
            clean_value(value),
        )
        if item.strip()
    ]

    return "&".join(values)


def safe_file_part(value):
    value = clean_value(value)

    return re.sub(
        r"[^A-Za-z0-9_-]",
        "_",
        value,
    )


# ==========================================================
# PARSER BSC
# ==========================================================

def parse_bsc(text):
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

def parse_msc(text):
    """
    Ogni MSC è composto da due righe fisiche.

    Prima riga:
    dati comuni + ramo SCTP A.

    Seconda riga:
    ramo SCTP B.

    Il risultato contiene una sola riga logica per MSC.
    """

    excel_rows = split_tabular_text(text)

    records = []
    current_record = None

    for row in excel_rows:
        first_column = safe_get(row, 0)

        # Nuovo record MSC
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
                "MSCNRILENGTH": safe_get(row, 12),
            }

            continue

        # Seconda riga SCTP dello stesso MSC
        if current_record is None:
            continue

        epid_b = safe_get(row, 3)
        said_b = safe_get(row, 4)
        remote_ip_b1 = safe_get(row, 5)
        remote_ip_b2 = safe_get(row, 6)

        if (
            looks_like_epid(epid_b)
            and said_b
            and looks_like_ip(remote_ip_b1)
            and looks_like_ip(remote_ip_b2)
        ):
            current_record["EPID_B"] = epid_b
            current_record["SAID_B"] = said_b
            current_record["REMOTE_IP_B1"] = remote_ip_b1
            current_record["REMOTE_IP_B2"] = remote_ip_b2
            current_record["RPN_B"] = safe_get(row, 7)
            current_record["PRIO_B"] = safe_get(row, 8)

    if current_record is not None:
        records.append(current_record)

    return pd.DataFrame(
        records,
        columns=MSC_COLUMNS,
    )


# ==========================================================
# VALIDAZIONE
# ==========================================================

def validate_bsc(bsc_info):
    if not bsc_info:
        return ["Tabella BSC non riconosciuta."]

    issues = []

    required = [
        "BSC",
        "SPID",
        "SPC",
        "EPID_A",
        "IP_A",
        "EPID_B",
        "IP_B",
    ]

    for field in required:
        if not clean_value(bsc_info.get(field)):
            issues.append(
                f"Campo BSC mancante: {field}"
            )

    return issues


def validate_msc(msc_df):
    if msc_df is None or msc_df.empty:
        return ["Tabella MSC non riconosciuta."]

    issues = []

    required = [
        "MSC",
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
    ]

    for row_number, row in msc_df.iterrows():
        msc_name = clean_value(
            row.get("MSC")
        ) or f"riga {row_number + 1}"

        missing = [
            field
            for field in required
            if not clean_value(row.get(field))
        ]

        if missing:
            issues.append(
                f"{msc_name}: campi mancanti "
                + ", ".join(missing)
            )

    duplicates = (
        msc_df["MSC"]
        .value_counts()
        .loc[lambda values: values > 1]
        .index
        .tolist()
    )

    if duplicates:
        issues.append(
            "MSC duplicati: "
            + ", ".join(duplicates)
        )

    return issues


# ==========================================================
# GESTIONE CHECKBOX MSC
# ==========================================================

def msc_checkbox_key(msc_name):
    return (
        "msc_check_"
        + safe_file_part(msc_name)
    )


def remove_msc_checkbox_state():
    keys_to_remove = [
        key
        for key in list(st.session_state.keys())
        if key.startswith("msc_check_")
    ]

    for key in keys_to_remove:
        del st.session_state[key]


def initialize_msc_checkboxes(msc_df):
    if msc_df is None or msc_df.empty:
        return

    for msc_name in msc_df["MSC"].tolist():
        key = msc_checkbox_key(msc_name)

        if key not in st.session_state:
            st.session_state[key] = True


def select_all_msc():
    msc_df = st.session_state.get("msc_df")

    if msc_df is None or msc_df.empty:
        return

    for msc_name in msc_df["MSC"].tolist():
        st.session_state[
            msc_checkbox_key(msc_name)
        ] = True


def deselect_all_msc():
    msc_df = st.session_state.get("msc_df")

    if msc_df is None or msc_df.empty:
        return

    for msc_name in msc_df["MSC"].tolist():
        st.session_state[
            msc_checkbox_key(msc_name)
        ] = False


def get_selected_msc(msc_df):
    selected = []

    if msc_df is None or msc_df.empty:
        return selected

    for msc_name in msc_df["MSC"].tolist():
        if st.session_state.get(
            msc_checkbox_key(msc_name),
            False,
        ):
            selected.append(msc_name)

    return selected


# ==========================================================
# GENERATORE SCRIPT
# ==========================================================

def add_section(lines, separator, title):
    lines.append(f" !{separator}!")
    lines.append(f" !*** {title} ***!")
    lines.append(f" !{separator}!")


def generate_script(
    bsc_info,
    selected_df,
    release,
    company_group,
):
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

    release_text = clean_value(release)

    if (
        release_text
        and not release_text.lower().startswith("release")
    ):
        release_text = f"Release {release_text}"

    # ------------------------------------------------------
    # INTESTAZIONE
    # ------------------------------------------------------

    lines.extend(
        [
            " !=============================================================!",
            " !                 *** DATI DI CENTRALE ***                    !",
            " !=============================================================!",
            f" ! CENTRALE       : {bsc_name:<43}!",
            " ! TIPOLOGIA      : BSC/EVO Controller 8230 R2    Rete  GSM/2G !",
            f" ! RELEASE        : {release_text:<43}!",
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

    add_section(
        lines,
        "-----------------------------",
        "MSC definition in Bsc",
    )

    lines.append("     rrmbp:msc=all;")
    lines.append("     rltdp:msc=all;")

    for _, row in selected_df.iterrows():
        msc = clean_value(row["MSC"])
        dpc = clean_value(row["DPC"])
        cnid = clean_value(row["CNID"])

        lines.append(
            f"     RRMBI:MSC={msc}, "
            f"SP={dpc}, CNID={cnid};"
            f"    !* MSC Server - {msc}!"
        )

    lines.append("     rrmbp:msc=all;")
    lines.append("     rltdp:msc=all;")

    # ------------------------------------------------------
    # NRI
    # ------------------------------------------------------

    add_section(
        lines,
        "-----------------------------------",
        "Define NRI Value and Lenght",
    )

    lines.append("     rrnrp:msc=all;")
    lines.append("     rrnlp;")

    for _, row in selected_df.iterrows():
        msc = clean_value(row["MSC"])
        nri = format_nri(row["NRI"])

        lines.append(
            f"     RRNRI:MSC={msc}, "
            f"NRI={nri};"
            f"    !* MSC Server - {msc}!"
        )

    lines.append("     rrnrp:msc=all;")
    lines.append("     rrnlp;")

    # ------------------------------------------------------
    # C7 SIGNALLING POINT
    # ------------------------------------------------------

    add_section(
        lines,
        "----------------------------------------------------",
        "C7 Signalling Point in the different Network",
    )

    lines.append("     c7spp:sp=all;")

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

    lines.append("     c7spp:sp=all;")

    # ------------------------------------------------------
    # SCCP
    # ------------------------------------------------------

    add_section(
        lines,
        "-----------------------------------------------",
        "C7 SCCP Network Broadcast Status Change",
    )

    lines.append("     c7ltp:ls=all;")
    lines.append("     c7rsp:dest=all;")
    lines.append("     c7ncp:sp=all,ssn=all;")

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

    lines.append("     c7ltp:ls=all;")
    lines.append("     c7rsp:dest=all;")
    lines.append("     c7ncp:sp=all,ssn=all;")

    # ------------------------------------------------------
    # SIGTRAN
    # ------------------------------------------------------

    lines.extend(
        [
            " !---------------------------------------------------------------!",
            " !   Sigtran Connection for signalling trasport                  !",
            " !---------------------------------------------------------------!",
        ]
    )

    add_section(
        lines,
        "------------------------------------------------------------------",
        "Create SCTP Associations towards MSC Pool",
    )

    for _, row in selected_df.iterrows():
        said_a = clean_value(row["SAID_A"])
        said_b = clean_value(row["SAID_B"])

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

        rpn_a = clean_value(row["RPN_A"])
        rpn_b = clean_value(row["RPN_B"])

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
    lines.append("     ihalp:epid=all;")

    # ------------------------------------------------------
    # C7 CHANGE
    # ------------------------------------------------------

    add_section(
        lines,
        "----------------------------------",
        "C7 Signalling Point Change",
    )

    lines.append("     c7spp:sp=all;")

    for _, row in selected_df.iterrows():
        msc = clean_value(row["MSC"])
        dpc = clean_value(row["DPC"])

        lines.append(
            f"     C7SPC:SP={dpc}, "
            f"NET=BOTH, PREF=IP;"
            f"    !* MSC Server - {msc}!"
        )

    # ------------------------------------------------------
    # M3UA ROUTING
    # ------------------------------------------------------

    add_section(
        lines,
        "---------------------------------------------",
        "M3UA, Routing Specification, Initiate",
    )

    lines.append("     m3rsp:dest=all;")

    for _, row in selected_df.iterrows():
        dpc = clean_value(row["DPC"])
        said_a = clean_value(row["SAID_A"])
        said_b = clean_value(row["SAID_B"])
        prio_a = clean_value(row["PRIO_A"])
        prio_b = clean_value(row["PRIO_B"])

        lines.append(
            f"     M3RSI:DEST={dpc}, "
            f"SAID={said_a}, PRIO={prio_a};"
        )
        lines.append(
            f"     M3RSI:DEST={dpc}, "
            f"SAID={said_b}, PRIO={prio_b};"
        )

    # ------------------------------------------------------
    # SCTP STATE
    # ------------------------------------------------------

    add_section(
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
    # ROUTING ACTIVATION
    # ------------------------------------------------------

    add_section(
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
    # ASSOCIATION STATE
    # ------------------------------------------------------

    add_section(
        lines,
        "---------------------------------------",
        "M3UA, Association State, Change",
    )

    for _, row in selected_df.iterrows():
        said_a = clean_value(row["SAID_A"])
        said_b = clean_value(row["SAID_B"])

        lines.append(
            f"     M3ASC:SAID={said_a}, PROC=ACT;"
        )
        lines.append(
            f"     M3ASC:SAID={said_b}, PROC=ACT;"
        )

    # ------------------------------------------------------
    # TRAFFIC DISTRIBUTION
    # ------------------------------------------------------

    add_section(
        lines,
        "-----------------------------------------------------------------",
        "Radio Control Cell, MSC Traffic Distribution Data, Change",
    )

    lines.append("     rltdp:msc=all;")

    for _, row in selected_df.iterrows():
        msc = clean_value(row["MSC"])
        cap = clean_value(row["CAP"])

        lines.append(
            f"     RLTDC:MSC={msc}, "
            f"MODE=ACTIVE, CAP={cap}, "
            "PART=100, RAND=219;"
        )

    lines.append("     rltdp:msc=all;")

    return "\n".join(lines) + "\n"


# ==========================================================
# GENERAZIONE ZIP
# ==========================================================

def generate_zip(
    bsc_info,
    selected_df,
    release,
    company_group,
):
    zip_buffer = io.BytesIO()
    scripts = {}

    bsc_name = safe_file_part(
        bsc_info.get("BSC")
    ) or "BSC"

    with zipfile.ZipFile(
        zip_buffer,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for _, row in selected_df.iterrows():
            msc_name = safe_file_part(
                row["MSC"]
            )

            single_df = pd.DataFrame(
                [row.to_dict()],
                columns=selected_df.columns,
            )

            script_text = generate_script(
                bsc_info=bsc_info,
                selected_df=single_df,
                release=release,
                company_group=company_group,
            )

            file_name = (
                f"{bsc_name}_{msc_name}_ADD.txt"
            )

            archive.writestr(
                file_name,
                script_text.encode("utf-8"),
            )

            scripts[file_name] = script_text

    zip_buffer.seek(0)

    return zip_buffer.getvalue(), scripts


# ==========================================================
# WORKFLOW SESSIONE
# ==========================================================

def run_analysis():
    bsc_text = st.session_state.get(
        "bsc_input_widget",
        "",
    )

    msc_text = st.session_state.get(
        "msc_input_widget",
        "",
    )

    bsc_info = parse_bsc(bsc_text)
    msc_df = parse_msc(msc_text)

    st.session_state["bsc_text"] = bsc_text
    st.session_state["msc_text"] = msc_text
    st.session_state["bsc_info"] = bsc_info
    st.session_state["msc_df"] = msc_df
    st.session_state["analysis_done"] = True

    remove_msc_checkbox_state()
    initialize_msc_checkboxes(msc_df)


def edit_data():
    st.session_state["analysis_done"] = False


def reset_all():
    remove_msc_checkbox_state()

    widget_keys = [
        "bsc_input_widget",
        "msc_input_widget",
        "separate_files_widget",
        "release_widget",
        "company_widget",
        "preview_file_widget",
    ]

    for key in widget_keys:
        if key in st.session_state:
            del st.session_state[key]

    for key, default_value in DEFAULT_STATE.items():
        st.session_state[key] = default_value


# ==========================================================
# SCHERMATA INPUT
# ==========================================================

if not st.session_state["analysis_done"]:
    st.subheader("1. Inserimento dati")

    st.info(
        "Copia dal foglio TIM BSC del LLD il blocco BSC "
        "e il blocco MSC, includendo le intestazioni."
    )

    tab_bsc, tab_msc = st.tabs(
        ["Tabella BSC", "Tabella MSC"]
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
# SCHERMATA RISULTATI
# ==========================================================

else:
    bsc_info = st.session_state["bsc_info"]
    msc_df = st.session_state["msc_df"]

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
            on_click=edit_data,
        )

    with top_col_3:
        st.button(
            "Nuova analisi",
            use_container_width=True,
            on_click=reset_all,
        )

    bsc_issues = validate_bsc(bsc_info)
    msc_issues = validate_msc(msc_df)

    # ------------------------------------------------------
    # BSC
    # ------------------------------------------------------

    st.markdown("### BSC")

    if bsc_info:
        metric_1, metric_2, metric_3 = (
            st.columns(3)
        )

        metric_1.metric(
            "BSC",
            bsc_info.get("BSC", ""),
        )
        metric_2.metric(
            "SPID",
            bsc_info.get("SPID", ""),
        )
        metric_3.metric(
            "SPC",
            bsc_info.get("SPC", ""),
        )

        bsc_table = pd.DataFrame(
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
            bsc_table,
            use_container_width=True,
            hide_index=True,
        )

    # ------------------------------------------------------
    # MSC E CHECKBOX
    # ------------------------------------------------------

    st.markdown("### MSC")

    if msc_df is None or msc_df.empty:
        st.error("Tabella MSC non riconosciuta.")
        st.stop()

    initialize_msc_checkboxes(msc_df)

    select_col_1, select_col_2 = st.columns(2)

    with select_col_1:
        st.button(
            "Seleziona tutti",
            use_container_width=True,
            on_click=select_all_msc,
        )

    with select_col_2:
        st.button(
            "Deseleziona tutti",
            use_container_width=True,
            on_click=deselect_all_msc,
        )

    checkbox_columns = st.columns(3)

    for position, (_, row) in enumerate(
        msc_df.iterrows()
    ):
        msc_name = clean_value(row["MSC"])
        dpc = clean_value(row["DPC"])

        with checkbox_columns[position % 3]:
            st.checkbox(
                f"{msc_name} | {dpc}",
                key=msc_checkbox_key(msc_name),
            )

    selected_names = get_selected_msc(msc_df)

    selected_df = msc_df[
        msc_df["MSC"].isin(selected_names)
    ].copy()

    selected_df.reset_index(
        drop=True,
        inplace=True,
    )

    count_col_1, count_col_2 = st.columns(2)

    count_col_1.metric(
        "MSC disponibili",
        len(msc_df),
    )
    count_col_2.metric(
        "MSC selezionati",
        len(selected_df),
    )

    if not selected_df.empty:
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

        with st.expander(
            "Anteprima dati selezionati"
        ):
            st.dataframe(
                selected_df[preview_columns],
                use_container_width=True,
                hide_index=True,
            )

    # ------------------------------------------------------
    # GENERAZIONE
    # ------------------------------------------------------

    st.markdown("### Generazione script")

    generation_col_1, generation_col_2 = (
        st.columns(2)
    )

    with generation_col_1:
        release = st.text_input(
            "Release",
            value="25.Q4",
            key="release_widget",
        )

    with generation_col_2:
        company_group = st.text_input(
            "Società / Gruppo",
            value="[MR]",
            key="company_widget",
        )

    separate_files = st.checkbox(
        "Crea un file separato per ogni MSC",
        value=False,
        key="separate_files_widget",
        help=(
            "Se selezionato viene creato un TXT per ogni "
            "MSC e tutti i file vengono inseriti in uno ZIP."
        ),
    )

    if selected_df.empty:
        st.warning(
            "Seleziona almeno un MSC."
        )
        st.stop()

    selected_issues = validate_msc(selected_df)
    blocking_issues = bsc_issues + selected_issues

    if blocking_issues:
        st.error(
            "Sono presenti dati mancanti."
        )

        with st.expander(
            "Visualizza anomalie",
            expanded=True,
        ):
            for issue in blocking_issues:
                st.warning(issue)

        st.stop()

    bsc_name = safe_file_part(
        bsc_info.get("BSC")
    ) or "BSC"

    # ------------------------------------------------------
    # OUTPUT SEPARATI + ZIP
    # ------------------------------------------------------

    if separate_files:
        zip_data, generated_scripts = generate_zip(
            bsc_info=bsc_info,
            selected_df=selected_df,
            release=release,
            company_group=company_group,
        )

        st.success(
            f"Creati {len(generated_scripts)} file separati."
        )

        st.download_button(
            "Scarica ZIP con i file separati",
            data=zip_data,
            file_name=(
                f"{bsc_name}_MSC_SEPARATI.zip"
            ),
            mime="application/zip",
            type="primary",
            use_container_width=True,
        )

        files_df = pd.DataFrame(
            {
                "File nello ZIP": list(
                    generated_scripts.keys()
                )
            }
        )

        st.dataframe(
            files_df,
            use_container_width=True,
            hide_index=True,
        )

        preview_name = st.selectbox(
            "Anteprima di un file",
            options=list(
                generated_scripts.keys()
            ),
            key="preview_file_widget",
        )

        st.text_area(
            "Contenuto",
            value=generated_scripts[preview_name],
            height=700,
        )

    # ------------------------------------------------------
    # OUTPUT UNICO
    # ------------------------------------------------------

    else:
        combined_script = generate_script(
            bsc_info=bsc_info,
            selected_df=selected_df,
            release=release,
            company_group=company_group,
        )

        st.success(
            f"Creato uno script unico con "
            f"{len(selected_df)} MSC."
        )

        st.download_button(
            "Scarica script BSC unico",
            data=combined_script.encode("utf-8"),
            file_name=(
                f"{bsc_name}_MSC_POOL_ADD.txt"
            ),
            mime="text/plain",
            type="primary",
            use_container_width=True,
        )

        with st.expander(
            "Anteprima script unico",
            expanded=True,
        ):
            st.text_area(
                "Script generato",
                value=combined_script,
                height=700,
            )
