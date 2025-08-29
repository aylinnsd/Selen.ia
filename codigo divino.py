import tkinter as tk
from tkinter import scrolledtext
import serial
import threading
import time

# Cambia esto por el puerto correcto donde esté conectado tu Arduino
SERIAL_PORT = 'COM3'  # En Linux/Mac puede ser '/dev/ttyUSB0' o similar
BAUD_RATE = 115200

class HuskyLensGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Datos HuskyLens")
        
        self.text_area = scrolledtext.ScrolledText(root, width=60, height=20, font=("Consolas", 12))
        self.text_area.pack(padx=10, pady=10)
        self.text_area.config(state=tk.DISABLED)

        # Botón para limpiar la pantalla
        self.clear_button = tk.Button(root, text="Limpiar pantalla", command=self.clear_text)
        self.clear_button.pack(pady=(0,10))

        # Inicializamos el puerto serial
        try:
            self.ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        except serial.SerialException as e:
            self.append_text(f"Error abriendo puerto serial: {e}\n")
            self.ser = None

        # Usamos un hilo para leer datos y no congelar la GUI
        if self.ser:
            self.running = True
            self.thread = threading.Thread(target=self.read_serial)
            self.thread.daemon = True
            self.thread.start()

        # Cerrar bien al cerrar ventana
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def append_text(self, text):
        self.text_area.config(state=tk.NORMAL)
        self.text_area.insert(tk.END, text)
        self.text_area.see(tk.END)
        self.text_area.config(state=tk.DISABLED)

    def clear_text(self):
        self.text_area.config(state=tk.NORMAL)
        self.text_area.delete('1.0', tk.END)
        self.text_area.config(state=tk.DISABLED)

    def read_serial(self):
        while self.running:
            try:
                line = self.ser.readline().decode('utf-8').strip()
                if line:
                    self.append_text(line + '\n')
            except Exception as e:
                self.append_text(f"Error leyendo serial: {e}\n")
                break
            time.sleep(0.1)

    def on_close(self):
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = HuskyLensGUI(root)
    root.mainloop()
