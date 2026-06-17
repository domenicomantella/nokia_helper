import streamlit as st
import xml.etree.ElementTree as ET
import openpyxl
from datetime import datetime
import io

# --- Costanti e Funzioni di elaborazione ---
class ProcessingMode:
    FULL_PROCESSING = "Elaborazione Completa (Modifica XML + Dati Excel)"
    NAMESPACE_STRIPPING = "Solo Pulizia Namespace e 'Roma4'"


def strip_namespace(element):
    if '}' in element.tag:
        element.tag = element.tag.split('}', 1)[1]
    for subelement in element:
        strip_namespace(subelement)


def trasforma_bcxu(logicalBcxuAddress, ip_to_number_table):
    return ip_to_number_table.get(logicalBcxuAddress)


def process_xml(xml_file, excel_file, search_key, mode):
    log = []
    try:
        # 1. Lettura del file e pulizia testuale immediata (valida per entrambi i modi)
        xml_string = xml_file.read().decode('utf-8')
        string_modified = False

        if "Roma4" in xml_string:
            xml_string = xml_string.replace("Roma4", "PLMN")
            log.append("Sostituzione 'Roma4' -> 'PLMN' effettuata nel testo XML.")
            string_modified = True

        # 2. Creazione dell'oggetto XML basato sul testo già pulito da Roma4
        root = ET.fromstring(xml_string)
        strip_namespace(root)
        log.append("Pulizia del namespace effettuata.")

        # 3. Se è stata scelta la modalità solo pulizia, esce subito
        if mode == ProcessingMode.NAMESPACE_STRIPPING:
            return save_file(root, xml_file.name, mode), log

        # --- Da qui in poi: Modalità Elaborazione Completa ---
        wb = openpyxl.load_workbook(excel_file, data_only=True)
        tnl_sheet = wb['TNL_TI_SRAN']

        COL_MAP = {
            'search_key': 3,
            'btsCuPlaneIpAddress': 40,
            'btsMPlaneIpAddress': 43,
            'btsSubnetMasklengthMplane': 41,
            'btsSubnetMasklengthCUplane': 41,
            'logicalBcxuAddress': 77
        }
        key_idx = COL_MAP['search_key']

        tnl_data = {
            str(row[key_idx]).strip(): {
                'btsCuPlaneIpAddress': row[COL_MAP['btsCuPlaneIpAddress']],
                'btsMPlaneIpAddress': row[COL_MAP['btsMPlaneIpAddress']],
                'btsSubnetMasklengthMplane': row[COL_MAP['btsSubnetMasklengthMplane']],
                'btsSubnetMasklengthCUplane': row[COL_MAP['btsSubnetMasklengthCUplane']],
                'logicalBcxuAddress': row[COL_MAP['logicalBcxuAddress']]
            }
            for row in tnl_sheet.iter_rows(min_row=2, values_only=True)
            if row[key_idx] and str(row[key_idx]).strip()
        }

        ip_to_number_table = {
            # BRESCIA BBS70D
            "19.140.1.152": "0", "19.140.1.153": "1", "19.140.1.154": "2",
            "19.140.1.155": "3", "19.140.1.156": "4", "19.140.1.157": "5",
            "19.140.1.158": "6", "19.140.1.159": "7",

            # MILANO Malpaga BMI70D
            "19.135.1.152": "0", "19.135.1.153": "1", "19.135.1.154": "2",
            "19.135.1.155": "3", "19.135.1.156": "4", "19.135.1.157": "5",
            "19.135.1.158": "6", "19.135.1.159": "7", "19.135.1.160": "8",
            "19.135.1.161": "9", "19.135.1.162": "10", "19.135.1.163": "11",
            "19.136.1.164": "12", "19.135.1.165": "13", "19.135.1.166": "14",
            "19.135.1.167": "15",

            # BERGAMO BBG70D
            "19.139.1.152": "0", "19.139.1.153": "1", "19.139.1.154": "2",
            "19.139.1.155": "3", "19.139.1.156": "4", "19.139.1.157": "5",
            "19.139.1.158": "6", "19.139.1.159": "7",

            # MILANO Bersaglio BMI71D
            "19.136.1.152": "0", "19.136.1.153": "1", "19.136.1.154": "2",
            "19.136.1.155": "3", "19.136.1.156": "4", "19.136.1.157": "5",
            "19.136.1.158": "6", "19.136.1.159": "7",
        }

        search_key = search_key.strip()

        # CORREZIONE IMPORTANTE:
        # se la chiave non è nell'Excel, errore e stop netto
        if search_key not in tnl_data:
            log.append(f"ERRORE: valore '{search_key}' non trovato nel file Excel.")
            return None, log

        excel_values = tnl_data[search_key]
        modifiche_effettuate = False
        all_mo = root.findall(".//managedObject[@class='BCF']")

        for mo in all_mo:
            dist_name = mo.get('distName')
            log.append(f"Elaborazione: {dist_name}")

            before_params = {p.get('name'): p.text for p in mo.findall('p')}

            bcxu_address_excel = excel_values.get('logicalBcxuAddress')
            bcxu_transformed = trasforma_bcxu(bcxu_address_excel, ip_to_number_table)

            params_to_add = {
                'btsCuPlaneIpAddress': excel_values.get('btsCuPlaneIpAddress'),
                'btsMPlaneIpAddress': excel_values.get('btsMPlaneIpAddress'),
                'btsSubnetMasklengthCUplane': excel_values.get('btsSubnetMasklengthCUplane'),
                'btsSubnetMasklengthMplane': excel_values.get('btsSubnetMasklengthMplane'),
                'logicalBcxuAddress': bcxu_transformed if bcxu_transformed is not None else bcxu_address_excel
            }

            existing_elements = {p.get('name'): p for p in mo.findall('p')}

            for name, value in params_to_add.items():
                value_str = str(value) if value is not None else ''

                if name in existing_elements:
                    if existing_elements[name].text != value_str:
                        existing_elements[name].text = value_str
                        modifiche_effettuate = True
                else:
                    p_element = ET.Element('p', attrib={'name': name})
                    p_element.text = value_str
                    mo.append(p_element)
                    modifiche_effettuate = True

            after_params = {p.get('name'): p.text for p in mo.findall('p')}

            for key in sorted(set(before_params.keys()) | set(after_params.keys())):
                val_before = before_params.get(key, "Non presente")
                val_after = after_params.get(key, "Non presente")
                log.append(f"{key}: {val_before} -> {val_after}")

        if not modifiche_effettuate and not string_modified:
            log.append("Nessuna modifica effettuata (né da Excel né da pulizia testo).")
            return None, log

        return save_file(root, xml_file.name, mode), log

    except Exception as e:
        log.append(f"ERRORE: {e}")
        return None, log


def save_file(root, original_filename, mode):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = original_filename.rsplit('.', 1)[0] if '.' in original_filename else original_filename
    mode_suffix = "_solo_pulizia" if mode == ProcessingMode.NAMESPACE_STRIPPING else "_modificato"
    file_output_name = f"{base_name}{mode_suffix}_{timestamp}.xml"

    ET.indent(root, space="  ", level=0)
    tree = ET.ElementTree(root)
    output_io = io.BytesIO()
    tree.write(output_io, encoding='utf-8', xml_declaration=True)
    output_io.seek(0)

    return file_output_name, output_io


# --- Interfaccia Streamlit ---
st.title("XML & Excel Processor Web App")

mode = st.selectbox(
    "Modalità Elaborazione:",
    [ProcessingMode.FULL_PROCESSING, ProcessingMode.NAMESPACE_STRIPPING]
)

xml_file = st.file_uploader("Carica file XML", type=["xml"])
excel_file = None
search_key = None

if mode == ProcessingMode.FULL_PROCESSING:
    excel_file = st.file_uploader("Carica file Excel TNL", type=["xlsx"])
    search_key = st.text_input("Valore da cercare (Colonna D):", value="BW07D")

if st.button("Avvia Elaborazione"):
    if not xml_file:
        st.error("Seleziona un file XML.")
    elif mode == ProcessingMode.FULL_PROCESSING and (not excel_file or not search_key or not search_key.strip()):
        st.error("Compila tutti i campi richiesti per l'elaborazione completa.")
    else:
        result, log = process_xml(xml_file, excel_file, search_key, mode)

        for entry in log:
            if entry.startswith("ERRORE:"):
                st.error(entry)
            else:
                st.text(entry)

        if result:
            file_name, file_data = result
            st.success(f"Elaborazione completata. File pronto per il download: {file_name}")
            st.download_button(
                "Scarica file XML modificato",
                data=file_data,
                file_name=file_name,
                mime="application/xml"
            )
