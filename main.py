import sys
import os
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('auto_responder.log'),
        logging.StreamHandler()
    ]
)

# Asegurar que los archivos se creen/lean en la carpeta del script o del .exe
if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))
else:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from tkinter import messagebox, Listbox, Scrollbar
import threading
import imapclient
import email
import smtplib
import json
from email.mime.text import MIMEText
from email import utils
import ssl
import time

RESPONDIDOS_FILE = 'respondidos.txt'
CONFIG_FILE = 'config.json'

# Configuración de servidores de email
EMAIL_CONFIG = {
    'migusto': {
        'imap_server': 'mail.migusto.com.ar',
        'smtp_server': 'mail.migusto.com.ar',
        'smtp_port': 465
    },
    'gmail': {
        'imap_server': 'imap.gmail.com',
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 587
    },
    'outlook': {
        'imap_server': 'outlook.office365.com',
        'smtp_server': 'smtp-mail.outlook.com',
        'smtp_port': 587
    }
}

# ------------------- Configuración persistente -------------------
def guardar_configuracion(email, password, subject, mensaje, servidor='migusto'):
    config = {
        'email': email,
        'password': password,
        'subject': subject,
        'mensaje': mensaje,
        'servidor': servidor
    }
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        logging.info("Configuración guardada exitosamente")
    except Exception as e:
        logging.error(f"Error guardando configuración: {e}")
        messagebox.showerror("Error", f"No se pudo guardar la configuración: {e}")

def cargar_configuracion():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # Asegurar compatibilidad con versiones anteriores
                if 'servidor' not in config:
                    config['servidor'] = 'migusto'
                return config
        except Exception as e:
            logging.error(f"Error cargando configuración: {e}")
            messagebox.showerror("Error", f"No se pudo cargar la configuración: {e}")
    return {'email': '', 'password': '', 'subject': '', 'mensaje': '', 'servidor': 'migusto'}

# ------------------- Lógica de auto-respuesta -------------------
def cargar_respondidos():
    try:
        with open(RESPONDIDOS_FILE, 'r', encoding='utf-8') as f:
            return set(line.strip() for line in f.readlines() if line.strip())
    except FileNotFoundError:
        logging.info("Archivo de respondidos no encontrado, creando uno nuevo")
        return set()
    except Exception as e:
        logging.error(f"Error cargando respondidos: {e}")
        return set()

def guardar_respondido(email):
    try:
        with open(RESPONDIDOS_FILE, 'a', encoding='utf-8') as f:
            f.write(email + '\n')
        logging.info(f"Email {email} agregado al historial")
    except Exception as e:
        logging.error(f"Error guardando email respondido: {e}")

def actualizar_historial():
    try:
        responded = cargar_respondidos()
        historial_listbox.delete(0, tk.END)
        for mail in sorted(responded):
            historial_listbox.insert(tk.END, mail)
    except Exception as e:
        logging.error(f"Error actualizando historial: {e}")

def enviar_respuesta(smtp_conn, destinatario, email_account, subject, mensaje_auto):
    try:
        mensaje = MIMEText(mensaje_auto, 'plain', 'utf-8')
        mensaje['Subject'] = subject
        mensaje['From'] = email_account
        mensaje['To'] = destinatario
        mensaje['Date'] = utils.formatdate(localtime=True)
        
        smtp_conn.sendmail(email_account, destinatario, mensaje.as_string())
        logging.info(f"Respuesta enviada exitosamente a {destinatario}")
        return True
    except Exception as e:
        logging.error(f"Error enviando respuesta a {destinatario}: {e}")
        return False

def auto_responder(email_account, email_password, subject, mensaje_auto, servidor, status_callback):
    logging.info("Iniciando auto-responder")
    
    if servidor not in EMAIL_CONFIG:
        error_msg = f"Servidor '{servidor}' no configurado"
        logging.error(error_msg)
        status_callback(error_msg)
        return
    
    config = EMAIL_CONFIG[servidor]
    IMAP_SERVER = config['imap_server']
    SMTP_SERVER = config['smtp_server']
    SMTP_PORT = config['smtp_port']

    respondidos = cargar_respondidos()
    imap = None
    smtp = None
    
    try:
        # Configurar SSL context
        context = ssl.create_default_context()
        if servidor == 'migusto':
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

        # Conectar IMAP
        status_callback("Conectando al servidor IMAP...")
        imap = imapclient.IMAPClient(IMAP_SERVER, ssl=True, ssl_context=context)
        imap.login(email_account, email_password)
        imap.select_folder('INBOX')
        logging.info("Conexión IMAP establecida")

        # Conectar SMTP
        status_callback("Conectando al servidor SMTP...")
        if SMTP_PORT == 587:
            smtp = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            smtp.starttls(context=context)
        else:
            smtp = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context)
        
        smtp.login(email_account, email_password)
        logging.info("Conexión SMTP establecida")

        # Buscar mensajes no leídos
        mensajes = imap.search('UNSEEN')
        status_callback(f'Correos no leídos encontrados: {len(mensajes)}')
        logging.info(f"Encontrados {len(mensajes)} correos no leídos")

        if not mensajes:
            status_callback("No hay correos nuevos para responder")
            return

        # Procesar cada mensaje
        for i, msgid in enumerate(mensajes, 1):
            try:
                raw = imap.fetch(msgid, ['RFC822'])[msgid][b'RFC822']
                if isinstance(raw, bytes):
                    msg = email.message_from_bytes(raw)
                    sender = utils.parseaddr(msg.get('From') or '')[1]
                else:
                    logging.warning(f"El mensaje {msgid} no es de tipo bytes, se omite")
                    continue

                if not sender:
                    logging.warning(f"No se pudo obtener el remitente del mensaje {msgid}")
                    continue

                if sender.lower() in respondidos:
                    status_callback(f'Ya se respondió a {sender}, salteando.')
                    imap.add_flags(msgid, [imapclient.SEEN])
                    continue

                # Enviar respuesta
                status_callback(f'Enviando respuesta a {sender} ({i}/{len(mensajes)})')
                if enviar_respuesta(smtp, sender, email_account, subject, mensaje_auto):
                    guardar_respondido(sender.lower())
                    imap.add_flags(msgid, [imapclient.SEEN])
                    status_callback(f'✓ Respuesta enviada a {sender}')
                else:
                    status_callback(f'✗ Error enviando a {sender}')

            except Exception as e:
                logging.error(f"Error procesando mensaje {msgid}: {e}")
                status_callback(f'Error procesando mensaje: {e}')

        status_callback('Proceso finalizado exitosamente.')
        logging.info("Proceso de auto-respuesta completado")

    except imapclient.exceptions.LoginError:
        error_msg = "Error de autenticación. Verifica email y contraseña."
        logging.error(error_msg)
        status_callback(error_msg)
    except Exception as e:
        error_msg = f'Error general en la ejecución: {e}'
        logging.error(error_msg)
        status_callback(error_msg)
    finally:
        # Cerrar conexiones
        try:
            if smtp:
                smtp.quit()
                logging.info("Conexión SMTP cerrada")
        except:
            pass
        try:
            if imap:
                imap.logout()
                logging.info("Conexión IMAP cerrada")
        except:
            pass

# ------------------- Interfaz gráfica mejorada -------------------
animando = False
modo_continuo = False
hilo_continuo = None

def iniciar():
    global animando, modo_continuo
    logging.info("Botón Iniciar presionado")
    
    email_account = entry_email.get().strip()
    email_password = entry_password.get()
    subject = entry_subject.get().strip()
    mensaje_auto = entry_mensaje.get("1.0", tk.END).strip()
    servidor = servidor_var.get()
    
    if not email_account or not email_password or not subject or not mensaje_auto:
        messagebox.showerror("Error", "Completa todos los campos.")
        return
    
    guardar_configuracion(email_account, email_password, subject, mensaje_auto, servidor)
    btn_iniciar.config(state=tk.DISABLED)
    btn_continuo.config(state=tk.DISABLED)
    status_var.set("Procesando...")
    
    def set_estado_final(msg):
        status_var.set(msg)
        btn_iniciar.config(state=tk.NORMAL)
        btn_continuo.config(state=tk.NORMAL)
        actualizar_historial()
    
    def run():
        auto_responder(email_account, email_password, subject, mensaje_auto, servidor, set_estado_final)
    
    threading.Thread(target=run, daemon=True).start()

def toggle_continuo():
    global modo_continuo, animando, hilo_continuo
    if not modo_continuo:
        modo_continuo = True
        btn_continuo.config(text="Detener Modo Continuo")
        btn_iniciar.config(state=tk.DISABLED)
        
        email_account = entry_email.get().strip()
        email_password = entry_password.get()
        subject = entry_subject.get().strip()
        mensaje_auto = entry_mensaje.get("1.0", tk.END).strip()
        servidor = servidor_var.get()
        
        if not email_account or not email_password or not subject or not mensaje_auto:
            messagebox.showerror("Error", "Completa todos los campos.")
            modo_continuo = False
            btn_continuo.config(text="Modo Continuo (esperar correos)")
            btn_iniciar.config(state=tk.NORMAL)
            return
        
        guardar_configuracion(email_account, email_password, subject, mensaje_auto, servidor)
        status_var.set("Esperando correos nuevos...")
        
        def set_estado_final(msg):
            if not modo_continuo:
                status_var.set("Modo continuo detenido.")
            else:
                status_var.set(msg)
            actualizar_historial()
        
        def run_continuo():
            global modo_continuo
            while modo_continuo:
                try:
                    status_var.set("Buscando correos...")
                    auto_responder(email_account, email_password, subject, mensaje_auto, servidor, set_estado_final)
                    if modo_continuo:
                        status_var.set("Esperando próximos correos...")
                    for _ in range(60):
                        if not modo_continuo:
                            break
                        time.sleep(1)
                except Exception as e:
                    logging.error(f"Error en modo continuo: {e}")
                    if modo_continuo:
                        status_var.set(f"Error: {e}")
                        time.sleep(10)  # Esperar antes de reintentar
            
            status_var.set("Modo continuo detenido.")
            btn_iniciar.config(state=tk.NORMAL)
            btn_continuo.config(text="Modo Continuo (esperar correos)")
        
        hilo_continuo = threading.Thread(target=run_continuo, daemon=True)
        hilo_continuo.start()
    else:
        modo_continuo = False
        btn_continuo.config(text="Modo Continuo (esperar correos)")
        btn_iniciar.config(state=tk.NORMAL)
        status_var.set("Modo continuo detenido.")

def limpiar_historial():
    try:
        if messagebox.askyesno("Confirmar", "¿Estás seguro de que quieres limpiar el historial?"):
            with open(RESPONDIDOS_FILE, 'w', encoding='utf-8') as f:
                f.write('')
            actualizar_historial()
            logging.info("Historial limpiado")
            messagebox.showinfo("Éxito", "Historial limpiado correctamente")
    except Exception as e:
        logging.error(f"Error limpiando historial: {e}")
        messagebox.showerror("Error", f"No se pudo limpiar el historial: {e}")

def on_close():
    # Guardar configuración al cerrar
    try:
        guardar_configuracion(
            entry_email.get(), 
            entry_password.get(), 
            entry_subject.get(), 
            entry_mensaje.get("1.0", tk.END).strip(),
            servidor_var.get()
        )
        logging.info("Aplicación cerrada")
    except Exception as e:
        logging.error(f"Error al cerrar: {e}")
    root.destroy()

# Cargar configuración previa
config = cargar_configuracion()

root = tk.Tk()
root.title("Auto-Responder Email")
root.geometry("1000x600")
root.minsize(1000, 600)
root.configure(bg="#23272f")
root.resizable(False, False)

# Estilos modo oscuro
DARK_BG = "#23272f"
DARK_FRAME = "#2c313c"
DARK_ENTRY = "#23272f"
DARK_LABEL = "#e0e6f0"
DARK_BUTTON = "#4f8cff"
DARK_BUTTON_HOVER = "#357ae8"
DARK_STATUS = "#7ecfff"
FONT = ("Segoe UI", 13)
FONT_BOLD = ("Segoe UI", 14, "bold")

style = {
    "label": {"font": FONT, "bg": DARK_FRAME, "fg": DARK_LABEL},
    "entry": {"font": FONT, "bg": DARK_ENTRY, "fg": DARK_LABEL, "insertbackground": DARK_LABEL, "relief": "flat", "highlightthickness": 1, "highlightbackground": "#444"},
    "text": {"font": FONT, "bg": DARK_ENTRY, "fg": DARK_LABEL, "insertbackground": DARK_LABEL, "relief": "flat", "highlightthickness": 1, "highlightbackground": "#444"},
    "button": {"font": FONT_BOLD, "bg": DARK_BUTTON, "fg": "white", "activebackground": DARK_BUTTON_HOVER, "activeforeground": "white", "relief": "flat", "bd": 0, "cursor": "hand2", "padx": 24, "pady": 10}
}

# Layout principal con panel lateral
main_frame = tk.Frame(root, bg=DARK_BG)
main_frame.pack(fill="both", expand=True)

# Panel izquierdo: formulario
form_frame = tk.Frame(main_frame, bg=DARK_FRAME)
form_frame.pack(side="left", fill="both", expand=True, padx=(32, 8), pady=32)

# Panel derecho: historial
historial_frame = tk.Frame(main_frame, bg=DARK_BG)
historial_frame.pack(side="right", fill="y", padx=(8, 32), pady=32)

historial_label = tk.Label(historial_frame, text="Historial de mails respondidos", font=("Segoe UI", 12, "bold"), bg=DARK_BG, fg=DARK_LABEL)
historial_label.pack(pady=(0, 8))

historial_listbox = Listbox(historial_frame, width=32, height=22, bg=DARK_FRAME, fg=DARK_LABEL, font=("Segoe UI", 11), selectbackground="#4f8cff", selectforeground="white", borderwidth=0, highlightthickness=1, highlightbackground="#444")
historial_listbox.pack(side="left", fill="y")

scrollbar = Scrollbar(historial_frame, orient="vertical", command=historial_listbox.yview)
scrollbar.pack(side="right", fill="y")
historial_listbox.config(yscrollcommand=scrollbar.set)

# Formulario en panel izquierdo
row = 0
tk.Label(form_frame, text="Servidor:", **style["label"]).grid(row=row, column=0, sticky="e", pady=10, padx=8)
servidor_var = tk.StringVar(value=config.get('servidor', 'migusto'))
servidor_menu = tk.OptionMenu(form_frame, servidor_var, 'migusto', 'gmail', 'outlook')
servidor_menu.config(bg=DARK_ENTRY, fg=DARK_LABEL, font=FONT, relief="flat", highlightthickness=1, highlightbackground="#444")
servidor_menu.grid(row=row, column=1, pady=10, padx=8, sticky="ew")
row += 1

tk.Label(form_frame, text="Email:", **style["label"]).grid(row=row, column=0, sticky="e", pady=10, padx=8)
entry_email = tk.Entry(form_frame, width=38, **style["entry"])
entry_email.grid(row=row, column=1, pady=10, padx=8)
entry_email.insert(0, config.get('email', ''))
row += 1

tk.Label(form_frame, text="Contraseña:", **style["label"]).grid(row=row, column=0, sticky="e", pady=10, padx=8)
entry_password = tk.Entry(form_frame, show="*", width=38, **style["entry"])
entry_password.grid(row=row, column=1, pady=10, padx=8)
entry_password.insert(0, config.get('password', ''))
row += 1

tk.Label(form_frame, text="Asunto:", **style["label"]).grid(row=row, column=0, sticky="e", pady=10, padx=8)
entry_subject = tk.Entry(form_frame, width=38, **style["entry"])
entry_subject.grid(row=row, column=1, pady=10, padx=8)
entry_subject.insert(0, config.get('subject', ''))
row += 1

tk.Label(form_frame, text="Mensaje automático:", **style["label"]).grid(row=row, column=0, sticky="ne", pady=10, padx=8)
entry_mensaje = tk.Text(form_frame, height=6, width=36, **style["text"])
entry_mensaje.grid(row=row, column=1, pady=10, padx=8)
entry_mensaje.insert("1.0", config.get('mensaje', ''))
row += 1

status_var = tk.StringVar()
status_label = tk.Label(form_frame, textvariable=status_var, fg=DARK_STATUS, bg=DARK_FRAME, font=("Segoe UI", 12, "italic"))
status_label.grid(row=row, column=0, columnspan=2, pady=(0, 18), sticky="ew")
row += 1

btn_iniciar = tk.Button(form_frame, text="Iniciar Auto-Responder", command=iniciar, **style["button"])
btn_iniciar.grid(row=row, column=0, columnspan=2, pady=(0, 6), sticky="ew")
row += 1

btn_continuo = tk.Button(form_frame, text="Modo Continuo (esperar correos)", command=toggle_continuo, **style["button"])
btn_continuo.grid(row=row, column=0, columnspan=2, pady=(0, 6), sticky="ew")
row += 1

btn_limpiar = tk.Button(form_frame, text="Limpiar Historial", command=limpiar_historial, **style["button"])
btn_limpiar.grid(row=row, column=0, columnspan=2, pady=(0, 18), sticky="ew")

# Cerrar guardando
root.protocol("WM_DELETE_WINDOW", on_close)

# Cargar historial inicial
actualizar_historial()

root.mainloop()
