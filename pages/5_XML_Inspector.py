import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET


# =====================================================
# Utility
# =====================================================

def remove_namespace(tag):
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def get_managed_objects(root):
    mos = []

    for elem in root.iter():
        if remove_namespace(elem.tag) == "managedObject":

            attribs = dict(elem.attrib)

            mos.append({
                "class": attribs.get("class", ""),
                "distName": attribs.get("distName", ""),
                "version": attribs.get("version", ""),
                "operation": attribs.get("operation", ""),
                "attributes": attribs
            })

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
st.caption("Analisi classi e attributi presenti nel file XML")

xml_file = st.file_uploader(
    "Carica XML Nokia",
    type=["xml"]
)

if xml_file is None:
    st.stop()

try:

    xml_data = xml_file.read()

    root = ET.fromstring(xml_data)

    mos = get_managed_objects(root)

except Exception as exc:

    st.error(f"Errore lettura XML: {exc}")
    st.stop()


# =====================================================
# Dataframe Managed Objects
# =====================================================

df = pd.DataFrame(mos)

if df.empty:

    st.warning("Nessun managedObject trovato")
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
# Tab
# =====================================================

tab1, tab2 = st.tabs([
    "Classi",
    "Dettaglio"
])

# =====================================================
# Tab Classi
# =====================================================

with tab1:

    st.subheader("Classi trovate")

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
        summary,
        use_container_width=True,
        hide_index=True
    )

# =====================================================
# Tab Dettaglio
# =====================================================

with tab2:

    classes = sorted(
        df["class"]
        .dropna()
        .unique()
        .tolist()
    )

    selected_class = st.selectbox(
        "Classe",
        classes
    )

    class_df = df[
        df["class"] == selected_class
    ]

    st.write(
        f"Oggetti trovati: {len(class_df)}"
    )

    for idx, row in class_df.iterrows():

        with st.expander(
            row["distName"]
            if row["distName"]
            else f"{selected_class}_{idx}"
        ):

            st.json(
                row["attributes"]
            )
