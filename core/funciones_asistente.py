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

