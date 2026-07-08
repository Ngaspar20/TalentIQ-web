"""
TalentIQ Desktop Launcher
Double-click to start the server and open the app in your browser.
.pyw extension = runs without a console window.
"""
import subprocess
import threading
import time
import webbrowser
import sys
import os
import signal
import tkinter as tk
from tkinter import messagebox

APP_DIR  = os.path.dirname(os.path.abspath(__file__))
PYTHON   = r"C:\Python314\python.exe"
HOST     = "127.0.0.1"
PORT     = "8080"
URL      = f"http://{HOST}:{PORT}"

server_proc = None


def start_server():
    global server_proc
    env = os.environ.copy()
    server_proc = subprocess.Popen(
        [PYTHON, "manage.py", "runserver", f"{HOST}:{PORT}"],
        cwd=APP_DIR,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def open_browser():
    time.sleep(2)
    webbrowser.open(URL)


def on_close():
    if server_proc:
        server_proc.terminate()
    root.destroy()
    sys.exit(0)


# ── Start server in background ───────────────────────────
threading.Thread(target=start_server, daemon=True).start()
threading.Thread(target=open_browser, daemon=True).start()

# ── Minimal tray window ──────────────────────────────────
root = tk.Tk()
root.title("TalentIQ")
root.resizable(False, False)
root.protocol("WM_DELETE_WINDOW", on_close)

# Centre the window
w, h = 320, 180
sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
root.configure(bg="#1e3a8a")

tk.Label(root, text="TalentIQ", font=("Segoe UI", 22, "bold"),
         bg="#1e3a8a", fg="white").pack(pady=(24, 2))
tk.Label(root, text="Recrutamento Inteligente para Saúde",
         font=("Segoe UI", 9), bg="#1e3a8a", fg="#93c5fd").pack()

status = tk.Label(root, text="A iniciar servidor...",
                  font=("Segoe UI", 9), bg="#1e3a8a", fg="#6ee7b7")
status.pack(pady=8)


def update_status():
    status.config(text=f"A correr em {URL}")
    btn.config(state="normal")


root.after(2200, update_status)

btn = tk.Button(
    root, text="Abrir no Browser", state="disabled",
    font=("Segoe UI", 10, "bold"),
    bg="#3b82f6", fg="white", activebackground="#2563eb",
    relief="flat", padx=16, pady=6, cursor="hand2",
    command=lambda: webbrowser.open(URL),
)
btn.pack(pady=4)

tk.Button(
    root, text="Parar e Fechar", font=("Segoe UI", 9),
    bg="#1e3a8a", fg="#fca5a5", activebackground="#1e3a8a",
    relief="flat", cursor="hand2", command=on_close,
).pack()

root.mainloop()
