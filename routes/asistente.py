from fastapi import APIRouter
from pydantic import BaseModel

from core.constantes import CLINICO, SALUDO, CORTESIA, ADMINISTRATIVO, CONSULTA_AGENDAR, CONSULTA_MODALIDAD
from core.utils_contacto import es_consulta_contacto, obtener_mensaje_contacto
from core.utils_seguridad import contiene_elementos_peligrosos
from core.faq_semantica import buscar_respuesta_semantica_con_score
from core.db.registro import registrar_interaccion, registrar_respuesta_openai
from core.db.sintomas import obtener_sintomas_existentes
from core.db.consulta import obtener_emociones_ya_registradas

from core.funciones_asistente import clasificar_input_inicial
from core.utils_generales import evitar_repeticion

from app import generar_respuesta_con_openai, detectar_emociones_negativas, user_sessions
from core.funciones_clinicas import hay_contexto_clinico_anterior

from core.resumen_clinico import (
    generar_resumen_clinico_y_estado,
    generar_resumen_interaccion_5,
    generar_resumen_interaccion_9,
    generar_resumen_interaccion_10,
)

router = APIRouter()


class UserInput(BaseModel):
    mensaje: str
    user_id: str

@router.post("/asistente")
async def asistente(input_data: UserInput):
    try:
        user_id = input_data.user_id
        mensaje = input_data.mensaje.strip()
        if not mensaje:
            return {"respuesta": "¿Podés repetir tu mensaje? No logré interpretarlo con claridad."}

        # Iniciar o actualizar sesión
        if user_id not in user_sessions:
            user_sessions[user_id] = {
                "mensajes": [],
                "emociones_detectadas": [],
                "contador": 1
            }
        session = user_sessions[user_id]
        session["mensajes"].append(mensaje)
        contador = session["contador"]

        # Clasificación del input
        tipo = clasificar_input_inicial(mensaje)

        if tipo == CORTESIA:
            return {"respuesta": "Entiendo, quedo atento por si más adelante querés continuar."}

        if contiene_elementos_peligrosos(mensaje):
            return {"respuesta": "Por seguridad, prefiero que lo consultes directamente con el Lic. Bustamante."}

        if tipo == SALUDO and contador == 1:
            return {"respuesta": "Hola, ¿qué tal? ¿Querés contarme un poco qué te está pasando últimamente?"}

        if tipo == CONSULTA_AGENDAR or tipo == CONSULTA_MODALIDAD or es_consulta_contacto(mensaje, user_id, mensaje):
            return {"respuesta": obtener_mensaje_contacto()}

        if tipo == ADMINISTRATIVO:
            return {"respuesta": "Sí, esos temas se atienden. Si querés coordinar una consulta, puedo darte el contacto."}

        if tipo == CLINICO:
            if contador == 5:
                respuesta = generar_resumen_interaccion_5(session, user_id, contador, contador)
            elif contador == 9:
                respuesta = generar_resumen_interaccion_9(session, user_id, contador, contador)
            elif contador >= 10:
                respuesta = generar_resumen_interaccion_10(session, user_id, contador, contador)
            else:
                emociones = detectar_emociones_negativas(mensaje)
                if emociones:
                    session["emociones_detectadas"].extend([
                        e for e in emociones if e not in session["emociones_detectadas"]
                    ])
                respuesta = generar_respuesta_con_openai(mensaje, contador, user_id, mensaje)
                respuesta = evitar_repeticion(respuesta, session.get("ultimas_respuestas", []))
        else:
            respuesta = "No estoy seguro de haber entendido el mensaje. ¿Querés contarme si hay algo que te esté afectando emocionalmente?"

        registrar_interaccion(user_id, mensaje)
        registrar_respuesta_openai(contador, respuesta)

        session["contador"] += 1
        return {"respuesta": respuesta}

    except Exception as e:
        return {"respuesta": "Lo siento, hubo un problema al procesar tu mensaje. Por favor, intentá nuevamente más tarde."}
