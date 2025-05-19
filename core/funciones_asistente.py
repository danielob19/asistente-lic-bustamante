# core/funciones_asistente.py

from core.constantes import CLINICO, SALUDO, CORTESIA, ADMINISTRATIVO, CONSULTA_AGENDAR, CONSULTA_MODALIDAD
from core.utils_contacto import es_consulta_contacto
from core.utils_seguridad import contiene_elementos_peligrosos, contiene_frase_de_peligro
from core.db.registro import registrar_auditoria_input_original
from core.db.consulta import es_saludo, es_cortesia, contiene_expresion_administrativa
from core.db.sintomas import detectar_emociones_negativas
from collections import Counter
import psycopg2
from core.db.config import conn  # Asegurate de tener la conexión importada correctamente
import re


def clasificar_input_inicial(texto: str) -> str:
    if not texto or not isinstance(texto, str):
        return "OTRO"

    texto = texto.lower().strip()

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
        "abordaje emocional", "tratamiento emocional", "atención psicológica"
    ]
    for verbo in [
        "hace", "hacen", "dan", "atiende", "atienden", "realiza", "realizan", "ofrece", "ofrecen",
        "trabaja con", "trabajan con", "brinda", "brindan"
    ]:
        for tema in temas_clinicos_comunes:
            patron = rf"{verbo}\s*(el|la|los|las)?\s*{re.escape(tema)}"
            if re.search(patron, texto, re.IGNORECASE):
                registrar_auditoria_input_original(
                    user_id="sistema",
                    mensaje_original=texto,
                    mensaje_purificado=texto,
                    clasificacion="ADMINISTRATIVO (verbo + tema clínico común)"
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

