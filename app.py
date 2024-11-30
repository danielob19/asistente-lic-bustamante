import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from fuzzywuzzy import fuzz
import openai

# Configuración de Flask
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "https://licbustamante.com.ar"}})

# Configuración de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Configuración de Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials_json = os.getenv("GOOGLE_CREDENTIALS_FILE")

if not credentials_json:
    raise ValueError("La variable de entorno GOOGLE_CREDENTIALS_FILE no está configurada.")

credentials = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(credentials_json), scope)
client = gspread.authorize(credentials)

# ID de la hoja de cálculo y nombre de la pestaña
spreadsheet_id = "1cAy1BEENCGHBKxTHBhNTtYjI9WokkW97"
worksheet_name = "tab2"  # Cambia si el nombre de la pestaña es diferente

# Función para obtener los encabezados de Google Sheets
def obtener_encabezados(worksheet):
    try:
        headers = worksheet.row_values(1)
        print(f"Encabezados detectados: {headers}")
        return headers
    except Exception as e:
        print(f"Error al obtener encabezados: {e}")
        return None

# Función para cotejar síntomas con fuzzy matching
def cotejar_sintomas(sintomas):
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(worksheet_name)
        headers = obtener_encabezados(worksheet)

        if headers != ['A', 'B', 'C', 'D']:
            raise ValueError("Los encabezados en la hoja no coinciden con 'A', 'B', 'C', 'D'.")

        datos = worksheet.get_all_records()
        coincidencias = []
        umbral_similitud = 80  # Umbral para considerar una coincidencia

        for fila in datos:
            for columna in ['A', 'B', 'C']:
                similitud = fuzz.token_sort_ratio(sintomas, fila[columna])
                if similitud >= umbral_similitud:
                    coincidencias.append(fila['D'])
                    break  # Sal del loop interno si ya hay una coincidencia

        return coincidencias
    except gspread.exceptions.APIError as api_error:
        print(f"API Error cotejando síntomas: {api_error}")
        return None
    except Exception as e:
        print(f"Error general cotejando síntomas: {e}")
        return None

# Función para registrar nuevos síntomas
def registrar_sintomas(sintomas):
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(worksheet_name)
        worksheet.append_row([sintomas, "", "", ""])
        print(f"Síntoma registrado: {sintomas}")
    except gspread.exceptions.APIError as api_error:
        print(f"API Error registrando síntomas: {api_error}")
    except Exception as e:
        print(f"Error general registrando síntomas: {e}")

# Ruta principal del asistente
@app.route("/asistente", methods=["POST"])
def asistente():
    try:
        data = request.get_json()
        mensaje_usuario = data.get("mensaje", "").strip().lower()

        if not mensaje_usuario:
            return jsonify({"respuesta": "Por favor, proporciona un mensaje válido."})

        coincidencias = cotejar_sintomas(mensaje_usuario)

        if coincidencias:
            diagnosticos = ", ".join(set(coincidencias))
            respuesta = (f"En base a los síntomas que mencionaste: {mensaje_usuario}, "
                         f"podría haber una coincidencia con los siguientes cuadros: {diagnosticos}. "
                         "Te sugiero contactar al Lic. Daniel O. Bustamante al WhatsApp +54 911 3310-1186 "
                         "para recibir una evaluación más detallada.")
        else:
            registrar_sintomas(mensaje_usuario)
            respuesta = ("No encontré coincidencias claras para los síntomas mencionados. "
                         "Tus síntomas serán registrados y puedes contactar al Lic. Daniel O. Bustamante "
                         "al WhatsApp +54 911 3310-1186 para orientación adicional.")

        return jsonify({"respuesta": respuesta})

    except Exception as e:
        print(f"Error procesando la solicitud: {e}")
        return jsonify({"respuesta": "Lo siento, ocurrió un error procesando tu solicitud."})

# Iniciar la aplicación
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
