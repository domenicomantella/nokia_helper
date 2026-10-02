import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="MSC Pool Builder V0",
    layout="wide"
)

st.title("MSC Pool Builder V0 - DEBUG")


uploaded_file = st.file_uploader(
    "Carica LLD TIM BSC",
    type=["xlsx"]
)

if uploaded_file:

    st.subheader("Informazioni File")

    st.write("Nome:", uploaded_file.name)
    st.write("Tipo:", uploaded_file.type)
    st.write("Dimensione:", uploaded_file.size)

    try:

        uploaded_file.seek(0)

        st.info("Tentativo apertura workbook...")

        workbook = pd.ExcelFile(
            uploaded_file,
            engine="openpyxl"
        )

        st.success("Workbook aperto correttamente")

        st.subheader("Fogli trovati")

        st.write(workbook.sheet_names)

        uploaded_file.seek(0)

        tim_df = pd.read_excel(
            uploaded_file,
            sheet_name="TIM BSC",
            header=None,
            engine="openpyxl"
        )

        st.success("Foglio TIM BSC letto correttamente")

        st.write("Dimensioni dataframe:")

        st.write(tim_df.shape)

        st.subheader("Anteprima prime 20 righe")

        st.dataframe(
            tim_df.head(20),
            use_container_width=True
        )

    except Exception as e:

        st.error("Errore durante la lettura del file")

        st.exception(e)
