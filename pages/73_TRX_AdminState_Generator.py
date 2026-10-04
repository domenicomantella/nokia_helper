import streamlit as st
import pandas as pd
from datetime import datetime
from io import StringIO

st.set_page_config(page_title="TRX AdminState Generator", page_icon="📡", layout="wide")

st.title("📡 TRX AdminState Generator")
st.markdown("""
Genera automaticamente due piani NetAct:

- **bloccoTRX** → adminState = 3
- **sbloccoTRX** → adminState = 1

Partendo da un export CSV NetAct degli allarmi.
""")


def parse_csv(uploaded_file):
    content = uploaded_file.read().decode("utf-8", errors="ignore")
    lines = content.splitlines()

    alarm_number = ""
    alarm_text = ""
    header_index = None

    for idx, line in enumerate(lines):
        if line.startswith("Alarm number:"):
            alarm_number = line.replace("Alarm number:", "").strip()

        if line.startswith("Alarm text:"):
            alarm_text = line.replace("Alarm text:", "").strip()

        if line.strip().startswith("NE name"):
            header_index = idx
            break

    if header_index is None:
        raise ValueError("Intestazione 'NE name' non trovata")

    csv_data = "\n".join(lines[header_index:])
    df = pd.read_csv(StringIO(csv_data))

    if "NE name" not in df.columns:
        raise ValueError("Colonna 'NE name' non trovata")

    total_rows = len(df)
    df = df.drop_duplicates(subset=["NE name"])
    duplicates_removed = total_rows - len(df)

    ne_list = df["NE name"].astype(str).tolist()

    return alarm_number, alarm_text, ne_list, duplicates_removed



def generate_xml(ne_list, admin_state):
    timestamp_xml = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000+02:00")

    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append("<!DOCTYPE raml SYSTEM 'raml20.dtd'>")
    lines.append('<raml version="2.0" xmlns="raml20.xsd">')
    lines.append('  <cmData type="plan" scope="all">')
    lines.append('    <header>')
    lines.append(f'      <log dateTime="{timestamp_xml}" action="created" appInfo="TRX AdminState Generator">InternalValues are used</log>')
    lines.append('    </header>')

    for dn in ne_list:
        lines.append(f'    <managedObject class="TRX" version="ASBSCFP24R3" distName="{dn}" operation="update">')
        lines.append(f'      <p name="adminState">{admin_state}</p>')
        lines.append('    </managedObject>')

    lines.append('  </cmData>')
    lines.append('</raml>')

    return "\n".join(lines)


uploaded_file = st.file_uploader("Carica CSV NetAct", type=["csv"])

if uploaded_file:
    try:
        alarm_number, alarm_text, ne_list, duplicates_removed = parse_csv(uploaded_file)

        st.success("CSV elaborato con successo")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("TRX trovati", len(ne_list))

        with col2:
            st.metric("Duplicati rimossi", duplicates_removed)

        st.subheader("Informazioni Allarme")
        st.write(f"**Alarm Number:** {alarm_number if alarm_number else 'N/D'}")
        st.write(f"**Alarm Text:** {alarm_text if alarm_text else 'N/D'}")

        with st.expander("Anteprima TRX"):
            st.dataframe(pd.DataFrame({"NE Name": ne_list}).head(50), use_container_width=True)

        xml_block = generate_xml(ne_list, 3)
        xml_unblock = generate_xml(ne_list, 1)

        timestamp_file = datetime.now().strftime("%Y%m%d_%H%M%S")

        st.subheader("Download XML")

        col1, col2 = st.columns(2)

        with col1:
            st.download_button(
                label="⬇️ Download Blocco TRX",
                data=xml_block,
                file_name=f"bloccoTRX_{timestamp_file}.xml",
                mime="application/xml"
            )

        with col2:
            st.download_button(
                label="⬇️ Download Sblocco TRX",
                data=xml_unblock,
                file_name=f"sbloccoTRX_{timestamp_file}.xml",
                mime="application/xml"
            )

    except Exception as e:
        st.error(f"Errore durante l'elaborazione: {e}")
