import streamlit as st

st.set_page_config(
    page_title="Test UI",
    layout="wide"
)

st.title("Nokia Node Explorer")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("MRBTS-ID", "500838")

with col2:
    st.metric("Nome", "MI_TEST")

with col3:
    st.metric("Release", "SBTS25R1")

st.divider()

tab_hw, tab_celle = st.tabs(
    ["HW", "CELLE"]
)

with tab_hw:
    st.write("Scheda HW")

with tab_celle:
    st.write("Scheda CELLE")
