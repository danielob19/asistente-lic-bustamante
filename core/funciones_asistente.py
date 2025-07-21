# core/funciones_asistente.py

from core.constantes import CLINICO, SALUDO, CORTESIA, ADMINISTRATIVO, CONSULTA_AGENDAR, CONSULTA_MODALIDAD
from core.utils_contacto import es_consulta_contacto
from core.utils_seguridad import contiene_elementos_peligrosos, contiene_frase_de_peligro
from core.db.registro import registrar_auditoria_input_original
from core.db.consulta import es_saludo, es_cortesia, contiene_expresion_administrativa
from core.db.sintomas import obtener_sintomas_existentes
from core.db.config import conn
import openai
from collections import Counter
import re
import unicodedata
import string

# ============================ NORMALIZACIÓN ============================
def normalizar_texto(texto: str) -> str:
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("utf-8")
    texto = texto.translate(str.maketrans("", "", string.punctuation))
    return texto

# ============================ CLASIFICADOR ============================
sintomas_cacheados = set()

def clasificar_input_inicial(texto: str) -> str:
    if not texto or not isinstance(texto, str):
        return "OTRO"

    texto = normalizar_texto(texto)

    frases_necesidad_terapia = [
        "necesito hacer terapia", "quiero empezar terapia", "necesito un tratamiento", "buscar ayuda psicologica",
        "necesito hablar con alguien", "quisiera hacer terapia", "podria iniciar terapia", "empezar psicoterapia",
        "hacer terapia de pareja", "hacer psicoterapia", "necesito ayuda", "quiero tratarme", "buscar un terapeuta"
    ]
    if any(frase in texto for frase in frases_necesidad_terapia):
        return "CLINICO"

    global sintomas_cacheados
    if not sintomas_cacheados:
        try:
            sintomas_existentes = obtener_sintomas_existentes()
            sintomas_cacheados.update(sintomas_existentes)
        except Exception as e:
            print(f"❌ Error al cargar síntomas cacheados: {e}")

    saludos = ["hola", "buenos dias", "buenas tardes", "buenas noches", "que tal", "como estas", "como esta"]
    if texto in saludos:
        return "CORTESIA"
    if any(s in texto for s in saludos) and es_tema_clinico_o_emocional(texto):
        return "CLINICO"

    expresiones_cortesia = [
        "gracias", "muchas gracias", "muy amable", "ok gracias", "perfecto gracias", "mil gracias",
        "te agradezco", "todo bien", "no necesito mas", "me quedo claro", "nada mas"
    ]
    if texto in expresiones_cortesia:
        return "CORTESIA"

    consultas_modalidad = [
        "es presencial", "es online", "son online", "es virtual", "atiende por videollamada", "por zoom",
        "se hace por videollamada", "atencion virtual", "por llamada", "me tengo que presentar",
        "se hace presencial", "ubicacion", "donde atiende", "donde queda", "donde esta", "ciudad",
        "zona", "provincia", "en que parte estas", "donde es la consulta", "direccion",
        "en que lugar se atiende", "donde se realiza", "debo ir al consultorio", "se hace a distancia",
        "atencion remota", "consultorio", "atencion online"
    ]
    if any(frase in texto for frase in consultas_modalidad):
        return "CONSULTA_MODALIDAD"

    clinicos_ampliados = [
        "nada me entusiasma", "nada me importa", "nada tiene sentido", "no tengo ganas", "no me interesa nada",
        "no me dan ganas", "no siento nada", "me quiero morir", "pienso en morirme", "me siento vacio", "no le encuentro sentido",
        "todo me supera", "ya no disfruto", "siento un peso", "me cuesta levantarme", "lloro sin razon", "me duele el alma",
        "estoy muy triste", "me siento solo", "no puedo mas", "no puedo dormir", "siento ansiedad", "me siento mal conmigo"
    ]
    if any(frase in texto for frase in clinicos_ampliados):
        return "CLINICO"

    if es_tema_clinico_o_emocional(texto):
        return "CLINICO"

    return "OTRO"

# ============================ PURIFICACIÓN CLÍNICA ============================
def purificar_input_clinico(texto: str) -> str:
    try:
        if not isinstance(texto, str):
            return ""
        texto_original = texto.strip().lower()
        texto = texto_original

        # Muletillas
        muletillas = [
            r'\b(este|eh+|mmm+|aj[aá]|tipo|digamos|sea|viste|bueno|a ver|me explico|ehh*)\b',
            r'\b(s[ií]|claro)\b'
        ]
        for patron in muletillas:
            texto = re.sub(patron, '', texto, flags=re.IGNORECASE)

        texto = re.sub(r'\s{2,}', ' ', texto).strip()

        # Coincidencias clínicas exactas
        coincidencias = {
            "nada me entusiasma, ni siquiera lo que solía gustarme": "anhedonia",
            "nada me importa, ni lo que antes me importaba": "apatía profunda",
            "no quiero ver a nadie ni salir de casa": "aislamiento",
            "pienso en morirme todo el tiempo": "ideación suicida",
            "lloro sin razón y no sé por qué": "llanto sin motivo"
        }
        for frase, reemplazo in coincidencias.items():
            if frase in texto:
                texto = reemplazo

        texto = re.sub(r'[\s\.,!?]+$', '', texto)
        texto = texto.strip()
        if texto:
            texto = texto[0].upper() + texto[1:]
        return texto
    except Exception as e:
        print(f"[Error] purificar_input_clinico: {e}")
        return ""

# ============================ EVALUACIONES EMOCIONALES ============================
def es_tema_clinico_o_emocional(mensaje: str) -> bool:
    if not mensaje or not isinstance(mensaje, str):
        return False
    mensaje = mensaje.lower().strip()
    palabras_clave = [
        "triste", "ansioso", "angustia", "ansiedad", "vacío", "dolor", "sufrimiento",
        "miedo", "enojo", "culpa", "vergüenza", "desesperanza", "soledad", "estrés",
        "abandono", "apatía", "insomnio", "despersonalización", "fobia", "ataques de pánico",
        "me quiero morir", "pienso en morirme", "no me reconozco", "todo me supera", "no puedo dormir"
    ]
    if any(p in mensaje for p in palabras_clave):
        return True

    patrones = [
        r"no\s+(puedo|quiero|logro)\b.*",
        r"ya no\s+(disfruto|me interesa|me importa)",
        r"me siento\s+(perdido|vacío|cansado|agotado|confundido|sin sentido)",
        r"no le encuentro sentido\s+(a la vida|a nada|a esto)"
    ]
    return any(re.search(p, mensaje) for p in patrones)

# ============================ OPENAI ============================
def evaluar_mensaje_openai(mensaje: str) -> str | None:
    try:
        prompt = (
            "Un usuario envió el siguiente mensaje que no tiene una intención clara. "
            "Respondé de manera neutral, breve y con un tono empático, como si fueras un asistente virtual profesional. "
            "No asumas información no incluida en el mensaje. Si no entendés, pedí aclaración. Mensaje:\n\n"
            f"{mensaje}"
        )
        respuesta = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.3
        )
        return respuesta.choices[0].message.get("content", "").strip()
    except Exception as e:
        print(f"❌ Error en evaluar_mensaje_openai: {e}")
        return None

# ============================ DETECCIÓN EMOCIONAL OPENAI ============================
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

# ============================ ESTADO PREDOMINANTE ============================
def inferir_estado_emocional_predominante(emociones: list[str]) -> str | None:
    if not emociones:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT estado_emocional FROM palabras_clave WHERE LOWER(sintoma) = ANY(%s)", (emociones,)
            )
            resultados = cur.fetchall()
        estados = [fila[0].strip() for fila in resultados if fila[0]]
        if len(estados) < 2:
            return None
        conteo = Counter(estados)
        return conteo.most_common(1)[0][0]
    except Exception as e:
        print(f"Error al inferir estado emocional: {e}")
        return None

# ============================ CLASIFICADOR DE INPUT SIMPLE ============================
def clasificar_input_inicial_simple(mensaje: str) -> dict:
    """
    Clasifica mensajes iniciales simples (como saludos, agradecimientos o despedidas)
    sin carga emocional ni contenido clínico relevante.

    Devuelve un dict con tipo: saludo_simple, agradecimiento, despedida u otro.
    """
    saludos = ["hola", "buenas", "buen día", "buenas tardes", "buenas noches", "holis", "saludos"]
    despedidas = ["chau", "adiós", "hasta luego", "nos vemos", "me voy", "me retiro"]
    agradecimientos = ["gracias", "muchas gracias", "mil gracias", "te agradezco", "gracias por tu ayuda"]

    mensaje = mensaje.lower().strip()

    if any(palabra in mensaje for palabra in saludos):
        return {"tipo": "saludo_simple"}
    if any(palabra in mensaje for palabra in despedidas):
        return {"tipo": "despedida"}
    if any(palabra in mensaje for palabra in agradecimientos):
        return {"tipo": "agradecimiento"}

    return {"tipo": "otro"}

# ============================ FILTRO DE MENSAJES REPETIDOS ============================
def eliminar_mensajes_repetidos(mensaje: str) -> str:
    if not isinstance(mensaje, str):
        return ""

    mensaje = mensaje.strip().lower()

    saludos_iniciales = ["hola", "buenas", "buen día", "buenas tardes", "buenas noches"]
    if any(mensaje.startswith(saludo) and len(mensaje.split()) <= 4 for saludo in saludos_iniciales):
        return ""  # Purgamos frases cortas tipo "hola, cómo estás"

    reemplazos_exactos = {
        "ok": "",
        "ok gracias": "",
        "gracias": "",
        "muchas gracias": "",
        "estás ahí?": "",
    }

    return reemplazos_exactos.get(mensaje, mensaje)

