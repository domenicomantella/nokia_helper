"""
Nokia Node Explorer - prima versione funzionale
================================================

Scopo
-----
Questa pagina Streamlit legge un export XML Nokia e costruisce una vista
operativa del nodo tramite un menu a schede:

- HW
- CELLE
- TRASPORTO
- ADIACENZE
- SECURITY
- Cerca Classe/Parametro

La pagina NON modifica mai il file XML caricato.

Principi adottati
-----------------
1. Le classi Nokia vengono cercate tramite nome completo esatto.
2. Parametri e classi mancanti non interrompono l'applicazione.
3. Runtime e configurazione vengono trattati allo stesso modo.
4. Le associazioni padre-figlio usano il distName:
   il distName del figlio, senza l'ultimo segmento, deve coincidere con
   il distName del padre.
5. Gli ordinamenti di identificativi e distName sono naturali:
   DCPORT-2 viene prima di DCPORT-10.
6. Le liste XML sono lette ricorsivamente, perché classi come IPRT possono
   contenere dati esclusivamente in list/item.

Dipendenze
----------
streamlit
pandas

Posizione consigliata nel repository
-------------------------------------
pages/7_Nokia_Node_Explorer.py
"""

import re
import xml.etree.ElementTree as ET
from collections import defaultdict

import pandas as pd
import streamlit as st


# =============================================================================
# CONFIGURAZIONE STREAMLIT
# =============================================================================

st.set_page_config(
    page_title="Nokia Node Explorer",
    page_icon="📡",
    layout="wide",
)


# =============================================================================
# NOMI COMPLETI DELLE CLASSI NOKIA UTILIZZATE
# =============================================================================

CLASS_MRBTS = "com.nokia.srbts:MRBTS"

# Hardware runtime/configurativo
CLASS_CABINET_R = "com.nokia.srbts.eqmr:CABINET_R"
CLASS_SMOD_R = "com.nokia.srbts.eqmr:SMOD_R"
CLASS_BBMOD_R = "com.nokia.srbts.eqmr:BBMOD_R"
CLASS_RMOD_R = "com.nokia.srbts.eqmr:RMOD_R"
CLASS_ALD_R = "com.nokia.srbts.eqmr:ALD_R"
CLASS_RETU_R = "com.nokia.srbts.eqmr:RETU_R"
CLASS_PWRMOD = "com.nokia.srbts.eqm:PWRMOD"
CLASS_DCPORT = "com.nokia.srbts.eqm:DCPORT"
CLASS_EAC_IN = "com.nokia.srbts.eqm:EAC_IN"

# Celle
CLASS_LNCEL = "NOKLTE:LNCEL"
CLASS_NRCELL = "com.nokia.srbts.nrbts:NRCELL"
CLASS_NRBTS = "com.nokia.srbts.nrbts:NRBTS"
CLASS_GNBCF = "com.nokia.srbts.gsm:GNBCF"
CLASS_GNBCF_R = "com.nokia.srbts.gsm:GNBCF_R"
CLASS_GNCEL = "com.nokia.srbts.gsm:GNCEL"
CLASS_GNCEL_R = "com.nokia.srbts.gsm:GNCEL_R"

# Trasporto
CLASS_IPADDRESSV4 = "com.nokia.srbts.tnl:IPADDRESSV4"
CLASS_VLANIF = "com.nokia.srbts.tnl:VLANIF"
CLASS_IPRT = "com.nokia.srbts.tnl:IPRT"
CLASS_SYNC = "com.nokia.srbts.mnl:SYNC"
CLASS_TOPP = "com.nokia.srbts.mnl:TOPP"
CLASS_IPSECC = "com.nokia.srbts.tnl:IPSECC"


# =============================================================================
# UTILITY GENERALI
# =============================================================================

def local_name(tag):
    """Rimuove l'eventuale namespace XML dal nome di un tag."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def clean_text(value):
    """Converte un valore in stringa pulita; None diventa stringa vuota."""
    if value is None:
        return ""
    return str(value).strip()


def normalize_nc(value):
    """Restituisce True se il valore rappresenta NC, ignorando spazi e case."""
    return clean_text(value).upper() == "NC"


def short_class_name(full_class_name):
    """Esempio: com.nokia.srbts.eqmr:BBMOD_R -> BBMOD_R."""
    value = clean_text(full_class_name)
    return value.rsplit(":", 1)[-1] if ":" in value else value


def natural_key(value):
    """Chiave di ordinamento naturale: X-2 precede X-10."""
    text = clean_text(value)
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", text)]


def last_dn_segment(dist_name):
    """Restituisce l'ultimo segmento del distName, ad esempio DCPORT-3."""
    parts = [part for part in clean_text(dist_name).split("/") if part]
    return parts[-1] if parts else ""


def parent_dn(dist_name):
    """Rimuove l'ultimo segmento dal distName."""
    parts = [part for part in clean_text(dist_name).split("/") if part]
    return "/".join(parts[:-1]) if len(parts) > 1 else ""


def extract_mrbts_id(dist_name):
    """Estrae il valore dopo MRBTS- dal distName, mantenendo il testo originale."""
    match = re.search(r"(?:^|/)MRBTS-([^/]+)", clean_text(dist_name))
    return match.group(1) if match else ""


def make_expected_dn(mrbts_id, suffix):
    """Costruisce un distName completo partendo dall'MRBTS reale."""
    return f"MRBTS-{mrbts_id}/{suffix}" if mrbts_id else ""


def dataframe_or_message(rows, message="Nessun dato trovato."):
    """Mostra una tabella oppure un messaggio informativo se non ci sono righe."""
    if not rows:
        st.info(message)
        return
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# =============================================================================
# PARSER XML GENERICO
# =============================================================================

def direct_parameters(element):
    """
    Legge solamente i tag <p> figli diretti dell'elemento.

    Ritorna un dizionario nome -> valore. Se nello stesso livello esistono
    parametri duplicati, l'ultimo valore incontrato prevale. Per le liste la
    funzione dedicata conserva invece ogni item separatamente.
    """
    result = {}
    for child in element:
        if local_name(child.tag) == "p":
            name = clean_text(child.attrib.get("name", "UNKNOWN"))
            result[name] = clean_text(child.text)
    return result


def parse_item(item_element):
    """Legge ricorsivamente un item XML, incluse eventuali liste annidate."""
    data = {
        "attributes": dict(item_element.attrib),
        "parameters": direct_parameters(item_element),
        "lists": [],
    }

    for child in item_element:
        if local_name(child.tag) == "list":
            data["lists"].append(parse_list(child))

    return data


def parse_list(list_element):
    """Legge una list Nokia e tutti gli item/list annidati."""
    data = {
        "name": clean_text(list_element.attrib.get("name", "UNKNOWN_LIST")),
        "attributes": dict(list_element.attrib),
        "parameters": direct_parameters(list_element),
        "items": [],
        "lists": [],
    }

    for child in list_element:
        tag = local_name(child.tag)
        if tag == "item":
            data["items"].append(parse_item(child))
        elif tag == "list":
            data["lists"].append(parse_list(child))

    return data


def parse_managed_objects(root):
    """
    Costruisce una rappresentazione uniforme dei managedObject.

    Ogni record contiene:
    - nome completo e breve della classe;
    - distName e attributi XML;
    - parametri p diretti;
    - liste e item ricorsivi;
    - riferimento interno all'elemento XML, utile per evoluzioni future.
    """
    objects = []

    for element in root.iter():
        if local_name(element.tag) != "managedObject":
            continue

        attributes = dict(element.attrib)
        full_class = clean_text(attributes.get("class", ""))
        lists = [
            parse_list(child)
            for child in element
            if local_name(child.tag) == "list"
        ]

        objects.append({
            "class": full_class,
            "short_class": short_class_name(full_class),
            "distName": clean_text(attributes.get("distName", "")),
            "version": clean_text(attributes.get("version", "")),
            "operation": clean_text(attributes.get("operation", "")),
            "attributes": attributes,
            "parameters": direct_parameters(element),
            "lists": lists,
            "element": element,
        })

    return objects


def build_class_index(objects):
    """Indicizza gli oggetti per nome completo della classe."""
    index = defaultdict(list)
    for obj in objects:
        index[obj["class"]].append(obj)
    return index


def select_fields(obj, fields, aliases=None):
    """
    Estrae da un MO soltanto i parametri richiesti.

    aliases consente di rinominare una colonna in output, per esempio:
    {"descr": "Slogan"}.
    """
    aliases = aliases or {}
    params = obj.get("parameters", {})
    row = {}
    for field in fields:
        row[aliases.get(field, field)] = params.get(field, "")
    return row


def object_by_exact_dn(class_index, class_name, dist_name):
    """Trova un oggetto di una classe tramite distName esatto."""
    for obj in class_index.get(class_name, []):
        if obj["distName"] == dist_name:
            return obj
    return None


def children_of(class_index, child_class, parent_dist_name):
    """Trova i figli diretti di un padre tramite la regola sul distName."""
    return [
        obj for obj in class_index.get(child_class, [])
        if parent_dn(obj["distName"]) == parent_dist_name
    ]


def first_child_of(class_index, child_class, parent_dist_name):
    """Restituisce il primo figlio diretto compatibile, oppure None."""
    children = children_of(class_index, child_class, parent_dist_name)
    return children[0] if children else None


def flatten_list_items(list_data, list_path=""):
    """
    Appiattisce ricorsivamente gli item di una lista.

    Ogni riga contiene i parametri dell'item e le colonne tecniche _Lista e
    _Item. Le liste annidate vengono percorse senza perdere i dati.
    """
    rows = []
    current_name = list_data.get("name", "UNKNOWN_LIST")
    current_path = f"{list_path}/{current_name}" if list_path else current_name

    for item_number, item in enumerate(list_data.get("items", []), start=1):
        row = {
            "_Lista": current_path,
            "_Item": item_number,
        }
        row.update(item.get("parameters", {}))
        rows.append(row)

        for nested_list in item.get("lists", []):
            rows.extend(flatten_list_items(nested_list, current_path))

    for nested_list in list_data.get("lists", []):
        rows.extend(flatten_list_items(nested_list, current_path))

    return rows


def find_named_list(obj, list_name):
    """Cerca ricorsivamente tutte le liste con il nome richiesto."""
    matches = []

    def visit(list_data):
        if clean_text(list_data.get("name", "")) == list_name:
            matches.append(list_data)
        for nested in list_data.get("lists", []):
            visit(nested)
        for item in list_data.get("items", []):
            for nested in item.get("lists", []):
                visit(nested)

    for root_list in obj.get("lists", []):
        visit(root_list)

    return matches


# =============================================================================
# COSTRUZIONE DATI HEADER
# =============================================================================

def get_node_header(class_index):
    """Ricava MRBTS-ID, nome geografico e release SW dal primo MRBTS."""
    mrbts_objects = class_index.get(CLASS_MRBTS, [])
    if not mrbts_objects:
        return {"MRBTS-ID": "", "Nome Geografico": "", "Release SW": ""}

    mrbts = mrbts_objects[0]
    return {
        "MRBTS-ID": extract_mrbts_id(mrbts["distName"]),
        "Nome Geografico": mrbts["parameters"].get("btsName", ""),
        "Release SW": mrbts.get("version", ""),
    }


# =============================================================================
# COSTRUZIONE DATI HW
# =============================================================================

def build_cabinet_data(class_index):
    """Costruisce i tre blocchi Cabinet, SMOD e BBMOD."""
    cabinet_rows = []
    for obj in class_index.get(CLASS_CABINET_R, []):
        row = select_fields(obj, ["productName", "productCode", "serialNumber"])
        row = {"distName": obj["distName"], **row}
        cabinet_rows.append(row)

    smod_rows = []
    for obj in class_index.get(CLASS_SMOD_R, []):
        row = select_fields(obj, [
            "configDN", "productName", "administrativeState",
            "operationalState", "productCode", "serialNumber",
            "activeRole", "horizontalPosition",
        ])
        smod_rows.append(row)

    # Primary prima; a parità di ruolo, ordinamento naturale per configDN.
    smod_rows.sort(key=lambda row: (
        0 if clean_text(row.get("activeRole")).lower() == "primary" else 1,
        natural_key(row.get("configDN", "")),
    ))

    bbmod_rows = []
    for obj in class_index.get(CLASS_BBMOD_R, []):
        row = select_fields(obj, [
            "configDN", "productName", "administrativeState",
            "operationalState", "productCode", "serialNumber",
            "horizontalPosition", "verticalPosition",
        ])
        bbmod_rows.append(row)
    bbmod_rows.sort(key=lambda row: natural_key(row.get("configDN", "")))

    cabinet_rows.sort(key=lambda row: natural_key(row.get("distName", "")))
    return cabinet_rows, smod_rows, bbmod_rows


def build_radio_data(class_index):
    """Costruisce la tabella Radio da RMOD_R."""
    rows = []
    for obj in class_index.get(CLASS_RMOD_R, []):
        rows.append(select_fields(obj, [
            "configDN", "productName", "administrativeState",
            "operationalState", "productCode", "serialNumber",
        ]))
    rows.sort(key=lambda row: natural_key(row.get("configDN", "")))
    return rows


def build_mha_ret_data(class_index):
    """Costruisce le tabelle MHA e RET applicando i filtri richiesti."""
    mha_rows = []
    for obj in class_index.get(CLASS_ALD_R, []):
        # Il requisito richiede l'esistenza del parametro mhaType.
        if "mhaType" not in obj["parameters"]:
            continue
        row = select_fields(obj, [
            "configDN", "mhaType", "administrativeState",
            "operationalState", "productCode", "serialNumber",
        ])
        mha_rows.append(row)
    mha_rows.sort(key=lambda row: natural_key(row.get("configDN", "")))

    ret_rows = []
    for obj in class_index.get(CLASS_RETU_R, []):
        if normalize_nc(obj["parameters"].get("baseStationID", "")):
            continue
        row = select_fields(obj, [
            "configDN", "antModel", "antSerial", "baseStationID",
            "sectorID", "angle",
        ])
        ret_rows.append(row)
    ret_rows.sort(key=lambda row: natural_key(row.get("configDN", "")))

    return mha_rows, ret_rows


def build_fpfh_data(class_index):
    """
    Costruisce PWRMOD e le DCPORT figlie.

    Il DCPORT ID viene calcolato dall'ultimo segmento del distName. Sono
    incluse soltanto le porte con portLabel diverso da NC.
    """
    groups = []

    pwrmods = sorted(
        class_index.get(CLASS_PWRMOD, []),
        key=lambda obj: natural_key(obj["parameters"].get("deviceName", "")),
    )

    for pwrmod in pwrmods:
        pwrmod_data = select_fields(pwrmod, ["deviceName", "ipv4Address"])
        pwrmod_data["distName"] = pwrmod["distName"]

        dcport_rows = []
        for dcport in children_of(class_index, CLASS_DCPORT, pwrmod["distName"]):
            port_label = dcport["parameters"].get("portLabel", "")
            if normalize_nc(port_label):
                continue

            row = {
                "DCPORT ID": last_dn_segment(dcport["distName"]),
                **select_fields(dcport, [
                    "portLabel", "powerSetting", "disconnectCurrent",
                    "disconnectVoltage", "reconnectVoltage",
                ]),
            }
            dcport_rows.append(row)

        dcport_rows.sort(key=lambda row: natural_key(row.get("DCPORT ID", "")))
        groups.append({"pwrmod": pwrmod_data, "dcports": dcport_rows})

    return groups


def build_eac_data(class_index):
    """Costruisce la tabella EAC-IN e crea Slogan dal parametro descr."""
    rows = []
    for obj in class_index.get(CLASS_EAC_IN, []):
        rows.append({
            "EAC-IN ID": last_dn_segment(obj["distName"]),
            "Slogan": obj["parameters"].get("descr", ""),
            "severity": obj["parameters"].get("severity", ""),
            "polarity": obj["parameters"].get("polarity", ""),
            "portId": obj["parameters"].get("portId", ""),
        })
    rows.sort(key=lambda row: natural_key(row.get("EAC-IN ID", "")))
    return rows


# =============================================================================
# COSTRUZIONE DATI CELLE
# =============================================================================

def build_lte_nbiot_data(class_index):
    """Separa LNCEL LTE e NB-IoT usando cellTechnology."""
    lte_rows = []
    nbiot_rows = []

    for obj in class_index.get(CLASS_LNCEL, []):
        row = select_fields(obj, [
            "cellName", "lcrId", "cellTechnology", "administrativeState",
            "operationalState", "eutraCelId",
        ])

        if clean_text(row.get("cellTechnology")).lower() == "nb-iot-fdd":
            nbiot_rows.append(row)
        else:
            lte_rows.append(row)

    lte_rows.sort(key=lambda row: natural_key(row.get("cellName", "")))
    nbiot_rows.sort(key=lambda row: natural_key(row.get("cellName", "")))
    return lte_rows, nbiot_rows


def build_nr_data(class_index):
    """Costruisce la tabella delle celle NR."""
    rows = []
    for obj in class_index.get(CLASS_NRCELL, []):
        rows.append(select_fields(obj, [
            "cellName", "lcrId", "cellTechnology", "administrativeState",
            "operationalState", "nrCellIdentity",
        ]))
    rows.sort(key=lambda row: natural_key(row.get("cellName", "")))
    return rows


def build_gsm_data(class_index):
    """
    Costruisce il riepilogo GNBCF e la tabella GNCEL.

    GNBCF_R e GNCEL_R vengono associati al rispettivo padre tramite distName.
    """
    bcf_rows = []
    for bcf in class_index.get(CLASS_GNBCF, []):
        runtime = first_child_of(class_index, CLASS_GNBCF_R, bcf["distName"])
        row = select_fields(
            bcf,
            ["bcfId", "bscId", "mPlaneRemoteIpAddressOmuSig"],
        )
        row["blockingState"] = (
            runtime["parameters"].get("blockingState", "") if runtime else ""
        )
        bcf_rows.append(row)

    bcf_rows.sort(key=lambda row: natural_key(row.get("bcfId", "")))

    cell_rows = []
    for cell in class_index.get(CLASS_GNCEL, []):
        runtime = first_child_of(class_index, CLASS_GNCEL_R, cell["distName"])
        row = {"lcelcId": cell["parameters"].get("lcelcId", "")}
        for field in [
            "gsmBtsId", "administrativeState", "operationalState",
            "blockingState",
        ]:
            row[field] = runtime["parameters"].get(field, "") if runtime else ""
        cell_rows.append(row)

    cell_rows.sort(key=lambda row: natural_key(row.get("lcelcId", "")))
    return bcf_rows, cell_rows


# =============================================================================
# COSTRUZIONE DATI TRASPORTO
# =============================================================================

def parameter_by_exact_dn(class_index, class_name, dist_name, parameter_name):
    """Legge un singolo parametro da classe e distName esatti."""
    obj = object_by_exact_dn(class_index, class_name, dist_name)
    if not obj:
        return ""
    return obj["parameters"].get(parameter_name, "")


def build_addressing_plan(class_index, node_header):
    """Costruisce la matrice 4G/5G/2G del piano di indirizzamento."""
    mrbts_id = node_header.get("MRBTS-ID", "")

    def dn(suffix):
        return make_expected_dn(mrbts_id, suffix)

    ip_4g_ucs = parameter_by_exact_dn(
        class_index, CLASS_IPADDRESSV4,
        dn("TNLSVC-1/TNL-1/IPNO-1/IPIF-1/IPADDRESSV4-1"),
        "localIpAddr",
    )
    vlan_4g_ucs = parameter_by_exact_dn(
        class_index, CLASS_VLANIF,
        dn("TNLSVC-1/TNL-1/ETHSVC-1/ETHIF-1/VLANIF-1"),
        "vlanId",
    )
    ip_4g_m = parameter_by_exact_dn(
        class_index, CLASS_IPADDRESSV4,
        dn("TNLSVC-1/TNL-1/IPNO-1/IPIF-2/IPADDRESSV4-1"),
        "localIpAddr",
    )
    vlan_4g_m = parameter_by_exact_dn(
        class_index, CLASS_VLANIF,
        dn("TNLSVC-1/TNL-1/ETHSVC-1/ETHIF-1/VLANIF-2"),
        "vlanId",
    )

    rows = [{
        "Tecnologia": "4G",
        "IP U/C/S Plane": ip_4g_ucs,
        "VLAN U/C/S Plane": vlan_4g_ucs,
        "IP M Plane": ip_4g_m,
        "VLAN M Plane": vlan_4g_m,
    }]

    # La riga 5G viene mostrata soltanto se il nodo contiene NRBTS o NRCELL.
    has_5g = bool(class_index.get(CLASS_NRBTS) or class_index.get(CLASS_NRCELL))
    if has_5g:
        rows.append({
            "Tecnologia": "5G",
            "IP U/C/S Plane": parameter_by_exact_dn(
                class_index, CLASS_IPADDRESSV4,
                dn("TNLSVC-1/TNL-1/IPNO-1/IPIF-1/IPADDRESSV4-2"),
                "localIpAddr",
            ),
            "VLAN U/C/S Plane": vlan_4g_ucs,
            "IP M Plane": ip_4g_m,
            "VLAN M Plane": vlan_4g_m,
        })

    # La riga 2G viene mostrata soltanto in presenza di GNBCF.
    if class_index.get(CLASS_GNBCF):
        rows.append({
            "Tecnologia": "2G",
            "IP U/C/S Plane": parameter_by_exact_dn(
                class_index, CLASS_IPADDRESSV4,
                dn("TNLSVC-1/TNL-1/IPNO-1/IPIF-4/IPADDRESSV4-1"),
                "localIpAddr",
            ),
            "VLAN U/C/S Plane": parameter_by_exact_dn(
                class_index, CLASS_VLANIF,
                dn("TNLSVC-1/TNL-1/ETHSVC-1/ETHIF-1/VLANIF-4"),
                "vlanId",
            ),
            "IP M Plane": parameter_by_exact_dn(
                class_index, CLASS_IPADDRESSV4,
                dn("TNLSVC-1/TNL-1/IPNO-1/IPIF-5/IPADDRESSV4-1"),
                "localIpAddr",
            ),
            "VLAN M Plane": parameter_by_exact_dn(
                class_index, CLASS_VLANIF,
                dn("TNLSVC-1/TNL-1/ETHSVC-1/ETHIF-1/VLANIF-5"),
                "vlanId",
            ),
        })

    return rows


def build_routing_table(class_index):
    """
    Estrae tutti gli item della lista staticRoutes da ogni oggetto IPRT.

    Le colonne dipendono dai parametri realmente presenti negli item.
    """
    rows = []

    for iprt in class_index.get(CLASS_IPRT, []):
        for static_routes in find_named_list(iprt, "staticRoutes"):
            for row in flatten_list_items(static_routes):
                rows.append({"distName IPRT": iprt["distName"], **row})

    return rows


def build_synch_data(class_index):
    """Costruisce i dati SYNC e TOPP, incluse le topMasterList."""
    sync_rows = []
    for obj in class_index.get(CLASS_SYNC, []):
        sync_rows.append({
            "distName": obj["distName"],
            "btsSyncMode": obj["parameters"].get("btsSyncMode", ""),
        })

    topp_groups = []
    for obj in class_index.get(CLASS_TOPP, []):
        header = {
            "distName": obj["distName"],
            "topStandardProfile": obj["parameters"].get("topStandardProfile", ""),
            "tuningProfile": obj["parameters"].get("tuningProfile", ""),
        }
        master_rows = []
        for top_master_list in find_named_list(obj, "topMasterList"):
            master_rows.extend(flatten_list_items(top_master_list))
        topp_groups.append({"header": header, "masters": master_rows})

    sync_rows.sort(key=lambda row: natural_key(row.get("distName", "")))
    topp_groups.sort(key=lambda group: natural_key(group["header"].get("distName", "")))
    return sync_rows, topp_groups


def build_ipsec_data(class_index, node_header):
    """Costruisce stato IPsec e indirizzi 4G/5G."""
    mrbts_id = node_header.get("MRBTS-ID", "")

    ipsec_enabled_values = [
        obj["parameters"].get("ipSecEnabled", "")
        for obj in class_index.get(CLASS_IPSECC, [])
    ]

    return {
        "IPsec Enabled": ", ".join(
            value for value in ipsec_enabled_values if clean_text(value)
        ),
        "IPsec address 4G": parameter_by_exact_dn(
            class_index,
            CLASS_IPADDRESSV4,
            make_expected_dn(
                mrbts_id,
                "TNLSVC-1/TNL-1/IPNO-1/IPIF-7/IPADDRESSV4-1",
            ),
            "localIpAddr",
        ),
        "IPsec address 5G": parameter_by_exact_dn(
            class_index,
            CLASS_IPADDRESSV4,
            make_expected_dn(
                mrbts_id,
                "TNLSVC-1/TNL-1/IPNO-1/IPIF-7/IPADDRESSV4-2",
            ),
            "localIpAddr",
        ),
    }


# =============================================================================
# COMPONENTI DI PRESENTAZIONE
# =============================================================================

def render_header(node_header):
    """Mostra i dati generali del nodo sopra il menu a schede."""
    st.title("📡 Nokia Node Explorer")
    col1, col2, col3 = st.columns(3)
    col1.metric("MRBTS-ID", node_header.get("MRBTS-ID") or "Non trovato")
    col2.metric("Nome Geografico", node_header.get("Nome Geografico") or "Non trovato")
    col3.metric("Release SW", node_header.get("Release SW") or "Non trovata")
    st.divider()


def render_hw_tab(class_index):
    """Renderizza tutte le sottoschede HW."""
    cabinet_tab, radio_tab, mha_ret_tab, fpfh_tab, eac_tab = st.tabs([
        "Cabinet", "Radio", "MHA / RET", "FPFH", "EAC-IN Allarmi Esterni"
    ])

    with cabinet_tab:
        cabinet_rows, smod_rows, bbmod_rows = build_cabinet_data(class_index)
        st.subheader("Cabinet")
        dataframe_or_message(cabinet_rows, "Classe CABINET_R non presente.")
        st.subheader("SMOD")
        dataframe_or_message(smod_rows, "Classe SMOD_R non presente.")
        st.subheader("BBMOD")
        dataframe_or_message(bbmod_rows, "Classe BBMOD_R non presente.")

    with radio_tab:
        st.subheader("Radio")
        dataframe_or_message(
            build_radio_data(class_index),
            "Classe RMOD_R non presente.",
        )

    with mha_ret_tab:
        mha_rows, ret_rows = build_mha_ret_data(class_index)
        st.subheader("MHA")
        dataframe_or_message(mha_rows, "Nessun MHA configurato.")
        st.subheader("RET")
        dataframe_or_message(ret_rows, "Nessun RET configurato.")

    with fpfh_tab:
        st.subheader("FPFH / Power Module")
        groups = build_fpfh_data(class_index)
        if not groups:
            st.info("Nessun PWRMOD configurato.")
        for group in groups:
            title = group["pwrmod"].get("deviceName") or group["pwrmod"].get("distName")
            with st.expander(f"PWRMOD: {title}"):
                dataframe_or_message([group["pwrmod"]])
                st.markdown("**DCPORT associate**")
                dataframe_or_message(group["dcports"], "Nessuna DCPORT valida associata.")

    with eac_tab:
        st.subheader("EAC-IN Allarmi Esterni")
        dataframe_or_message(
            build_eac_data(class_index),
            "Nessun EAC-IN configurato.",
        )


def render_cells_tab(class_index):
    """Renderizza LTE, NB-IoT, NR e GSM."""
    lte_tab, nbiot_tab, nr_tab, gsm_tab = st.tabs(["LTE", "NB-IoT", "NR", "GSM"])
    lte_rows, nbiot_rows = build_lte_nbiot_data(class_index)

    with lte_tab:
        st.subheader("Celle LTE")
        dataframe_or_message(lte_rows, "Nessuna cella LTE trovata.")

    with nbiot_tab:
        st.subheader("Celle NB-IoT")
        dataframe_or_message(nbiot_rows, "Nessuna cella NB-IoT trovata.")

    with nr_tab:
        st.subheader("Celle NR")
        dataframe_or_message(build_nr_data(class_index), "Nessuna cella NR trovata.")

    with gsm_tab:
        st.subheader("GSM - GNBCF")
        bcf_rows, cell_rows = build_gsm_data(class_index)
        dataframe_or_message(bcf_rows, "Tecnologia GSM non presente.")
        st.subheader("GSM - Celle")
        dataframe_or_message(cell_rows, "Nessuna cella GSM trovata.")


def render_transport_tab(class_index, node_header):
    """Renderizza Piano indirizzamento, Routing Table, SYNCH e IPsec."""
    addressing_tab, routing_tab, synch_tab, ipsec_tab = st.tabs([
        "Piano indirizzamento", "Routing Table", "SYNCH", "IPsec"
    ])

    with addressing_tab:
        st.subheader("Piano indirizzamento")
        dataframe_or_message(build_addressing_plan(class_index, node_header))

    with routing_tab:
        st.subheader("Routing Table")
        dataframe_or_message(
            build_routing_table(class_index),
            "Nessuna static route trovata nella classe IPRT.",
        )

    with synch_tab:
        sync_rows, topp_groups = build_synch_data(class_index)
        st.subheader("SYNC")
        dataframe_or_message(sync_rows, "Classe SYNC non presente.")
        st.subheader("TOPP")
        if not topp_groups:
            st.info("Classe TOPP non presente.")
        for group in topp_groups:
            dataframe_or_message([group["header"]])
            st.markdown("**topMasterList**")
            dataframe_or_message(group["masters"], "Lista topMasterList non presente o vuota.")

    with ipsec_tab:
        st.subheader("IPsec")
        dataframe_or_message([build_ipsec_data(class_index, node_header)])


# =============================================================================
# FLUSSO PRINCIPALE DELL'APPLICAZIONE
# =============================================================================

xml_file = st.file_uploader(
    "Carica il file XML Nokia",
    type=["xml"],
    help="Il file viene letto in memoria e non viene modificato.",
)

if xml_file is None:
    st.title("📡 Nokia Node Explorer")
    st.info("Carica un file XML Nokia per visualizzare il nodo.")
    st.stop()

try:
    xml_bytes = xml_file.getvalue()
    root = ET.fromstring(xml_bytes)
    managed_objects = parse_managed_objects(root)
except ET.ParseError as exc:
    st.error(f"XML non valido: {exc}")
    st.stop()
except Exception as exc:
    st.error(f"Errore durante la lettura dell'XML: {exc}")
    st.stop()

if not managed_objects:
    st.warning("Nessun managedObject trovato nel file XML.")
    st.stop()

class_index = build_class_index(managed_objects)
node_header = get_node_header(class_index)

render_header(node_header)

hw_tab, cells_tab, transport_tab, adjacency_tab, security_tab, search_tab = st.tabs([
    "HW",
    "CELLE",
    "TRASPORTO",
    "ADIACENZE",
    "SECURITY",
    "Cerca Classe/Parametro",
])

with hw_tab:
    render_hw_tab(class_index)

with cells_tab:
    render_cells_tab(class_index)

with transport_tab:
    render_transport_tab(class_index, node_header)

with adjacency_tab:
    st.info("Working in progress")

with security_tab:
    st.info("Working in progress")

with search_tab:
    st.info("Working in progress")
