import html
import re
import streamlit as st


# ============================================================
# CONFIGURAZIONE PAGINA
# ============================================================

st.set_page_config(
    page_title="BSC Pool Script Builder",
    page_icon="🧩",
    layout="wide",
)

st.title("BSC Pool Script Builder")

st.write(
    "Unisce gli script TXT prodotti per destinazioni differenti "
    "in un unico script BSC, mantenendo una sola copia delle "
    "sezioni e dei commenti comuni."
)


# ============================================================
# LETTURA FILE
# ============================================================

def decode_uploaded_file(uploaded_file):
    """
    Legge il file caricato provando le codifiche più comuni.
    """

    raw_data = uploaded_file.getvalue()

    encodings = [
        "utf-8-sig",
        "utf-8",
        "cp1252",
        "latin-1",
    ]

    for encoding in encodings:
        try:
            return raw_data.decode(encoding)
        except UnicodeDecodeError:
            continue

    return raw_data.decode(
        "utf-8",
        errors="replace",
    )


def normalize_newlines(text):
    """
    Uniforma i fine riga.
    """

    return (
        text
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )


# ============================================================
# CLASSIFICAZIONE RIGHE
# ============================================================

def is_blank_line(line):
    """
    Restituisce True se la riga è vuota.
    """

    return not line.strip()


def is_comment_line(line):
    """
    Tutte le righe che iniziano con ! sono commenti.
    """

    return line.lstrip().startswith("!")


def is_section_title(line):
    """
    Riconosce i titoli funzionali delle sezioni.

    Esempi:

    !*** MSC definition in Bsc ***!
    !*** Define NRI Value and Lenght ***!
    !*** Create SCTP Association towards MSC Server => VPI20U ***!
    """

    stripped = line.strip()

    return bool(
        re.match(
            r"^!\s*\*{3}.*\*{3}\s*!?\s*$",
            stripped,
            flags=re.IGNORECASE,
        )
    )


def normalize_line_for_comparison(line):
    """
    Normalizza una riga per confrontarla senza modificare
    il testo effettivamente scritto nell'output.
    """

    normalized = html.unescape(line)
    normalized = normalized.replace("\\", "")
    normalized = normalized.strip().lower()
    normalized = re.sub(r"\s+", " ", normalized)

    return normalized


# ============================================================
# CHIAVE COMUNE DELLA SEZIONE
# ============================================================

def get_section_key(title_line):
    """
    Genera una chiave logica comune per la sezione.

    Il titolo originale viene mantenuto nell'output, ma la chiave
    usata per confrontare i file elimina gli elementi variabili
    legati alla destinazione.

    Esempio:

    Create SCTP Association ... => VPI20U
    Create SCTP Association ... => VRM30U

    diventano la stessa sezione.
    """

    normalized = normalize_line_for_comparison(
        title_line
    )

    # Elimina i marcatori grafici iniziali e finali.
    normalized = re.sub(
        r"^!\s*\*+",
        "",
        normalized,
    )

    normalized = re.sub(
        r"\*+\s*!?$",
        "",
        normalized,
    )

    normalized = normalized.strip()

    # Tutto ciò che compare dopo => è considerato
    # una destinazione variabile.
    normalized = re.sub(
        r"\s*=\s*>\s*[a-z0-9_.-]+.*$",
        "",
        normalized,
        flags=re.IGNORECASE,
    )

    # Gestisce anche il caso in cui nel testo sia rimasta
    # l'entità HTML invece del simbolo >.
    normalized = re.sub(
        r"\s*=&gt;\s*[a-z0-9_.-]+.*$",
        "",
        normalized,
        flags=re.IGNORECASE,
    )

    normalized = re.sub(
        r"\s+",
        " ",
        normalized,
    ).strip()

    return normalized


# ============================================================
# PRINT GENERALI
# ============================================================

def is_general_print(line):
    """
    Identifica i comandi di print/interrogazione generale.

    Regole:

    1. Il comando termina con 'all;'
    2. Il comando appartiene all'elenco dei print speciali

    I print generali vengono presi una sola volta dal primo file
    e mantenuti nella loro posizione originale.
    """

    normalized = normalize_line_for_comparison(
        line
    )

    special_general_prints = {
        "rrnlp;",
    }

    return (
        normalized.endswith("all;")
        or normalized in special_general_prints
    )


# ============================================================
# SUDDIVISIONE DEL FILE IN SEZIONI
# ============================================================

def split_into_sections(text):
    """
    Divide il file in sezioni.

    Ogni riga !*** ... ***! apre una nuova sezione.

    Le righe precedenti al primo titolo costituiscono
    il preambolo del file.
    """

    text = normalize_newlines(text)
    lines = text.split("\n")

    sections = []

    current_section = {
        "key": "__PREAMBLE__",
        "title_line": None,
        "lines": [],
    }

    for line in lines:

        if is_section_title(line):

            sections.append(
                current_section
            )

            current_section = {
                "key": get_section_key(line),
                "title_line": line,
                "lines": [],
            }

        else:
            current_section["lines"].append(
                line
            )

    sections.append(
        current_section
    )

    # Elimina soltanto eventuali sezioni completamente
    # vuote create prima del primo titolo.
    cleaned_sections = []

    for section in sections:

        has_content = (
            section["title_line"] is not None
            or any(
                line.strip()
                for line in section["lines"]
            )
        )

        if has_content:
            cleaned_sections.append(
                section
            )

    return cleaned_sections


def build_section_map(sections):
    """
    Crea una mappa:

    chiave logica -> lista delle sezioni corrispondenti

    La lista permette di gestire eventuali sezioni con
    lo stesso titolo ripetute nello stesso file.
    """

    section_map = {}

    for section in sections:

        key = section["key"]

        if key not in section_map:
            section_map[key] = []

        section_map[key].append(
            section
        )

    return section_map


# ============================================================
# ESTRAZIONE DEI COMANDI SPECIFICI
# ============================================================

def extract_specific_commands(section):
    """
    Estrae i comandi specifici di una destinazione.

    Vengono esclusi:

    - righe vuote;
    - commenti;
    - print generali.

    L'ordine originale dei comandi viene mantenuto.

    Esempio SCTP:

    IHADI destinazione
    IHADI destinazione
    IHAPC destinazione
    IHAPC destinazione
    """

    commands = []

    if section is None:
        return commands

    for line in section["lines"]:

        if is_blank_line(line):
            continue

        if is_comment_line(line):
            continue

        if is_general_print(line):
            continue

        commands.append(line)

    return commands


# ============================================================
# POSIZIONAMENTO DEI COMANDI NEL TEMPLATE
# ============================================================

def find_specific_command_positions(lines):
    """
    Trova le posizioni dei comandi specifici nel template.

    Sono considerate specifiche le righe che non sono:

    - vuote;
    - commenti;
    - print generali.
    """

    positions = []

    for index, line in enumerate(lines):

        if is_blank_line(line):
            continue

        if is_comment_line(line):
            continue

        if is_general_print(line):
            continue

        positions.append(index)

    return positions


def resolve_insertion_position(template_lines):
    """
    Determina dove inserire i comandi aggregati.

    Se il template contiene già comandi specifici, viene usata
    la posizione del primo comando specifico.

    Se non ne contiene, i comandi vengono inseriti prima del
    blocco finale di print/commenti/righe vuote.
    """

    specific_positions = find_specific_command_positions(
        template_lines
    )

    if specific_positions:
        return specific_positions[0]

    position = len(template_lines)

    while position > 0:

        previous_line = template_lines[position - 1]

        if (
            is_blank_line(previous_line)
            or is_comment_line(previous_line)
            or is_general_print(previous_line)
        ):
            position -= 1
        else:
            break

    return position


# ============================================================
# MERGE DI UNA SEZIONE COMUNE
# ============================================================

def merge_common_section(
    template_section,
    matching_sections,
):
    """
    Fonde tutte le destinazioni nella stessa sezione funzionale.

    La struttura e i commenti sono quelli del primo file.

    I comandi specifici vengono aggiunti a blocchi completi,
    seguendo l'ordine di caricamento dei file.
    """

    template_lines = list(
        template_section["lines"]
    )

    all_specific_commands = []

    # Ogni sezione corrisponde a una destinazione.
    # I comandi vengono aggiunti come blocco completo,
    # mantenendo l'ordine del file.
    for section in matching_sections:

        destination_commands = (
            extract_specific_commands(section)
        )

        all_specific_commands.extend(
            destination_commands
        )

    specific_positions = (
        find_specific_command_positions(
            template_lines
        )
    )

    insertion_position = (
        resolve_insertion_position(
            template_lines
        )
    )

    # Rimuove dal template i comandi specifici originali.
    # Verranno reinseriti insieme ai comandi delle altre
    # destinazioni.
    specific_position_set = set(
        specific_positions
    )

    cleaned_template_lines = []

    adjusted_insertion_position = 0

    for index, line in enumerate(template_lines):

        if index < insertion_position:

            if index not in specific_position_set:
                adjusted_insertion_position += 1

        if index in specific_position_set:
            continue

        cleaned_template_lines.append(line)

    # Inserisce tutti i blocchi destinazione nella posizione
    # occupata dai comandi specifici nel primo file.
    cleaned_template_lines[
        adjusted_insertion_position:
        adjusted_insertion_position
    ] = all_specific_commands

    return cleaned_template_lines


# ============================================================
# RICONOSCIMENTO INTESTAZIONE GENERALE
# ============================================================

def is_central_data_section(section):
    """
    La sezione DATI DI CENTRALE viene copiata esclusivamente
    dal primo file.
    """

    key = section["key"].lower()

    return "dati di centrale" in key


# ============================================================
# INDIVIDUAZIONE DELLA DECORAZIONE DEL TITOLO
# ============================================================

def move_leading_separator_to_next_section(sections):
    """
    Nei file originali, il separatore superiore della sezione:

    !-----------------------------------!

    si trova normalmente prima del titolo:

    !*** Titolo sezione ***!

    Poiché il parser apre la sezione sulla riga del titolo,
    il separatore potrebbe rimanere nella sezione precedente.

    Questa funzione sposta l'ultimo separatore grafico della
    sezione precedente all'inizio della sezione successiva.
    """

    if len(sections) < 2:
        return sections

    moved_sections = []

    for section in sections:

        moved_sections.append(
            {
                "key": section["key"],
                "title_line": section["title_line"],
                "lines": list(section["lines"]),
                "leading_lines": [],
            }
        )

    for index in range(1, len(moved_sections)):

        previous_section = moved_sections[index - 1]
        current_section = moved_sections[index]

        previous_lines = previous_section["lines"]

        separator_index = None

        # Salta eventuali righe vuote finali.
        check_index = len(previous_lines) - 1

        while (
            check_index >= 0
            and is_blank_line(
                previous_lines[check_index]
            )
        ):
            check_index -= 1

        if check_index >= 0:

            candidate = previous_lines[check_index]
            stripped = candidate.strip()

            # Riconosce:
            # !----------------------!
            # !======================!
            if re.match(
                r"^![=\-]+\s*!$",
                stripped,
            ):
                separator_index = check_index

        if separator_index is not None:

            leading = previous_lines[
                separator_index:
            ]

            previous_section["lines"] = (
                previous_lines[
                    :separator_index
                ]
            )

            current_section["leading_lines"] = (
                leading
            )

    return moved_sections


# ============================================================
# MERGE COMPLETO
# ============================================================

def merge_txt_files(uploaded_files):
    """
    Esegue il merge completo dei file caricati.
    """

    parsed_files = []

    for uploaded_file in uploaded_files:

        text = decode_uploaded_file(
            uploaded_file
        )

        sections = split_into_sections(
            text
        )

        sections = (
            move_leading_separator_to_next_section(
                sections
            )
        )

        parsed_files.append(
            {
                "name": uploaded_file.name,
                "sections": sections,
                "section_map": build_section_map(
                    sections
                ),
            }
        )

    # Il primo file stabilisce:
    # - ordine delle sezioni;
    # - intestazioni;
    # - commenti;
    # - posizione dei print;
    # - formattazione.
    template_file = parsed_files[0]

    final_lines = []

    # Gestisce eventuali sezioni con stessa chiave
    # ripetute più volte nello stesso file.
    key_occurrences = {}

    for template_section in template_file["sections"]:

        section_key = template_section["key"]

        occurrence_index = key_occurrences.get(
            section_key,
            0,
        )

        key_occurrences[section_key] = (
            occurrence_index + 1
        )

        # Separatore grafico precedente al titolo.
        final_lines.extend(
            template_section.get(
                "leading_lines",
                [],
            )
        )

        # Titolo originale del primo file.
        if template_section["title_line"] is not None:

            final_lines.append(
                template_section["title_line"]
            )

        # Il preambolo e i dati di centrale vengono copiati
        # integralmente dal primo file.
        if (
            section_key == "__PREAMBLE__"
            or is_central_data_section(
                template_section
            )
        ):

            final_lines.extend(
                template_section["lines"]
            )

            continue

        # Cerca nei file caricati la stessa sezione logica.
        matching_sections = []

        for parsed_file in parsed_files:

            candidate_sections = (
                parsed_file["section_map"].get(
                    section_key,
                    [],
                )
            )

            if occurrence_index < len(
                candidate_sections
            ):

                matching_sections.append(
                    candidate_sections[
                        occurrence_index
                    ]
                )

        merged_lines = merge_common_section(
            template_section=template_section,
            matching_sections=matching_sections,
        )

        final_lines.extend(
            merged_lines
        )

    # Rimuove solo le righe vuote in eccesso alla fine.
    while (
        final_lines
        and not final_lines[-1].strip()
    ):
        final_lines.pop()

    return "\n".join(final_lines) + "\n"


# ============================================================
# INTERFACCIA STREAMLIT
# ============================================================

uploaded_files = st.file_uploader(
    "Carica i file TXT nell'ordine desiderato",
    type=["txt"],
    accept_multiple_files=True,
    help=(
        "Il primo file determina intestazioni, commenti, "
        "ordine delle sezioni e posizione dei print generali."
    ),
)


if uploaded_files:

    st.subheader("File caricati")

    for index, uploaded_file in enumerate(
        uploaded_files,
        start=1,
    ):

        if index == 1:

            st.write(
                f"**{index}. {uploaded_file.name}** "
                "• template principale"
            )

        else:

            st.write(
                f"**{index}. {uploaded_file.name}**"
            )


if len(uploaded_files) < 2:

    st.info(
        "Carica almeno due file TXT per eseguire il merge."
    )

else:

    try:

        merged_text = merge_txt_files(
            uploaded_files
        )

        st.success(
            f"Merge completato: "
            f"{len(uploaded_files)} file elaborati."
        )

        output_name = st.text_input(
            "Nome del file finale",
            value="BSC_POOL_MERGED.txt",
        )

        if not output_name.lower().endswith(
            ".txt"
        ):
            output_name += ".txt"

        st.download_button(
            label="Scarica il TXT unificato",
            data=merged_text.encode(
                "utf-8"
            ),
            file_name=output_name,
            mime="text/plain",
            use_container_width=True,
        )

        st.subheader(
            "Anteprima del file unificato"
        )

        st.text_area(
            label="Contenuto generato",
            value=merged_text,
            height=700,
        )

    except Exception as error:

        st.error(
            f"Errore durante il merge: {error}"
        )
