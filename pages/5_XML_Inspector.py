import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET


# =====================================================
# Utility
# =====================================================

def remove_namespace(tag):
    """Rimuove namespace XML se presente"""

    if "}" in tag:
        return tag.split("}", 1)[1]

    return tag


def get_managed_objects(root):

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

                param_value = ""

                if child.text:
                    param_value = child.text.strip()

                params[param_name] = param_value

        mos.append(
            {
                "class": attribs.get("class", ""),
                "distName": attribs.get("distName", ""),
                "version": attribs.get("version", ""),
                "operation": attribs.get("operation", ""),
                "attributes": attribs,
                "parameters": params,
            }
        )

    return mos


# =====================================================
# Streamlit UI
# =====================================================

st.set_page_config(
    page_title="Nokia XML Inspector",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 Nokia XML Inspector")
st.caption(
    "Visualizzazione classi, managed object e parametri XML"
)


xml_file = st.file_uploader(
    "Carica XML Nokia",
    type=["xml"]
)

if xml_file is None:
    st.stop()


# =====================================================
# Parse XML
# =====================================================

try:

    xml_bytes = xml_file.read()

    root = ET.fromstring(xml_bytes)

    mos = get_managed_objects(root)

except Exception as exc:

    st.error(
        f"Errore lettura XML: {exc}"
    )

    st.stop()


# =====================================================
# Dataframe
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

tab_classi, tab_dettaglio = st.tabs(
    [
        "Classi",
        "Dettaglio"
    ]
)


# =====================================================
# TAB CLASSI
# =====================================================

with tab_classi:

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
        summary,
        use_container_width=True,
        hide_index=True
    )


# =====================================================
# TAB DETTAGLIO
# =====================================================

with tab_dettaglio:

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

        titolo = (
            row["distName"]
            if row["distName"]
            else f"{selected_class}_{idx}"
        )

        with st.expander(titolo):

            st.subheader(
                "Attributi Managed Object"
            )

            st.json(
                row["attributes"]
            )

            st.subheader(
                "Parametri"
            )

            params = row["parameters"]

            if len(params) == 0:

                st.info(
                    "Nessun parametro trovato"
                )

            else:

                df_params = pd.DataFrame(
                    [
                        {
                            "Parametro": k,
                            "Valore": v
                        }
                        for k, v in params.items()
                    ]
                )

                st.dataframe(
                    df_params,
                    use_container_width=True,
                    hide_index=True
                )
