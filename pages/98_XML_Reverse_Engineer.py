import xml.etree.ElementTree as ET

import pandas as pd
import streamlit as st


# =====================================================
# CONFIGURAZIONE PAGINA
# =====================================================

st.set_page_config(
    page_title="Nokia XML Reverse Engineer",
    page_icon="🔎",
    layout="wide",
)


# =====================================================
# FUNZIONI XML
# =====================================================

def local_name(tag):
    """Restituisce il nome locale di un tag XML, senza namespace."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def clean_text(value):
    """Normalizza un valore testuale XML."""
    if value is None:
        return ""
    return str(value).strip()


def short_class_name(full_class_name):
    """Ricava il nome breve della classe Nokia mantenendo il nome completo."""
    value = clean_text(full_class_name)
    if ":" in value:
        return value.rsplit(":", 1)[1]
    return value


def extract_parameters(parent):
    """Legge i parametri p figli diretti di un elemento XML."""
    parameters = []

    for child in parent:
        if local_name(child.tag) != "p":
            continue

        parameters.append(
            {
                "Parametro": clean_text(child.attrib.get("name", "UNKNOWN")),
                "Valore": clean_text(child.text),
                "Attributi": dict(child.attrib),
            }
        )

    return parameters


def parse_item(item_element, item_number, parent_path):
    """Legge ricorsivamente un item, inclusi parametri e liste annidate."""
    item_path = f"{parent_path}/item[{item_number}]"

    item_data = {
        "numero": item_number,
        "percorso": item_path,
        "attributi": dict(item_element.attrib),
        "parametri": extract_parameters(item_element),
        "liste": [],
        "altri_elementi": [],
    }

    for child in item_element:
        child_tag = local_name(child.tag)

        if child_tag == "list":
            item_data["liste"].append(parse_list(child, item_path))
        elif child_tag != "p":
            item_data["altri_elementi"].append(parse_generic_element(child, item_path))

    return item_data


def parse_list(list_element, parent_path):
    """Legge ricorsivamente una list Nokia e tutti gli item contenuti."""
    list_name = clean_text(list_element.attrib.get("name", "UNKNOWN_LIST"))
    list_path = f"{parent_path}/list:{list_name}"

    list_data = {
        "nome": list_name,
        "percorso": list_path,
        "attributi": dict(list_element.attrib),
        "parametri_diretti": extract_parameters(list_element),
        "item": [],
        "liste_annidate": [],
        "altri_elementi": [],
    }

    item_number = 0

    for child in list_element:
        child_tag = local_name(child.tag)

        if child_tag == "item":
            item_number += 1
            list_data["item"].append(
                parse_item(child, item_number, list_path)
            )
        elif child_tag == "list":
            list_data["liste_annidate"].append(
                parse_list(child, list_path)
            )
        elif child_tag != "p":
            list_data["altri_elementi"].append(
                parse_generic_element(child, list_path)
            )

    return list_data


def parse_generic_element(element, parent_path):
    """Registra elementi XML non standard senza perderne il contenuto."""
    tag_name = local_name(element.tag)
    element_path = f"{parent_path}/{tag_name}"

    data = {
        "tag": tag_name,
        "percorso": element_path,
        "attributi": dict(element.attrib),
        "testo": clean_text(element.text),
        "figli": [],
    }

    for child in element:
        data["figli"].append(parse_generic_element(child, element_path))

    return data


def get_managed_objects(root):
    """Estrae tutti i managedObject, i parametri, le liste e gli item."""
    managed_objects = []

    for mo_index, element in enumerate(root.iter(), start=1):
        if local_name(element.tag) != "managedObject":
            continue

        attributes = dict(element.attrib)
        full_class = clean_text(attributes.get("class", ""))
        dist_name = clean_text(attributes.get("distName", ""))

        parameters = extract_parameters(element)
        lists = []
        other_elements = []

        for child in element:
            child_tag = local_name(child.tag)

            if child_tag == "list":
                lists.append(parse_list(child, dist_name or full_class or "managedObject"))
            elif child_tag != "p":
                other_elements.append(
                    parse_generic_element(
                        child,
                        dist_name or full_class or "managedObject",
                    )
                )

        managed_objects.append(
            {
                "MO_ID": len(managed_objects) + 1,
                "Classe completa": full_class,
                "Classe breve": short_class_name(full_class),
                "distName": dist_name,
                "version": clean_text(attributes.get("version", "")),
                "operation": clean_text(attributes.get("operation", "")),
                "attributi": attributes,
                "parametri": parameters,
                "liste": lists,
                "altri_elementi": other_elements,
                "numero_parametri": len(parameters),
                "numero_liste": len(lists),
            }
        )

    return managed_objects


# =====================================================
# FUNZIONI DI VISUALIZZAZIONE
# =====================================================

def parameters_dataframe(parameters):
    """Converte una lista di parametri in DataFrame."""
    if not parameters:
        return pd.DataFrame(columns=["Parametro", "Valore"])

    return pd.DataFrame(
        [
            {
                "Parametro": parameter.get("Parametro", ""),
                "Valore": parameter.get("Valore", ""),
            }
            for parameter in parameters
        ]
    )


def render_generic_element(element_data, key_prefix):
    """Visualizza un elemento XML non standard."""
    label = element_data.get("tag", "elemento")
    path = element_data.get("percorso", "")

    with st.expander(f"Elemento: {label} | {path}"):
        attributes = element_data.get("attributi", {})
        text = element_data.get("testo", "")

        if attributes:
            st.caption("Attributi")
            st.json(attributes)

        if text:
            st.caption("Testo")
            st.code(text)

        for child_index, child in enumerate(element_data.get("figli", []), start=1):
            render_generic_element(child, f"{key_prefix}_child_{child_index}")


def render_list(list_data, key_prefix):
    """Visualizza ricorsivamente una lista e i relativi item."""
    list_name = list_data.get("nome", "UNKNOWN_LIST")
    items = list_data.get("item", [])
    nested_lists = list_data.get("liste_annidate", [])
    direct_parameters = list_data.get("parametri_diretti", [])

    title = (
        f"Lista: {list_name} | "
        f"Item: {len(items)} | "
        f"Liste annidate: {len(nested_lists)}"
    )

    with st.expander(title):
        st.caption(f"Percorso XML: {list_data.get('percorso', '')}")

        attributes = list_data.get("attributi", {})
        if attributes:
            st.caption("Attributi della lista")
            st.json(attributes)

        if direct_parameters:
            st.caption("Parametri diretti della lista")
            st.dataframe(
                parameters_dataframe(direct_parameters),
                use_container_width=True,
                hide_index=True,
            )

        if not items and not nested_lists and not direct_parameters:
            st.info("Lista vuota.")

        for item_index, item in enumerate(items, start=1):
            item_parameters = item.get("parametri", [])
            item_lists = item.get("liste", [])

            with st.expander(
                f"Item {item_index} | Parametri: {len(item_parameters)} | "
                f"Liste annidate: {len(item_lists)}"
            ):
                st.caption(f"Percorso XML: {item.get('percorso', '')}")

                item_attributes = item.get("attributi", {})
                if item_attributes:
                    st.caption("Attributi item")
                    st.json(item_attributes)

                if item_parameters:
                    st.dataframe(
                        parameters_dataframe(item_parameters),
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.info("L'item non contiene parametri p diretti.")

                for nested_index, nested_list in enumerate(item_lists, start=1):
                    render_list(
                        nested_list,
                        f"{key_prefix}_item_{item_index}_list_{nested_index}",
                    )

                for other_index, other in enumerate(
                    item.get("altri_elementi", []), start=1
                ):
                    render_generic_element(
                        other,
                        f"{key_prefix}_item_{item_index}_other_{other_index}",
                    )

        for nested_index, nested_list in enumerate(nested_lists, start=1):
            render_list(
                nested_list,
                f"{key_prefix}_nested_{nested_index}",
            )

        for other_index, other in enumerate(
            list_data.get("altri_elementi", []), start=1
        ):
            render_generic_element(
                other,
                f"{key_prefix}_other_{other_index}",
            )


def count_all_items(list_data):
    """Conta ricorsivamente tutti gli item di una lista."""
    total = len(list_data.get("item", []))

    for item in list_data.get("item", []):
        for nested_list in item.get("liste", []):
            total += count_all_items(nested_list)

    for nested_list in list_data.get("liste_annidate", []):
        total += count_all_items(nested_list)

    return total


# =====================================================
# INTERFACCIA STREAMLIT
# =====================================================

st.title("Nokia XML Reverse Engineer")
st.caption(
    "Analisi completa di managedObject, attributi, parametri, liste e item."
)

xml_file = st.file_uploader(
    "Carica un file XML Nokia",
    type=["xml"],
)

if xml_file is None:
    st.info("Carica un file XML per avviare l'analisi.")
    st.stop()

try:
    xml_bytes = xml_file.getvalue()
    root = ET.fromstring(xml_bytes)
    managed_objects = get_managed_objects(root)
except ET.ParseError as exc:
    st.error(f"XML non valido: {exc}")
    st.stop()
except Exception as exc:
    st.error(f"Errore durante l'analisi XML: {exc}")
    st.stop()

if not managed_objects:
    st.warning("Nessun managedObject trovato nel file XML.")
    st.stop()

objects_df = pd.DataFrame(managed_objects)

total_lists = int(objects_df["numero_liste"].sum())
total_direct_parameters = int(objects_df["numero_parametri"].sum())
total_items = sum(
    count_all_items(list_data)
    for managed_object in managed_objects
    for list_data in managed_object.get("liste", [])
)

metric_1, metric_2, metric_3, metric_4, metric_5 = st.columns(5)
metric_1.metric("Managed Object", len(objects_df))
metric_2.metric("Classi distinte", objects_df["Classe completa"].nunique())
metric_3.metric("Parametri diretti", total_direct_parameters)
metric_4.metric("Liste dirette", total_lists)
metric_5.metric("Item totali", total_items)

summary_tab, explorer_tab = st.tabs(
    ["Riepilogo classi", "Esplora classe"]
)

with summary_tab:
    summary = (
        objects_df.groupby(["Classe breve", "Classe completa"], dropna=False)
        .agg(
            Occorrenze=("MO_ID", "count"),
            Parametri_diretti=("numero_parametri", "sum"),
            Liste_dirette=("numero_liste", "sum"),
        )
        .reset_index()
        .sort_values(
            by=["Occorrenze", "Classe breve"],
            ascending=[False, True],
        )
    )

    class_filter = st.text_input(
        "Filtra le classi",
        placeholder="Esempio: IPRT, BBMOD_R, LNREL",
    )

    if class_filter:
        mask = (
            summary["Classe breve"].str.contains(
                class_filter,
                case=False,
                na=False,
                regex=False,
            )
            | summary["Classe completa"].str.contains(
                class_filter,
                case=False,
                na=False,
                regex=False,
            )
        )
        summary = summary[mask]

    st.dataframe(
        summary,
        use_container_width=True,
        hide_index=True,
    )

with explorer_tab:
    class_options = sorted(objects_df["Classe completa"].dropna().unique().tolist())

    selected_class = st.selectbox(
        "Seleziona la classe",
        class_options,
        format_func=lambda value: f"{short_class_name(value)} | {value}",
    )

    class_objects = objects_df[
        objects_df["Classe completa"] == selected_class
    ].copy()

    st.write(f"Oggetti trovati: {len(class_objects)}")

    object_labels = []
    object_indexes = []

    for dataframe_index, row in class_objects.iterrows():
        dist_name = clean_text(row["distName"])
        label = dist_name if dist_name else f"MO #{row['MO_ID']}"
        object_labels.append(label)
        object_indexes.append(dataframe_index)

    selected_label = st.selectbox(
        "Seleziona il Managed Object",
        object_labels,
    )

    selected_position = object_labels.index(selected_label)
    selected_index = object_indexes[selected_position]
    selected_object = objects_df.loc[selected_index]

    st.subheader("Attributi Managed Object")
    st.json(selected_object["attributi"])

    st.subheader("Parametri diretti")
    direct_parameters = selected_object["parametri"]

    if direct_parameters:
        st.dataframe(
            parameters_dataframe(direct_parameters),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Nessun parametro p diretto presente nel Managed Object.")

    st.subheader("Liste e item")
    object_lists = selected_object["liste"]

    if object_lists:
        for list_index, list_data in enumerate(object_lists, start=1):
            render_list(list_data, f"root_list_{list_index}")
    else:
        st.info("Nessuna lista presente nel Managed Object.")

    other_elements = selected_object["altri_elementi"]
    if other_elements:
        st.subheader("Altri elementi XML")
        for other_index, other in enumerate(other_elements, start=1):
            render_generic_element(other, f"root_other_{other_index}")
