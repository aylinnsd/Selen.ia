import tkinter as tk
from tkinter import scrolledtext, ttk
import serial
import serial.tools.list_ports as list_ports
import threading
import time
import re
from datetime import datetime

# ================== COLORES / ESTILO ==================
BG_COLOR     = "#0B0B3B"
TEXT_COLOR   = "#E0B0FF"
HEADER_COLOR = "#9B59B6"
BUTTON_COLOR = "#FF6F61"
BUTTON_HOVER = "#FF9A76"
SCROLL_BG    = "#1C1C3C"
ALERT_COLOR  = "#FF3333"
SAFE_COLOR   = "#33FF77"
PILL_BG      = "#14143A"

def now_hms():
    from datetime import datetime
    return datetime.now().strftime("%H:%M:%S")

class SelenIAGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SELENIA — Exploración de Objetos")
        self.root.geometry("1100x820")
        self.root.configure(bg=BG_COLOR)

        # ===== Estado interno =====
        self.running         = False
        self.ser_husky       = None
        self.th_husky        = None

        self.last_danger_time = 0.0
        self.danger_timeout   = 0.8
        self.last_status      = None
        self.seen_ids         = set()

        # ===== HEADER =====
        header = tk.Frame(self.root, bg=HEADER_COLOR)
        header.pack(fill=tk.X, pady=(10, 16))
        tk.Label(
            header, text="SELENIA — Exploración de Objetos",
            font=("Arial Black", 24), fg=TEXT_COLOR, bg=HEADER_COLOR,
            padx=12, pady=14
        ).pack()

        # ===== Barra superior (puerto / modo) =====
        top = tk.Frame(self.root, bg=BG_COLOR)
        top.pack(fill=tk.X, padx=20)

        # Puertos disponibles
        ports = [p.device for p in list_ports.comports()] or ["(sin puertos)"]

        tk.Label(top, text="Puerto HuskyLens:", font=("Arial", 12), fg=TEXT_COLOR, bg=BG_COLOR)\
            .grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.cb_husky = ttk.Combobox(top, values=ports, state="readonly", width=18)
        self.cb_husky.grid(row=0, column=1, padx=4, pady=4)
        if ports and ports[0] != "(sin puertos)":
            self.cb_husky.current(0)

        tk.Label(top, text="Baudios:", font=("Arial", 12), fg=TEXT_COLOR, bg=BG_COLOR)\
            .grid(row=0, column=2, sticky="e", padx=4, pady=4)
        self.cb_baud_h = ttk.Combobox(top, values=["9600","57600","115200"], state="readonly", width=10)
        self.cb_baud_h.grid(row=0, column=3, padx=4, pady=4)
        self.cb_baud_h.set("115200")

        # Botón Conectar/Desconectar
        self.btn_conn = tk.Label(
            top, text="Conectar", font=("Arial", 13, "bold"),
            fg="white", bg=BUTTON_COLOR, padx=14, pady=8, cursor="hand2"
        )
        self.btn_conn.bind("<Button-1>", lambda e: self.toggle_connection())
        self.btn_conn.bind("<Enter>",  lambda e: self.btn_conn.config(bg=BUTTON_HOVER))
        self.btn_conn.bind("<Leave>",  lambda e: self.btn_conn.config(bg=BUTTON_COLOR))
        self.btn_conn.grid(row=0, column=4, padx=(16,6), pady=4)

        # Botón Limpiar pantalla
        self.btn_clear = tk.Label(
            top, text="Limpiar pantalla", font=("Arial", 11, "bold"),
            fg="white", bg=BUTTON_COLOR, padx=10, pady=6, cursor="hand2"
        )
        self.btn_clear.bind("<Button-1>", lambda e: self.clear_text())
        self.btn_clear.bind("<Enter>",  lambda e: self.btn_clear.config(bg=BUTTON_HOVER))
        self.btn_clear.bind("<Leave>",  lambda e: self.btn_clear.config(bg=BUTTON_COLOR))
        self.btn_clear.grid(row=0, column=5, padx=(8, 0), pady=4)

        # Modo
        tk.Label(top, text="Modo:", font=("Arial", 12), fg=TEXT_COLOR, bg=BG_COLOR)\
            .grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.mode_var = tk.StringVar(value="tracking")
        self.mode_combo = ttk.Combobox(
            top, textvariable=self.mode_var, state="readonly",
            values=["classification", "tracking"], font=("Arial", 12), width=16
        )
        self.mode_combo.grid(row=1, column=1, padx=4, pady=4)

        # Última línea (debug)
        tk.Label(top, text="Última línea:", font=("Arial", 12), fg=TEXT_COLOR, bg=BG_COLOR)\
            .grid(row=1, column=2, sticky="e", padx=4, pady=4)
        self.last_line_var = tk.StringVar(value="—")
        self.last_line_lbl = tk.Label(top, textvariable=self.last_line_var, font=("Consolas", 10),
                                      fg=TEXT_COLOR, bg=BG_COLOR, anchor="w")
        self.last_line_lbl.grid(row=1, column=3, columnspan=2, sticky="w", padx=4, pady=4)

        # ===== Píldora de estado =====
        pill = tk.Frame(self.root, bg=PILL_BG, highlightthickness=2, highlightbackground=HEADER_COLOR)
        pill.pack(fill=tk.X, padx=20, pady=(12, 6))
        self.status_label = tk.Label(
            pill, text="Estado: Desconectado",
            font=("Arial Black", 20), fg=SAFE_COLOR, bg=PILL_BG, pady=6
        )
        self.status_label.pack(pady=6)

        # ===== Área de texto =====
        center = tk.Frame(self.root, bg=BG_COLOR)
        center.pack(fill=tk.BOTH, expand=True, padx=20, pady=(8, 20))
        self.text_area = scrolledtext.ScrolledText(
            center, width=130, height=28, font=("Consolas", 12),
            bg=SCROLL_BG, fg=TEXT_COLOR, insertbackground=TEXT_COLOR,
            borderwidth=2, relief=tk.FLAT
        )
        self.text_area.pack(fill=tk.BOTH, expand=True)
        self.text_area.config(state=tk.DISABLED)

        # Atajo teclado: Ctrl+L limpia pantalla
        self.root.bind("<Control-l>", lambda e: self.clear_text())

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ================= Conexión =================
    def toggle_connection(self):
        if self.running:
            self.disconnect_serial()
        else:
            self.connect_serial()

    def connect_serial(self):
        port = self.cb_husky.get()
        if not port or port == "(sin puertos)":
            self.append_text(f"[{now_hms()}] No hay puerto seleccionado.\n")
            return
        baud = int(self.cb_baud_h.get())

        try:
            self.ser_husky = serial.Serial(port, baud, timeout=0.1)
            time.sleep(0.5)
            self.append_text(f"[{now_hms()}] Conectado HuskyLens en {port} @ {baud}\n")
            self.status_label.config(text="Estado: Conectado (HuskyLens)", fg=TEXT_COLOR)
            self.running = True
            self.th_husky = threading.Thread(target=self.loop_husky, daemon=True)
            self.th_husky.start()
            self.btn_conn.config(text="Desconectar")
        except serial.SerialException as e:
            self.append_text(f"[{now_hms()}] Error al conectar: {e}\n")

    def disconnect_serial(self):
        self.running = False
        try:
            if self.th_husky and self.th_husky.is_alive():
                self.th_husky.join(timeout=0.8)
        except:
            pass
        try:
            if self.ser_husky and self.ser_husky.is_open:
                self.ser_husky.close()
        except:
            pass
        self.status_label.config(text="Estado: Desconectado", fg=SAFE_COLOR)
        self.btn_conn.config(text="Conectar")
        self.append_text(f"[{now_hms()}] Desconectado.\n")

    # ================= Hilo lectura =================
    def loop_husky(self):
        while self.running and self.ser_husky:
            try:
                line = self.ser_husky.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    self.last_line_var.set(line[:120] + ("…" if len(line) > 120 else ""))
                    if self.mode_var.get() == "classification":
                        self.process_classification(line)
                    else:
                        self.process_tracking(line)
                else:
                    if self.mode_var.get() == "classification":
                        self.update_status_classification()
                time.sleep(0.02)
            except Exception as e:
                self.append_text(f"[{now_hms()}] Error Husky: {e}\n")
                break

    # ================= GUI utils =================
    def append_text(self, text):
        self.text_area.config(state=tk.NORMAL)
        self.text_area.insert(tk.END, text)
        self.text_area.see(tk.END)
        self.text_area.config(state=tk.DISABLED)

    def clear_text(self):
        self.text_area.config(state=tk.NORMAL)
        self.text_area.delete("1.0", tk.END)
        self.text_area.config(state=tk.DISABLED)

    # ================= Classification =================
    def process_classification(self, line: str):
        if re.search(r'\bID[:=\s]*1\b', line, flags=re.IGNORECASE):
            self.last_danger_time = time.time()

        status_text, status_color = self.get_classification_status()
        self.status_label.config(text=status_text, fg=status_color)

        if status_text != self.last_status:
            self.append_text(f"[{now_hms()}] {status_text}\n")
            self.last_status = status_text

    def get_classification_status(self):
        if time.time() - self.last_danger_time < self.danger_timeout:
            return ("PELIGRO", ALERT_COLOR)
        else:
            return ("Material seguro", SAFE_COLOR)

    def update_status_classification(self):
        status_text, status_color = self.get_classification_status()
        self.status_label.config(text=status_text, fg=status_color)
        if status_text != self.last_status:
            self.append_text(f"[{now_hms()}] {status_text}\n")
            self.last_status = status_text

    # ================= Tracking (X, Y, Z con px) =================
    def process_tracking(self, line: str):
        """
        Acepta Z:42, Z=42, Z 42, etc.
        Si no hay etiqueta, intenta usar el tercer número tras X e Y.
        """
        id_match = re.search(r'(?i)\bID\b\s*[:=]?\s*(-?\d+)', line)
        obj_id = int(id_match.group(1)) if id_match else None

        x_match = re.search(r'(?i)\bX\b\s*[:=]?\s*(-?\d+)', line)
        y_match = re.search(r'(?i)\bY\b\s*[:=]?\s*(-?\d+)', line)
        z_match = re.search(r'(?i)\bZ\b\s*[:=]?\s*(-?\d+)', line)

        if not (x_match and y_match):
            self.append_text(f"[{now_hms()}] {line}\n")
            return

        x = int(x_match.group(1))
        y = int(y_match.group(1))

        if z_match:
            z = int(z_match.group(1))
        else:
            after_y = line[y_match.end():]
            cand = re.search(r'(-?\d+)', after_y)
            z = int(cand.group(1)) if cand else None

        if obj_id is not None:
            self.seen_ids.add(obj_id)

        self.append_text(
            f"[{now_hms()}] ID:{(obj_id if obj_id is not None else '—')}  "
            f"X:{x}px  Y:{y}px  Z:{(str(z) + 'px') if z is not None else '—'}\n"
        )

        self.status_label.config(
            text=f"Tracking: {len(self.seen_ids)} ID(s) únicos detectados",
            fg=TEXT_COLOR
        )

    # ================= Cierre =================
    def on_close(self):
        self.running = False
        try:
            if self.th_husky and self.th_husky.is_alive():
                self.th_husky.join(timeout=0.8)
        except:
            pass
        try:
            if self.ser_husky and self.ser_husky.is_open:
                self.ser_husky.close()
        except:
            pass
        self.root.destroy()

# --------------- MAIN ---------------
if __name__ == "__main__":
    root = tk.Tk()
    app = SelenIAGUI(root)
    root.mainloop()
