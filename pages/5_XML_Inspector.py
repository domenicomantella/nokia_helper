import io
from collections import Counter
from pathlib import Path
import xml.etree.ElementTree as ET

import pandas as pd
import streamlit as st


st.set_page_config(page_title="Nokia XML Inspector", page_icon="🔎", layout="wide")

DEFAULT_REFERENCE_PATH = Path("data/ref_bts_parameters_26R1_25R3.xlsx")
REFERENCE_SHEET = "Parameter List"
REFERENCE_HEADER_ROW = 6


def local_name(tag):
    """Restituisce il nome locale del tag, indipendentemente dal namespace."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def clean_value(value):
    if value is None:
        return ""
    return str(value).strip()


def iter_by_local_name(root, wanted_name):
    for element in root.iter():
        if local_name(element.tag) == wanted_name:
            yield element


def flatten_parameter(element, prefix=""):
    """Appiattisce p/list/item preservando il percorso logico del parametro."""
    rows = []
    tag = local_name(element.tag)
    name = clean_value(element.get("name"))
    current = ".".join(part for part in (prefix, name) if part)

    children = list(element)
    direct_text = clean_value(element.text)

    if tag == "p" and not children:
        rows.append((current or name or "(senza nome)", direct_text))
        return rows

    if direct_text and current:
        rows.append((current, direct_text))

    item_index = 0
    for child in children:
        child_tag = local_name(child.tag)
        if child_tag == "item":
            item_index += 1
            item_prefix = f"{current}[{item_index}]" if current else f"item[{item_index}]"
            for grandchild in child:
                rows.extend(flatten_parameter(grandchild, item_prefix))
        else:
            rows.extend(flatten_parameter(child, current))

    return rows


@st.cache_data(show_spinner=False)
def parse_xml(xml_bytes):
    root = ET.fromstring(xml_bytes)
    objects = []
    parameters = []

    for index, mo in enumerate(iter_by_local_name(root, "managedObject"), start=1):
        mo_class = clean_value(mo.get("class")) or "(classe non indicata)"
        dist_name = clean_value(mo.get("distName"))
        version = clean_value(mo.get("version"))
        operation = clean_value(mo.get("operation"))

        object_row = {
            "MO #": index,
            "Classe MO": mo_class,
            "distName": dist_name,
            "Versione": version,
            "Operazione": operation,
        }
        objects.append(object_row)

        for child in mo:
            if local_name(child.tag) in {"p", "list"}:
                for parameter_name, value in flatten_parameter(child):
                    parameters.append({
                        "MO #": index,
                        "Classe MO": mo_class,
                        "distName": dist_name,
                        "Parametro": parameter_name,
                        "Valore": value,
                    })

    objects_df = pd.DataFrame(objects)
    parameters_df = pd.DataFrame(parameters)

    if objects_df.empty:
        objects_df = pd.DataFrame(columns=["MO #", "Classe MO", "distName", "Versione", "Operazione"])
    if parameters_df.empty:
        parameters_df = pd.DataFrame(columns=["MO #", "Classe MO", "distName", "Parametro", "Valore"])

    return objects_df, parameters_df


@st.cache_data(show_spinner=False)
def load_reference_from_bytes(file_bytes):
    return pd.read_excel(
        io.BytesIO(file_bytes),
        sheet_name=REFERENCE_SHEET,
        header=REFERENCE_HEADER_ROW - 1,
        engine="openpyxl",
    )


@st.cache_data(show_spinner=False)
def load_reference_from_path(path_string):
    return pd.read_excel(
        path_string,
        sheet_name=REFERENCE_SHEET,
        header=REFERENCE_HEADER_ROW - 1,
        engine="openpyxl",
    )


def normalize_reference(df):
    required = [
        "Technology", "Abbreviated Name", "MO Class", "Parameter Category",
        "Parent Structure", "Full Name", "Data Type", "Units", "Description",
        "Range and step", "Default Value", "Default Value Notes", "Special Value",
        "Special Value Notes", "Modification", "Required on Creation",
        "Related Parameters", "Parameter Relationships", "Features", "Interfaces",
        "Restriction Status",
    ]
    available = [column for column in required if column in df.columns]
    result = df[available].copy()
    result = result.dropna(how="all")
    for column in result.columns:
        result[column] = result[column].fillna("").astype(str).str.strip()
    return result


def base_parameter_name(parameter_path):
    """Ricava il nome Nokia finale da percorsi come list[1].itemParam."""
    final_part = clean_value(parameter_path).split(".")[-1]
    return final_part.split("[")[0]


def create_catalog_lookup(reference_df):
    lookup = reference_df.copy()
    lookup["MO Class"] = lookup["MO Class"].astype(str).str.strip()
    lookup["Abbreviated Name"] = lookup["Abbreviated Name"].astype(str).str.strip()
    lookup = lookup.drop_duplicates(subset=["MO Class", "Abbreviated Name"], keep="first")
    return lookup


def dataframe_to_csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8-sig")


st.title("Nokia XML Inspector")
st.caption("Analisi non distruttiva degli XML di configurazione Nokia con consultazione opzionale del catalogo parametri.")

with st.sidebar:
    st.header("File")
    xml_file = st.file_uploader("XML di configurazione nodo", type=["xml"])

    reference_df = None
    if DEFAULT_REFERENCE_PATH.exists():
        try:
            reference_df = normalize_reference(load_reference_from_path(str(DEFAULT_REFERENCE_PATH)))
            st.success(f"Catalogo caricato: {DEFAULT_REFERENCE_PATH.name}")
        except Exception as exc:
            st.warning(f"Catalogo locale non leggibile: {exc}")

    if reference_df is None:
        reference_file = st.file_uploader(
            "Catalogo parametri Nokia (opzionale)",
            type=["xlsx"],
            help="File atteso: ref_bts_parameters_26R1_25R3.xlsx o compatibile.",
        )
        if reference_file is not None:
            try:
                reference_df = normalize_reference(load_reference_from_bytes(reference_file.getvalue()))
                st.success("Catalogo parametri caricato.")
            except Exception as exc:
                st.error(f"Impossibile leggere il catalogo: {exc}")

if xml_file is None:
    st.info("Carica un XML di configurazione per avviare l'analisi.")
    st.stop()

try:
    objects_df, parameters_df = parse_xml(xml_file.getvalue())
except ET.ParseError as exc:
    st.error(f"XML non valido: {exc}")
    st.stop()
except Exception as exc:
    st.error(f"Errore durante la lettura dell'XML: {exc}")
    st.stop()

class_counts = (
    objects_df["Classe MO"].value_counts().rename_axis("Classe MO").reset_index(name="Numero oggetti")
    if not objects_df.empty else pd.DataFrame(columns=["Classe MO", "Numero oggetti"])
)

catalog_classes = set()
if reference_df is not None and "MO Class" in reference_df.columns:
    catalog_classes = set(reference_df["MO Class"].dropna().astype(str).str.strip())
    class_counts["Nel catalogo"] = class_counts["Classe MO"].isin(catalog_classes).map({True: "Sì", False: "No"})

metric1, metric2, metric3, metric4 = st.columns(4)
metric1.metric("Managed Object", len(objects_df))
metric2.metric("Classi distinte", objects_df["Classe MO"].nunique())
metric3.metric("Parametri letti", len(parameters_df))
metric4.metric(
    "Classi riconosciute",
    f"{class_counts['Nel catalogo'].eq('Sì').sum()}/{len(class_counts)}" if "Nel catalogo" in class_counts else "Catalogo non caricato",
)

summary_tab, classes_tab, objects_tab, parameters_tab, catalog_tab = st.tabs(
    ["Riepilogo", "Classi MO", "Managed Object", "Parametri XML", "Catalogo Nokia"]
)

with summary_tab:
    st.subheader("Riepilogo del file")
    st.write(f"**Nome file:** {xml_file.name}")
    st.write(f"**Elemento radice:** `{local_name(ET.fromstring(xml_file.getvalue()).tag)}`")

    if objects_df.empty:
        st.warning("Nel file non sono stati trovati elementi managedObject.")
    else:
        top_classes = class_counts.head(15)
        st.bar_chart(top_classes.set_index("Classe MO")["Numero oggetti"])

    if reference_df is not None and "Nel catalogo" in class_counts:
        unknown = class_counts[class_counts["Nel catalogo"] == "No"]
        if unknown.empty:
            st.success("Tutte le classi MO presenti nell'XML risultano nel catalogo caricato.")
        else:
            st.warning("Alcune classi MO dell'XML non risultano nel catalogo caricato.")
            st.dataframe(unknown, use_container_width=True, hide_index=True)

with classes_tab:
    st.subheader("Classi presenti nell'XML")
    class_search = st.text_input("Filtra classe MO", key="class_search")
    visible_classes = class_counts
    if class_search:
        visible_classes = visible_classes[
            visible_classes["Classe MO"].str.contains(class_search, case=False, na=False, regex=False)
        ]
    st.dataframe(visible_classes, use_container_width=True, hide_index=True)
    st.download_button(
        "Scarica riepilogo classi CSV",
        dataframe_to_csv_bytes(visible_classes),
        file_name="nokia_xml_classi.csv",
        mime="text/csv",
    )

with objects_tab:
    st.subheader("Managed Object")
    available_classes = sorted(objects_df["Classe MO"].dropna().unique().tolist())
    selected_classes = st.multiselect("Classi MO", available_classes)
    dist_filter = st.text_input("Cerca nel distName")

    visible_objects = objects_df.copy()
    if selected_classes:
        visible_objects = visible_objects[visible_objects["Classe MO"].isin(selected_classes)]
    if dist_filter:
        visible_objects = visible_objects[
            visible_objects["distName"].str.contains(dist_filter, case=False, na=False, regex=False)
        ]

    st.dataframe(visible_objects, use_container_width=True, hide_index=True)
    st.download_button(
        "Scarica Managed Object CSV",
        dataframe_to_csv_bytes(visible_objects),
        file_name="nokia_xml_managed_objects.csv",
        mime="text/csv",
    )

with parameters_tab:
    st.subheader("Parametri configurati nell'XML")
    pcol1, pcol2, pcol3 = st.columns(3)
    with pcol1:
        parameter_class = st.selectbox(
            "Classe MO",
            ["Tutte"] + sorted(parameters_df["Classe MO"].dropna().unique().tolist()),
        )
    with pcol2:
        parameter_search = st.text_input("Nome parametro")
    with pcol3:
        value_search = st.text_input("Valore")

    visible_parameters = parameters_df.copy()
    if parameter_class != "Tutte":
        visible_parameters = visible_parameters[visible_parameters["Classe MO"] == parameter_class]
    if parameter_search:
        visible_parameters = visible_parameters[
            visible_parameters["Parametro"].str.contains(parameter_search, case=False, na=False, regex=False)
        ]
    if value_search:
        visible_parameters = visible_parameters[
            visible_parameters["Valore"].str.contains(value_search, case=False, na=False, regex=False)
        ]

    if reference_df is not None and not visible_parameters.empty:
        lookup = create_catalog_lookup(reference_df)
        enriched = visible_parameters.copy()
        enriched["Abbreviated Name"] = enriched["Parametro"].map(base_parameter_name)
        enriched = enriched.merge(
            lookup,
            how="left",
            on=["Classe MO", "Abbreviated Name"],
            suffixes=("", " catalogo"),
        )
        visible_parameters = enriched

    st.dataframe(visible_parameters, use_container_width=True, hide_index=True)
    st.download_button(
        "Scarica parametri CSV",
        dataframe_to_csv_bytes(visible_parameters),
        file_name="nokia_xml_parametri.csv",
        mime="text/csv",
    )

with catalog_tab:
    st.subheader("Consultazione catalogo parametri")
    if reference_df is None:
        st.info("Aggiungi il catalogo Excel nella cartella data oppure caricalo dalla barra laterale.")
    else:
        ccol1, ccol2, ccol3 = st.columns(3)
        with ccol1:
            catalog_class = st.selectbox(
                "MO Class",
                ["Tutte"] + sorted(reference_df["MO Class"].dropna().unique().tolist()),
                key="catalog_class",
            )
        with ccol2:
            catalog_parameter = st.text_input("Parametro o nome esteso", key="catalog_parameter")
        with ccol3:
            catalog_technology = st.selectbox(
                "Tecnologia",
                ["Tutte"] + sorted(reference_df["Technology"].dropna().unique().tolist()),
            )

        visible_catalog = reference_df.copy()
        if catalog_class != "Tutte":
            visible_catalog = visible_catalog[visible_catalog["MO Class"] == catalog_class]
        if catalog_technology != "Tutte":
            visible_catalog = visible_catalog[visible_catalog["Technology"] == catalog_technology]
        if catalog_parameter:
            mask = visible_catalog["Abbreviated Name"].str.contains(
                catalog_parameter, case=False, na=False, regex=False
            )
            if "Full Name" in visible_catalog.columns:
                mask |= visible_catalog["Full Name"].str.contains(
                    catalog_parameter, case=False, na=False, regex=False
                )
            visible_catalog = visible_catalog[mask]

        st.caption(f"Risultati: {len(visible_catalog)}")
        st.dataframe(visible_catalog, use_container_width=True, hide_index=True)
        st.download_button(
            "Scarica risultati catalogo CSV",
            dataframe_to_csv_bytes(visible_catalog),
            file_name="nokia_catalogo_parametri.csv",
            mime="text/csv",
        )
