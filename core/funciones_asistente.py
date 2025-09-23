from core.constantes import CLINICO, SALUDO, CORTESIA, ADMINISTRATIVO, CONSULTA_AGENDAR, CONSULTA_MODALIDAD
from core.utils_contacto import es_consulta_contacto
from core.utils_seguridad import contiene_elementos_peligrosos, contiene_frase_de_peligro
from core.db.registro import registrar_auditoria_input_original
from core.db.consulta import es_saludo, es_cortesia, contiene_expresion_administrativa
from core.db.sintomas import obtener_sintomas_existentes
import openai
from collections import Counter
import re
import unicodedata
import string
import json
from datetime import datetime, timedelta

# ============================ DETECCIÓN DE EMOCIONES NEGATIVAS ============================
def detectar_emociones_negativas(mensaje: str):
    if not mensaje or not isinstance(mensaje, str):
        return []
    prompt = (
        "Analizá el siguiente mensaje desde una perspectiva clínica y detectá exclusivamente emociones negativas o estados afectivos vinculados a malestar psicológico.\n\n"
        "Devolvé una lista separada por comas, sin explicaciones ni texto adicional.\n\n"
        f"Mensaje: {mensaje}"
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
            temperature=0.0
        )
        emociones = response.choices[0].message.get("content", "").strip().lower()
        emociones = emociones.replace("emociones negativas detectadas:", "").strip()
        emociones = [e.strip() for e in emociones.split(",") if e.strip() and e != "ninguna"]
        return emociones
    except Exception as e:
        print(f"❌ Error al detectar emociones negativas: {e}")
        return []


# ============================ NORMALIZACIÓN ============================
def normalizar_texto(texto: str) -> str:
    if not isinstance(texto, str):
        return ""
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("utf-8")
    texto = texto.translate(str.maketrans("", "", string.punctuation))
    texto = re.sub(r"\s+", " ", texto)
    return texto


# ============================ CLASIFICADOR DE INPUT INICIAL ============================
sintomas_cacheados = set()

def clasificar_input_inicial(texto: str) -> str:
    if not texto or not isinstance(texto, str):
        return "OTRO"

    texto = normalizar_texto(texto)

    frases_terapia = [
        "necesito hacer terapia", "quiero empezar terapia", "necesito un tratamiento", "buscar ayuda psicologica",
        "necesito hablar con alguien", "quisiera hacer terapia", "podria iniciar terapia", "empezar psicoterapia",
        "hacer terapia de pareja", "hacer psicoterapia", "necesito ayuda", "quiero tratarme", "buscar un terapeuta"
    ]
    if any(frase in texto for frase in frases_terapia):
        return CLINICO

    global sintomas_cacheados
    if not sintomas_cacheados:
        try:
            sintomas_cacheados.update(obtener_sintomas_existentes())
        except Exception as e:
            print(f"[Error al cargar síntomas]: {e}")

    saludos = ["hola", "buenos dias", "buenas tardes", "buenas noches", "que tal", "como estas"]
    if texto in saludos:
        return CORTESIA
    if any(s in texto for s in saludos) and es_tema_clinico_o_emocional(texto):
        return CLINICO

    expresiones_cortesia = [
        "gracias", "muchas gracias", "muy amable", "ok gracias", "perfecto gracias", "mil gracias",
        "te agradezco", "todo bien", "no necesito mas", "me quedo claro", "nada mas"
    ]
    if texto in expresiones_cortesia:
        return CORTESIA

    consultas_modalidad = [
        "es presencial", "es online", "son online", "es virtual", "atiende por videollamada", "por zoom",
        "ubicacion", "donde atiende", "ciudad", "zona", "provincia", "donde queda", "direccion",
        "consultorio", "se hace presencial", "es a distancia", "atencion virtual", "se hace por videollamada"
    ]
    if any(frase in texto for frase in consultas_modalidad):
        return CONSULTA_MODALIDAD

    clinicos_directos = [
        "nada me entusiasma", "nada me importa", "nada tiene sentido", "no tengo ganas", "no me interesa nada",
        "me quiero morir", "pienso en morirme", "me siento vacio", "todo me supera", "siento un peso",
        "lloro sin razon", "me duele el alma", "estoy muy triste", "me siento solo", "no puedo mas",
        "no puedo dormir", "siento ansiedad", "me siento mal conmigo"
    ]
    if any(frase in texto for frase in clinicos_directos):
        return CLINICO

    if es_tema_clinico_o_emocional(texto):
        return CLINICO

    return "OTRO"


# ============================ CLASIFICADOR SIMPLE (SALUDO/DESPEDIDA) ============================
def clasificar_input_inicial_simple(mensaje: str) -> dict:
    mensaje = mensaje.lower().strip()
    palabras = mensaje.split()

    if any(p in mensaje for p in ["hola", "buenas", "buen dia"]) and len(palabras) <= 3:
        return {"tipo": "saludo_simple"}
    if any(p in mensaje for p in ["chau", "adios", "hasta luego"]):
        return {"tipo": "despedida"}
    if any(p in mensaje for p in ["gracias", "mil gracias"]):
        return {"tipo": "agradecimiento"}

    return {"tipo": "otro"}


# ============================ EVALUACIÓN CON OPENAI ============================
def evaluar_mensaje_openai(mensaje: str) -> dict:
    try:
        prompt = (
            "Clasificá el siguiente mensaje según los siguientes criterios:\n\n"
            "- intencion_general: ADMINISTRATIVO, CLINICO, CLINICO_CONTINUACION o DESCONOCIDO\n"
            "- temas_administrativos: una lista de temas administrativos si los hay (por ejemplo: honorarios, modalidad, contacto)\n"
            "- emociones_detectadas: una lista de emociones negativas detectadas si las hay\n\n"
            "Respondé exclusivamente en formato JSON con las tres claves mencionadas.\n"
            f"Mensaje: \"{mensaje}\"\n"
        )

        respuesta = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=200
        )

        contenido = respuesta.choices[0].message.get("content", "").strip()
        resultado = json.loads(contenido)

        return {
            "intencion_general": resultado.get("intencion_general", "").upper(),
            "temas_administrativos": resultado.get("temas_administrativos", []),
            "emociones_detectadas": resultado.get("emociones_detectadas", [])
        }
    except Exception as e:
        print(f"[Error en evaluar_mensaje_openai]: {e}")
        return {
            "intencion_general": "",
            "temas_administrativos": [],
            "emociones_detectadas": []
        }


# ============================ FILTRO DE REPETIDOS ============================
def eliminar_mensajes_repetidos(mensaje: str) -> str:
    if not isinstance(mensaje, str):
        return ""

    mensaje = mensaje.strip().lower()
    saludos_iniciales = ["hola", "buenas", "buen dia", "buenas tardes", "buenas noches"]
    if any(mensaje.startswith(s) and len(mensaje.split()) <= 4 for s in saludos_iniciales):
        return ""

    reemplazos = {
        "ok": "",
        "ok gracias": "",
        "gracias": "",
        "muchas gracias": "",
        "estas ahi?": ""
    }
    return reemplazos.get(mensaje, mensaje)


# ============================ FILTRO DE RUIDO ============================
def es_mensaje_vacio_o_irrelevante(mensaje: str) -> bool:
    if not mensaje or len(mensaje.strip()) < 2:
        return True
    return bool(re.fullmatch(r"[^\wáéíóúñ]+", mensaje.strip()))


# ============================ TEMA CLÍNICO O EMOCIONAL ============================
def es_tema_clinico_o_emocional(mensaje: str) -> bool:
    if not mensaje or not isinstance(mensaje, str):
        return False
    mensaje = mensaje.lower().strip()
    palabras = [
        "triste", "ansioso", "angustia", "ansiedad", "vacío", "dolor", "sufrimiento", "miedo",
        "enojo", "culpa", "vergüenza", "desesperanza", "soledad", "estrés", "abandono", "apatía",
        "insomnio", "despersonalización", "fobia", "ataques de pánico", "me quiero morir",
        "pienso en morirme", "todo me supera", "no puedo dormir"
    ]
    patrones = [
        r"no\s+(puedo|quiero|logro)\b.*",
        r"ya no\s+(disfruto|me interesa|me importa)",
        r"me siento\s+(perdido|vacío|cansado|agotado|confundido|sin sentido)",
        r"no le encuentro sentido\s+(a la vida|a nada|a esto)"
    ]
    return any(p in mensaje for p in palabras) or any(re.search(p, mensaje) for p in patrones)


# ============================ CONSULTAS A BD ============================

from core.db.conexion import ejecutar_consulta

def obtener_ultimo_historial_emocional(user_id):
    """
    Devuelve el último registro clínico del usuario y acumula
    todos los malestares/emociones previas en orden cronológico único.
    """

    # Último registro (para fecha y emociones actuales)
    ultimo = ejecutar_consulta("""
        SELECT *
        FROM historial_clinico_usuario
        WHERE user_id = %s
        ORDER BY fecha DESC
        LIMIT 1
    """, (user_id,))

    # Todos los registros (para acumular malestares previos)
    todos = ejecutar_consulta("""
        SELECT emociones
        FROM historial_clinico_usuario
        WHERE user_id = %s
        ORDER BY fecha ASC
    """, (user_id,))

    if not ultimo:
        return None

    # Unir todas las emociones registradas (únicas, sin duplicados)
    malestares_acumulados = []
    for reg in todos:
        if reg.get("emociones"):
            malestares_acumulados.extend(reg["emociones"])

    # Eliminar duplicados y mantener el orden de aparición
    malestares_acumulados = list(dict.fromkeys(malestares_acumulados))

    # Convertir resultado en un objeto/dict similar al que devolvía SQLAlchemy
    return {
        "fecha": ultimo[0]["fecha"],
        "emociones": ultimo[0]["emociones"],
        "malestares_acumulados": malestares_acumulados
    }


def verificar_memoria_persistente(user_id, mensaje_actual=None, dias_maximos=7):
    """
    Obtiene el último historial emocional del usuario si corresponde.
    Aplica filtros:
    - Ignora saludos o mensajes administrativos.
    - Ignora si han pasado más de `dias_maximos` días desde la última emoción negativa.
    """
    # Normalizar mensaje para análisis
    if mensaje_actual:
        msg = normalizar_texto(mensaje_actual)
        saludos_admin = [
            "hola", "buen dia", "buenos dias", "buenas tardes", "buenas noches",
            "gracias", "ok", "perfecto", "listo", "todo bien", "muchas gracias"
        ]
        if msg in saludos_admin:
            return None

    # Obtener último historial clínico
    ultimo = obtener_ultimo_historial_emocional(user_id)
    if not ultimo:
        return None

    # Calcular tiempo transcurrido
    fecha_ultima = ultimo["fecha"]
    ahora = datetime.now()
    diferencia = ahora - fecha_ultima

    if diferencia.days > dias_maximos:
        return None  # Demasiado tiempo → no usar memoria

    # Calcular años, meses y días aproximados
    dias = diferencia.days
    anios = dias // 365
    meses = (dias % 365) // 30
    dias_restantes = (dias % 365) % 30

    ultimo["tiempo_transcurrido"] = {
        "años": anios,
        "meses": meses,
        "dias": dias_restantes
    }

    return ultimo
