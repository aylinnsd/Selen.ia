import tkinter as tk
from tkinter import scrolledtext, ttk
import serial
import threading
import time
import re
from datetime import datetime

# ================== COLORES ==================
BG_COLOR     = "#0B0B3B"
TEXT_COLOR   = "#E0B0FF"
HEADER_COLOR = "#9B59B6"
BUTTON_COLOR = "#FF6F61"
BUTTON_HOVER = "#FF9A76"
SCROLL_BG    = "#1C1C3C"
ALERT_COLOR  = "#FF3333"
SAFE_COLOR   = "#33FF77"
PILL_BG      = "#14143A"

# ================== PUERTOS ==================
HUSKY_PORT   = "COM3"    # Arduino con HuskyLens (lectura)
HUSKY_BAUD   = 115200

GLASSES_PORT = "COM6"    # Arduino de los lentes/buzzer (salida alerta)
GLASSES_BAUD = 115200

def now_hms():
    return datetime.now().strftime("%H:%M:%S")

class SelenIAGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SELENIA — Exploración de Objetos")
        self.root.geometry("1100x820")
        self.root.configure(bg=BG_COLOR)

        # ===== Estado interno =====
        self.running          = False
        self.ser_husky        = None
        self.ser_glasses      = None
        self.th_husky         = None
        self.glasses_ok       = False
        self.last_alert_sent  = None     # None / "PELIGRO" / "SEGURO"

        self.last_danger_time = 0.0
        self.danger_timeout   = 0.8      # ventana para mantener "PELIGRO"
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

        # ===== Barra superior =====
        top = tk.Frame(self.root, bg=BG_COLOR)
        top.pack(fill=tk.X, padx=20)

        # Botón Conectar/Desconectar
        self.btn_conn = tk.Label(
            top, text="Conectar", font=("Arial", 13, "bold"),
            fg="white", bg=BUTTON_COLOR, padx=14, pady=8, cursor="hand2"
        )
        self.btn_conn.bind("<Button-1>", lambda e: self.toggle_connection())
        self.btn_conn.bind("<Enter>",  lambda e: self.btn_conn.config(bg=BUTTON_HOVER))
        self.btn_conn.bind("<Leave>",  lambda e: self.btn_conn.config(bg=BUTTON_COLOR))
        self.btn_conn.grid(row=0, column=0, padx=(16,6), pady=4)

        # Botón Limpiar pantalla
        self.btn_clear = tk.Label(
            top, text="Limpiar pantalla", font=("Arial", 11, "bold"),
            fg="white", bg=BUTTON_COLOR, padx=10, pady=6, cursor="hand2"
        )
        self.btn_clear.bind("<Button-1>", lambda e: self.clear_text())
        self.btn_clear.bind("<Enter>",  lambda e: self.btn_clear.config(bg=BUTTON_HOVER))
        self.btn_clear.bind("<Leave>",  lambda e: self.btn_clear.config(bg=BUTTON_COLOR))
        self.btn_clear.grid(row=0, column=1, padx=(8, 0), pady=4)

        # Selector de Modo
        tk.Label(top, text="Modo:", font=("Arial", 12), fg=TEXT_COLOR, bg=BG_COLOR)\
            .grid(row=1, column=0, sticky="e", padx=4, pady=4)
        self.mode_var = tk.StringVar(value="classification")  # <- por defecto classification (PELIGRO/SEGURO)
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
        self.last_line_lbl.grid(row=1, column=3, sticky="w", padx=4, pady=4)

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
            self.disconnect_serials()
        else:
            self.connect_serials()

    def connect_serials(self):
        # Conectar HuskyLens (lectura)
        try:
            self.ser_husky = serial.Serial(HUSKY_PORT, HUSKY_BAUD, timeout=0.1)
            time.sleep(0.5)
            self.append_text(f"[{now_hms()}] Conectado HuskyLens en {HUSKY_PORT}\n")
            self.status_label.config(text="Estado: Conectado (HuskyLens)", fg=TEXT_COLOR)
            self.running = True
            self.th_husky = threading.Thread(target=self.loop_husky, daemon=True)
            self.th_husky.start()
            self.btn_conn.config(text="Desconectar")
        except serial.SerialException as e:
            self.append_text(f"[{now_hms()}] Error Husky: {e}\n")
            return

        # Conectar Lentes (salida alerta)
        try:
            self.ser_glasses = serial.Serial(GLASSES_PORT, GLASSES_BAUD, timeout=0.2)
            time.sleep(0.2)
            self.glasses_ok = True
            self.append_text(f"[{now_hms()}] Lentes conectados en {GLASSES_PORT}\n")
        except serial.SerialException as e:
            self.glasses_ok = False
            self.append_text(f"[{now_hms()}] No se pudo abrir {GLASSES_PORT}: {e}\n")

    def disconnect_serials(self):
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
        try:
            if self.ser_glasses and self.ser_glasses.is_open:
                self.ser_glasses.close()
        except:
            pass
        self.glasses_ok = False
        self.last_alert_sent = None
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

    # ================= Comunicación con lentes =================
    def send_alert_to_glasses(self, status_text):
        """
        Envía '1\\n' si PELIGRO, '0\\n' si seguro.
        Evita re-enviar si no cambió el estado.
        (Solo se usa en modo classification.)
        """
        if not self.glasses_ok:
            return
        want = "PELIGRO" if status_text == "PELIGRO" else "SEGURO"
        if want == self.last_alert_sent:
            return
        try:
            if want == "PELIGRO":
                self.ser_glasses.write(b"1\n")
            else:
                self.ser_glasses.write(b"0\n")
            self.last_alert_sent = want
        except Exception as e:
            self.append_text(f"[{now_hms()}] Error a lentes: {e}\n")
            self.glasses_ok = False

    # ================= Classification =================
    def process_classification(self, line: str):
        # Si aparece ID 1 -> activar ventana de peligro
        if re.search(r'\bID[:=\s]*1\b', line, flags=re.IGNORECASE):
            self.last_danger_time = time.time()

        status_text, status_color = self.get_classification_status()
        self.status_label.config(text=status_text, fg=status_color)

        # Enviar al Arduino de los lentes
        self.send_alert_to_glasses(status_text)

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
        # Mantener sincronizados los lentes aunque no lleguen líneas nuevas
        self.send_alert_to_glasses(status_text)
        if status_text != self.last_status:
            self.append_text(f"[{now_hms()}] {status_text}\n")
            self.last_status = status_text

    # ================= Tracking (solo X, Y, Z en px) =================
    def process_tracking(self, line: str):
        """
        Acepta Z como:
          Z:42, Z=42, Z 42, z:42, z=42, z 42
        Si no hay etiqueta, intenta usar el 3er número tras X e Y.
        Imprime: [hh:mm:ss] ID:<id|—> X:<px> Y:<px> Z:<px|—>
        """
        # ID opcional
        id_match = re.search(r'(?i)\bID\b\s*[:=]?\s*(-?\d+(?:\.\d+)?)', line)
        obj_id = int(float(id_match.group(1))) if id_match else None

        # X e Y requeridos
        x_match = re.search(r'(?i)\bX\b\s*[:=]?\s*(-?\d+(?:\.\d+)?)', line)
        y_match = re.search(r'(?i)\bY\b\s*[:=]?\s*(-?\d+(?:\.\d+)?)', line)
        if not (x_match and y_match):
            self.append_text(f"[{now_hms()}] {line}\n")
            return

        # Z etiquetado (tolerante)
        z_match = re.search(r'(?i)\bZ\b\s*[:=]?\s*(-?\d+(?:\.\d+)?)', line)

        def to_num(s):
            v = float(s)
            return int(v) if v.is_integer() else v

        x = to_num(x_match.group(1))
        y = to_num(y_match.group(1))

        if z_match:
            z = to_num(z_match.group(1))
        else:
            # 1) primer número tras Y
            after_y = line[y_match.end():]
            cand = re.search(r'(-?\d+(?:\.\d+)?)', after_y)
            if cand:
                z = to_num(cand.group(1))
            else:
                # 2) patrón X..Y..(tercer número)
                xyz_cand = re.search(
                    r'(?i)\bX\b\s*[:=]?\s*(-?\d+(?:\.\d+)?)\D+\bY\b\s*[:=]?\s*(-?\d+(?:\.\d+)?)\D+(-?\d+(?:\.\d+)?)',
                    line
                )
                z = to_num(xyz_cand.group(3)) if xyz_cand else None

        if obj_id is not None:
            self.seen_ids.add(int(obj_id))

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
        self.disconnect_serials()
        self.root.destroy()

# --------------- MAIN ---------------
if __name__ == "__main__":
    root = tk.Tk()
    app = SelenIAGUI(root)
    root.mainloop()
