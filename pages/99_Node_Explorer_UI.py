import streamlit as st

# =====================================================
# CONFIGURAZIONE PAGINA
# =====================================================

st.set_page_config(
    page_title="Nokia Node Explorer",
    page_icon="📡",
    layout="wide"
)

# =====================================================
# HEADER FISSO DEL NODO
# =====================================================

st.title("📡 Nokia Node Explorer")

with st.container(border=True):

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "MRBTS-ID",
            "500838"
        )

    with col2:
        st.metric(
            "Nome Geografico",
            "MI_EXAMPLE"
        )

    with col3:
        st.metric(
            "Release SW",
            "SBTS25R1"
        )

st.divider()

# =====================================================
# MENU A SCHEDE PRINCIPALE
# =====================================================

tab_hw, tab_celle, tab_trasporto, tab_adiacenze, tab_security, tab_cerca = st.tabs(
    [
        "HW",
        "CELLE",
        "TRASPORTO",
        "ADIACENZE",
        "SECURITY",
        "CERCA CLASSE"
    ]
)

# =====================================================
# HW
# =====================================================

with tab_hw:

    hw_cabinet, hw_radio, hw_ret, hw_fpfh, hw_fse = st.tabs(
        [
            "Cabinet",
            "Radio",
            "LHA / RET",
            "FPFH",
            "FSE"
        ]
    )

    with hw_cabinet:

        st.subheader("Cabinet")

        st.info(
            "Qui verranno visualizzati BBMOD, SMOD, INVUNIT..."
        )

    with hw_radio:

        st.subheader("Radio")

        st.info(
            "Qui verranno visualizzati RMOD e relative informazioni runtime."
        )

    with hw_ret:

        st.subheader("LHA / RET")

        st.info(
            "Qui verranno visualizzati RETU, ALD, LNA."
        )

    with hw_fpfh:

        st.subheader("FPFH")

        st.info(
            "Sezione futura."
        )

    with hw_fse:

        st.subheader("FSE")

        st.info(
            "Sezione futura."
        )

# =====================================================
# CELLE
# =====================================================

with tab_celle:

    celle_lte, celle_nr, celle_gsm = st.tabs(
        [
            "LTE",
            "NR",
            "GSM"
        ]
    )

    with celle_lte:

        st.subheader("LTE")

        st.metric(
            "Numero Celle LTE",
            "9"
        )

    with celle_nr:

        st.subheader("NR")

        st.metric(
            "Numero Celle NR",
            "3"
        )

    with celle_gsm:

        st.subheader("GSM")

        st.metric(
            "Numero Celle GSM",
            "0"
        )

# =====================================================
# TRASPORTO
# =====================================================

with tab_trasporto:

    piano_ip, synch, ipsec = st.tabs(
        [
            "Piano Indirizzamento",
            "SYNCH",
            "IPsec"
        ]
    )

    with piano_ip:

        st.subheader("Piano Indirizzamento")

        st.info(
            "IP, Gateway, VLAN, Routing."
        )

    with synch:

        st.subheader("Synchronization")

        st.info(
            "PTP, NTP, SyncE."
        )

    with ipsec:

        st.subheader("IPsec")

        st.info(
            "Tunnel e
