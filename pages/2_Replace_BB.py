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
# FUNZIONI UTILI
# =========================
def pretty_xml(root):
    """
    Restituisce XML formattato e senza righe vuote inutili.
    """
    rough_string = ET.tostring(root, encoding="utf-8")
    reparsed = minidom.parseString(rough_string)
    xml_pretty = reparsed.toprettyxml(indent="  ")
    xml_pretty = "\n".join(line for line in xml_pretty.split("\n") if line.strip())
    return xml_pretty


def validate_node_name(nodo, device_category):
    """
    BaseBand -> 5 caratteri alfanumerici
    Controller -> 10 caratteri alfanumerici
    """
    if device_category == "BaseBand":
        return re.match(r"^[A-Za-z0-9]{5}$", nodo or "") is not None
    elif device_category == "Controller":
        return re.match(r"^[A-Za-z0-9]{10}$", nodo or "") is not None
    return False


def validate_ipv4(ip_value):
    ip_pattern = r"^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
    return re.match(ip_pattern, ip_value or "") is not None


def remove_tag_everywhere(root, tag_to_remove):
    """
    Rimuove tutti i tag con un certo nome da tutto l'albero XML.
    Serve per eliminare hardwareSerialNumber se non valorizzato.
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
    if serial_number_bb:
        for elem in root.iter("hardwareSerialNumber"):
            elem.text = serial_number_bb
    else:
        remove_tag_everywhere(root, "hardwareSerialNumber")

    # Se LMT, aggiorna/aggiunge backup e defaultRouter
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
    Aggiorna solo il tag <name> del ProjectInfo.xml
    con lo stesso valore del Node Name.
    """
    name_elem = root.find("name")
    if name_elem is not None:
        name_elem.text = nodo
    return root


# =========================
# CREA ZIP IN MEMORIA
# =========================
def build_zip_in_memory(nodo, nodeinfo_xml_string, projectinfo_xml_string):
    """
    Struttura ZIP:
    Replace_<nodo>.zip
    └── Replace_<nodo>/
        ├── ProjectInfo.xml
        └── <nodo>/
            └── NodeInfo.xml
    """
    zip_filename = f"Replace_{nodo}.zip"
    main_folder = f"Replace_{nodo}"

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        zipf.writestr(f"{main_folder}/ProjectInfo.xml", projectinfo_xml_string)
        zipf.writestr(f"{main_folder}/{nodo}/NodeInfo.xml", nodeinfo_xml_string)

    zip_buffer.seek(0)
    return zip_filename, zip_buffer


# =========================
# CREAZIONE PROGETTO
# =========================
def create_project(nodo, serial_number_bb, device_type, backup_name=None, ip_defgtw=None):
    log = []

    # Controllo esistenza template
    if not os.path.exists(NODEINFO_TEMPLATE):
        st.error(f"Template mancante: {NODEINFO_TEMPLATE}")
        return

    if not os.path.exists(PROJECTINFO_TEMPLATE):
        st.error(f"Template mancante: {PROJECTINFO_TEMPLATE}")
        return

    try:
        # ===== NODEINFO =====
        node_tree = ET.parse(NODEINFO_TEMPLATE)
        node_root = node_tree.getroot()

        node_root = update_nodeinfo(
            node_root,
            nodo=nodo,
            serial_number_bb=serial_number_bb,
            device_type=device_type,
            backup_name=backup_name,
            ip_defgtw=ip_defgtw
        )

        nodeinfo_xml_string = pretty_xml(node_root)
        log.append("NodeInfo.xml creato correttamente.")

        # ===== PROJECTINFO =====
        project_tree = ET.parse(PROJECTINFO_TEMPLATE)
        project_root = project_tree.getroot()

        project_root = update_projectinfo(project_root, nodo)
        projectinfo_xml_string = pretty_xml(project_root)
        log.append("ProjectInfo.xml aggiornato correttamente.")

        # ===== ZIP =====
        zip_filename, zip_buffer = build_zip_in_memory(
            nodo=nodo,
            nodeinfo_xml_string=nodeinfo_xml_string,
            projectinfo_xml_string=projectinfo_xml_string
        )

        st.success(f"Progetto creato con successo: {zip_filename}")

        with st.expander("Log elaborazione"):
            for entry in log:
                st.write(f"- {entry}")

        st.download_button(
            "📦 Scarica ZIP",
            data=zip_buffer,
            file_name=zip_filename,
            mime="application/zip"
        )

    except Exception as e:
        st.error(f"Errore durante la creazione del progetto: {e}")


# =========================
# INTERFACCIA STREAMLIT
# =========================
def replace_bb_controller():
    st.title("Replace BB Controller")

    col1, col2 = st.columns(2)

    with col1:
        device_category = st.radio(
            "Categoria dispositivo",
            ["BaseBand", "Controller"]
        )

    with col2:
        device_type = st.radio(
            "Tipo dispositivo",
            ["ZT", "LMT"]
        )

    nodo = st.text_input("Node Name")
    serial_number_bb = st.text_input("SerialNumber BB")

    backup_name = None
    ip_defgtw = None

    # Campi aggiuntivi solo per LMT
    if device_type == "LMT":
        backup_name = st.text_input("BackUp Name")
        ip_defgtw = st.text_input("IP defGTW O&M")

    # =========================
    # VALIDAZIONE LIVE NODE NAME
    # =========================
    if nodo:
        if device_category == "BaseBand":
            if not re.match(r"^[A-Za-z0-9]{5}$", nodo):
                st.error("Node Name per BaseBand deve contenere esattamente 5 caratteri alfanumerici (A-Z, 0-9).")
                return

        elif device_category == "Controller":
            if not re.match(r"^[A-Za-z0-9]{10}$", nodo):
                st.error("Node Name per Controller deve contenere esattamente 10 caratteri alfanumerici (A-Z, 0-9).")
                return

    # =========================
    # VALIDAZIONE LIVE IP LMT
    # =========================
    if device_type == "LMT" and ip_defgtw:
        if not validate_ipv4(ip_defgtw):
            st.error("L'indirizzo IP non è valido. Inserisci un IPv4 corretto (es. 192.168.1.1).")
            return

    # =========================
    # BOTTONE CREAZIONE
    # =========================
    if st.button("Crea Progetto"):

        if not nodo:
            st.error("Inserisci il Node Name.")
            return

        if not validate_node_name(nodo, device_category):
            if device_category == "BaseBand":
                st.error("Node Name per BaseBand deve contenere esattamente 5 caratteri alfanumerici (A-Z, 0-9).")
            else:
                st.error("Node Name per Controller deve contenere esattamente 10 caratteri alfanumerici (A-Z, 0-9).")
            return

        if device_type == "LMT":
            if not backup_name:
                st.error("Inserisci il BackUp Name.")
                return

            if not ip_defgtw:
                st.error("Inserisci IP defGTW O&M.")
                return

            if not validate_ipv4(ip_defgtw):
                st.error("L'indirizzo IP non è valido. Inserisci un IPv4 corretto.")
                return

        create_project(
            nodo=nodo,
            serial_number_bb=serial_number_bb,
            device_type=device_type,
            backup_name=backup_name,
            ip_defgtw=ip_defgtw
        )


replace_bb_controller()
