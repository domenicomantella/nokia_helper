import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="MSC Pool Builder V0",
    layout="wide"
)

st.title("MSC Pool Builder V0")


# =====================================================
# LETTURA DATI BSC
# =====================================================

def extract_bsc_info(df):

    header_row = None

    for idx in range(len(df)):

        row = (
            df.iloc[idx]
            .fillna("")
            .astype(str)
            .tolist()
        )

        text = " ".join(row).upper()

        if (
            "RELEASE BSC" in text
            and "APG" in text
            and "CTH" in text
        ):
            header_row = idx
            break

    if header_row is None:
        return None

    headers = (
        df.iloc[header_row]
        .fillna("")
        .astype(str)
        .tolist()
    )

    values = (
        df.iloc[header_row + 1]
        .fillna("")
        .astype(str)
        .tolist()
    )

    info = {}

    for h, v in zip(headers, values):

        h = h.strip()

        if h:
            info[h] = v.strip()

    return info


# =====================================================
# LETTURA DATI BSC NETWORK
# =====================================================

def extract_bsc_network(df):

    marker = None

    for idx in range(len(df)):

        row = (
            df.iloc[idx]
            .fillna("")
            .astype(str)
            .tolist()
        )

        text = " ".join(row).upper()

        if (
            "SPID (BSC)" in text
            and "SPC (BSC)" in text
        ):
            marker = idx
            break

    if marker is None:
        return None

    try:

        row_a = df.iloc[marker + 1]
        row_b = df.iloc[marker + 3]

        info = {
            "BSC": row_a[0],
            "SPID": row_a[1],
            "SPC": row_a[2],
            "EPID_A": row_a[3],
            "LOCAL_IP_A": row_a[5],
            "EPID_B": row_b[3],
            "LOCAL_IP_B": row_b[5]
        }

        return info

    except Exception:

        return None


# =====================================================
# LETTURA TABELLA MSC
# =====================================================

def extract_msc_table(df):

    start_row = None

    for idx in range(len(df)):

        row = (
            df.iloc[idx]
            .fillna("")
            .astype(str)
            .tolist()
        )

        text = " ".join(row).upper()

        if "TWO MULTI HOMING SCTP ASSOCIATIONS" in text:
            start_row = idx
            break

    if start_row is None:
        return None

    header_row = None

    for idx in range(start_row, start_row + 30):

        first_col = str(df.iloc[idx, 0]).strip().upper()

        if first_col == "MSC":
            header_row = idx
            break

    if header_row is None:
        return None

    records = []

    row = header_row + 1

    while row < len(df):

        msc = str(df.iloc[row, 0]).strip()

        if (
            msc == ""
            or msc.lower() == "nan"
            or msc.upper() == "MGW"
        ):
            break

        try:

            record = {
                "MSC": msc,
                "DPC": df.iloc[row, 2],
                "EPID": df.iloc[row, 3],
                "SAID1": df.iloc[row, 4],
                "RIP1": df.iloc[row, 5],
                "RIP2": df.iloc[row, 6],
                "RPN": df.iloc[row, 7],
                "PRIO": df.iloc[row, 8],
                "CNID": df.iloc[row, 9],
                "NRI": df.iloc[row, 10],
                "CAP": df.iloc[row, 11]
            }

            records.append(record)

        except Exception:
            pass

        row += 2

    return pd.DataFrame(records)


# =====================================================
# UI
# =====================================================

uploaded_file = st.file_uploader(
    "Carica LLD TIM BSC",
    type=["xlsx"]
)

if uploaded_file:

    try:

        xls = pd.ExcelFile(uploaded_file)

        tim_df = pd.read_excel(
            xls,
            sheet_name="TIM BSC",
            header=None
        )

        bsc_info = extract_bsc_info(tim_df)

        net_info = extract_bsc_network(tim_df)

        msc_df = extract_msc_table(tim_df)

        # ==========================================
        # BSC INFO
        # ==========================================

        if bsc_info:

            st.subheader("BSC")

            c1, c2, c3, c4 = st.columns(4)

            c1.metric(
                "BSC",
                bsc_info.get("BSC", "")
            )

            c2.metric(
                "Release",
                bsc_info.get("Release BSC", "")
            )

            c3.metric(
                "APG",
                bsc_info.get("APG- Release", "")
            )

            c4.metric(
                "CTH",
                bsc_info.get("CTH", "")
            )

        # ==========================================
        # NETWORK INFO
        # ==========================================

        if net_info:

            st.subheader("BSC Network")

            net_df = pd.DataFrame(
                [net_info]
            )

            st.dataframe(
                net_df,
                use_container_width=True
            )

        # ==========================================
        # MSC TABLE
        # ==========================================

        if msc_df is not None:

            st.subheader(
                f"MSC Pool ({len(msc_df)})"
            )

            st.dataframe(
                msc_df,
                use_container_width=True,
                height=500
            )

            csv = msc_df.to_csv(
                index=False
            )

            st.download_button(
                "Scarica CSV",
                csv,
                "msc_pool.csv",
                "text/csv"
            )

        else:

            st.error(
                "Tabella MSC non trovata"
            )

    except Exception as e:

        st.error(
            f"Errore: {e}"
        )