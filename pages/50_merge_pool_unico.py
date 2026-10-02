import streamlit as st
from io import StringIO

st.set_page_config(page_title="TXT Merge Tool", layout="wide")

st.title("TXT Merge Tool")

uploaded_files = st.file_uploader(
    "Carica i file TXT",
    type=["txt"],
    accept_multiple_files=True
)

def is_print_command(line):
    line = line.strip().lower()

    return (
        line.endswith("=all;")
        or ":msc=all;" in line
        or ":sp=all;" in line
        or ":dest=all;" in line
        or ":ls=all;" in line
        or ":ssn=all;" in line
        or ":epid=all;" in line
        or ":said=all;" in line
    )

def merge_files(files):

    merged_lines = []

    seen_prints = set()

    for file in files:

        text = file.read().decode("utf-8", errors="ignore")

        for raw_line in text.splitlines():

            line = raw_line.rstrip()

            if not line:
                merged_lines.append("")
                continue

            # Mantieni sempre i commenti
            if line.lstrip().startswith("!"):
                merged_lines.append(line)
                continue

            # Gestione print generali
            if is_print_command(line):

                key = line.strip().lower()

                if key not in seen_prints:
                    merged_lines.append(line)
                    seen_prints.add(key)

                continue

            # Tutto il resto sempre mantenuto
            merged_lines.append(line)

    return "\n".join(merged_lines)

if uploaded_files:

    merged_text = merge_files(uploaded_files)

    st.success(f"File elaborati: {len(uploaded_files)}")

    st.download_button(
        label="Scarica TXT Unificato",
        data=merged_text,
        file_name="merged_pool.txt",
        mime="text/plain"
    )

    with st.expander("Anteprima"):
        st.text_area(
            "",
            merged_text,
            height=600
        )