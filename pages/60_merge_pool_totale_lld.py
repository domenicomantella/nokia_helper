import streamlit as st
import pandas as pd
import re
import olefile
import tempfile

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

    if st.button(
        "Analizza LLD",
        use_container_width=True
    ):

        uploaded_file.seek(0)

        first_bytes = uploaded_file.read(64)

        uploaded_file.seek(0)

        st.subheader("Signature")

        st.code(
            repr(first_bytes)
        )

        st.subheader("Hex Dump")

        st.code(
            first_bytes.hex()
        )

        st.subheader("Tipo riconosciuto")

        if first_bytes.startswith(b"PK"):

            st.success(
                "Workbook XLSX (ZIP)"
            )

        elif first_bytes.startswith(
            b"\xd0\xcf\x11\xe0"
        ):

            st.warning(
                "Contenitore OLE2 legacy"
            )

        else:

            st.error(
                "Formato sconosciuto"
            )

        try:

            uploaded_file.seek(0)

            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".xls"
            ) as tmp:

                tmp.write(
                    uploaded_file.read()
                )

                temp_name = tmp.name

            ole = olefile.OleFileIO(
                temp_name
            )

            st.subheader(
                "Stream OLE trovati"
            )

            st.write(
                ole.listdir()
            )

        except Exception as e:

            st.exception(e)

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

    st.write(
        "Lunghezza BSC:",
        len(bsc_text)
    )

    st.write(
        "Lunghezza MSC:",
        len(msc_text)
    )
