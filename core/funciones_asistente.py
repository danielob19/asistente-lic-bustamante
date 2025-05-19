# core/funciones_asistente.py

from core.constantes import CLINICO, SALUDO, CORTESIA, ADMINISTRATIVO, CONSULTA_AGENDAR, CONSULTA_MODALIDAD
from core.utils_contacto import es_consulta_contacto
from core.utils_seguridad import contiene_elementos_peligrosos, contiene_frase_de_peligro
from core.db.registro import registrar_auditoria_input_original
from core.db.consulta import es_saludo, es_cortesia, contiene_expresion_administrativa
from core.db.sintomas import detectar_emociones_negativas


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
