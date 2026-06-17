import re
import ipaddress
from io import BytesIO
from pathlib import Path
import xml.etree.ElementTree as ET

import streamlit as st


# =========================
# CONFIG
# =========================
st.title("📡 Cambio Sincronismo Nokia")
st.write("Genera il file XML a partire dal template presente nel repository.")

# Se questo file è dentro /pages, il template è in /templates
BASE_DIR = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = BASE_DIR / "templates" / "Semiloose.xml"


# =========================
# FUNZIONI DI SUPPORTO
# =========================
def get_namespace(tag: str) -> str:
    """
    Estrae il namespace da un tag XML nel formato:
    {namespace}tag
    """
    match = re.match(r"\{(.*)\}", tag)
    return match.group(1) if match else ""


def build_queries(ns_uri: str):
    """
    Costruisce le query XPath compatibili sia con XML namespaced
    sia con XML senza namespace.
    """
    if ns_uri:
        ns = {"ns": ns_uri}
        q_managed_object = ".//ns:managedObject"
        q_master_ip = './/ns:p[@name="masterIpAddr"]'
        q_splane_dn = './/ns:p[@name="sPlaneIpAddressDN"]'
    else:
        ns = {}
        q_managed_object = ".//managedObject"
        q_master_ip = './/p[@name="masterIpAddr"]'
        q_splane_dn = './/p[@name="sPlaneIpAddressDN"]'

    return ns, q_managed_object, q_master_ip, q_splane_dn


def valida_nodo(nodo: str) -> bool:
    """
    Per ora accettiamo solo cifre.
    Esempio corretto: 150258
    """
    return nodo.isdigit()


def genera_xml(nodo: str, timeserver_ip: str):
    """
    Legge il template e applica le sostituzioni:
    - MRBTS-/...  -> MRBTS-<nodo>/...
    - masterIpAddr -> <timeserver_ip>

    Restituisce:
    - bytes XML generato
    - contatori modifiche
    """
    tree = ET.parse(TEMPLATE_PATH)
    root = tree.getroot()

    # Gestione namespace
    ns_uri = get_namespace(root.tag)
    if ns_uri:
        ET.register_namespace("", ns_uri)

    ns, q_managed_object, q_master_ip, q_splane_dn = build_queries(ns_uri)

    mrbts_value = f"MRBTS-{nodo}"

    distname_modificati = 0
    splane_modificati = 0
    masterip_modificati = 0

    # 1) Aggiorna tutti i distName contenenti MRBTS-/
    for mo in root.findall(q_managed_object, ns):
        dist_name = mo.get("distName", "")
        if "MRBTS-/" in dist_name:
            nuovo_dist_name = dist_name.replace("MRBTS-/", f"{mrbts_value}/")
            if nuovo_dist_name != dist_name:
                mo.set("distName", nuovo_dist_name)
                distname_modificati += 1

    # 2) Aggiorna sPlaneIpAddressDN se contiene MRBTS-/
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

    # Salvataggio in memoria
    output = BytesIO()
    tree.write(output, encoding="utf-8", xml_declaration=True)
    output.seek(0)

    return output, distname_modificati, splane_modificati, masterip_modificati


# =========================
# UI
# =========================
with st.form("form_cambio_sincronismo"):
    nodo = st.text_input(
        "Nodo",
        placeholder="Es. 150258",
        help="Il valore verrà usato per costruire MRBTS-<nodo> e per nominare il file finale."
    )

    timeserver_ip = st.text_input(
        "IP timeserver",
        placeholder="Es. 10.20.30.40",
        help="Verrà inserito nel campo masterIpAddr."
    )

    submit = st.form_submit_button("Genera XML", use_container_width=True)


if submit:
    errori = []

    # Verifica template
    if not TEMPLATE_PATH.exists():
        errori.append(f"Template non trovato: {TEMPLATE_PATH}")

    # Verifica nodo
    nodo = nodo.strip()
    if not nodo:
        errori.append("Inserisci il nodo.")
    elif not valida_nodo(nodo):
        errori.append("Il nodo deve contenere solo cifre (es. 150258).")

    # Verifica IP
    timeserver_ip = timeserver_ip.strip()
    if not timeserver_ip:
        errori.append("Inserisci l'IP del timeserver.")
    else:
        try:
            ipaddress.ip_address(timeserver_ip)
        except ValueError:
            errori.append("L'IP del timeserver non è valido.")

    # Mostra errori oppure genera file
    if errori:
        for err in errori:
            st.error(err)
    else:
        output, dist_cnt, splane_cnt, ip_cnt = genera_xml(
            nodo=nodo,
            timeserver_ip=timeserver_ip
        )

        nome_file = f"Semiloose_{nodo}.xml"

        st.success("XML generato correttamente ✅")
        st.write(f"**File generato:** `{nome_file}`")
        st.write(f"**distName aggiornati:** {dist_cnt}")
        st.write(f"**sPlaneIpAddressDN aggiornati:** {splane_cnt}")
        st.write(f"**masterIpAddr aggiornati:** {ip_cnt}")

        st.download_button(
            label="📥 Scarica XML",
            data=output,
            file_name=nome_file,
            mime="application/xml",
            use_container_width=True
        )
