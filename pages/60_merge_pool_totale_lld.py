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

    lines = [
        l.strip()
        for l in text.splitlines()
        if l.strip()
    ]

    if len(lines) < 5:
        return None

    bsc_info = {}

    try:

        # prima riga dati

        first = lines[1].split("\t")

        bsc_info["BSC"] = first[0]
        bsc_info["SPID"] = first[1]
        bsc_info["SPC"] = first[2]

        bsc_info["EPID_A"] = first[3]
        bsc_info["IP_A"] = first[5]

        # ricerca seconda EPID

        for line in lines:

            cols = line.split("\t")

            if len(cols) > 3:

                epid = cols[3].strip()

                if epid.startswith("BBG") and epid != bsc_info["EPID_A"]:

                    bsc_info["EPID_B"] = epid

                    if len(cols) > 5:
                        bsc_info["IP_B"] = cols[5]

                    break

        return bsc_info

    except Exception:

        return None


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
