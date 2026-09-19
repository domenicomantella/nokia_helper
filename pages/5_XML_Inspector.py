import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET


# =====================================================
# Utility
# =====================================================

def remove_namespace(tag):
    """Rimuove il namespace XML"""

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
        lists = {}

        # ==========================================
        # Analisi figli diretti del Managed Object
        # ==========================================

        for child in elem:

            child_tag = remove_namespace(child.tag)

            # --------------------------------------
            # PARAMETRI <p>
            # --------------------------------------

            if child_tag == "p":

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

            # --------------------------------------
            # LISTE <list>
            # --------------------------------------

            elif child_tag == "list":

                list_name = child.attrib.get(
                    "name",
                    "UNKNOWN_LIST"
                )

                list_items = []

                for item in child:

                    if remove_namespace(item.tag) != "item":
                        continue

                    item_values = {}

                    for subitem in item:

                        if remove_namespace(subitem.tag) != "p":
                            continue

                        sub_name = subitem.attrib.get(
                            "name",
                            "UNKNOWN"
                        )

                        sub_value = (
                            subitem.text.strip()
                            if subitem.text
                            else ""
                        )

                        item_values[sub_name] = sub_value

                    if item_values:
                        list_items.append(item_values)

                lists[list_name] = list_items

        mos.append(
            {
                "class": attribs.get("class", ""),
                "distName": attribs.get("distName", ""),
                "version": attribs.get("version", ""),
                "operation": attribs.get("operation", ""),
                "attributes": attribs,
                "parameters": params,
                "lists": lists,
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

st.caption(
    "Visualizzazione classi, parametri e liste dei Managed Object Nokia"
)

# =====================================================
# Upload XML
# =====================================================

xml_file = st.file_uploader(
    "Carica XML Nokia",
    type=["xml"]
)

if xml_file is None:
    st.stop()

# =====================================================
# Parsing XML
# =====================================================

try:

    xml_bytes = xml_file.read()

    root = ET.fromstring(xml_bytes)

    mos = get_managed_objects(root)

except Exception as 
