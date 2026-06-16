import streamlit as st
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
import os
import zipfile
import re
import io


# =========================
# CONFIGURAZIONE PATH
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "..", "templates")

NODEINFO_TEMPLATE = os.path.join(TEMPLATES_DIR, "NodeInfo.xml")
PROJECTINFO_TEMPLATE = os.path.join(TEMPLATES_DIR, "ProjectInfo.xml")


# =========================
# FUNZIONI UTILI
# =========================
def pretty_xml_from_root(root):
    """
    Converte un root XML in stringa leggibile
    eliminando le righe vuote introdotte da minidom.
    """
    rough_string = ET.tostring(root, encoding="utf-8")
    reparsed = minidom.parseString(rough_string)
    xml_pretty = reparsed.toprettyxml(indent="  ")
    xml_pretty = "\n".join(line for line in xml_pretty.split("\n") if line.strip())
    return xml_pretty


def validate_ipv4(ip_value):
    ip_pattern = r"^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
    return re.match(ip_pattern, ip_value or "") is not None


def validate_node_name(nodo, device_category):
    if device_category == "BaseBand":
        return re.match(r"^[A-Za-z0-9]{5}$", nodo or "") is not None
    elif device_category == "Controller":
        return re.match(r"^[A-Za-z0-9]{10}$", nodo or "") is not None
    return False


def remove_tag_everywhere(root, tag_to_remove):
    """
    Rimuove un tag da tutto l'albero XML.
    """
    for parent in root.iter():
        children = list(parent)
        for child in children:
            if child.tag == tag_to_remove:
                parent.remove(child)


# =========================
# MODIFICA NODEINFO.XML
# =========================
def update_nodeinfo(root, nodo, serial_number_bb, device_type, backup_name=None, ip_defgtw=None):
    # Aggiorna tutti i tag <name>
    for elem in root.iter("name"):
        elem.text = nodo

    # Gestione hardwareSerialNumber
    hardware_tags = list(root.iter("hardwareSerialNumber"))
    if serial_number_bb:
        for elem in hardware_tags:
            elem.text = serial_number_bb
    else:
        remove_tag_everywhere(root, "hardwareSerialNumber")

    # Gestione campi LMT
    if device_type == "LMT":
        backup_elem = root.find(".//backup")
        if backup_elem is None:
            backup_elem = ET.SubElement(root, "backup")
        backup_elem.text = backup_name or ""

        router_elem = root.find(".//defaultRouter")
        if router_elem is None:
            router_elem = ET.SubElement(root, "defaultRouter")
        router_elem.text = ip_defgtw or ""

    return root


# =========================
# MODIFICA PROJECTINFO.XML
# =========================
def update_projectinfo(root, nodo):
    """
    Modifica ProjectInfo.xml:
    aggiorna solo il tag <name>
    """
    name_elem = root.find("name")
    if name_elem is not None:
        name_elem.text = nodo
        return root, 1
    return root, 0


# =========================
# CREA ZIP IN MEMORIA
# =========================
def build_zip_in_memory(nodo, nodeinfo_xml_string, projectinfo_xml_string):
    """
    Crea lo ZIP in memoria con questa struttura:

    Replace_<nodo>.zip
    └── Replace_<nodo>/
        ├── ProjectInfo.xml
        └── <nodo>/
            └── NodeInfo.xml
    """
    main_folder = f"Replace_{nodo}"
    zip_filename = f"{main_folder}.zip"

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
