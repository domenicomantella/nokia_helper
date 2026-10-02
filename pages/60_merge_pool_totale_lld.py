import streamlit as st
import pandas as pd
import re

st.set_page_config(
    page_title="MSC Pool Builder V0",
    layout="wide"
)

st.title("MSC Pool Builder V0")


# ==========================================================
# PARSER BSC
# ==========================================================

def parse_bsc(text):

    rows = []

    for line in text.splitlines():

        cols = [
            c.strip()
            for c in line.split("\t")
        ]

        if any(cols):
            rows.append(cols)

    first_row = None
    second_row = None

    for r in rows:

        if len(r) > 5:

            # prima riga A

            if (
                len(r[0]) > 0
                and len(r[1]) > 0
                and "BBG" in r[3]
            ):

                first_row = r
                continue

            # seconda riga B

            if (
                len(r) > 3
                and r[3].startswith("BBG")
            ):

                second_row = r

                if first_row:
                    break

    if not first_row:
        return None

    info = {}

    info["BSC"] = first_row[0]
    info["SPID"] = first_row[1]
    info["SPC"] = first_row[2]

    info["EPID_A"] = first_row[3]
    info["IP_A"] = first_row[5]
    info["PORT_A"] = first_row[7]

    if second_row:

        info["EPID_B"] = second_row[3]
        info["IP_B"] = second_row[5]

        if len(second_row) > 7:
            info["PORT_B"] = second_row[7]

    return info

# ==========================================================
# PARSER MSC
# ==========================================================

def looks_like_msc(name):

    if not name:
        return False

    return bool(
        re.match(
            r"^V[A-Z]{2}\d+[A-Z]$",
            name.strip()
        )
    )


def parse_msc(text):

    rows = []

    for line in text.splitlines():

        line = line.strip()

        if not line:
            continue

        cols = line.split("\t")

        if len(cols) < 10:
            continue

        first_col = cols[0].strip()

        if not looks_like_msc(first_col):
            continue

        try:

            rows.append({
                "MSC": cols[0],
                "SPID": cols[1],
                "DPC": cols[2],
                "EPID_A": cols[3],
                "SAID_A": cols[4],
                "IP_A1": cols[5],
                "IP_A2": cols[6],
                "RPN": cols[7],
                "PRIO": cols[8],
                "CNID": cols[9],
                "NRI": cols[10],
                "CAP": cols[11],
                "MSCNRILENGTH": cols[12]
            })

        except Exception:
            pass

    return pd.DataFrame(rows)


# ==========================================================
# UI
# ==========================================================

tab_bsc, tab_msc = st.tabs(
    [
        "Tabella BSC",
        "Tabella MSC"
    ]
)

with tab_bsc:

    bsc_text = st.text_area(
        "Incolla la tabella BSC",
        height=250
    )

with tab_msc:

    msc_text = st.text_area(
        "Incolla la tabella MSC",
        height=400
    )


if st.button(
    "Analizza",
    use_container_width=True
):

    # ==========================================
    # BSC
    # ==========================================

    bsc_info = parse_bsc(
        bsc_text
    )

    st.subheader(
        "Informazioni BSC"
    )

    if bsc_info:

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "BSC",
            bsc_info.get("BSC", "")
        )

        c2.metric(
            "SPC",
            bsc_info.get("SPC", "")
        )

        c3.metric(
            "SPID",
            bsc_info.get("SPID", "")
        )

        st.json(
            bsc_info
        )

    else:

        st.error(
            "Tabella BSC non riconosciuta"
        )

    # ==========================================
    # MSC
    # ==========================================

    msc_df = parse_msc(
        msc_text
    )

    st.subheader(
        f"MSC trovati ({len(msc_df)})"
    )

    if len(msc_df):

        st.dataframe(
            msc_df,
            use_container_width=True,
            height=500
        )

    else:

        st.error(
            "Tabella MSC non riconosciuta"
        )
