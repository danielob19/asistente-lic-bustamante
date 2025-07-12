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
import unicodedata
import string

def normalizar_texto(texto: str) -> str:
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("utf-8")
    texto = texto.translate(str.maketrans("", "", string.punctuation))
    return texto

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
            print(f"❌ Error al cargar síntomas cacheados en clasificar_input_inicial: {e}")

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

    frases_consulta_directa = [
        "atienden estos casos", "atiende estos casos", "atienden el caso", "atiende el caso",
        "tratan este tipo de temas", "trata este tipo de temas",
        "manejan este tipo de situaciones", "manejan estos casos",
        "hacen tratamiento de esto", "hace tratamiento de esto",
        "el licenciado puede atender esto", "pueden ayudar con esto",
        "esto lo trata el profesional", "esto lo trabajan en terapia",
        "esto se trabaja en terapia", "este tema lo abordan"
    ]
    if any(frase in texto for frase in frases_consulta_directa):
        return "ADMINISTRATIVO"

    temas_clinicos_comunes = [
        "terapia de pareja", "psicoterapia", "tratamiento psicologico", "consultas psicologicas",
        "abordaje emocional", "tratamiento emocional", "atencion psicologica", "tratamiento de pareja"
    ]
    verbos_clinicos = [
        "hace", "hacen", "dan", "atiende", "atienden", "realiza", "realizan", "ofrece", "ofrecen",
        "trabaja con", "trabajan con", "brinda", "brindan"
    ]
    for verbo in verbos_clinicos:
        for tema in temas_clinicos_comunes:
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

    if re.search(r"\b(atiende|atienden|trabaja con|trabajan con|hace|hacen|dan|ofrece|ofrecen)\s+(una\s+)?pareja\b", texto, re.IGNORECASE):
        registrar_auditoria_input_original(
            user_id="sistema",
            mensaje_original=texto,
            mensaje_purificado=texto,
            clasificacion="ADMINISTRATIVO (mención directa a pareja)"
        )
        return "ADMINISTRATIVO"

    verbos_consulta = [
        "trata", "tratan", "atiende", "atienden", "aborda", "abordan",
        "se ocupa de", "se ocupan de", "interviene en", "intervienen en",
        "trabaja con", "trabajan con", "hace tratamiento de", "hacen tratamiento de",
        "realiza tratamiento de", "realizan tratamiento de",
        "da tratamiento a", "dan tratamiento a", "maneja", "manejan",
        "ayuda con", "ayudan con", "acompaña en", "acompanan en",
        "resuelve", "resuelven", "puede tratar", "pueden tratar",
        "puede ayudar con", "pueden ayudar con", "atiende el tema de", "trata el tema de",
        "puede atender", "pueden atender", "esta capacitado para tratar", "estan capacitados para tratar"
    ]
    for verbo in verbos_consulta:
        for sintoma in sintomas_cacheados:
            if verbo in texto and sintoma in texto:
                return "ADMINISTRATIVO"

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

