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


def clasificar_input_inicial(mensaje: str) -> str:
    mensaje = mensaje.lower().strip()

    if contiene_elementos_peligrosos(mensaje):
        return "INPUT_SOSPECHOSO"

    if contiene_frase_de_peligro(mensaje):
        return "FRASE_PELIGRO"

    if es_saludo(mensaje):
        return SALUDO

    if es_cortesia(mensaje):
        return CORTESIA

    if contiene_expresion_administrativa(mensaje):
        return ADMINISTRATIVO

    if es_consulta_contacto(mensaje):
        return CONSULTA_AGENDAR

    if "modalidad" in mensaje or "online" in mensaje or "videollamada" in mensaje or "presencial" in mensaje:
        return CONSULTA_MODALIDAD

    emociones_detectadas = detectar_emociones_negativas(mensaje)
    if emociones_detectadas:
        return CLINICO

    return "FUERA_DE_CONTEXTO"

def generar_resumen_interaccion_5(session, user_id, contador, interaccion):
    emociones = session.get("emociones_detectadas", [])
    if emociones:
        resumen = (
            f"Por lo que comentás, se observa un conjunto de emociones asociadas a malestar: {', '.join(emociones)}. "
            f"¿Considerás que podría tratarse de un estado depresivo, ansioso o algún otro?"
        )
        return resumen
    return "¿Podés contarme un poco más para comprender mejor lo que estás sintiendo?"

def generar_resumen_interaccion_9(session, user_id, contador, interaccion):
    emociones_previas = session.get("emociones_detectadas", [])
    mensajes_previos = session.get("mensajes", [])[-4:]  # interacciones 6, 7, 8 y 9

    emociones_nuevas = []
    for mensaje in mensajes_previos:
        nuevas = detectar_emociones_negativas(mensaje) or []
        for emocion in nuevas:
            emocion = emocion.lower().strip()
            if emocion not in emociones_previas and emocion not in emociones_nuevas:
                emociones_nuevas.append(emocion)

    if emociones_nuevas:
        emociones_totales = emociones_previas + emociones_nuevas
        resumen = (
            f"Por lo que comentas, pues al malestar anímico que describiste anteriormente, "
            f"advierto que se suman {', '.join(emociones_nuevas)}, "
            f"por lo que daría la impresión de que se trata de un estado emocional predominantemente "
            f"{inferir_estado_emocional_predominante(emociones_totales)}. "
            f"No obstante, para estar seguros se requiere de una evaluación psicológica profesional. "
            f"Te sugiero que lo consultes con el Lic. Bustamante."
        )
        return resumen

    return "¿Querés contarme un poco más para que podamos profundizar en lo que estás sintiendo?"

def generar_resumen_interaccion_10(session, user_id, contador, interaccion):
    return (
        "He encontrado interesante nuestra conversación, pero para profundizar más en el análisis de tu malestar, "
        "sería ideal que consultes con un profesional. Por ello, te sugiero que te contactes con el Lic. Bustamante. "
        "Lamentablemente, no puedo continuar con la conversación más allá de este punto."
    )

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

