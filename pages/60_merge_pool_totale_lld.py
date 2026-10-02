import streamlit as st
import olefile
import tempfile

st.set_page_config(
    page_title="LLD Inspector",
    layout="wide"
)

st.title("LLD Inspector")

uploaded_file = st.file_uploader(
    "Carica LLD",
    type=["xls", "xlsx"]
)

if uploaded_file:

    st.write("Nome:", uploaded_file.name)
    st.write("Dimensione:", uploaded_file.size)

    if st.button("Analizza LLD"):

        uploaded_file.seek(0)

        first_bytes = uploaded_file.read(64)

        uploaded_file.seek(0)

        st.subheader("Signature")
        st.code(repr(first_bytes))

        st.subheader("Hex Dump")
        st.code(first_bytes.hex())

        if first_bytes.startswith(b"\xd0\xcf\x11\xe0"):
            st.warning("Contenitore OLE2")

        elif first_bytes.startswith(b"PK"):
            st.success("Contenitore ZIP/XLSX")

        try:

            uploaded_file.seek(0)

            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".xls"
            ) as tmp:

                tmp.write(uploaded_file.read())
                temp_name = tmp.name

            ole = olefile.OleFileIO(temp_name)

            st.subheader("Stream OLE")

            st.write(ole.listdir())

        except Exception as e:

            st.exception(e)
