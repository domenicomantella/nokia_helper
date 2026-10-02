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
    "Carica due o più file TXT. Il primo file viene utilizzato come "
    "struttura principale del file unificato."
)


# ============================================================
# FUNZIONI DI LETTURA
# ============================================================

def decode_uploaded_file(uploaded_file):
    """
    Legge un file caricato da Streamlit provando le codifiche più comuni.

    Restituisce il testo mantenendo le righe originali.
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

    return raw_data.decode("utf-8", errors="replace")


def normalize_newlines(text):
    """
    Uniforma i caratteri di fine riga.
    """

    return (
        text
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )


# ============================================================
# RICONOSCIMENTO DELLE RIGHE
# ============================================================

def is_blank_line(line):
    """
    Riconosce una riga vuota.
    """

    return not line.strip()


def is_comment_line(line):
    """
    Riconosce i commenti dei file comando.

    Sono considerate commenti tutte le righe che,
    dopo eventuali spazi iniziali, iniziano con '!'.
    """

    return line.lstrip().startswith("!")


def is_section_title(line):
    """
    Riconosce una riga titolo del tipo:

    !*** MSC definition in Bsc ***!
    !*** Define NRI Value and Lenght ***!
    """

    stripped = line.strip()

    return bool(
        re.match(
            r"^!\s*\*{3}.*\*{3}\s*!?\s*$",
            stripped,
            flags=re.IGNORECASE,
        )
    )


def normalize_section_title(line):
    """
    Normalizza il titolo della sezione per confrontarlo
    tra file diversi.
    """

    normalized = line.strip().lower()

    normalized = re.sub(r"\s+", " ", normalized)
    normalized = normalized.replace("\\", "")

    return normalized


def is_general_print(line):
    """
    Identifica i print generali.

    Sono considerati print generali:

    1. I comandi che terminano con 'all;'
    2. I comandi senza parametri inseriti esplicitamente
       nell'elenco SPECIAL_GENERAL_PRINTS

    I print vengono mantenuti nelle posizioni presenti
    nel primo file utilizzato come template.
    """

    stripped = line.strip().lower()

    special_general_prints = {
        "rrnlp;",
    }

    return (
        stripped.endswith("all;")
        or stripped in special_general_prints
    )

def get_command_name(line):
    """
    Estrae il nome principale del comando.

    Esempi:

    RRMBI:MSC=VPI20U  -> RRMBI
    C7SPI:SP=3-6423   -> C7SPI
    rrnlp;             -> RRNLP
    """

    stripped = line.strip()

    if not stripped:
        return ""

    match = re.match(
        r"^([A-Za-z0-9_-]+)",
        stripped,
    )

    if match:
        return match.group(1).upper()

    return stripped.upper()


# ============================================================
# SUDDIVISIONE IN SEZIONI
# ============================================================

def split_into_sections(text):
    """
    Divide il file in sezioni utilizzando le righe !*** ... ***!
    come titolo.

    La parte precedente al primo titolo viene conservata
    come sezione iniziale.
    """

    text = normalize_newlines(text)
    lines = text.split("\n")

    sections = []

    current_title = "__PREAMBLE__"
    current_title_line = None
    current_lines = []

    for line in lines:

        if is_section_title(line):

            if current_lines or current_title_line is not None:
                sections.append(
                    {
                        "title": current_title,
                        "title_line": current_title_line,
                        "lines": current_lines,
                    }
                )

            current_title = normalize_section_title(line)
            current_title_line = line
            current_lines = []

        else:
            current_lines.append(line)

    if current_lines or current_title_line is not None:
        sections.append(
            {
                "title": current_title,
                "title_line": current_title_line,
                "lines": current_lines,
            }
        )

    return sections


def build_section_map(sections):
    """
    Crea una mappa:

    titolo sezione -> lista di sezioni con quel titolo

    La lista permette di gestire anche eventuali titoli ripetuti.
    """

    section_map = {}

    for section in sections:
        title = section["title"]

        if title not in section_map:
            section_map[title] = []

        section_map[title].append(section)

    return section_map


# ============================================================
# ANALISI DEL CONTENUTO DELLA SEZIONE
# ============================================================

def collect_commands_by_type(section):
    """
    Raccoglie i comandi non-commento e non-print della sezione,
    raggruppandoli per nome comando.

    I print che terminano con all; non vengono raccolti:
    saranno mantenuti nelle posizioni del file template.
    """

    commands = {}

    if section is None:
        return commands

    for line in section["lines"]:

        if is_blank_line(line):
            continue

        if is_comment_line(line):
            continue

        if is_general_print(line):
            continue

        command_name = get_command_name(line)

        if not command_name:
            continue

        if command_name not in commands:
            commands[command_name] = []

        # Il resto dei comandi viene riportato.
        # Non viene eliminato anche se identico.
        commands[command_name].append(line)

    return commands


def find_trailing_output_position(lines):
    """
    Cerca il punto prima del blocco finale formato da:

    - righe vuote
    - commenti
    - print generali

    Serve per inserire eventuali comandi presenti solamente
    nei file successivi e non nel template.
    """

    position = len(lines)

    while position > 0:

        line = lines[position - 1]

        if (
            is_blank_line(line)
            or is_comment_line(line)
            or is_general_print(line)
        ):
            position -= 1
        else:
            break

    return position


# ============================================================
# MERGE DELLA SINGOLA SEZIONE
# ============================================================

def merge_operational_section(
    template_section,
    matching_sections,
):
    """
    Unisce una sezione operativa.

    Regole:

    1. Commenti e struttura vengono presi dal primo file.
    2. I print generali vengono mantenuti una sola volta
       per ciascuna posizione presente nel template.
    3. I comandi specifici vengono raccolti da tutti i file.
    4. I comandi vengono inseriti rispettando l'ordine
       dei tipi comando del template.
    """

    output_lines = []

    all_commands = {}
    command_order = []

    # Raccoglie i comandi da tutti i file nell'ordine
    # in cui i file sono stati caricati.
    for section in matching_sections:

        commands = collect_commands_by_type(section)

        for command_name, command_lines in commands.items():

            if command_name not in all_commands:
                all_commands[command_name] = []
                command_order.append(command_name)

            all_commands[command_name].extend(command_lines)

    inserted_commands = set()

    template_lines = template_section["lines"]

    for line in template_lines:

        # Commenti, righe vuote e print generali
        # restano nella posizione del primo file.
        if (
            is_blank_line(line)
            or is_comment_line(line)
            or is_general_print(line)
        ):
            output_lines.append(line)
            continue

        command_name = get_command_name(line)

        # Alla prima occorrenza del tipo comando,
        # inserisce tutte le righe raccolte dai file.
        if command_name not in inserted_commands:

            command_lines = all_commands.get(
                command_name,
                [line],
            )

            output_lines.extend(command_lines)
            inserted_commands.add(command_name)

        # Le eventuali occorrenze successive dello stesso
        # comando nel template non vengono replicate,
        # perché sono già state inserite tutte insieme.

    # Gestione di eventuali tipi comando presenti solamente
    # nei file successivi.
    missing_commands = []

    for command_name in command_order:

        if command_name not in inserted_commands:
            missing_commands.extend(
                all_commands[command_name]
            )

    if missing_commands:

        insert_position = find_trailing_output_position(
            output_lines
        )

        output_lines[
            insert_position:insert_position
        ] = missing_commands

    return output_lines


# ============================================================
# MERGE COMPLETO
# ============================================================

def is_central_data_section(section):
    """
    Riconosce la sezione DATI DI CENTRALE.

    Questa sezione viene copiata solamente dal primo file,
    perché rappresenta l'intestazione comune dello script.
    """

    title = section["title"].lower()

    return "dati di centrale" in title


def merge_txt_files(uploaded_files):
    """
    Esegue il merge completo dei file.
    """

    parsed_files = []

    for uploaded_file in uploaded_files:

        text = decode_uploaded_file(uploaded_file)
        sections = split_into_sections(text)

        parsed_files.append(
            {
                "name": uploaded_file.name,
                "sections": sections,
                "section_map": build_section_map(sections),
            }
        )

    # Il primo file è il template.
    template_file = parsed_files[0]

    final_lines = []

    # Conta quante volte è già comparso un titolo.
    # Serve se nel template esistono sezioni omonime.
    title_occurrences = {}

    for template_section in template_file["sections"]:

        title = template_section["title"]

        occurrence_index = title_occurrences.get(title, 0)
        title_occurrences[title] = occurrence_index + 1

        # Aggiunge il titolo della sezione preso dal template.
        if template_section["title_line"] is not None:
            final_lines.append(
                template_section["title_line"]
            )

        # Preambolo e dati di centrale:
        # copia esatta dal primo file.
        if (
            title == "__PREAMBLE__"
            or is_central_data_section(template_section)
        ):
            final_lines.extend(
                template_section["lines"]
            )
            continue

        matching_sections = []

        for parsed_file in parsed_files:

            file_sections = parsed_file[
                "section_map"
            ].get(title, [])

            if occurrence_index < len(file_sections):
                matching_sections.append(
                    file_sections[occurrence_index]
                )

        merged_section_lines = merge_operational_section(
            template_section=template_section,
            matching_sections=matching_sections,
        )

        final_lines.extend(merged_section_lines)

    # Evita un numero eccessivo di righe vuote finali.
    while final_lines and not final_lines[-1].strip():
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

    st.subheader("Ordine dei file")

    for index, uploaded_file in enumerate(
        uploaded_files,
        start=1,
    ):
        if index == 1:
            st.write(
                f"**{index}. {uploaded_file.name}** "
                "(template principale)"
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

        if not output_name.lower().endswith(".txt"):
            output_name = output_name + ".txt"

        st.download_button(
            label="Scarica il TXT unificato",
            data=merged_text.encode("utf-8"),
            file_name=output_name,
            mime="text/plain",
            use_container_width=True,
        )

        st.subheader("Anteprima del file unificato")

        st.text_area(
            label="Contenuto generato",
            value=merged_text,
            height=700,
        )

    except Exception as error:

        st.error(
            f"Errore durante il merge: {error}"
        )
