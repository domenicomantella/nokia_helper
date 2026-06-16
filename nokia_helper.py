import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk # ttk per il Combobox
import xml.etree.ElementTree as ET
import os
import openpyxl
from datetime import datetime

# --- Costanti e Funzioni di elaborazione ---

# Definisce le opzioni di elaborazione per il menu a tendina
class ProcessingMode:
    FULL_PROCESSING = "Elaborazione Completa (Modifica XML + Dati Excel)"
    NAMESPACE_STRIPPING = "Solo Pulizia Namespace e 'Roma4'"

def strip_namespace(element):
    """
    Rimuove il namespace da un elemento XML.
    """
    if '}' in element.tag:
        element.tag = element.tag.split('}', 1)[1]
    for subelement in element:
        strip_namespace(subelement)

def trasforma_bcxu(logicalBcxuAddress, ip_to_number_table):
    """
    Trasforma un indirizzo IP in un numero usando una tabella.
    """
    return ip_to_number_table.get(logicalBcxuAddress)

# --- Classe principale dell'applicazione GUI (Rifattorizzata) ---

class XMLProcessorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("XML & Excel Processor")
        self.geometry("850x700")
        
        # Variabile per il modo di elaborazione scelto
        self.mode_var = tk.StringVar(self)
        self.mode_var.set(ProcessingMode.FULL_PROCESSING) # Valore predefinito
        
        self.create_widgets()

    def create_widgets(self):
        # Frame principale
        main_frame = tk.Frame(self, padx=15, pady=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Configurazione del Frame
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(7, weight=1)

        row_idx = 0

        # --- Selettore Modo Elaborazione (NUOVO) ---
        tk.Label(main_frame, text="Modalità Elaborazione:").grid(row=row_idx, column=0, sticky="w", pady=5)
        self.mode_selector = ttk.Combobox(main_frame, textvariable=self.mode_var, width=60, state="readonly")
        self.mode_selector['values'] = (ProcessingMode.FULL_PROCESSING, ProcessingMode.NAMESPACE_STRIPPING)
        self.mode_selector.grid(row=row_idx, column=1, columnspan=2, sticky="we", padx=5)
        self.mode_selector.bind("<<ComboboxSelected>>", self.toggle_excel_inputs)
        row_idx += 1
        
        # --- Selettore file XML ---
        tk.Label(main_frame, text="File XML:").grid(row=row_idx, column=0, sticky="w", pady=5)
        self.xml_path_entry = tk.Entry(main_frame, width=50)
        self.xml_path_entry.grid(row=row_idx, column=1, sticky="we", padx=5)
        self.xml_button = tk.Button(main_frame, text="Scegli file...", command=self.select_xml_file)
        self.xml_button.grid(row=row_idx, column=2)
        row_idx += 1

        # --- Selettore file Excel ---
        tk.Label(main_frame, text="File Excel TNL:").grid(row=row_idx, column=0, sticky="w", pady=5)
        self.excel_path_entry = tk.Entry(main_frame, width=50)
        self.excel_path_entry.grid(row=row_idx, column=1, sticky="we", padx=5)
        self.excel_button = tk.Button(main_frame, text="Scegli file...", command=self.select_excel_file)
        self.excel_button.grid(row=row_idx, column=2)
        row_idx += 1

        # --- Input per la chiave di ricerca ---
        tk.Label(main_frame, text="Valore da cercare (Colonna D):").grid(row=row_idx, column=0, sticky="w", pady=5)
        self.search_key_entry = tk.Entry(main_frame, width=50)
        self.search_key_entry.grid(row=row_idx, column=1, sticky="we", padx=5)
        self.search_key_entry.insert(0, "BW07D") # Valore predefinito
        row_idx += 1

        # Bottone di elaborazione
        self.process_button = tk.Button(main_frame, text="Avvia Elaborazione", command=self.start_processing, height=2, font=('Arial', 10, 'bold'))
        self.process_button.grid(row=row_idx, column=0, columnspan=3, pady=25)
        row_idx += 1
        
        # Separatore visivo
        ttk.Separator(main_frame, orient='horizontal').grid(row=row_idx, columnspan=3, sticky="ew", pady=10)
        row_idx += 1
        
        # Area di log e output
        tk.Label(main_frame, text="Log di Elaborazione:").grid(row=row_idx, column=0, sticky="w", pady=5)
        row_idx += 1
        self.log_area = scrolledtext.ScrolledText(main_frame, width=90, height=25, wrap=tk.WORD, font=("Consolas", 9))
        self.log_area.grid(row=row_idx, column=0, columnspan=3, sticky="nsew")

    def toggle_excel_inputs(self, event=None):
        """Disabilita/abilita gli input correlati ad Excel a seconda della modalità."""
        is_full_mode = self.mode_var.get() == ProcessingMode.FULL_PROCESSING
        state = tk.NORMAL if is_full_mode else tk.DISABLED
        
        self.excel_path_entry.config(state=state)
        self.excel_button.config(state=state)
        self.search_key_entry.config(state=state)
        
        # Pulisci o inserisci il testo predefinito nel log per indicare la modalità
        if not is_full_mode:
            self.log_message("\nModalità 'Solo Pulizia': I campi Excel e Chiave di Ricerca verranno ignorati.", color="blue")
        else:
            self.log_message("\nModalità 'Elaborazione Completa': Tutti i campi sono attivi.", color="green")


    def select_xml_file(self):
        file_path = filedialog.askopenfilename(defaultextension=".xml", filetypes=[("File XML", "*.xml")])
        if file_path:
            self.xml_path_entry.delete(0, tk.END)
            self.xml_path_entry.insert(0, file_path)

    def select_excel_file(self):
        file_path = filedialog.askopenfilename(defaultextension=".xlsx", filetypes=[("File Excel", "*.xlsx")])
        if file_path:
            self.excel_path_entry.delete(0, tk.END)
            self.excel_path_entry.insert(0, file_path)

    def log_message(self, message, color="black"):
        """Aggiunge un messaggio all'area di log con un'opzione di colore."""
        self.log_area.tag_config(color, foreground=color)
        self.log_area.insert(tk.END, message + "\n", color)
        self.log_area.see(tk.END) # Scrolla in automatico

    def start_processing(self):
        self.log_area.delete("1.0", tk.END) # Pulisce il log
        xml_file_path = self.xml_path_entry.get()
        processing_mode = self.mode_var.get()

        if not xml_file_path:
            messagebox.showerror("Errore", "Per favore, seleziona il file XML.")
            return

        # Raccolta condizionale dei dati
        if processing_mode == ProcessingMode.FULL_PROCESSING:
            excel_file_path = self.excel_path_entry.get()
            search_key = self.search_key_entry.get().strip()
            if not excel_file_path or not search_key:
                messagebox.showerror("Errore", "In modalità 'Elaborazione Completa', devi compilare tutti i campi.")
                return
        else:
            excel_file_path = None
            search_key = None
            
        self.processa_xml_file(xml_file_path, excel_file_path, search_key, processing_mode)


    def processa_xml_file(self, file_input_xml, file_input_tnl, search_key_excel, mode):
        """
        Elabora i dati e modifica i file XML a seconda della modalità scelta.
        """
        self.log_message(f"Avvio elaborazione in modalità: {mode}", color="purple")
        self.log_message(f"File XML selezionato: {file_input_xml}")
        self.log_message("-" * 40)

        # Controlla se il file XML esiste
        if not os.path.exists(file_input_xml):
            self.log_message(f"Errore: Il file '{file_input_xml}' non è stato trovato.", color="red")
            messagebox.showerror("Errore", "File XML non trovato.")
            return
        
        try:
            # 1. Fase di pre-elaborazione (Applicata in ENTRAMBE le modalità)
            with open(file_input_xml, 'r', encoding='utf-8') as f:
                xml_string = f.read()

            string_modified = False
            if "Roma4" in xml_string:
                xml_string = xml_string.replace("Roma4", "PLMN")
                self.log_message("Sostituzione testuale effettuata: 'Roma4' -> 'PLMN'.", color="dark green")
                string_modified = True
                
            # Parsa la stringa XML
            root = ET.fromstring(xml_string)
            # Rimuove il namespace (Applicato in ENTRAMBE le modalità)
            strip_namespace(root)
            self.log_message("Pulizia del Namespace effettuata (rimossi i prefissi dei tag).", color="dark green")


            if mode == ProcessingMode.NAMESPACE_STRIPPING:
                # 2. Modalità SOLO PULIZIA
                if not string_modified:
                    self.log_message("\nSolo la pulizia del Namespace è stata eseguita. Nessuna altra modifica.", color="blue")
                    
                self.save_file(root, file_input_xml)
                return


            # 3. Modalità ELABORAZIONE COMPLETA (Richiede Excel)
            if not os.path.exists(file_input_tnl):
                self.log_message(f"Errore: Il file '{file_input_tnl}' non è stato trovato.", color="red")
                messagebox.showerror("Errore", "File Excel non trovato.")
                return
            
            self.log_message(f"File Excel selezionato: {file_input_tnl}")
            self.log_message(f"Valore da cercare in Excel: {search_key_excel}")

            # --- Mappa delle Colonne Excel (0-based) per chiarezza ---
            COL_MAP = {
                'search_key': 3,                     # Colonna D (e.g., BW07D)
                'btsCuPlaneIpAddress': 40,           # Colonna AO
                'btsMPlaneIpAddress': 43,            # Colonna AR
                'btsSubnetMasklengthMplane': 41,     # Colonna AP
                'btsSubnetMasklengthCUplane': 41,    # Colonna AP
                'logicalBcxuAddress': 77             # Colonna BU
            }
            key_idx = COL_MAP['search_key']
            
            # Carica il file Excel e il foglio di lavoro
            wb = openpyxl.load_workbook(file_input_tnl, data_only=True)
            tnl_sheet = wb['TNL_TI_SRAN']
            
            # Mappa i dati dell'Excel
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

            # Tabella per trasformare l'IP in numero
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
                "19.135.1.164": "12", "19.135.1.165": "13", "19.135.1.166": "14",
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
                
            # Controlla se il valore cercato è presente nel file Excel
            if search_key_excel not in tnl_data:
                self.log_message(f"Errore: Il valore '{search_key_excel}' non è stato trovato nella colonna D del file Excel.", color="red")
                messagebox.showerror("Errore", f"Valore '{search_key_excel}' non trovato in Excel.")
                return
                
            excel_values = tnl_data[search_key_excel]
            modifiche_effettuate = False
            all_mo = root.findall(".//managedObject[@class='BCF']")
                
            if not all_mo:
                self.log_message("Nessun tag 'managedObject' con class='BCF' trovato per la modifica dei parametri.", color="orange")
            
            for mo in all_mo:
                dist_name = mo.get('distName')
                self.log_message("\n" + "-" * 50)
                self.log_message(f"Elaborazione del tag con distName: {dist_name}")

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
                self.log_message("\nConfronto dei parametri:")
                self.print_comparison_table(before_params, after_params)
                    
            if not modifiche_effettuate and not string_modified:
                self.log_message("\nNessuna modifica ai parametri BCF o 'Roma4' effettuata. File di output non generato.", color="blue")
                messagebox.showinfo("Completato", "Nessuna modifica ai parametri BCF o 'Roma4' effettuata.")
                return

            self.save_file(root, file_input_xml)

        # --- Gestione Errori ---
        except openpyxl.utils.exceptions.InvalidFileException:
            self.log_message(f"Errore: Il file '{file_input_tnl}' non è un file Excel valido.", color="red")
            messagebox.showerror("Errore", "Il file Excel non è valido.")
        except KeyError as e:
            self.log_message(f"Errore: Il foglio di lavoro 'TNL_TI_SRAN' non è stato trovato o errore di colonna: {e}.", color="red")
            messagebox.showerror("Errore", f"Foglio di lavoro o colonna non trovata: {e}")
        except ET.ParseError as e:
            self.log_message(f"Errore durante il parsing del file XML: {e}", color="red")
            messagebox.showerror("Errore", f"Errore di parsing XML: {e}")
        except Exception as e:
            self.log_message(f"Si è verificato un errore inaspettato: {e}", color="red")
            messagebox.showerror("Errore", f"Errore inaspettato: {e}")

    def save_file(self, root, original_filename):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.dirname(original_filename)
        base_name = os.path.basename(original_filename).split('.')[0]
        
        # Aggiungo un'indicazione nel nome del file per la modalità solo pulizia
        mode_suffix = "_solo_pulizia" if self.mode_var.get() == ProcessingMode.NAMESPACE_STRIPPING else "_modificato"
        
        file_output = os.path.join(output_dir, f"{base_name}{mode_suffix}_{timestamp}.xml")

        try:
            # Assicura che l'ElementTree abbia il root corretto
            ET.indent(root, space="  ", level=0) 
            tree = ET.ElementTree(root)
            tree.write(file_output, encoding='utf-8', xml_declaration=True)
            self.log_message(f"\nElaborazione completata. Il file di output è stato salvato come:\n'{file_output}'", color="green")
            messagebox.showinfo("Completato", f"Il file di output è stato salvato come:\n{file_output}")
        except Exception as e:
            self.log_message(f"Errore durante il salvataggio del file: {e}", color="red")
            messagebox.showerror("Errore", f"Impossibile salvare il file: {e}")

    def print_comparison_table(self, before_params, after_params):
        """Stampa una tabella di confronto nell'area di log."""
        all_keys = sorted(list(set(before_params.keys()) | set(after_params.keys())))
        
        # Aumento la larghezza delle colonne per una migliore leggibilità
        self.log_message(f"{'Nome':<35} | {'Valore Prima':<25} | {'Valore Dopo':<25}")
        self.log_message("-" * 90)
        
        for key in all_keys:
            val_before = before_params.get(key, "Non presente")
            val_after = after_params.get(key, "Non presente")
            # Logga solo i parametri modificati o aggiunti se desiderato, qui loggo tutti
            self.log_message(f"{key:<35} | {str(val_before):<25} | {str(val_after):<25}")

if __name__ == "__main__":
    app = XMLProcessorApp()
    app.mainloop()