import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="MSC Pool Builder V0",
    layout="wide"
)

st.title("MSC Pool Builder V0")


def detect_excel_engine(uploaded_file):
    """
    Determina se il file è XLSX o XLS
    guardando la signature binaria.
    """

    uploaded_file.seek(0)
    header = uploaded_file.read(8)
    uploaded_file.seek(0)

    # XLSX = ZIP
    if header.startswith(b"PK"):
        return "openpyxl"

    # XLS = OLE2
    if header.startswith(b"\xd0\xcf\x11\xe0"):
        return "xlrd"

    return None


uploaded_file = st.file_uploader(
    "Carica file LLD",
    type=["xlsx", "xls"]
)

if uploaded_file:

    st.subheader("Informazioni File")

    st.write("Nome:", uploaded_file.name)
    st.write("Tipo:", uploaded_file.type)
    st.write("Dimensione:", uploaded_file.size)

    try:

        engine = detect_excel_engine(uploaded_file)

        st.write("Engine rilevato:", engine)

        if engine is None:

            st.error(
                "Formato Excel non riconosciuto"
            )

            st.stop()

        uploaded_file.seek(0)

        workbook = pd.ExcelFile(
            uploaded_file,
            engine=engine
        )

        st.success(
            "Workbook aperto correttamente"
        )

        st.subheader("Fogli trovati")

        st.write(workbook.sheet_names)

        if "TIM BSC" in workbook.sheet_names:

            uploaded_file.seek(0)

            df = pd.read_excel(
                uploaded_file,
                sheet_name="TIM BSC",
                header=None,
                engine=engine
            )

            st.success(
                "Foglio TIM BSC letto correttamente"
            )

            st.write(
                "Dimensioni:",
                df.shape
            )

            st.subheader(
                "Prime 20 righe"
            )

            st.dataframe(
                df.head(20),
                use_container_width=True
            )

        else:

            st.warning(
                "Foglio TIM BSC non trovato"
            )

    except Exception as e:

        st.error(
            "Errore durante la lettura del file"
        )

        st.exception(e)
