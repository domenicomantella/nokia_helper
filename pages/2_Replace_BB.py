import streamlit as st
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
import os
import shutil
import zipfile
import re

# Funzione per creare il progetto
def create_project(nodo, serial_number_bb, device_type, backup_name=None, ip_defgtw=None):
    xml_file_path = os.path.join('templates', 'NodeInfo.xml')
    project_info_path = os.path.join('templates', 'ProjectInfo.xml')

    tree = ET.parse(xml_file_path)
    root = tree.getroot()

    for elem in root.iter('name'):
        elem.text = nodo

    if serial_number_bb:
        for elem in root.iter('hardwareSerialNumber'):
            elem.text = serial_number_bb
    else:
        for elem in root.findall('hardwareSerialNumber'):
            root.remove(elem)

    if device_type == "LMT":
        ip_pattern = r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
        if not re.match(ip_pattern, ip_defgtw):
            st.error("L'indirizzo IP non è valido. Inserisci un indirizzo IPv4 corretto (es. 192.168.1.1)")
            return

        backup_elem = root.find('backup')
        if backup_elem is None:
            backup_elem = ET.SubElement(root, 'backup')
        backup_elem.text = backup_name

        router_elem = root.find('defaultRouter')
        if router_elem is None:
            router_elem = ET.SubElement(root, 'defaultRouter')
        router_elem.text = ip_defgtw

    main_folder = f"Replace_{nodo}"
    os.makedirs(main_folder, exist_ok=True)

    sub_folder = os.path.join(main_folder, nodo)
    os.makedirs(sub_folder, exist_ok=True)

    modified_xml_path = os.path.join(sub_folder, os.path.basename(xml_file_path))

    rough_string = ET.tostring(root, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    with open(modified_xml_path, "w", encoding="utf-8") as f:
        f.write(reparsed.toprettyxml(indent="  "))

    shutil.copy(project_info_path, main_folder)

    zip_filename = f"{main_folder}.zip"
    with zipfile.ZipFile(zip_filename, 'w') as zipf:
        zipf.write(os.path.join(main_folder, os.path.basename(project_info_path)), os.path.basename(project_info_path))
        for foldername, subfolders, filenames in os.walk(sub_folder):
            for filename in filenames:
                filepath = os.path.join(foldername, filename)
                arcname = os.path.relpath(filepath, main_folder)
                zipf.write(filepath, arcname)

    st.success(f"Progetto creato con successo: {zip_filename}")
    st.write(f"Percorso: {os.path.abspath(zip_filename)}")

# Pagina Replace BB Controller
def replace_bb_controller():
    st.title("Replace BB Controller")

    col1, col2 = st.columns(2)
    with col1:
        device_category = st.radio("Categoria dispositivo", ["BaseBand", "Controller"])
    with col2:
        device_type = st.radio("Tipo dispositivo", ["ZT", "LMT"])

    nodo = st.text_input("Node Name")

    if device_category == "BaseBand":
        if nodo and not re.match(r'^[A-Za-z0-9]{5}$', nodo):
            st.error("Node Name per BaseBand deve contenere esattamente 5 caratteri alfanumerici (A-Z, 0-9)")
            return
    elif device_category == "Controller":
        if nodo and not re.match(r'^[A-Za-z0-9]{10}$', nodo):
            st.error("Node Name per Controller deve contenere esattamente 10 caratteri alfanumerici (A-Z, 0-9)")
            return

    serial_number_bb = st.text_input("SerialNumber BB")

    backup_name = ip_defgtw = None
    if device_type == "LMT":
        backup_name = st.text_input("BackUp Name")
        ip_defgtw = st.text_input("IP defGTW O&M")

    if st.button("Crea Progetto"):
        create_project(nodo, serial_number_bb, device_type, backup_name, ip_defgtw)
replace_bb_controller()

