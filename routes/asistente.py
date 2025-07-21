from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from core.contexto import user_sessions
from core.utils.modulo_clinico import procesar_clinico
from core.utils.modulo_administrativo import procesar_administrativo
from core.funciones_asistente import (
    normalizar_texto,
    evaluar_mensaje_openai,
    eliminar_mensajes_repetidos,
    clasificar_input_inicial_simple,
)
from core.db.registro import registrar_auditoria_input_original
from core.constantes import SALUDO_INICIAL

router = APIRouter()

@router.post("/asistente")
async def asistente(request: Request):
    try:
        data = await request.json()
        user_id = data.get("user_id", "frontend-user")
        mensaje_original = data.get("mensaje", "").strip()
        mensaje_usuario = normalizar_texto(mensaje_original)

        if user_id not in user_sessions:
            session = {
                "contador_interacciones": 1,
                "ultimas_respuestas": [],
                "emociones_detectadas": [],
                "emociones_totales_detectadas": 0,
                "emociones_sugerencia_realizada": False,
                "emociones_corte_aplicado": False
            }
        else:
            session = user_sessions[user_id]
            session["contador_interacciones"] += 1

        contador = session["contador_interacciones"]

        # Filtro de reinicio: si el mensaje es saludo sin carga emocional y estamos cerca del inicio
        if contador <= 2:
            resultado_saludo = clasificar_input_inicial_simple(mensaje_usuario)
            if resultado_saludo.get("tipo") == "saludo_simple":
                respuesta = SALUDO_INICIAL
                session["ultimas_respuestas"].append(respuesta)
                user_sessions[user_id] = session
                return JSONResponse(content={"respuesta": respuesta})

        # Eliminar repeticiones exactas
        mensaje_usuario = eliminar_mensajes_repetidos(mensaje_usuario)

        # Evaluar intención usando OpenAI
        resultado = evaluar_mensaje_openai(mensaje_usuario)
        intencion_general = resultado.get("intencion_general", "")
        temas_administrativos = resultado.get("temas_administrativos", [])
        emociones_detectadas = resultado.get("emociones_detectadas", [])

        registrar_auditoria_input_original(
            user_id=user_id,
            mensaje_original=mensaje_original,
            mensaje_purificado=mensaje_usuario,
            clasificacion=intencion_general
        )

        # Derivación a módulo clínico si hay emociones o se infiere intención clínica
        if intencion_general in ["CLINICO", "CLINICO_CONTINUACION"] or emociones_detectadas:
            input_data = {
                "mensaje_usuario": mensaje_usuario,
                "mensaje_original": mensaje_original,
                "user_id": user_id,
                "session": session,
                "contador": contador
            }
            respuesta = procesar_clinico(input_data)
            user_sessions[user_id] = session
            return JSONResponse(content=respuesta)

        # Si la intención es administrativa, pasamos al módulo administrativo
        elif intencion_general == "ADMINISTRATIVO" or temas_administrativos:
            input_data = {
                "mensaje_usuario": mensaje_usuario,
                "mensaje_original": mensaje_original,
                "user_id": user_id,
                "session": session,
                "temas_administrativos": temas_administrativos,
                "contador": contador
            }
            respuesta = procesar_administrativo(input_data)
            user_sessions[user_id] = session
            return JSONResponse(content=respuesta)

        # Si no se pudo determinar la intención
        else:
            respuesta = (
                "Ocurrió un error al procesar tu solicitud. Podés intentarlo nuevamente más tarde "
                "o escribirle al Lic. Bustamante por WhatsApp: +54 911 3310-1186."
            )
            session["ultimas_respuestas"].append(respuesta)
            user_sessions[user_id] = session
            return JSONResponse(content={"respuesta": respuesta})

    except Exception as e:
        print(f"❌ Error inesperado en el endpoint /asistente: {e}")
        respuesta = (
            "Ocurrió un error inesperado. Podés volver a intentarlo más tarde o contactar al Lic. Bustamante "
            "por WhatsApp: +54 911 3310-1186."
        )
        return JSONResponse(content={"respuesta": respuesta})


# CORS
from fastapi.middleware.cors import CORSMiddleware

origins = [
    "https://licbustamante.com.ar",
    "http://localhost",
    "http://localhost:3000",
    "http://127.0.0.1:3000"
]

router.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
