import re
import ipaddress
from io import BytesIO
from pathlib import Path
import xml.etree.ElementTree as ET
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st


# =========================
# CONFIG
# =========================
st.title("📡 Cambio Sincronismo Nokia")
st.write("Genera il file XML a partire dal template presente nel repository.")

BASE_DIR = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = BASE_DIR / "templates" / "Semiloose.xml"


# =========================
# FUNZIONI DI SUPPORTO
# =========================
def get_namespace(tag: str) -> str:
    match = re.match(r"\{(.*)\}", tag)
    return match.group(1) if match else ""


def build_queries(ns_uri: str):
    if ns_uri:
        ns = {"ns": ns_uri}
        q_managed_object = ".//ns:managedObject"
        q_master_ip = './/ns:p[@name="masterIpAddr"]'
        q_splane_dn = './/ns:p[@name="sPlaneIpAddressDN"]'
        q_log = ".//ns:log"
    else:
        ns = {}
        q_managed_object = ".//managedObject"
        q_master_ip = './/p[@name="masterIpAddr"]'
        q_splane_dn = './/p[@name="sPlaneIpAddressDN"]'
        q_log = ".//log"

    return ns, q_managed_object, q_master_ip, q_splane_dn, q_log


def valida_nodo(nodo: str) -> bool:
    return nodo.isdigit()


def genera_timestamp():
    """
    Genera timestamp con gestione automatica ora legale/solare.
    """
    now = datetime.now(ZoneInfo("Europe/Rome"))
    # formato: 2026-06-17T15:20:00.000+02:00
    return now.strftime("%Y-%m-%dT%H:%M:%S.000%z")[:-2] + ":00"


def genera_xml(nodo: str, timeserver_ip: str):
    tree = ET.parse(TEMPLATE_PATH)
    root = tree.getroot()

    ns_uri = get_namespace(root.tag)
    if ns_uri:
        ET.register_namespace("", ns_uri)

    ns, q_managed_object, q_master_ip, q_splane_dn, q_log = build_queries(ns_uri)

    mrbts_value = f"MRBTS-{nodo}"

    distname_modificati = 0
    splane_modificati = 0
    masterip_modificati = 0
    timestamp_modificati = 0

    # 1) Aggiorna distName
    for mo in root.findall(q_managed_object, ns):
        dist_name = mo.get("distName", "")
        if "MRBTS-/" in dist_name:
            nuovo_dist_name = dist_name.replace("MRBTS-/", f"{mrbts_value}/")
            if nuovo_dist_name != dist_name:
                mo.set("distName", nuovo_dist_name)
                distname_modificati += 1

    # 2) Aggiorna sPlaneIpAddressDN
    for p in root.findall(q_splane_dn, ns):
        testo = p.text or ""
        if "MRBTS-/" in testo:
            nuovo_testo = testo.replace("MRBTS-/", f"{mrbts_value}/")
            if nuovo_testo != testo:
                p.text = nuovo_testo
                splane_modificati += 1

    # 3) Aggiorna masterIpAddr
    for p in root.findall(q_master_ip, ns):
        p.text = timeserver_ip
        masterip_modificati += 1

    # 4) Aggiorna timestamp
    nuovo_timestamp = genera_timestamp()
    for log in root.findall(q_log, ns):
        log.set("dateTime", nuovo_timestamp)
        timestamp_modificati += 1

    # Salva in memoria
    output = BytesIO()
    tree.write(output, encoding="utf-8", xml_declaration=True)
    output.seek(0)

    return (
        output,
        distname_modificati,
        splane_modificati,
        masterip_modificati,
        timestamp_modificati
    )


# =========================
# UI
# =========================
with st.form("form_cambio_sincronismo"):

    nodo = st.text_input(
        "Nodo",
        placeholder="Es. 150258"
    )

    timeserver_ip = st.text_input(
        "IP timeserver",
        placeholder="Es. 10.20.30.40"
    )

    submit = st.form_submit_button("Genera XML", use_container_width=True)


if submit:

    errori = []

    if not TEMPLATE_PATH.exists():
        errori.append(f"Template non trovato: {TEMPLATE_PATH}")

    nodo = nodo.strip()
    if not nodo:
        errori.append("Inserisci il nodo.")
    elif not valida_nodo(nodo):
        errori.append("Il nodo deve contenere solo cifre.")

    timeserver_ip = timeserver_ip.strip()
    if not timeserver_ip:
        errori.append("Inserisci l'IP del timeserver.")
    else:
        try:
            ipaddress.ip_address(timeserver_ip)
        except ValueError:
            errori.append("IP non valido.")

    if errori:
        for err in errori:
            st.error(err)
    else:
        (
            output,
            dist_cnt,
            splane_cnt,
            ip_cnt,
            ts_cnt
        ) = genera_xml(nodo, timeserver_ip)

        nome_file = f"Semiloose_{nodo}.xml"

        st.success("XML generato correttamente ✅")
        st.write(f"**File:** `{nome_file}`")
        st.write(f"distName aggiornati: {dist_cnt}")
        st.write(f"sPlane aggiornati: {splane_cnt}")
        st.write(f"masterIpAddr aggiornati: {ip_cnt}")
        st.write(f"timestamp aggiornati: {ts_cnt}")

        st.download_button(
            label="📥 Scarica XML",
            data=output,
            file_name=nome_file,
            mime="application/xml",
            use_container_width=True
        )
