import streamlit as st
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
import os
import zipfile
import re
import io


# =========================
# PATH TEMPLATE
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "..", "templates")

NODEINFO_TEMPLATE = os.path.join(TEMPLATES_DIR, "NodeInfo.xml")
PROJECTINFO_TEMPLATE = os.path.join(TEMPLATES_DIR, "ProjectInfo.xml")


# =========================
# XML PRETTY CLEAN
# =========================
def pretty_xml(root):
    rough_string = ET.tostring(root, encoding="utf-8")
    reparsed = minidom.parseString(rough_string)
    xml_pretty = reparsed.toprettyxml(indent="  ")
    xml_pretty = "\n".join(line for line in xml_pretty.split("\n") if line.strip())
    return xml_pretty


# =========================
# VALIDAZIONI
# =========================
def validate_node(nodo, category):
    if category == "BaseBand":
        return re.match(r"^[A-Za-z0-9]{5}$", nodo or "") is not None
    else:
        return re.match(r"^[A-Za-z0-9]{10}$", nodo or "") is not None


def validate_ip(ip):
    pattern = r"^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
    return re.match(pattern, ip or "") is not None


# =========================
# MODIFICA NODEINFO
# =========================
def update_nodeinfo(root, nodo, serial, device_type, backup=None, ip=None):

    for elem in root.iter("name"):
        elem.text = nodo

    for elem in root.findall(".//hardwareSerialNumber"):
        if serial:
            elem.text = serial
        else:
            parent = elem.getparent() if hasattr(elem, "getparent") else None
            if parent is not None:
                parent.remove(elem)

    if device_type == "LMT":
        backup_elem = root.find(".//backup")
        if backup_elem is None:
            backup_elem = ET.SubElement(root, "backup")
        backup_elem.text = backup or ""

        router_elem = root.find(".//defaultRouter")
        if router_elem is None:
            router_elem = ET.SubElement(root, "defaultRouter")
        router_elem.text = ip or ""

    return root


# =========================
# MODIFICA PROJECTINFO
# =========================
def update_projectinfo(root, nodo):
    name_elem = root.find("name")
    if name_elem is not None:
        name_elem.text = nodo
    return root


# =========================
# CREA ZIP
# =========================
def create_zip(nodo, node_xml, project_xml):

    buffer = io.BytesIO()
    zip_name = f"Replace_{nodo}.zip"

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"Replace_{nodo}/ProjectInfo.xml", project_xml)
        z.writestr(f"Replace_{nodo}/{nodo}/NodeInfo.xml", node_xml)

    buffer.seek(0)
    return zip_name, buffer


# =========================
# LOGICA PRINCIPALE
# =========================
def create_project(nodo, serial, device_type, backup=None, ip=None):

    try:
        node_tree = ET.parse(NODEINFO_TEMPLATE)
        node_root = node_tree.getroot()

        node_root = update_nodeinfo(node_root, nodo, serial, device_type, backup, ip)
        node_xml = pretty_xml(node_root)

        project_tree = ET.parse(PROJECTINFO_TEMPLATE)
        project_root = project_tree.getroot()

        project_root = update_projectinfo(project_root, nodo)
        project_xml = pretty_xml(project_root)

        zip_name, zip_buffer = create_zip(nodo, node_xml, project_xml)

        st.success("Progetto creato correttamente!")

        st.download_button(
            "📦 Scarica ZIP",
            data=zip_buffer,
            file_name=zip_name,
            mime="application/zip"
        )

    except Exception as e:
        st.error(f"Errore: {e}")


# =========================
# UI STREAMLIT
# =========================
def app():

    st.title("Replace BB Controller")

    col1, col2 = st.columns(2)

    with col1:
        category = st.radio("Categoria dispositivo", ["BaseBand", "Controller"])

    with col2:
        device_type = st.radio("Tipo dispositivo", ["ZT", "LMT"])

    nodo = st.text_input("Node Name")
    serial = st.text_input("SerialNumber BB")

    backup = None
    ip = None

    if device_type == "LMT":
        backup = st.text_input("Backup Name")
        ip = st.text_input("IP defGTW O&M")

    if nodo and not validate_node(nodo, category):
        st.error("Formato Node Name non valido")
        return

    if ip and not validate_ip(ip):
        st.error("IP non valido")
        return

    if st.button("Crea Progetto"):
        if not nodo:
            st.error("Inserisci Node Name")
            return

        if device_type == "LMT" and (not backup or not ip):
            st.error("Compila tutti i campi LMT")
            return

        create_project(nodo, serial, device_type, backup, ip)


# =========================
# AVVIO
# =========================
app()
