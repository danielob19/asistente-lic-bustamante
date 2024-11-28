# Asistente Lic. Bustamante

¡Bienvenido al Asistente Lic. Bustamante! Este proyecto es un asistente profesional diseñado para interactuar con usuarios mediante el modelo de OpenAI, analizar síntomas y registrar datos en Google Sheets.

## Descripción del Proyecto

El asistente:
- Responde profesionalmente a las consultas del usuario.
- Limita las respuestas a un máximo de 70 palabras.
- Registra las interacciones en una hoja de cálculo de Google Sheets.
- Sugiere al usuario contactar al Lic. Daniel O. Bustamante si lo considera oportuno.

---

## Requisitos Previos

1. **Claves y Configuración Necesarias**:
   - Una clave API válida de OpenAI.
   - Un archivo de credenciales JSON para Google Sheets (por ejemplo, `asistente-441318-e6835310ec59.json`).
   - Asegúrate de tener acceso a Google Sheets y de compartir el archivo con el correo asociado al archivo JSON.

---

## Archivos Principales

### `app.py`
Contiene el código principal de la aplicación Flask:
- Endpoint `GET /`: Prueba básica.
- Endpoint `POST /asistente`: Genera respuestas y registra datos en Google Sheets.

### `requirements.txt`
Incluye las dependencias necesarias:
- Flask
- Flask-CORS
- OpenAI
- Gspread
- Oauth2client
- Gunicorn

---

## Despliegue

### Pasos para Desplegar en Render

1. **Configura la Aplicación en Render**:
   - Fuente: Conecta tu repositorio de GitHub.
   - Build Command: `pip install -r requirements.txt`.
   - Start Command: `gunicorn app:app`.

2. **Configura Variables de Entorno**:
   - Agrega `OPENAI_API_KEY` con tu clave de OpenAI.

3. **Despliega la Aplicación**:
   - Render iniciará el proceso de construcción y desplegará la aplicación.
   - La URL pública estará disponible al finalizar el despliegue.

---

## Pruebas

### Endpoint `GET /`
Prueba la ruta de inicio:
```bash
curl -X GET https://<tu-app>.onrender.com/
