import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET


# =====================================================
# Utility
# =====================================================

def remove_namespace(tag):
    """
    Rimuove eventuale namespace XML
    """

    if "}" in tag:
        return tag.split("}", 1)[1]

    return tag


def get_managed_objects(root):
    """
    Estrae tutti i Managed Object dal file XML
    """

    mos = []

    for elem in root.iter():

        if remove_namespace(elem.tag) != "managedObject":
            continue

        attribs = dict(elem.attrib)

        params = {}

        for child in elem:

            if remove_namespace(child.tag) == "p":

                param_name = child.attrib.get(
                    "name",
                    "UNKNOWN"
                )

                param_value = (
                    child.text.strip()
                    if child.text
                    else ""
                )

                params[param_name] = param_value

        mos.append(
            {
                "class": attribs.get("class", ""),
                "distName": attribs.get("distName", ""),
                "version": attribs.get("version", ""),
                "operation": attribs.get("operation", ""),
                "attributes": attribs,
                "parameters": params
            }
        )

    return mos


# =====================================================
# UI
# =====================================================

st.set_page_config(
    page_title="Nokia XML Inspector",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 Nokia XML Inspector")
st.caption("Visualizzazione classi, managed object e parametri XML")


xml_file = st.file_uploader(
    "Carica XML Nokia",
    type=["xml"]
)

if xml_file is None:
    st.stop()


# =====================================================
# Lettura XML
# =====================================================

try:

    xml_data = xml_file.read()

    root = ET.fromstring(xml_data)

    mos = get_managed_objects(root)

except Exception as exc:

    st.error(
        f"Errore lettura XML: {exc}"
    )

    st.stop()


# =====================================================
# DataFrame
# =====================================================

df = pd.DataFrame(mos)

if df.empty:

    st.warning(
        "Nessun managedObject trovato"
    )

    st.stop()


# =====================================================
# Metriche
# =====================================================

col1, col2 = st.columns(2)

with col1:

    st.metric(
        "Managed Object",
        len(df)
    )

with col2:

    st.metric(
        "Classi Distinte",
        df["class"].nunique()
    )


# =====================================================
# Tabs
# =====================================================

tab1, tab2 = st.tabs(
    [
        "Classi",
        "Dettaglio"
    ]
)


# =====================================================
# TAB CLASSI
# =====================================================

with tab1:

    st.subheader(
        "Classi trovate"
    )

    summary = (
        df.groupby("class")
        .size()
        .reset_index(name="Occorrenze")
        .sort_values(
            by="Occorrenze",
            ascending=False
        )
    )

    st.dataframe(
        summary
