from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from core.funciones_asistente import es_mensaje_vacio_o_irrelevante
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

        # 🔍 Validación temprana de mensaje irrelevante
        if es_mensaje_vacio_o_irrelevante(mensaje_usuario):
            respuesta = (
                "No recibí un mensaje claro. Podés escribir una consulta o directamente contactar al Lic. Bustamante "
                "por WhatsApp: +54 911 3310-1186."
            )
            session = user_sessions.get(user_id, {
                "contador_interacciones": 1,
                "ultimas_respuestas": [],
                "emociones_detectadas": [],
                "emociones_totales_detectadas": 0,
                "emociones_sugerencia_realizada": False,
                "emociones_corte_aplicado": False
            })
            session["ultimas_respuestas"].append(respuesta)
            session["contador_interacciones"] += 1
            user_sessions[user_id] = session
            return JSONResponse(content={"respuesta": respuesta})
        
                

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

        # 🧩 CÓDIGO CORREGIDO — BLOQUE CRÍTICO
        # Eliminar repeticiones exactas
        mensaje_usuario = eliminar_mensajes_repetidos(mensaje_usuario)
        
        # Evaluar intención usando OpenAI
        resultado = evaluar_mensaje_openai(mensaje_usuario)
        
        # Validar que la respuesta de OpenAI sea un dict válido
        if not resultado or not isinstance(resultado, dict):
            respuesta = (
                "Ocurrió un error inesperado al intentar interpretar tu mensaje. "
                "Podés volver a intentarlo más tarde o contactar directamente al Lic. Bustamante por WhatsApp: +54 911 3310-1186."
            )
            session["ultimas_respuestas"].append(respuesta)
            user_sessions[user_id] = session
            return JSONResponse(content={"respuesta": respuesta})
        
        # Extraer datos de la respuesta
        intencion_general = resultado.get("intencion_general", "")
        temas_administrativos = resultado.get("temas_administrativos", [])
        emociones_detectadas = resultado.get("emociones_detectadas", [])
        
        # Registrar auditoría del input original
        registrar_auditoria_input_original(
            user_id=user_id,
            mensaje_original=mensaje_original,
            mensaje_purificado=mensaje_usuario,
            clasificacion=intencion_general
        )
        

        # 🔍 Punto crítico #5: Conflicto clínico-administrativo
        if intencion_general in ["CLINICO", "CLINICO_CONTINUACION"] and temas_administrativos:
            # Si hay temas administrativos claros, priorizamos el módulo administrativo
            respuesta = procesar_administrativo(
                mensaje_usuario=mensaje_usuario,
                mensaje_original=mensaje_original,
                user_id=user_id,
                session=session,
                temas_administrativos=temas_administrativos,
                contador=contador
            )
            user_sessions[user_id] = session
            return JSONResponse(content=respuesta)

        # Si no hubo prioridad administrativa, pasamos a flujo clínico si hay emociones o intención clínica
        elif intencion_general in ["CLINICO", "CLINICO_CONTINUACION"] or emociones_detectadas:
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
        

        # 🔍 Validación de intención administrativa con emociones clínicas
        elif intencion_general == "ADMINISTRATIVO" or temas_administrativos:
            if emociones_detectadas:
                # Derivamos al módulo clínico si hay emociones, aunque parezca administrativo
                input_data = {
                    "mensaje_usuario": mensaje_usuario,
                    "mensaje_original": mensaje_original,
                    "user_id": user_id,
                    "session": session,
                    "contador": contador
                }
                respuesta = procesar_clinico(input_data)
            else:
                # Flujo administrativo puro
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
    # Intentar preservar sesión si existe
    session = user_sessions.get(user_id, {"contador_interacciones": 1, "ultimas_respuestas": []})
    session["ultimas_respuestas"].append(respuesta)
    session["contador_interacciones"] += 1
    user_sessions[user_id] = session
    return JSONResponse(content={"respuesta": respuesta})


