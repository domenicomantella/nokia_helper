import streamlit as st
import pandas as pd
import re

st.set_page_config(
    page_title="MSC Pool Builder V1",
    layout="wide"
)

st.title("MSC Pool Builder V1")

st.header("Upload LLD")

uploaded_file = st.file_uploader(
    "Carica LLD",
    type=["xls", "xlsx"]
)

if uploaded_file:

    st.write("Nome:", uploaded_file.name)
    st.write("Dimensione:", uploaded_file.size)

    st.success("File caricato correttamente")

st.header("Modalità Manuale")

bsc_text = st.text_area(
    "Incolla tabella BSC",
    height=200
)

msc_text = st.text_area(
    "Incolla tabella MSC",
    height=300
)

if st.button("Analizza"):

    st.write("Lunghezza BSC:", len(bsc_text))
    st.write("Lunghezza MSC:", len(msc_text))
