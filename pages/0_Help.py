import streamlit as st

def help_page():

    st.title("Help - Portale Utility Tecniche")

    st.markdown("""
    ## 📌 Descrizione generale

    Questa applicazione è un portale interno sviluppato in **Streamlit** che raccoglie una serie di utility tecniche 
    per supportare attività operative e di configurazione sulla rete.

    Il portale è modulare: ogni funzionalità è disponibile tramite una pagina dedicata.

    ---
    
    ## 🧩 Moduli disponibili

    ### 🔹 Replace BB Controller

    Questo modulo permette la creazione automatizzata dei file di configurazione per attività di replace.

    #### Funzionalità:
    - Generazione di:
        - `NodeInfo.xml`
        - `ProjectInfo.xml`
    - Creazione automatica di un file `.zip`
    - Normalizzazione automatica del nome nodo (MAIUSCOLO)

    #### Logica operativa:
    - Modalità **ZT**
        - Richiede Serial Number
        - Inserisce `hardwareSerialNumber`
    - Modalità **LMT**
        - NON richiede Serial Number
        - Rimuove `hardwareSerialNumber`
        - Richiede:
            - Backup Name
            - IP Default Gateway

    #### Output:
    ```
    Replace_<NODO>.zip
    ├── ProjectInfo.xml
    └── <NODO>/
        └── NodeInfo.xml
    ```

    ---
    
    ### 🔹 XML & Excel Processor

    Questo modulo consente l’elaborazione di file XML combinando informazioni provenienti da file Excel.

    #### Modalità disponibili:

    ##### ✅ 1. Elaborazione Completa
    - Modifica il file XML utilizzando dati provenienti da Excel
    - Arricchisce i parametri dei nodi con:
        - indirizzi IP (M-plane / CU-plane)
        - subnet
        - logical address
    - Effettua aggiornamenti o aggiunta automatica dei parametri XML
    
    ##### ✅ 2. Solo Pulizia
    - Rimuove namespace XML
    - Sostituisce automaticamente:
        - `Roma4` → `PLMN`
    - NON utilizza file Excel
    
    ---
    
    ## ⚙️ Funzionamento XML Processor

    ### Input richiesti:
    
    - File XML
    - File Excel (solo modalità completa)
    - Chiave di ricerca (colonna Excel)

    ---
    
    ### Logica di elaborazione

    1. Lettura XML
        - Pulizia testo (`Roma4`)
        - Rimozione namespace

    2. In modalità completa:
        - Lettura Excel (foglio `TNL_TI_SRAN`)
        - Ricerca dati tramite chiave
        - Costruzione parametri
    
    3. Aggiornamento XML:
        - Modifica parametri esistenti
        - Aggiunta parametri mancanti
        - Conversione `logicalBcxuAddress`

    4. Generazione file finale

    ---
    
    ### Output
    
    File XML modificato con:
    
    - nome originale
    - suffisso:
        - `_modificato`
        - `_solo_pulizia`
    - timestamp automatico

    ---
    
    ## 🔒 Gestione dati

    - I template utilizzati nel portale non contengono dati sensibili
    - I valori vengono inseriti a runtime tramite input utente
    - L’elaborazione avviene completamente lato server (sandbox)

    ---
    
    ## 🚧 Moduli in sviluppo

    Alcune funzionalità potrebbero essere:
    
    - non ancora visibili
    - bloccate
    - in fase di sviluppo

    ---
    
    ### 🔜 Modulo Merge & PDF (in sviluppo)

    Previsto un modulo avanzato per:
    
    - integrazione dati da più sorgenti:
        - XML
        - Excel
        - CSV
        - DOCX
    - correlazione dati tramite chiavi comuni
    - generazione report PDF finale

    ---
    
    ## 🧠 Architettura

    Il portale è progettato secondo un modello modulare:

    ```
    Input → Parsing → Normalizzazione → Elaborazione → Output
    ```

    Ogni modulo è indipendente ma integrato nel portale.

    ---
    
    ## 👨‍💻 Note tecniche

    - Framework: **Streamlit**
    - Linguaggio: **Python**
    - Librerie principali:
        - xml.etree.ElementTree
        - openpyxl
    - Struttura multipagina

    ---
    
    ## ✅ Versione

    Stato attuale: **In sviluppo controllato**
    
    """)

help_page()
