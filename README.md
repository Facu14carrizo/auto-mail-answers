# Auto-Responder de Emails

Una aplicación de escritorio para responder automáticamente a correos electrónicos entrantes.

## 🚀 Características

- **Interfaz gráfica moderna** con tema oscuro
- **Respuesta automática** a correos no leídos
- **Modo continuo** para monitorear nuevos correos
- **Historial** de emails respondidos
- **Configuración persistente** de credenciales
- **Soporte para servidores IMAP/SMTP** personalizados

## 📋 Requisitos

- Python 3.7 o superior
- Cuenta de email con acceso IMAP/SMTP

## 🔧 Instalación

1. **Clona el repositorio:**
   ```bash
   git clone <url-del-repositorio>
   cd auto-aswers-py
   ```

2. **Instala las dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configura tus credenciales:**
   - Edita `config.json` con tus datos reales

## ⚙️ Configuración

### Archivo config.json
```json
{
  "email": "tu-email@dominio.com",
  "password": "tu-contraseña",
  "subject": "Asunto de respuesta automática",
  "mensaje": "Contenido del mensaje automático"
}
```

### Servidores de Email
El programa está configurado para usar:
- **IMAP/SMTP:** 
- **Puerto SMTP:** 465 (SSL)

Para usar otros servidores, modifica las variables en `main.py`:
```python
IMAP_SERVER = 'tu-servidor-imap.com'
SMTP_SERVER = 'tu-servidor-smtp.com'
SMTP_PORT = 465
```

## 🎯 Uso

1. **Ejecuta la aplicación:**
   ```bash
   python main.py
   ```

2. **Completa los campos:**
   - Email y contraseña
   - Asunto del mensaje automático
   - Contenido del mensaje

3. **Elige el modo:**
   - **Iniciar:** Procesa correos una vez
   - **Modo Continuo:** Monitorea continuamente nuevos correos

## 📁 Estructura del Proyecto

```
auto-aswers-py/
├── main.py                 # Código principal
├── config.json            # Configuración principal
├── respondidos.txt        # Historial de emails 
├── requirements.txt       # Dependencias
└── README.md             # Este archivo
```

### Estructura del código
- **Interfaz gráfica:** Tkinter con tema oscuro
- **Comunicación email:** imapclient + smtplib
- **Persistencia:** JSON para configuración, TXT para historial
- **Threading:** Operaciones de email en hilos separados

## 📝 Notas

- El programa marca automáticamente los correos como leídos
- Solo responde a correos no leídos
- Evita respuestas duplicadas usando el historial
- Guarda la configuración automáticamente al cerrar

## 📄 Licencia

Este proyecto es de uso interno para empresas.