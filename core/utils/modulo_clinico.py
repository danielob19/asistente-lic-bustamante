# core/utils/modulo_clinico.py

import re
import time
import unicodedata
from typing import Dict, Any

from core.utils.clinico_contexto import hay_contexto_clinico_anterior
from core.utils_contacto import obtener_mensaje_contacto
from core.funciones_asistente import detectar_emociones_negativas
from core.utils.generador_openai import generar_respuesta_con_openai
from core.constantes import CLINICO, CLINICO_CONTINUACION
from core.db.registro import (
    registrar_respuesta_openai,
    registrar_auditoria_respuesta,
    registrar_interaccion,
    registrar_emocion
)
from core.db.sintomas import (
    registrar_sintoma,
    obtener_sintomas_existentes
)
from core.contexto import user_sessions


def procesar_clinico(input_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Procesa mensajes clínicos: detecta emociones, realiza inferencias con OpenAI,
    registra resultados en PostgreSQL y devuelve una respuesta filtrada y profesional.

    :param input_data: Diccionario con claves: mensaje_original, mensaje_usuario, user_id, session, contador
    :return: Diccionario con respuesta final {"respuesta": ...}
    """

    mensaje_original = input_data["mensaje_original"]
    mensaje_usuario = input_data["mensaje_usuario"]
    user_id = input_data["user_id"]
    session = input_data["session"]
    contador = input_data["contador"]

    # Obtener lista de síntomas ya registrados en la base de datos
    sintomas_existentes = obtener_sintomas_existentes()

    # Detectar emociones desde el mensaje actual
    emociones_detectadas = detectar_emociones_negativas(mensaje_usuario) or []

    # Filtrar emociones detectadas para evitar registrar duplicados
    emociones_nuevas = []
    for emocion in emociones_detectadas:
        emocion = emocion.lower().strip()
        emocion = re.sub(r'[^\w\sáéíóúüñ]+$', '', emocion)

        # Verificar si la emoción ya fue detectada en la sesión
        if emocion not in session["emociones_detectadas"]:
            # Si la emoción no está en la base de datos, agregarla y registrarla
            if emocion not in sintomas_existentes:
                emociones_nuevas.append(emocion)
                registrar_sintoma(emocion)  # ✅ Registrar solo si no existe

    # ✅ Esta función será extendida para:
    # - Registrar en PostgreSQL
    # - Obtener cuadro clínico por OpenAI
    # - Generar respuesta clínica profesional
    # - Registrar auditoría y respuesta final

    return {
        "respuesta": (
            "El módulo clínico ha sido activado correctamente. Falta completar el procesamiento completo."
        )
    }
