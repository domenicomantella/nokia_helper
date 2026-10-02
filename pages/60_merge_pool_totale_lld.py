import streamlit as st

st.set_page_config(
    page_title="MSC Pool Builder V0",
    layout="wide"
)

st.title("MSC Pool Builder V0 - DEBUG FILE")

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

        first_bytes = uploaded_file.read(20)

        st.subheader("Primi 20 bytes")

        st.code(repr(first_bytes))

        uploaded_file.seek(0)

        file_bytes = uploaded_file.read()

        st.subheader("Dimensione byte letti")

        st.write(len(file_bytes))

    except Exception as e:

        st.exception(e)
