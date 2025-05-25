# core/funciones_asistente.py

from core.db.sintomas import obtener_sintomas_existentes
from core.constantes import CLINICO, SALUDO, CORTESIA, ADMINISTRATIVO, CONSULTA_AGENDAR, CONSULTA_MODALIDAD
from core.utils_contacto import es_consulta_contacto
from core.utils_seguridad import contiene_elementos_peligrosos, contiene_frase_de_peligro
from core.db.registro import registrar_auditoria_input_original
from core.db.consulta import es_saludo, es_cortesia, contiene_expresion_administrativa
from core.db.sintomas import detectar_emociones_negativas
import openai
from collections import Counter
import psycopg2
from core.db.config import conn  # Asegurate de tener la conexión importada correctamente
import re

sintomas_cacheados = set()

def clasificar_input_inicial(texto: str) -> str:
    if not texto or not isinstance(texto, str):
        return "OTRO"

    texto = texto.lower().strip()

    # 🧠 Frases clínicas indirectas que expresan necesidad de iniciar terapia
    frases_necesidad_terapia = [
        "necesito hacer terapia", "quiero empezar terapia", "necesito un tratamiento", "buscar ayuda psicológica",
        "necesito hablar con alguien", "quisiera hacer terapia", "podría iniciar terapia", "empezar psicoterapia",
        "hacer terapia de pareja", "hacer psicoterapia", "necesito ayuda", "quiero tratarme", "buscar un terapeuta"
    ]
    if any(frase in texto for frase in frases_necesidad_terapia):
        return "CLINICO"
    

    # 🧠 Cargar síntomas desde la BD si el set global está vacío
    global sintomas_cacheados
    if not sintomas_cacheados:
        try:
            sintomas_existentes = obtener_sintomas_existentes()
            sintomas_cacheados.update(sintomas_existentes)
        except Exception as e:
            print(f"❌ Error al cargar síntomas cacheados en clasificar_input_inicial: {e}")

    # 👋 Saludos y detección combinada con malestar clínico
    saludos = ["hola", "buenos días", "buenas tardes", "buenas noches", "qué tal", "como estás", "como esta"]
    if any(s in texto for s in saludos) and es_tema_clinico_o_emocional(texto):
        return "CLINICO"
    if texto in saludos:
        return "SALUDO"

    # 🙏 Frases de agradecimiento o cortesía
    expresiones_cortesia = [
        "gracias", "muchas gracias", "muy amable", "ok gracias", "perfecto, gracias", "mil gracias",
        "te agradezco", "todo bien", "no necesito más", "me quedó claro", "nada más"
    ]
    if texto in expresiones_cortesia:
        return "CORTESIA"

    # 🔎 Consultas sobre modalidad de atención (ubicación, virtualidad)
    consultas_modalidad = [
        "es presencial", "es online", "son online", "es virtual", "atiende por videollamada", "por zoom",
        "se hace por videollamada", "atención virtual", "por llamada", "me tengo que presentar",
        "se hace presencial", "ubicación", "dónde atiende", "donde atiende", "donde queda",
        "dónde está", "ciudad", "zona", "provincia", "en qué parte estás", "dónde es la consulta",
        "dirección", "en qué lugar se atiende", "dónde se realiza", "debo ir al consultorio",
        "se hace a distancia", "atención remota", "consultorio", "atención online"
    ]
    if any(frase in texto for frase in consultas_modalidad):
        return "CONSULTA_MODALIDAD"

    # 🧠 Malestar clínico directo (abstracciones y síntomas)
    clinicos_ampliados = [
        "nada me entusiasma", "nada me importa", "nada tiene sentido", "no tengo ganas", "no me interesa nada",
        "no me dan ganas", "no siento nada", "me quiero morir", "pienso en morirme", "me siento vacío", "no le encuentro sentido",
        "todo me supera", "ya no disfruto", "siento un peso", "me cuesta levantarme", "lloro sin razón", "me duele el alma",
        "estoy muy triste", "me siento solo", "no puedo más", "no puedo dormir", "siento ansiedad", "me siento mal conmigo"
    ]
    if any(frase in texto for frase in clinicos_ampliados):
        return "CLINICO"

    # 🗒️ Consultas clínicas explícitas disfrazadas de preguntas
    frases_consulta_directa = [
        "¿atienden estos casos?", "¿atiende estos casos?", "¿atienden el caso?", "¿atiende el caso?",
        "¿tratan este tipo de temas?", "¿trata este tipo de temas?",
        "¿manejan este tipo de situaciones?", "¿manejan estos casos?",
        "¿hacen tratamiento de esto?", "¿hace tratamiento de esto?",
        "¿el licenciado puede atender esto?", "¿pueden ayudar con esto?",
        "¿esto lo trata el profesional?", "¿esto lo trabajan en terapia?",
        "¿esto se trabaja en terapia?", "¿este tema lo abordan?"
    ]
    if any(frase in texto for frase in frases_consulta_directa):
        return "ADMINISTRATIVO"

    # 📋 Consultas indirectas: verbo + tema clínico (frecuentes en landing pages)
    temas_clinicos_comunes = [
    "terapia de pareja", "psicoterapia", "tratamiento psicológico", "consultas psicológicas",
    "abordaje emocional", "tratamiento emocional", "atención psicológica", "tratamiento de pareja"
    ]
    
    verbos_clinicos = [
        "hace", "hacen", "dan", "atiende", "atienden", "realiza", "realizan", "ofrece", "ofrecen",
        "trabaja con", "trabajan con", "brinda", "brindan"
    ]
    
    for verbo in verbos_clinicos:
        for tema in temas_clinicos_comunes:
            # 🔄 Ajuste específico para tratamiento(s) de pareja
            if tema == "tratamiento de pareja":
                patron = rf"{verbo}\s*(el|la|los|las)?\s*tratamientos?\s+de\s+pareja"
            else:
                patron = rf"{verbo}\s*(el|la|los|las)?\s*{re.escape(tema)}"
    
            if re.search(patron, texto, re.IGNORECASE):
                registrar_auditoria_input_original(
                    user_id="sistema",
                    mensaje_original=texto,
                    mensaje_purificado=texto,
                    clasificacion="ADMINISTRATIVO (verbo + tema clínico común)"
                )
                return "ADMINISTRATIVO"

    
    # 🆕 Captura directa de frases como “atienden pareja”
    if re.search(r"\b(atiende|atienden|trabaja con|trabajan con|hace|hacen|dan|ofrece|ofrecen)\s+(una\s+)?pareja\b", texto, re.IGNORECASE):
        registrar_auditoria_input_original(
            user_id="sistema",
            mensaje_original=texto,
            mensaje_purificado=texto,
            clasificacion="ADMINISTRATIVO (mención directa a pareja)"
        )
        return "ADMINISTRATIVO"


    # 🧠 Consultas indirectas sobre síntomas mediante verbos + síntomas cacheados
    verbos_consulta = [
        "trata", "tratan", "atiende", "atienden", "aborda", "abordan",
        "se ocupa de", "se ocupan de", "interviene en", "intervienen en",
        "trabaja con", "trabajan con", "hace tratamiento de", "hacen tratamiento de",
        "realiza tratamiento de", "realizan tratamiento de",
        "da tratamiento a", "dan tratamiento a", "maneja", "manejan",
        "ayuda con", "ayudan con", "acompaña en", "acompañan en",
        "resuelve", "resuelven", "puede tratar", "pueden tratar",
        "puede ayudar con", "pueden ayudar con", "atiende el tema de", "trata el tema de",
        "puede atender", "pueden atender", "está capacitado para tratar", "están capacitados para tratar"
    ]
    for verbo in verbos_consulta:
        for sintoma in sintomas_cacheados:
            if verbo in texto and sintoma in texto:
                return "ADMINISTRATIVO"

    # 🧠 Evaluación final: si el mensaje contiene síntomas o malestar
    if es_tema_clinico_o_emocional(texto):
        return "CLINICO"

    return "OTRO"


def inferir_estado_emocional_predominante(emociones: list[str]) -> str | None:
    """
    Dada una lista de emociones o síntomas, infiere el estado emocional predominante
    a partir de coincidencias en la tabla `palabras_clave`.

    Retorna el estado emocional más frecuente solo si hay 2 o más coincidencias.
    """
    if not emociones:
        return None

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT estado_emocional
                FROM palabras_clave
                WHERE LOWER(sintoma) = ANY(%s)
                """,
                (emociones,)
            )
            resultados = cur.fetchall()

        estados = [fila[0].strip() for fila in resultados if fila[0]]

        if len(estados) < 2:
            return None

        conteo = Counter(estados)
        estado_predominante, _ = conteo.most_common(1)[0]
        return estado_predominante

    except Exception as e:
        print(f"Error al inferir estado emocional: {e}")
        return None

def purificar_input_clinico(texto: str) -> str:

    try:
        if not isinstance(texto, str):
            return ""

        texto_original = texto.strip().lower()
        texto = texto_original

        # 🛡️ Detectar negación para no perder sentido clínico
        negadores_criticos = ["nada", "nadie", "ninguno", "ninguna", "no"]
        contiene_negador = any(re.search(rf'\b{n}\b', texto_original) for n in negadores_criticos)

        # 🗑️ Limpieza de muletillas
        muletillas = [
            r'\b(este|eh+|mmm+|ajá|tipo|digamos|sea|viste|bueno|a ver|me explico|ehh*)\b',
            r'\b(sí|si|claro)\b'
        ]
        for patron in muletillas:
            texto = re.sub(patron, '', texto, flags=re.IGNORECASE)

        texto = re.sub(r'\s{2,}', ' ', texto).strip()

        # ✅ Coincidencias clínicas completas
        coincidencias_exactas = {
            "nada me entusiasma, ni siquiera lo que solía gustarme": "anhedonia",
            "nada me importa, ni lo que antes me importaba": "apatía profunda",
            "no quiero ver a nadie ni salir de casa": "aislamiento",
            "pienso en morirme todo el tiempo": "ideación suicida",
            "lloro sin razón y no sé por qué": "llanto sin motivo"
        }
        for frase, valor in coincidencias_exactas.items():
            if frase in texto:
                texto = valor
                break

        # ✂️ Limpieza final y estandarización gramatical
        texto = re.sub(r'\b(\w{1}) (\w+)', r'\1 \2', texto)
        texto = re.sub(r'(\.{2,})', '.', texto)
        texto = re.sub(r'(,{2,})', ',', texto)
        texto = re.sub(r'[\s\.,!?]+$', '', texto)
        texto = texto.strip()

        # Capitalización
        if texto:
            texto = texto[0].upper() + texto[1:]

        return texto

    except Exception as e:
        print(f"[Error] purificar_input_clinico: {e}")
        return ""

def es_tema_clinico_o_emocional(mensaje: str) -> bool:
    """
    Evalúa si un mensaje contiene contenido emocional o clínico mediante palabras clave o patrones frecuentes.

    Args:
        mensaje (str): El texto del usuario.

    Returns:
        bool: True si se detecta un contenido clínico o emocional, False en caso contrario.
    """
    if not mensaje or not isinstance(mensaje, str):
        return False

    mensaje = mensaje.lower().strip()

    # Palabras clave clínicas frecuentes
    palabras_clave = [
        "triste", "ansioso", "angustia", "ansiedad", "vacío", "dolor", "sufrimiento",
        "miedo", "enojo", "culpa", "vergüenza", "desesperanza", "soledad", "estrés",
        "abandono", "apatía", "insomnio", "despersonalización", "fobia", "ataques de pánico",
        "indecisión súbita", "desborde", "desbordamiento", "nervioso", "desesperado",
        "indiferente", "ya no siento", "nada me entusiasma", "me quiero morir",
        "pienso en morirme", "no me reconozco", "todo me supera", "no puedo dormir"
    ]
    if any(palabra in mensaje for palabra in palabras_clave):
        return True

    # Patrones típicos de malestar emocional
    patrones_emocionales = [
        r"me cuesta\s+(vivir|seguir|levant[a-z]+|encontrarle sentido)",
        r"no\s+(puedo|quiero|logro)\b.*",
        r"ya no\s+(disfruto|me interesa|me importa)",
        r"siento que\s+(todo está mal|no valgo|todo es en vano)",
        r"me siento\s+(perdido|vacío|cansado|agotado|confundido|sin sentido)",
        r"no le encuentro sentido\s+(a la vida|a nada|a esto)",
        r"no tengo ganas", r"nada me importa", r"todo me cuesta", r"nada vale la pena",
        r"no sirvo para nada", r"siento que no sirvo", r"me cuesta\s+(vivir|seguir|todo)",
        r"no sé si esto es normal", r"me siento perdido", r"siento que no puedo más",
        r"me siento solo", r"todo me da igual", r"me tiene sin ganas",
        r"no duermo", r"no puedo dormir", r"no tengo energía",
    ]
    if any(re.search(p, mensaje) for p in patrones_emocionales):
        return True

    # ⚠️ Nuevos patrones de aislamiento o desinterés confundidos con cortesía
    patrones_aislamiento = [
        r"\bno\s+me\s+interesa\s+hablar\s+con\s+nadie\b",
        r"\bno\s+quiero\s+hablar\s+con\s+nadie\b",
        r"\bno\s+quiero\s+ver\s+a\s+nadie\b",
        r"\bno\s+tengo\s+ganas\s+de\s+hablar\b",
        r"\bprefiero\s+estar\s+solo[a]?\b",
        r"\bquiero\s+aislarme\b"
    ]
    if any(re.search(p, mensaje) for p in patrones_aislamiento):
        return True

    return False


def detectar_emociones_negativas(mensaje):
    if not mensaje or not isinstance(mensaje, str):
        print("⚠️ Input inválido para detectar emociones: no es string o es None")
        return []

    prompt = (
        "Analizá el siguiente mensaje desde una perspectiva clínica y detectá exclusivamente emociones negativas o estados afectivos vinculados a malestar psicológico. "
        "Tu tarea es identificar manifestaciones emocionales que indiquen sufrimiento, alteración afectiva o malestar clínico.\n\n"

        "Indicaciones:\n"
        "- Devolvé una lista separada por comas, sin explicaciones ni texto adicional.\n"
        "- Si hay ambigüedad, asigná la emoción negativa más cercana desde el punto de vista clínico.\n"
        "- Si hay múltiples emociones, incluilas todas separadas por comas.\n"
        "- Si no se detectan emociones negativas, devolvé únicamente: ninguna.\n\n"

        "Ejemplos clínicamente válidos:\n"
        "- Emociones simples: tristeza, ansiedad, culpa, vergüenza, impotencia, miedo, irritabilidad, angustia.\n"
        "- Estados complejos: vacío emocional, desgaste emocional, desesperanza, sensación de abandono, temor al rechazo, apatía profunda.\n\n"
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

        print("\n===== DEPURACIÓN - DETECCIÓN DE EMOCIONES =====")
        print(f"Mensaje analizado: {mensaje}")
        print(f"Respuesta de OpenAI: {emociones}")

        emociones = emociones.replace("emociones negativas detectadas:", "").strip()
        emociones = [emocion.strip() for emocion in emociones.split(",") if emocion.strip()]

        if "ninguna" in emociones:
            print("No se detectaron emociones negativas.\n")
            return []

        print(f"Emociones detectadas: {emociones}\n")
        return emociones

    except Exception as e:
        print(f"❌ Error al detectar emociones negativas: {e}")
        return []

