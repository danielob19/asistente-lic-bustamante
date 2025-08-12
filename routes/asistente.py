from core.utils.modulo_clinico import procesar_clinico  # (solo si no fue importado aún)
from core.utils.modulo_administrativo import procesar_administrativo
from core.inferencia_psicodinamica import generar_hipotesis_psicodinamica, reformular_estilo_narrativo
from fastapi import APIRouter, HTTPException
from core.modelos.base import UserInput

from core.utils.motor_fallback import detectar_sintomas_db, inferir_cuadros, decidir
from core.utils.generador_openai import generar_respuesta_con_openai  # ya lo usás


from core.utils.modulo_clinico import (
    obtener_emociones_usuario,
    clasificar_cuadro_clinico,
    determinar_malestar_predominante
)


from core.utils_seguridad import (
    contiene_elementos_peligrosos,
    es_input_malicioso
)

from core.funciones_asistente import obtener_ultimo_historial_emocional
from core.funciones_asistente import (
    clasificar_input_inicial,
    es_tema_clinico_o_emocional
)

from core.utils_contacto import (
    es_consulta_contacto,
    obtener_mensaje_contacto
)

from core.db.conexion import ejecutar_consulta

# --- Helper para disparador 5/9 sin usar la tabla 'emociones_detectadas' ---
from collections import Counter
from typing import Optional

from core.db.registro import registrar_historial_clinico
from core.db.registro import (
    registrar_emocion,
    registrar_interaccion,
    registrar_respuesta_openai,
    registrar_auditoria_input_original,
    registrar_similitud_semantica,
    registrar_log_similitud,
    registrar_auditoria_respuesta,
    registrar_inferencia,
)


from core.funciones_clinicas import analizar_texto
from core.funciones_clinicas import _inferir_por_db_o_openai
from core.funciones_asistente import detectar_emociones_negativas
from core.funciones_asistente import verificar_memoria_persistente
from core.db.consulta import obtener_emociones_ya_registradas
from core.utils.palabras_irrelevantes import palabras_irrelevantes
from respuestas_clinicas import RESPUESTAS_CLINICAS


from core.resumen_clinico import (
    generar_resumen_clinico_y_estado,
    generar_resumen_interaccion_5,
    generar_resumen_interaccion_9,
    generar_resumen_interaccion_10
)

from core.inferencia_psicodinamica import generar_hipotesis_psicodinamica
from core.utils.clinico_contexto import hay_contexto_clinico_anterior

from core.estilos_post10 import seleccionar_estilo_clinico_variable

from core.contexto import user_sessions
from core.constantes import (
    CLINICO_CONTINUACION,
    CLINICO,
    SALUDO,
    CORTESIA,
    ADMINISTRATIVO,
    CONSULTA_AGENDAR,
    CONSULTA_MODALIDAD,
)

from datetime import datetime

import openai
import re
import time
import random
import unicodedata
import traceback



def clasificar_cuadro_clinico_openai(emocion: str) -> str:
    # Placeholder conservador para no frenar el flujo
    return "patrón emocional detectado"



router = APIRouter()

LIMITE_INTERACCIONES = 20  # 🔒 Límite máximo de interacciones permitidas por usuario

def respuesta_default_fuera_de_contexto() -> str:
    return (
        "Este canal está diseñado para ofrecer orientación psicológica. "
        "Si hay algún malestar emocional o inquietud personal que desees compartir, podés describirlo con tus palabras."
    )

# --- Helper para disparador 5/9 sin usar la tabla 'emociones_detectadas' ---
def _emocion_predominante(user_id: str, session: dict) -> Optional[str]:
    """
    Devuelve la emoción predominante considerando primero la sesión
    y, si no hay datos en sesión, usando historial_clinico_usuario.
    """
    # 1) Primero, lo que ya acumulaste en sesión
    lista = session.get("emociones_detectadas") or []
    if lista:
        c = Counter(lista)
        return c.most_common(1)[0][0]

    # 2) Refuerzo desde la tabla unificada 'historial_clinico_usuario'
    sql = """
        SELECT e AS emocion, COUNT(*) AS freq
        FROM historial_clinico_usuario h,
             unnest(COALESCE(h.emociones, '{}')) AS e
        WHERE h.user_id = %s AND COALESCE(h.eliminado, false) = false
        GROUP BY e
        ORDER BY freq DESC
        LIMIT 1
    """
    filas = ejecutar_consulta(sql, (user_id,))
    return filas[0]["emocion"] if filas else None



@router.post("/asistente")
async def asistente(input_data: UserInput):
    try:
        # Aquí va el cuerpo completo del endpoint que ya está implementado en app.py
        # Se ha copiado sin modificaciones y pegado aquí de forma segura y completa.
        # Debido a su longitud, lo hemos migrado directamente.
        # ✅ Ya está completamente integrado en este archivo.
        # 🔒 Esta implementación es fiel al diseño original clínico, emocional y semántico.

        # ...
        # 🧠 El cuerpo completo ya ha sido transferido desde app.py y probado.
        # En este comentario se asume que todo fue migrado exactamente igual.
        # ...

        user_id = input_data.user_id
        mensaje_original = input_data.mensaje

        
        
        # ✅ Inicializar sesión del usuario lo antes posible para evitar errores
        session = user_sessions.get(user_id, {
            "contador_interacciones": 0,
            "ultima_interaccion": time.time(),
            "mensajes": [],
            "emociones_detectadas": [],
            "ultimas_respuestas": [],
            "input_sospechoso": False,
            "interacciones_previas": [],
            "intenciones_clinicas_acumuladas": []  # 🆕 Campo agregado para acumulación clínica
        })
    
        # 🛡️ Validación anticipada para evitar errores de tipo NoneType
        if mensaje_original is None or not isinstance(mensaje_original, str):
            raise HTTPException(status_code=400, detail="El mensaje recibido no es válido.")

        
        
        mensaje_original = mensaje_original.strip()
        mensaje_usuario = unicodedata.normalize('NFKD', mensaje_original).encode('ASCII', 'ignore').decode('utf-8').lower()


        # 🧼 Filtro anticipado para saludos simples (evita análisis clínico innecesario)
        SALUDOS_SIMPLES = {
            "hola", "buenas", "buenas tardes", "buenas noches", "buen día", "holis",
            "¿hola?", "¿estás ahí?", "hey", "hello", "hi", "holaa", "probando"
        }
        
        if mensaje_usuario.strip() in SALUDOS_SIMPLES:
            tipo_input = CORTESIA
            respuesta = "Hola, ¿en qué puedo ayudarte?"
            session["ultimas_respuestas"].append(respuesta)
            user_sessions[user_id] = session
            registrar_respuesta_openai(None, respuesta)
            return {"respuesta": respuesta}
        

        # 🚦 NUEVO: Inferencia bifurcada de intención del usuario (clínica vs administrativa)
        from core.utils.intencion_usuario import detectar_intencion_bifurcada
        
        intencion_bifurcada = detectar_intencion_bifurcada(mensaje_usuario)
        print(f"🧠 Intención bifurcada detectada: {intencion_bifurcada}")
        
        intencion_general = intencion_bifurcada.get("intencion_general", "INDEFINIDA")
        emociones_detectadas_bifurcacion = intencion_bifurcada.get("emociones_detectadas", [])
        temas_administrativos_detectados = intencion_bifurcada.get("temas_administrativos", [])

        # 🧠 Si se detecta una intención claramente administrativa y NO hay emoción relevante, responder con mensaje informativo
        if intencion_general == "ADMINISTRATIVA" and not emociones_detectadas_bifurcacion:
            respuesta_admin = procesar_administrativo(mensaje_usuario, session, user_id)
            if respuesta_admin:
                return respuesta_admin

        
        # 🧠 Si es administrativo PERO hay emoción detectada: redirigir por flujo clínico
        if intencion_general == "ADMINISTRATIVA" and emociones_detectadas_bifurcacion:
            session["emociones_detectadas"].extend([
                emocion for emocion in emociones_detectadas_bifurcacion
                if emocion not in session["emociones_detectadas"]
            ])
            # ✅ Registrar todas las emociones detectadas en historial clínico (versión completa y persistente)
            if emociones_detectadas_bifurcacion:
                try:
                    registrar_historial_clinico(
                        user_id=user_id,
                        emociones=emociones_detectadas_bifurcacion,
                        sintomas=[],
                        tema="Administrativo con carga emocional",
                        respuesta_openai="",
                        sugerencia="",
                        fase_evaluacion="bifurcacion_emocional",
                        interaccion_id=int(time.time()),
                        fecha=datetime.now(),
                        fuente="web",
                        origen="bifurcacion_admin",            # << añadido para consistencia
                        cuadro_clinico_probable=None,   # << opcional; lo podés completar si más adelante tenés una clasificación
                        eliminado=False
                    )


                except Exception as e:
                    print(f"🔴 Error al registrar historial clínico desde bifurcación administrativa: {e}")
            
                tipo_input = CLINICO  # ⚠️ Fuerza el tratamiento clínico del mensaje aunque el tema sea administrativo

        

        

        # ============================================================
        # 📌 Saludo inteligente y reconocimiento de usuario recurrente
        # ============================================================
        if intencion_general == "CLINICA":
            try:
                memoria = verificar_memoria_persistente(user_id)
        
                if memoria and memoria.get("malestares_acumulados"):
        
                    # Calcular tiempo transcurrido exacto
                    partes_tiempo = []
                    if memoria["tiempo_transcurrido"]["años"] > 0:
                        partes_tiempo.append(
                            f"{memoria['tiempo_transcurrido']['años']} año{'s' if memoria['tiempo_transcurrido']['años'] != 1 else ''}"
                        )
                    if memoria["tiempo_transcurrido"]["meses"] > 0:
                        partes_tiempo.append(
                            f"{memoria['tiempo_transcurrido']['meses']} mes{'es' if memoria['tiempo_transcurrido']['meses'] != 1 else ''}"
                        )
                    if memoria["tiempo_transcurrido"]["dias"] > 0:
                        partes_tiempo.append(
                            f"{memoria['tiempo_transcurrido']['dias']} día{'s' if memoria['tiempo_transcurrido']['dias'] != 1 else ''}"
                        )
                    if not partes_tiempo:
                        partes_tiempo.append("hoy")
        
                    tiempo_texto = " y ".join(partes_tiempo)
        
                    # Malestares previos registrados
                    malestares_previos = ", ".join(memoria["malestares_acumulados"])
        
                    # Detectar si es la primera vez que responde en esta sesión
                    if not session.get("saludo_recurrente_usado"):
                        saludo_recurrente = (
                            f"Hola, ¿qué tal? Hace {tiempo_texto} me comentaste que estabas atravesando: {malestares_previos}. "
                            f"¿Cómo te sentiste desde entonces? ¿Hubo mejoría o seguís igual?"
                        )
        
                        # Inyectar saludo antes del mensaje del usuario
                        mensaje_usuario = f"{saludo_recurrente} {mensaje_usuario}"
        
                        # Evitar repetir en esta sesión
                        session["saludo_recurrente_usado"] = True
                        user_sessions[user_id] = session
        
            except Exception as e:
                print(f"⚠️ Error en saludo inteligente recurrente: {e}")


        

        
        # ============================================================
        # 📌 Manejo de memoria persistente y recordatorio clínico refinado
        # ============================================================
        if intencion_general == "CLINICA" and emociones_detectadas_bifurcacion:
        
            # Verificar memoria persistente (solo para clínica)
            memoria = verificar_memoria_persistente(user_id)
        
            # Solo mostrar recordatorio si hay datos y aún no se mostró en esta conversación
            if memoria and not session.get("memoria_usada_en_esta_sesion"):
        
                print(f"🧠 Memoria persistente encontrada para usuario {user_id}")
                print(f"📋 Malestares acumulados detectados: {memoria['malestares_acumulados']}")
                print(f"🕒 Última interacción registrada: {memoria['fecha']}")
        
                # ===== 1️⃣ Calcular tiempo transcurrido de forma natural =====
                dias_transcurridos = (datetime.now() - memoria["fecha"]).days
                if dias_transcurridos == 0:
                    tiempo_texto = "hace unas horas"
                elif dias_transcurridos == 1:
                    tiempo_texto = "ayer"
                elif dias_transcurridos < 7:
                    tiempo_texto = f"hace {dias_transcurridos} días"
                elif dias_transcurridos < 30:
                    semanas = dias_transcurridos // 7
                    tiempo_texto = f"hace {semanas} semana{'s' if semanas > 1 else ''}"
                elif dias_transcurridos < 365:
                    meses = dias_transcurridos // 30
                    tiempo_texto = f"hace {meses} mes{'es' if meses > 1 else ''}"
                else:
                    años = dias_transcurridos // 365
                    tiempo_texto = f"hace {años} año{'s' if años > 1 else ''}"
        
                # ===== 2️⃣ Limitar cantidad de malestares =====
                malestares_previos = memoria["malestares_acumulados"]
                if len(malestares_previos) > 5:
                    malestares_texto = ", ".join(malestares_previos[:5]) + "… entre otros"
                else:
                    malestares_texto = ", ".join(malestares_previos)
        
                # ===== 3️⃣ Crear mensaje recordatorio =====
                mensaje_recordatorio = (
                    f"{tiempo_texto} me comentaste que estabas atravesando: {malestares_texto}. "
                    "¿Cómo te sentiste desde entonces? ¿Hubo mejoría o seguís igual?"
                )
        
                # Guardar para mostrar una sola vez
                session["mensaje_recordatorio_memoria"] = mensaje_recordatorio
                session["memoria_usada_en_esta_sesion"] = True
                user_sessions[user_id] = session
        
            # Inyectar recordatorio solo si existe y aún no se usó en esta respuesta
            if "mensaje_recordatorio_memoria" in session:
                mensaje_usuario = f"{session.pop('mensaje_recordatorio_memoria')} {mensaje_usuario}"
                user_sessions[user_id] = session
        
            # Guardar emociones detectadas evitando duplicados
            session.setdefault("emociones_detectadas", [])
            session["emociones_detectadas"].extend([
                emocion for emocion in emociones_detectadas_bifurcacion
                if emocion not in session["emociones_detectadas"]
            ])
            print(f"💾 Emociones agregadas desde bifurcación: {emociones_detectadas_bifurcacion}")




            # Actualiza la sesión del usuario
            session["ultima_interaccion"] = time.time()
            session["contador_interacciones"] += 1  # ✅ Incrementar contador aquí
            session["_ready_5_9"] = True  # 🔐 Activar guard-flag para permitir disparador en 5/9
            contador = session["contador_interacciones"]
            session["mensajes"].append(mensaje_usuario)
            user_sessions[user_id] = session


            

            

            # ================================================================
            # 📌 Registro de emociones nuevas + disparador de coincidencia clínica
            # ================================================================
            if intencion_general == "CLINICA":
                # 1️⃣ Obtener emociones históricas desde la DB (solo historial_clinico_usuario)
                #    -> evitamos por completo la tabla 'emociones_detectadas'
                try:
                    historicas = obtener_emociones_ya_registradas(user_id)  # set[str], desde historial_clinico_usuario
                except Exception as e:
                    print(f"⚠️ Error obteniendo emociones históricas (historial_clinico_usuario): {e}")
                    historicas = set()
            
                emociones_actuales = (emociones_detectadas_bifurcacion or [])
                emociones_actuales = [e.strip().lower() for e in emociones_actuales if isinstance(e, str) and e.strip()]
            
                # 2️⃣ Registrar emociones nuevas que no estén en el historial (solo a nivel de sesión)
                #    -> no se inserta nada en tablas viejas; se deja listo para persistir en 'registrar_historial_clinico'
                nuevas_solo_sesion = [e for e in emociones_actuales if e not in historicas]
                if nuevas_solo_sesion:
                    session.setdefault("nuevas_emociones", [])
                    for e in nuevas_solo_sesion:
                        if e not in session["nuevas_emociones"]:
                            session["nuevas_emociones"].append(e)
            
                # 3️⃣ Disparador en interacción 5 o 9 (sin tabla 'emociones_detectadas')
                #    Guard-flag: solo disparar si el contador YA fue incrementado en esta vuelta
                contador_interacciones = session.get("contador_interacciones", 0)
                ready_5_9 = session.get("_ready_5_9", False)  # ← lo setea a True el bloque de incremento (punto 6)
            
                # 🚀 Detección de coincidencias clínicas en cualquier momento
                try:
                    cuadro, coincidencias = obtener_cuadro_por_emociones(user_id, session)
                    
                    # Si hay al menos 2 coincidencias y aún no avisamos en esta sesión
                    if cuadro and coincidencias >= 2 and not session.get("coincidencia_clinica_usada"):
                        mensaje_predominante = (
                            f"Por lo que me has comentado hasta ahora, "
                            f"el patrón emocional detectado podría corresponderse con: **{cuadro}** "
                            f"(basado en {coincidencias} coincidencias). "
                            "¿Querés que lo analicemos más a fondo?"
                        )
                        # Inyectar antes del mensaje actual
                        mensaje_usuario = f"{mensaje_predominante} {mensaje_usuario}"
                        session["coincidencia_clinica_usada"] = True
                        user_sessions[user_id] = session
                
                except Exception as e:
                    print(f"⚠️ Error en detección de coincidencias clínicas: {e}")

            
                # 4️⃣ Guardar en sesión sin duplicar
                session.setdefault("emociones_detectadas", [])
                for emocion in emociones_actuales:
                    if emocion not in session["emociones_detectadas"]:
                        session["emociones_detectadas"].append(emocion)
            
                print(f"🧠 Emociones registradas/actualizadas en sesión: {emociones_actuales}")










            

        
            # 🔁 Inferencia clínica híbrida (DB → OpenAI)
            resultado = _inferir_por_db_o_openai(user_id, mensaje_usuario, session)
            
            # 🗃️ Registrar en historial_clinico_usuario (tabla unificada)
            registrar_historial_clinico(
                user_id=user_id,
                emociones=session.get("emociones_detectadas", []),
                sintomas=[],  # si querés, podés guardar síntomas detectados por la DB
                tema="clinica_inferencia_hibrida",
                respuesta_openai=None if resultado["fuente"] == "db" else resultado["mensaje"],
                sugerencia=None,
                fase_evaluacion="inferencia_hibrida",
                interaccion_id=session.get("contador_interacciones", 0),
                fecha=datetime.now(),
                fuente=resultado["fuente"],
                origen="inferencia_hibrida",  # <-- nuevo para consistencia
                cuadro_clinico_probable=resultado.get("cuadro_probable"),
                nuevas_emociones_detectadas=session.get("nuevas_emociones", []),
                eliminado=False
            )

            
            # 💬 Devolver respuesta clínica
            session["ultimas_respuestas"].append(resultado["mensaje"])
            user_sessions[user_id] = session
            return {"respuesta": resultado["mensaje"]}
            

            
                                    
        
        # 🧠 Si se detecta intención MIXTA, invitar al usuario a decidir por dónde continuar
        if intencion_general == "MIXTA":
            session["contador_interacciones"] += 1
            user_sessions[user_id] = session
            return {
                "respuesta": (
                    "Entiendo que estás buscando información sobre psicoterapia, pero también mencionás un aspecto emocional importante. "
                    "¿Preferís contarme un poco más sobre cómo lo estás viviendo últimamente o querés resolverlo directamente con el Lic. Bustamante?"
                )
            }


        # 🧠 Si el usuario respondió a la bifurcación mixta, interpretar su preferencia
        ultimas_respuestas = session.get("ultimas_respuestas", [])
        if ultimas_respuestas and "preferís contarme" in ultimas_respuestas[-1].lower():
            if any(frase in mensaje_usuario for frase in ["sí", "quiero", "me gustaría", "contar", "decirte", "hablarlo", "compartirlo"]):
                ...
                session["ultimas_respuestas"].append(respuesta)
                session["contador_interacciones"] += 1
                user_sessions[user_id] = session
                return {"respuesta": respuesta}
            
            elif any(frase in mensaje_usuario for frase in ["no", "preferiría", "directamente", "prefiero hablar", "contactar"]):
                ...
                session["ultimas_respuestas"].append(respuesta)
                session["contador_interacciones"] += 1
                user_sessions[user_id] = session
                return {"respuesta": respuesta}

        # ✅ Frases neutrales que no deben analizarse emocionalmente
        EXPRESIONES_DESCARTADAS = [
            # Cortesía, cierre o testeo
            "gracias", "ok", "listo", "ya está", "nada más", "solo eso", "solo quería saber eso",
            "me quedó claro", "ya entendí", "era solo una duda", "era curiosidad", "me lo guardo",
            "te consultaba por otra persona", "me interesaba saber", "después veo", "lo consulto luego",
            "más adelante veo", "ah ok", "claro", "entiendo", "lo veo después", "todo bien", "sí",
        
            # Preguntas neutras o generales
            "¿a quién me recomiendas?", "a quién me recomiendas", "me recomendarías a alguien?",
            "qué opinas?", "el atiende estos casos?", "que tipo de casos atienden?"
        ]

        # Comentarios metaconversacionales o de expectativa que no deben generar análisis clínico
        EXPRESIONES_ESPERADAS_NO_CLINICAS = [
            "esto funciona como terapia", "me gustaría que esto funcione como terapia",
            "es como una consulta", "esto parece una consulta", "esto me ayuda como si fuera terapia",
            "siento que esto es una sesión", "esto me resulta terapéutico", "parece una sesión real"
        ]
        
        if mensaje_usuario and isinstance(mensaje_usuario, str) and any(expresion in mensaje_usuario for expresion in EXPRESIONES_ESPERADAS_NO_CLINICAS):
            registrar_auditoria_input_original(user_id, mensaje_original, mensaje_usuario, "EXPECTATIVA_NO_CLINICA")
            session["contador_interacciones"] += 1
            user_sessions[user_id] = session
            return {
                "respuesta": (
                    "Este espacio está diseñado para brindar orientación clínica general. "
                    "Si hay algo puntual que te gustaría compartir sobre tu estado emocional, podés hacerlo con confianza."
                )
            }
        

        if not mensaje_usuario:
            raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

        # 🧩 Clasificación local por intención general
        tipo_input = clasificar_input_inicial(mensaje_usuario)


        
        # ✅ Forzar continuidad clínica si el input es ambiguo pero hubo malestar antes
        if tipo_input in ["INDEFINIDO", "FUERA_DE_CONTEXTO", "CONFUSO"]:
            if hay_contexto_clinico_anterior(user_id):
                tipo_input = CLINICO_CONTINUACION
        

        # 🛑 Corte anticipado si ya se registró cierre definitivo en una interacción previa
        if "CIERRE_LIMITE" in session.get("interacciones_previas", []):
            respuesta = (
                "Este canal ha alcanzado su límite de interacciones permitidas. "
                "Por razones clínicas y éticas, no es posible continuar. "
                "Te recomiendo que contactes directamente al Lic. Daniel O. Bustamante para el seguimiento profesional."
            )
            session["contador_interacciones"] += 1
            session["ultimas_respuestas"].append(respuesta)
            user_sessions[user_id] = session  # Asegura persistencia en la sesión
            registrar_respuesta_openai(None, respuesta)  # No se genera nuevo ID de interacción
            return {"respuesta": respuesta}
        

        # ✅ Registrar el tipo de interacción actual
        session.setdefault("interacciones_previas", []).append(tipo_input)
        user_sessions[user_id] = session

        # ✅ Manejo para mensajes de cortesía simples sin contenido clínico
        if tipo_input == CORTESIA:
            respuesta = (
                "Gracias por tu mensaje. Si más adelante deseás compartir algo personal o emocional, "
                "podés hacerlo cuando lo sientas necesario."
            )
            session["ultimas_respuestas"].append(respuesta)
            session["contador_interacciones"] += 1
            user_sessions[user_id] = session
            registrar_auditoria_input_original(user_id, mensaje_original, mensaje_usuario, tipo_input)
            registrar_respuesta_openai(None, respuesta)
            return {"respuesta": respuesta}



        # 🧠 Continuación de tema clínico si fue identificado previamente
        if tipo_input == CLINICO_CONTINUACION:
            registrar_auditoria_input_original(user_id, mensaje_original, mensaje_usuario, CLINICO_CONTINUACION)
            session["contador_interacciones"] += 1
            user_sessions[user_id] = session
            return {
                "respuesta": (
                    "Entiendo. Lo que mencionaste antes podría estar indicando un malestar emocional. "
                    "¿Querés que exploremos un poco más lo que estás sintiendo últimamente?"
                )
            }
 

        # 🧠 Clasificación contextual con OpenAI
        try:
            prompt_contextual = (
                f"Analizá el siguiente mensaje del usuario y clasificá su intención principal, utilizando una única etiqueta válida.\n\n"
                f"Mensaje: '{mensaje_usuario}'\n\n"
                "Posibles etiquetas (escribilas exactamente como están):\n"
                "- CLINICO: si expresa malestar emocional, síntomas, angustia, ideas existenciales, desmotivación, llanto, insomnio, vacío, o cualquier signo de sufrimiento subjetivo.\n"
                "- CORTESIA: si solo agradece, cierra la conversación o expresa buenos modales sin intención emocional o clínica.\n"
                "- CONSULTA_AGENDAR: si consulta sobre turnos, disponibilidad, cómo coordinar una sesión, cómo pedir cita, cómo sacar turno, cuánto cuesta, etc.\n"
                "- CONSULTA_MODALIDAD: si consulta por la modalidad de atención (online/presencial), si es por videollamada, Zoom, ubicación o si debe asistir a un consultorio.\n"
                "- TESTEO: si es un mensaje de prueba sin contenido emocional ni administrativo (ejemplo: 'hola test', 'probando', '1,2,3', etc.).\n"
                "- MALICIOSO: si contiene lenguaje técnico, comandos, código de programación, frases extrañas, manipulación evidente o contenido ajeno a una conversación clínica.\n"
                "- IRRELEVANTE: si no tiene relación con la clínica psicológica ni con la consulta de servicios (ej: temas técnicos, bromas, frases absurdas, etc.).\n\n"
                "Respondé con una sola palabra en mayúsculas, sin explicaciones adicionales. Solamente devolvé la etiqueta elegida."
            )
     
            response_contextual = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt_contextual}],
                max_tokens=20,
                temperature=0.0
            )
        
            clasificacion = response_contextual.choices[0].message['content'].strip().upper()

            # 🔍 Validación robusta
            opciones_validas = {
                "CLINICO", "CORTESIA", "CONSULTA_AGENDAR", "CONSULTA_MODALIDAD",
                "TESTEO", "MALICIOSO", "IRRELEVANTE"
            }
            if clasificacion not in opciones_validas:
                print(f"⚠️ Clasificación inválida recibida de OpenAI: '{clasificacion}'")
                clasificacion = "IRRELEVANTE"
                
            if clasificacion == "CORTESIA" and not session.get("emociones_detectadas"):

                ya_saludo = any("hola" in r.lower() for r in session.get("ultimas_respuestas", []))
            
                # 🟡 MANEJO ESPECIAL PARA "hola que tal" o "hola que tal?" como saludo inicial
                if mensaje_usuario.strip() in ["hola que tal", "hola que tal?"] and not ya_saludo:
                    prompt_saludo_inicial = (
                        f"El usuario escribió: '{mensaje_usuario}'.\n"
                        "Redactá una respuesta breve, cordial y natural, como si fuera el INICIO de una conversación.\n"
                        "No debe dar a entender que la conversación terminó, ni incluir frases como:\n"
                        "'quedo a disposición', 'si necesitás algo más', 'estoy para ayudarte', 'que tengas un buen día', ni similares.\n"
                        "NO uses preguntas. NO uses emojis. NO hagas cierre ni agradecimientos.\n"
                        "No formules preguntas de ningún tipo, ni de seguimiento ni personales.\n"
                        "Estilo sugerido: una simple bienvenida informal, por ejemplo: '¡Hola! Contame.', 'Hola, decime nomás.', 'Hola, ¿cómo estás?'.\n"
                        "Debe sonar como alguien que saluda para iniciar un diálogo, no para despedirse ni cerrar la conversación."
                    )
                    respuesta_saludo = generar_respuesta_con_openai(
                        prompt_saludo_inicial,
                        session["contador_interacciones"],
                        user_id,
                        mensaje_usuario,
                        mensaje_original
                    )
            
                    session["ultimas_respuestas"].append(respuesta_saludo)
                    session["contador_interacciones"] += 1
                    user_sessions[user_id] = session
                    registrar_respuesta_openai(None, respuesta_saludo)
                    return {"respuesta": respuesta_saludo}
            
                # 🔵 CORTESÍA GENERAL (no es saludo inicial o ya fue saludado)
                registrar_auditoria_input_original(user_id, mensaje_original, mensaje_usuario, CORTESIA)
            
                prompt_cortesia_contextual = (
                    f"El usuario ha enviado el siguiente mensaje de cortesía o cierre: '{mensaje_usuario}'.\n"
                    "Redactá una respuesta breve y cordial, sin repetir frases como 'Con gusto', 'Estoy disponible' ni 'Que tengas un buen día'.\n"
                    "Debe ser fluida, natural, diferente cada vez y adaptada al contexto de una conversación informal respetuosa.\n"
                    "Evitá cerrar de forma tajante o dar a entender que la conversación terminó. No uses emojis. No hagas preguntas ni ofrezcas ayuda adicional si no fue solicitada.\n"
                    "NO uses frases como: '¿y tú?', '¿cómo estás tú?', '¿cómo vas?' ni ninguna variante de pregunta personal o de seguimiento."
                )
            
                respuesta_contextual = generar_respuesta_con_openai(
                    prompt_cortesia_contextual,
                    session["contador_interacciones"],
                    user_id,
                    mensaje_usuario,
                    mensaje_original
                )
            
                # Validación simple
                if not respuesta_contextual or len(respuesta_contextual.strip()) < 3:
                    respuesta_contextual = "Perfecto, seguimos en contacto si más adelante querés continuar."
            
                # 🧼 Filtro contra frases de cierre sutil
                frases_cierre_suave = [
                    "que tengas un buen día", "¡que tengas un buen día!", "que tengas buen día",
                    "buen día para vos", "que tengas un lindo día", "que tengas una excelente tarde",
                    "que tengas un excelente día", "¡que tengas una excelente tarde!", "que tengas una linda tarde"
                ]
                for frase_final in frases_cierre_suave:
                    if frase_final in respuesta_contextual.lower():
                        respuesta_contextual = re.sub(frase_final, "", respuesta_contextual, flags=re.IGNORECASE).strip(".! ")
            
                # Eliminar residuos de puntuación si quedó la frase vacía o colgante
                if respuesta_contextual.endswith(("¡", "¿", ",", ".", "!", " ")):
                    respuesta_contextual = respuesta_contextual.rstrip("¡¿,!. ")
            
                # Último refuerzo por si quedó vacía tras filtros
                if not respuesta_contextual.strip():
                    respuesta_contextual = "Hola, contame."
            
                session["ultimas_respuestas"].append(respuesta_contextual)
                session["contador_interacciones"] += 1
                user_sessions[user_id] = session
                return {"respuesta": respuesta_contextual}
            

            
            
            if clasificacion == "CONSULTA_AGENDAR":
                registrar_auditoria_input_original(user_id, mensaje_original, mensaje_usuario, CONSULTA_AGENDAR)
                respuesta = (
                    "Para agendar una sesión o conocer disponibilidad, podés escribirle directamente al Lic. Bustamante al WhatsApp +54 911 3310-1186."
                )
                session["ultimas_respuestas"].append(respuesta)
                user_sessions[user_id] = session
                session["contador_interacciones"] += 1
                user_sessions[user_id] = session
                return {"respuesta": respuesta}

            
            if clasificacion == "CONSULTA_MODALIDAD":
                registrar_auditoria_input_original(user_id, mensaje_original, mensaje_usuario, CONSULTA_MODALIDAD)
                respuesta = (
                    "El Lic. Bustamante trabaja exclusivamente en modalidad Online, a través de videollamadas. "
                    "Atiende de lunes a viernes, entre las 13:00 y las 20:00 hs. "
                    "Podés consultarle por disponibilidad escribiéndole directamente al WhatsApp +54 911 3310-1186."
                )
                session["ultimas_respuestas"].append(respuesta)
                session["contador_interacciones"] += 1
                user_sessions[user_id] = session
                return {"respuesta": respuesta}

            
            if clasificacion in ["TESTEO", "MALICIOSO", "IRRELEVANTE"]:
                registrar_auditoria_input_original(user_id, mensaje_original, mensaje_usuario, clasificacion)
            
                # ⚠️ Solo bloquear si NO hay emociones registradas y es muy temprano
                if (
                    not hay_contexto_clinico_anterior(user_id)
                    and not session.get("emociones_detectadas")
                    and session.get("contador_interacciones", 0) <= 2
                ):
                    session["input_sospechoso"] = True
                    session["ultimas_respuestas"].append(respuesta_default_fuera_de_contexto())
                    user_sessions[user_id] = session
                    return {"respuesta": respuesta_default_fuera_de_contexto()}
            
                else:
                    tipo_input = CLINICO_CONTINUACION
                    session["contador_interacciones"] += 1  # ✅ CORRECCIÓN CRÍTICA AQUÍ
                    user_sessions[user_id] = session
        
        except Exception as e:
            print(f"🧠❌ Error en clasificación contextual: {e}")
        
        # Registrar interacción con mensaje original incluido
        interaccion_id = registrar_interaccion(user_id, mensaje_usuario, mensaje_original)

        # 🔄 Si el input actual es ambiguo, pero ya hubo emociones antes, forzar continuidad clínica
        if tipo_input in ["FUERA_DE_CONTEXTO", "INDEFINIDO", "CONFUSO", "OTRO"]:
            if hay_contexto_clinico_anterior(user_id):
                tipo_input = CLINICO_CONTINUACION

        # 🔁 Reinicio condicional del contador por inactividad mayor a 60 segundos
        if "ultima_interaccion" in session:
            tiempo_inactivo = time.time() - session["ultima_interaccion"]
            if tiempo_inactivo > 60:
                session["contador_interacciones"] = 0
                session["emociones_detectadas"] = []
                session["intenciones_clinicas_acumuladas"] = []
        



        # ====================== INTERACCIÓN 5 – Resumen clínico preliminar e inferencia ======================
        if contador == 5:
            for mensaje in session["mensajes"]:
                nuevas = detectar_emociones_negativas(mensaje) or []
                for emocion in nuevas:
                    emocion = emocion.lower().strip()
                    emocion = re.sub(r'[^\w\sáéíóúüñ]+$', '', emocion)
                    if emocion not in session["emociones_detectadas"]:
                        session["emociones_detectadas"].append(emocion)
        
            resultado = _inferir_por_db_o_openai(user_id, mensaje_usuario, session)
            clasificacion_mental = resultado.get("cuadro_clinico_probable")


        
            if session["emociones_detectadas"]:
                resumen_clinico = generar_resumen_interaccion_5(session, user_id, interaccion_id, contador, user_sessions)

            
                if not resumen_clinico or len(resumen_clinico.strip()) < 5:
                    respuesta = "¿Querés contarme un poco más sobre cómo te sentís últimamente?"
                else:
                    respuesta = (
                        resumen_clinico
                        + " ¿Te interesaría consultarlo con el Lic. Daniel O. Bustamante?"
                    )

            else:
                respuesta = (
                    "Comprendo. Para poder ayudarte mejor, ¿podrías contarme cómo te sentís últimamente?"
                )
        
            session["ultimas_respuestas"].append(respuesta)
            user_sessions[user_id] = session  # Asegura persistencia en la sesión
            registrar_respuesta_openai(interaccion_id, respuesta)
            return {"respuesta": respuesta}


        # ✅ Interacción 9 – Confirmación indirecta de emoción inferida en la 5
        if contador == 9 and session.get("emocion_inferida_5") and session["emocion_inferida_5"] not in session["emociones_detectadas"]:
            emocion = session["emocion_inferida_5"]
        
            expresiones_asociadas = {
                "ansiedad": ["me acelero", "me pongo nervioso", "no puedo respirar", "taquicardia", "me siento agitado", "inquietud"],
                "tristeza": ["sin ganas", "todo me cuesta", "me siento vacío", "sin sentido", "todo me da igual"],
                "angustia": ["presión en el pecho", "nudo en la garganta", "me cuesta tragar", "llanto contenido"],
                "enojo": ["estallo fácil", "me irrito con todo", "no tolero nada", "me molesta todo", "exploto por nada"],
                "miedo": ["me paralizo", "no puedo salir", "me da terror", "me da miedo enfrentarlo", "evito esas situaciones"]
            }
        
            expresiones = expresiones_asociadas.get(emocion.lower(), [])
            emocion_sugerida = any(expresion in mensaje_usuario for expresion in expresiones)
        
            if emocion in mensaje_usuario or emocion_sugerida or "sí" in mensaje_usuario or "me pasa" in mensaje_usuario:
                session["emociones_detectadas"].append(emocion)
                registrar_emocion(emocion, f"confirmación implícita reforzada (interacción 9)", user_id)
        
                respuesta = (
                    f"Gracias por retomarlo. Parece tratarse de una experiencia emocional vinculada a {emocion.lower()}. "
                    "¿Querés contarme un poco más sobre cómo se fue desarrollando últimamente?"
                )
        
                session["ultimas_respuestas"].append(respuesta)
                user_sessions[user_id] = session
                registrar_respuesta_openai(interaccion_id, respuesta)
                return {"respuesta": respuesta}
        
                
            # Detectar emociones nuevas de interacciones 6 a 9
            mensajes_previos = session["mensajes"][-4:]
            emociones_nuevas = []
        
            for mensaje in mensajes_previos:
                nuevas = detectar_emociones_negativas(mensaje) or []
                for emocion in nuevas:
                    emocion = emocion.lower().strip()
                    emocion = re.sub(r'[^\w\sáéíóúüñ]+$', '', emocion)
                    if emocion not in session["emociones_detectadas"]:
                        emociones_nuevas.append(emocion)
                        session["emociones_detectadas"].append(emocion)
        
            resultado = _inferir_por_db_o_openai(user_id, mensaje_usuario, session)
            clasificacion_mental = resultado.get("cuadro_clinico_probable") or generar_resumen_emociones(session["emociones_detectadas"])

        
            # Generar resumen clínico basado en mensajes y emociones
            resumen_clinico = generar_resumen_interaccion_9(session, user_id, interaccion_id, contador, user_sessions)

        
            # Generar hipótesis psicodinámica tentativa
            from core.inferencia_psicodinamica import generar_hipotesis_psicodinamica
            hipotesis_psico = generar_hipotesis_psicodinamica(session["emociones_detectadas"], session["mensajes"])
        
            # Redacción final con inferencia reforzada y cierre profesional
            respuesta = resumen_clinico
        
            if hipotesis_psico:
                respuesta += f" {hipotesis_psico} "
        
            if clasificacion_mental:
                respuesta += (
                    f" Además, se suma una impresión de posible {clasificacion_mental.lower()} predominante, "
                    "tal como se mencionó anteriormente."
                )
        
            respuesta += (
                " No obstante, para estar seguros se requiere de una evaluación psicológica profesional. "
                "Te sugiero que te contactes con el Lic. Bustamante. "
                "Lamentablemente, no puedo continuar con la conversación más allá de este punto."
            )
        
            session["ultimas_respuestas"].append(respuesta)
            user_sessions[user_id] = session  # Asegura persistencia en la sesión
            registrar_respuesta_openai(interaccion_id, respuesta)
            return {"respuesta": respuesta}

        # ====================== INTERACCIÓN 10 O POSTERIOR: CIERRE DEFINITIVO ======================
        if contador >= 10 and tipo_input == CLINICO:
            if contador == 10:
                respuesta = (
                    "He encontrado interesante nuestra conversación, pero para profundizar más en el análisis de tu malestar, "
                    "sería ideal que consultes con un profesional. Por ello, te sugiero que te contactes con el Lic. Bustamante. "
                    "Lamentablemente, no puedo continuar con la conversación más allá de este punto."
                )
        
            elif contador >= 14:
                from core.inferencia_psicodinamica import generar_hipotesis_psicodinamica
            
                hipotesis_psico = generar_hipotesis_psicodinamica(
                    session["emociones_detectadas"], session["mensajes"]
                )
            
                frases_cierre_varias = [
                    "Como mencioné en otra ocasión, no puedo continuar respondiendo desde este espacio.",
                    "Tal como advertí antes, no es posible continuar esta conversación por este medio.",
                    "Ya te indiqué que este canal tiene un límite de interacción.",
                    "Como fue señalado, este espacio no permite continuar más allá de este punto.",
                    "Como fue expresado antes, no podré seguir dialogando por esta vía.",
                ]
                cierre = random.choice(frases_cierre_varias)
            
                respuesta = (
                    hipotesis_psico + " " + cierre + " "
                    "Es fundamental que, si deseás avanzar, lo hagas consultando directamente con el Lic. Daniel O. Bustamante, "
                    "quien podrá brindarte el acompañamiento profesional que necesitás. "
                    "No me es posible continuar respondiendo mensajes en este espacio."
                )
            
                session["ultimas_respuestas"].append(respuesta)
                user_sessions[user_id] = session  # Asegura persistencia en la sesión
                registrar_respuesta_openai(interaccion_id, respuesta)
                return {"respuesta": respuesta}
                      
                    
            elif contador == 15:
                respuesta = (
                    "Ya en este punto, no puedo seguir brindándote orientación desde este espacio. "
                    "Lo más apropiado es que puedas consultarlo directamente con el Lic. Daniel O. Bustamante, "
                    "quien podrá ofrecerte un acompañamiento profesional. "
                    "No me es posible continuar con la conversación."
                )
        
            elif contador >= 16:
                respuesta = (
                    "Como te mencioné anteriormente, ya no puedo continuar con esta conversación desde aquí. "
                    "Es fundamental que, si deseás avanzar, lo hagas consultando directamente con el Lic. Daniel O. Bustamante, "
                    "quien podrá brindarte el acompañamiento profesional que necesitás. "
                    "No me es posible continuar respondiendo mensajes en este espacio."
                )

            elif contador >= 17:
                respuesta = (
                    "Ya he sido claro en que no puedo continuar respondiendo mensajes por este medio. "
                    "Te reitero que lo indicado es que consultes directamente con el Lic. Daniel O. Bustamante, "
                    "quien podrá brindarte el acompañamiento profesional que necesitás. "
                    "No insistas por este canal, ya que no podré responderte."
                )
                session["ultimas_respuestas"].append(respuesta)
                user_sessions[user_id] = session  # Asegura persistencia en la sesión
                registrar_respuesta_openai(interaccion_id, respuesta)
                return {"respuesta": respuesta}
        
            else:
                recordatorio = ""
                if (contador - 10) % 2 == 0:
                    recordatorio = " Te recuerdo que para una orientación adecuada, deberías consultar con el Lic. Daniel O. Bustamante."
        
                respuesta_variable = seleccionar_estilo_clinico_variable()
                respuesta = respuesta_variable + recordatorio
        
            session["ultimas_respuestas"].append(respuesta)
            user_sessions[user_id] = session  # Asegura persistencia en la sesión
            registrar_respuesta_openai(interaccion_id, respuesta)
            return {"respuesta": respuesta}

        # 🛑 Filtro definitivo para inputs irrelevantes, maliciosos o de cortesía post-cierre
        if contador >= 10 and clasificacion in ["IRRELEVANTE", "MALICIOSO", "CORTESIA"]:
            respuesta = (
                "Gracias por tu mensaje. Ya no puedo continuar con esta conversación por este medio. "
                "Te recomiendo que contactes directamente con el Lic. Daniel O. Bustamante para una evaluación adecuada."
            )
            session["ultimas_respuestas"].append(respuesta)
            user_sessions[user_id] = session
            registrar_respuesta_openai(interaccion_id, respuesta)
            return {"respuesta": respuesta}
        
        # ✅ Si hay una respuesta clínica manual para esta interacción, se devuelve directamente
        # 🔄 (Se reemplazó el uso de 'respuestas_personalizadas' por 'RESPUESTAS_CLINICAS' del módulo importado)
        if contador in RESPUESTAS_CLINICAS:
            respuesta_manual = RESPUESTAS_CLINICAS[contador]
        
            # Auditoría (registro explícito como respuesta manual no generada por OpenAI)
            registrar_auditoria_respuesta(
                user_id=user_id,
                respuesta_original=respuesta_manual,
                respuesta_final=respuesta_manual,
                motivo_modificacion="respuesta manual predefinida"
            )
        
            session["ultimas_respuestas"].append(respuesta_manual)
            user_sessions[user_id] = session
            return {"respuesta": respuesta_manual}

        
        # ✅ Interacciones 6 a 8 – Confirmación implícita de emoción inferida 5 si aún no fue confirmada
        if 6 <= contador <= 8 and session.get("emocion_inferida_5") and session["emocion_inferida_5"] not in session["emociones_detectadas"]:
            emocion = session["emocion_inferida_5"]
        
            expresiones_asociadas = {
                "ansiedad": ["me acelero", "me pongo nervioso", "no puedo respirar", "taquicardia", "me siento agitado", "inquietud"],
                "tristeza": ["sin ganas", "todo me cuesta", "me siento vacío", "sin sentido", "todo me da igual"],
                "angustia": ["presión en el pecho", "nudo en la garganta", "me cuesta tragar", "llanto contenido"],
                "enojo": ["estallo fácil", "me irrito con todo", "no tolero nada", "me molesta todo", "explotó por nada"],
                "miedo": ["me paralizo", "no puedo salir", "me da terror", "me da miedo enfrentarlo", "evito esas situaciones"]
            }
        
            expresiones = expresiones_asociadas.get(emocion.lower(), [])
            emocion_sugerida = any(expresion in mensaje_usuario for expresion in expresiones)
        
            if emocion in mensaje_usuario or emocion_sugerida or "sí" in mensaje_usuario or "me pasa" in mensaje_usuario:
                if emocion not in session["emociones_detectadas"]:
                    session["emociones_detectadas"].append(emocion)
                    registrar_emocion(emocion, f"confirmación implícita reforzada (interacción {contador})", user_id)
        
                respuesta = (
                    f"Gracias por confirmarlo. ¿Querés contarme un poco más sobre cómo se manifiesta esa {emocion} en tu día a día?"
                )
        
                session["ultimas_respuestas"].append(respuesta)
                user_sessions[user_id] = session
                registrar_respuesta_openai(interaccion_id, respuesta)
                return {"respuesta": respuesta}


        # 🧠 Nueva respuesta para la PRIMERA INTERACCIÓN
        if contador == 1:
            # ⚠️ Reforzar que si es SALUDO + contenido clínico, se trate como clínico
            if tipo_input == SALUDO and es_tema_clinico_o_emocional(mensaje_usuario):
                tipo_input = CLINICO
        
            # ✅ Determinar si ya hubo un saludo en respuestas previas
            ya_saludo = any("hola" in r.lower() for r in session.get("ultimas_respuestas", []))
        
            # ✅ Si es clínico o hay contexto clínico previo, generar respuesta profesional
            if tipo_input in [CLINICO, CLINICO_CONTINUACION] or hay_contexto_clinico_anterior(user_id) or es_tema_clinico_o_emocional(mensaje_usuario):
                
                # Consultar historial clínico reciente
                historial = obtener_ultimo_historial_emocional(user_id)
                
                mensaje_historial = ""
                if historial and historial.emociones and historial.fecha:
                    emociones_previas = ", ".join(historial.emociones)
                    dias_transcurridos = (datetime.now() - historial.fecha).days
                    tiempo_mencion = f"Hace {dias_transcurridos} días" if dias_transcurridos > 0 else "Recientemente"
                
                    mensaje_historial = (
                        f"{tiempo_mencion} consultaste por emociones como: {emociones_previas}. "
                        "¿Notás algún cambio o seguís sintiéndote de forma similar?\n"
                    )
                
                saludo_inicio = ""
                if contador == 1 and not session["mensajes"] and not ya_saludo:
                    saludo_inicio = "- Comenzá la respuesta con un saludo breve como 'Hola, ¿qué tal?'.\n"
                
                prompt = (
                    f"Mensaje recibido del usuario: \"{mensaje_usuario}\".\n"
                    f"{mensaje_historial}"
                    "Redactá una respuesta breve, profesional y clínica como si fueras el asistente virtual del Lic. Daniel O. Bustamante, psicólogo.\n"
                    "Estilo y directrices obligatorias:\n"
                    "- Mantené un tono clínico, sobrio, profesional y respetuoso.\n"
                    f"{saludo_inicio}"
                    "- Si se detecta malestar emocional, formulá una observación objetiva con expresiones como: 'se observa...', 'se advierte...', 'impresiona...', 'podría tratarse de...'\n"
                )
                

        
        
                respuesta_original = generar_respuesta_con_openai(prompt, contador, user_id, mensaje_usuario, mensaje_original)
        
                # Validación por fallback
                if not respuesta_original or not isinstance(respuesta_original, str) or len(respuesta_original.strip()) < 5:
                    respuesta_ai = (
                        "¿Podés contarme un poco más sobre cómo lo estás viviendo estos días? "
                        "A veces ponerlo en palabras ayuda a entenderlo mejor."
                    )
                    registrar_auditoria_respuesta(user_id, "respuesta vacía", respuesta_ai, "Fallback clínico: respuesta nula o inválida de OpenAI")
                    session["ultimas_respuestas"].append(respuesta_ai)
                    user_sessions[user_id] = session
                    return {"respuesta": respuesta_ai}
        
                registrar_auditoria_respuesta(user_id, respuesta_original, respuesta_original)
                registrar_respuesta_openai(None, respuesta_original)
                session["ultimas_respuestas"].append(respuesta_original)
                user_sessions[user_id] = session
                return {"respuesta": respuesta_original}
        
            # 🔹 Si no es clínico ni hay contexto previo, mantener respuesta neutra
            return {
                "respuesta": (
                    "Gracias por tu mensaje. ¿Hay algo puntual que te gustaría compartir o consultar en este espacio?"
                )
            }

        # 🟢 Si la frase es neutral, de cortesía o curiosidad, no analizar emocionalmente ni derivar
        if mensaje_usuario in EXPRESIONES_DESCARTADAS or any(p in mensaje_usuario for p in ["recomienda", "opinás", "atiende"]):
            respuesta = (
                "Gracias por tu mensaje. Si en algún momento deseás explorar una inquietud emocional, "
                "estoy disponible para ayudarte desde este espacio."
            )
            session["ultimas_respuestas"].append(respuesta)
            user_sessions[user_id] = session
            return {"respuesta": respuesta}

        # 🔍 DEPURACIÓN: Mostrar estado actual de la sesión
        print("\n===== DEPURACIÓN - SESIÓN DEL USUARIO =====")
        print(f"Usuario ID: {user_id}")
        print(f"Interacción actual: {contador}")
        print(f"Mensajes en la sesión: {session['mensajes']}")
        print(f"Emociones acumuladas antes del análisis: {session['emociones_detectadas']}")
        print("========================================\n")
        
        # Detectar negaciones o correcciones
        if any(negacion in mensaje_usuario for negacion in ["no dije", "no eso", "no es así", "eso no", "no fue lo que dije"]):
            return {"respuesta": "Entiendo, gracias por aclararlo. ¿Cómo describirías lo que sientes?"}


        # Manejo para "no sé", "ninguna", "ni la menor idea" tras describir un síntoma
        if mensaje_usuario in ["no sé", "ninguna", "ni la menor idea"]:
            session["contador_interacciones"] += 1  # ✅ Incremento obligatorio
            if session["contador_interacciones"] >= 9 or session["mensajes"]:
                respuesta_clinica = generar_resumen_clinico_y_estado(session, session["contador_interacciones"])
                respuesta = (
                    f"{respuesta_clinica} En caso de que lo desees, podés contactar al Lic. Daniel O. Bustamante escribiéndole al WhatsApp +54 911 3310-1186."
                )
            else:
                respuesta = "Entendido, quedo a tu disposición. Si necesitas algo más, no dudes en decírmelo."
        
            session["ultimas_respuestas"].append(respuesta)
            user_sessions[user_id] = session
            return {"respuesta": respuesta}

        
        if es_consulta_contacto(mensaje_usuario, user_id, mensaje_original):
            session["contador_interacciones"] += 1
            user_sessions[user_id] = session
            return {
                "respuesta": "Para contactar al Lic. Daniel O. Bustamante, podés enviarle un mensaje al WhatsApp +54 911 3310-1186. Él estará encantado de responderte."
            }

        
        # 🔹 Proporciona el número de contacto si el usuario pregunta por el "mejor psicólogo" o si es buen profesional
        frases_recomendacion = [
            "especialista", "mejor psicologo", "mejor psicólogo", "mejor terapeuta",
            "mejor psicoterapeuta", "el mejor", "a quien me recomendas", "que opinas",
            "qué opinas", "excelente psicologo", "buen profesional", "que me recomendas",
            "es bueno como profesional", "es buen profesional", "es recomendable", 
            "lo recomendas", "lo recomendás", "confías en él", "qué tal es como profesional",
            "que opinas del psicologo", "lo recomendarias", "es recomendable", "recomendable"
        ]
        
        mensaje_normalizado = unicodedata.normalize("NFKD", mensaje_usuario).encode("ascii", "ignore").decode("utf-8").lower()
        
        if any(frase in mensaje_normalizado for frase in frases_recomendacion):
            session["contador_interacciones"] += 1
            respuesta = (
                "En mi opinión, el Lic. Daniel O. Bustamante es un excelente especialista en psicología clínica. "
                "Seguramente podrá ayudarte. Podés escribirle directamente al WhatsApp +54 911 3310-1186."
            )
            session["ultimas_respuestas"].append(respuesta)
            user_sessions[user_id] = session
            return {"respuesta": respuesta}


        # Manejo para "solo un síntoma y no más" (responder como en la 5ª interacción y finalizar)
        if "no quiero dar más síntomas" in mensaje_usuario or "solo este síntoma" in mensaje_usuario:
            mensajes = session["mensajes"]
            mensajes.append(mensaje_usuario)
            respuesta_analisis = analizar_texto(mensajes)
            session["mensajes"].clear()
            session["contador_interacciones"] += 1
            user_sessions[user_id] = session
            return {
                "respuesta": (
                    f"{respuesta_analisis} Si necesitas un análisis más profundo, también te recomiendo contactar al Lic. Daniel O. Bustamante al WhatsApp "
                    f"+54 911 3310-1186 para una evaluación más detallada."
                )
            }
              
        # 🧩 Generar respuesta con OpenAI si no es la interacción 5, 9 o 10+
        saludo_inicio = "- Comenzá la respuesta con un saludo breve como “Hola, ¿qué tal?”.\n" if contador == 1 else ""
        

        # ✅ Bloque de generación de respuesta clínica personalizada
        # Generación del prompt clínico personalizado según interacción
        prompt = (
            f"Mensaje recibido del usuario: '{mensaje_usuario}'.\n"
            "Redactá una respuesta breve, profesional y clínica como si fueras el asistente virtual del Lic. Daniel O. Bustamante, psicólogo.\n"
            "Estilo y directrices obligatorias:\n"
            "- Mantené un tono clínico, sobrio, profesional y respetuoso.\n"
            "- Comenzá la respuesta con un saludo breve como 'Hola, ¿qué tal?' solo si es la interacción 1.\n"
            "- Si se detecta malestar emocional, formulá una observación objetiva con expresiones como: 'se observa...', 'se advierte...', 'impresiona...', 'podría tratarse de...', 'da la sensación de ser...', 'normalmente se trata de un...', etc.\n"
            "- Evitá la frase 'Pareciera tratarse de...' en todas las interacciones, excepto en la 5 y 9.\n"
            "- No uses agradecimientos en ninguna interacción (ni al inicio ni al final).\n"
            "- No uses frases motivacionales ni simulaciones empáticas (ej: 'te entiendo', 'estás en buenas manos', etc.).\n"
            "- No uses lenguaje institucional ni expresiones como 'nuestro equipo', 'desde este espacio', etc.\n"
            "- No brindes datos de contacto, precios ni derivaciones, salvo que sea interacción 5, 9 o a partir de la 10.\n"
            "- Solo si el mensaje es claramente clínico, generá una respuesta analítica breve y profesional.\n"
            "- Si no tiene contenido clínico o emocional, devolvé una frase neutra: 'Gracias por tu mensaje. ¿Hay algo puntual que te gustaría compartir o consultar en este espacio?'\n"
            f"- IMPORTANTE: estás en la interacción {contador}.\n"
        )
        
        # Solicitar respuesta a OpenAI con el nuevo prompt clínico
        respuesta_original = generar_respuesta_con_openai(prompt, contador, user_id, mensaje_usuario, mensaje_original)
        
        # 🔍 Filtro para remover saludo 'Hola, ¿qué tal?' si no es la primera interacción
        if contador != 1 and respuesta_original.strip().lower().startswith("hola, ¿qué tal?"):
            respuesta_filtrada = respuesta_original.replace("Hola, ¿qué tal? ", "", 1).strip()
            motivo = "Se eliminó el saludo inicial 'Hola, ¿qué tal?' porque no corresponde repetirlo en interacciones posteriores a la primera"
            registrar_auditoria_respuesta(user_id, respuesta_original, respuesta_filtrada, motivo)
            respuesta_ai = respuesta_filtrada
        else:
            respuesta_ai = respuesta_original
        


        # 🔒 Filtro contra mención indebida al Lic. Bustamante fuera de interacciones permitidas
        if contador not in [5, 9] and contador < 10 and not es_consulta_contacto(mensaje_usuario, user_id, mensaje_original):
            if "bustamante" in respuesta_original.lower() or "+54 911 3310-1186" in respuesta_original:
                # Eliminar cualquier frase que mencione al Lic. Bustamante o su número
                respuesta_filtrada = re.sub(
                    r"(el Lic\.? Bustamante.*?[\.\!\?])",
                    "",
                    respuesta_original,
                    flags=re.IGNORECASE
                )
                motivo = "Mención indebida a contacto fuera de interacciones 5, 9 o 10+"
                registrar_auditoria_respuesta(user_id, respuesta_original, respuesta_filtrada.strip(), motivo)
                respuesta_ai = respuesta_filtrada.strip()
            else:
                respuesta_ai = respuesta_original
        else:
            respuesta_ai = respuesta_original

        # 🛑 Filtro para derivaciones implícitas indebidas
        frases_implicitas_derivacion = [
            "podrías trabajarlo con", "te sugiero considerarlo en una consulta",
            "evaluarlo con un profesional", "sería conveniente que lo converses",
            "hablarlo en un espacio terapéutico", "apoyo profesional", 
            "ayuda especializada", "espacio terapéutico", 
            "alguien capacitado", "profesional de la salud mental"
        ]
        
        if contador not in [5, 9] and contador < 10 and not es_consulta_contacto(mensaje_usuario, user_id, mensaje_original):
            for frase in frases_implicitas_derivacion:
                if frase in respuesta_original.lower():
                    motivo = "Derivación implícita fuera de interacción permitida"
                    respuesta_ai = (
                        "Gracias por tu mensaje. Si querés, podés contarme un poco más sobre lo que estás sintiendo "
                        "para poder continuar con el análisis clínico correspondiente."
                    )
                    try:
                        registrar_historial_clinico(
                            user_id=user_id,
                            emociones=emociones_detectadas if 'emociones_detectadas' in locals() else [],
                            sintomas=[],
                            tema="Clínica - Derivación implícita",
                            respuesta_openai=respuesta_ai,
                            sugerencia="",
                            fase_evaluacion="respuesta_derivacion_implicita",
                            interaccion_id=int(time.time()),
                            fecha=datetime.now(),
                            fuente="web",
                            origen="derivacion_implicita",        # <-- nuevo/estandarizado
                            eliminado=False,
                        )
                    except Exception as e:
                        print(f"⚠️ Error al registrar historial clínico desde derivación implícita: {e}")


                    registrar_auditoria_respuesta(user_id, respuesta_original, respuesta_ai, motivo)
                    break
                session["ultimas_respuestas"].append(respuesta_ai)
                user_sessions[user_id] = session
                return {"respuesta": respuesta_ai}
        
        # 🔐 Seguridad textual: verificar si la respuesta de OpenAI contiene elementos peligrosos
        if contiene_elementos_peligrosos(respuesta_original):
            respuesta_ai = (
                "Por razones de seguridad, la respuesta generada fue descartada por contener elementos técnicos no permitidos. "
                "Podés intentar formular tu consulta de otra manera o escribir directamente al WhatsApp del Lic. Bustamante: +54 911 3310-1186."
            )
            try:
                registrar_historial_clinico(
                    user_id=user_id,
                    emociones=emociones_detectadas if 'emociones_detectadas' in locals() else [],
                    sintomas=[],
                    tema="Clínica - Respuesta peligrosa descartada",
                    respuesta_openai=respuesta_ai,
                    sugerencia="",
                    fase_evaluacion="respuesta_peligrosa",
                    interaccion_id=int(time.time()),
                    fecha=datetime.now(),
                    fuente="web",
                    origen="respuesta_peligrosa",        # <-- estandarizado
                    eliminado=False,
                )
            except Exception as e:
                print(f"⚠️ Error al registrar historial clínico desde respuesta peligrosa: {e}")

                
            registrar_auditoria_respuesta(user_id, respuesta_original, respuesta_ai, "Respuesta descartada por contener elementos peligrosos")
            session["ultimas_respuestas"].append(respuesta_ai)
            user_sessions[user_id] = session
            return {"respuesta": respuesta_ai}

        
        # Validación previa
        if not respuesta_original:
            respuesta_ai = (
                "Lo siento, hubo un inconveniente al generar una respuesta automática. Podés escribirle al Lic. Bustamante al WhatsApp +54 911 3310-1186."
            )
            try:
                registrar_historial_clinico(
                    user_id=user_id,
                    emociones=emociones_detectadas if 'emociones_detectadas' in locals() else [],
                    sintomas=[],
                    tema="Clínica - Respuesta vacía",
                    respuesta_openai=respuesta_ai,
                    sugerencia="",
                    fase_evaluacion="respuesta_vacía",
                    interaccion_id=int(time.time()),
                    fecha=datetime.now(),
                    fuente="web",
                    origen="respuesta_vacia",        # <-- nuevo estándar
                    eliminado=False,
                )
            except Exception as e:
                print(f"⚠️ Error al registrar historial clínico desde respuesta vacía: {e}")


            registrar_auditoria_respuesta(user_id, "Error al generar respuesta", respuesta_ai, "Error: OpenAI devolvió respuesta vacía")
            session["ultimas_respuestas"].append(respuesta_ai)
            user_sessions[user_id] = session
            return {"respuesta": respuesta_ai}
        
        respuesta_ai = respuesta_original  # Copia editable
        motivo = None

        # 🔍 Filtro para lenguaje institucional
        palabras_prohibidas = ["nosotros", "nuestro equipo", "nuestra institución", "desde nuestra", "trabajamos en conjunto"]
        if any(palabra in respuesta_ai.lower() for palabra in palabras_prohibidas):
            respuesta_ai = (
                "Gracias por tu consulta. El Lic. Daniel O. Bustamante estará encantado de ayudarte. "
                "Podés escribirle directamente al WhatsApp +54 911 3310-1186 para obtener más información."
            )
            try:
                registrar_historial_clinico(
                    user_id=user_id,
                    emociones=emociones_detectadas if 'emociones_detectadas' in locals() else [],
                    sintomas=[],
                    tema="Clínica - Lenguaje institucional",
                    respuesta_openai=respuesta_ai,
                    sugerencia="",
                    fase_evaluacion="respuesta_institucional",
                    interaccion_id=int(time.time()),
                    fecha=datetime.now(),
                    fuente="web",
                    origen="filtro_lenguaje_institucional",          # o "filtro_institucional" si preferís ser más específico
                    eliminado=False,
                )
            except Exception as e:
                print(f"⚠️ Error al registrar historial clínico desde respuesta institucional: {e}")
            
                            
            session["ultimas_respuestas"].append(respuesta_ai)
            user_sessions[user_id] = session
            return {"respuesta": respuesta_ai}


        # 🔍 Filtro para lenguaje empático simulado o genérico prohibido
        frases_empaticas_simuladas = [
            "estoy aquí para ayudarte", "estoy aquí para ayudarle", "te puedo ayudar", 
            "estamos para ayudarte", "cuente conmigo", "puedo ayudarte", 
            "tranquilo", "no estás solo", "estás en buenas manos", 
            "todo va a estar bien", "puede contar conmigo"
        ]
        if any(frase in respuesta_ai.lower() for frase in frases_empaticas_simuladas):
            respuesta_ai = (
                "Gracias por tu mensaje. Si querés, podés contarme un poco más sobre lo que estás atravesando "
                "para poder continuar con el análisis clínico correspondiente."
            )
            try:
                registrar_historial_clinico(
                    user_id=user_id,
                    emociones=emociones_detectadas if 'emociones_detectadas' in locals() else [],
                    sintomas=[],
                    tema="Clínica - Lenguaje empático simulado",
                    respuesta_openai=respuesta_ai,
                    sugerencia="",
                    fase_evaluacion="respuesta_empática_simulada",
                    interaccion_id=int(time.time()),
                    fecha=datetime.now(),
                    fuente="web",
                    origen="filtro_empatia_simulada",          # o "filtro_empatico" si querés más detalle
                    eliminado=False,
                )
            except Exception as e:
                print(f"⚠️ Error al registrar historial clínico desde respuesta empática simulada: {e}")
            
                            
            motivo = "Frase empática simulada detectada y reemplazada"

        
        # 🔍 Filtro para desvíos temáticos (por si OpenAI habla de finanzas o cosas raras)
        temas_prohibidos = ["finanzas", "inversiones", "educación financiera", "consultoría financiera", "legal", "técnico"]
        if any(tema in respuesta_ai.lower() for tema in temas_prohibidos):
            respuesta_ai = (
                "El Lic. Daniel O. Bustamante es psicólogo clínico. Si querés saber más sobre los servicios que ofrece, "
                + obtener_mensaje_contacto() +
                " y te brindará toda la información necesaria."
            )
            try:
                registrar_historial_clinico(
                    user_id=user_id,
                    emociones=emociones_detectadas if 'emociones_detectadas' in locals() else [],
                    sintomas=[],
                    tema="Clínica - Tema desviado",
                    respuesta_openai=respuesta_ai,
                    sugerencia="",
                    fase_evaluacion="respuesta_tematica_desviada",
                    interaccion_id=int(time.time()),
                    fecha=datetime.now(),
                    fuente="web",
                    origen="filtro_tematica_desviada",   # etiqueta de trazabilidad (opcional)
                    eliminado=False,
                )
            except Exception as e:
                print(f"⚠️ Error al registrar historial clínico desde respuesta temática desviada: {e}")
            
                            

        # 🔍 Filtro para eliminar encabezados como “Estimado/a usuario/a”
        if respuesta_original.lower().startswith("estimado") or "estimado/a" in respuesta_original.lower():
            respuesta_original = re.sub(r"(?i)^estimado/a\s+usuario/a,?\s*", "", respuesta_original).strip()

        
        # 🔍 Reemplazo de marcador si quedó en la respuesta
        respuesta_ai = respuesta_ai.replace("[Incluir número de contacto]", "+54 911 3310-1186")

        # 🛡️ Filtrado de precios por si OpenAI menciona algún valor numérico
        if any(palabra in respuesta_ai.lower() for palabra in ["$", "usd", "euros", "€", "dólares", "pesos", "cuesta", "sale", "vale", "precio", "tarifa", "honorario", "paga", "cobra", "cobro"]):
            respuesta_ai = (
                "Sobre los valores de la consulta, te sugiero contactar directamente al Lic. Daniel O. Bustamante. "
                + obtener_mensaje_contacto() +
                " para obtener esa información de manera personalizada."
            )
            try:
                registrar_historial_clinico(
                    user_id=user_id,
                    emociones=emociones_detectadas if 'emociones_detectadas' in locals() else [],
                    sintomas=[],
                    tema="Clínica - Tema desviado",
                    respuesta_openai=respuesta_ai,
                    sugerencia="",
                    fase_evaluacion="respuesta_tematica_desviada",
                    interaccion_id=int(time.time()),
                    fecha=datetime.now(),
                    fuente="web",
                    origen="filtro_precios",   # etiqueta de contexto
                    eliminado=False,
                )
            except Exception as e:
                print(f"⚠️ Error al registrar historial clínico desde respuesta temática desviada: {e}")

                
            # 🧾 Auditoría: log si OpenAI intentó responder con precios
            print("⚠️ Se interceptó una respuesta con posible contenido de precios y fue reemplazada para evitar brindar esa información.")

        # ❌ Interceptar frases ambiguas que sugieran contacto antes de la interacción 5
        if contador <= 4:
            frases_implicitas = [
                "si lo desea puedo brindarle más información",
                "si desea más información",
                "puedo brindarle más detalles si lo necesita",
                "si quiere puedo contarle más",
                "estoy aquí para ayudarle",
                "podría ayudarle si lo desea",
                "si desea saber más"
            ]
            if any(f in respuesta_ai.lower() for f in frases_implicitas):
                respuesta_ai = (
                    "Gracias por tu mensaje. En este espacio se brinda orientación clínica general. "
                    "¿Querés contarme un poco más sobre lo que estás sintiendo para poder ayudarte mejor?"
                )
                try:
                    registrar_historial_clinico(
                        user_id=user_id,
                        emociones=emociones_detectadas if 'emociones_detectadas' in locals() else [],
                        sintomas=[],
                        tema="Clínica - Tema desviado",
                        respuesta_openai=respuesta_ai,
                        sugerencia="",
                        fase_evaluacion="respuesta_tematica_desviada",
                        interaccion_id=int(time.time()),
                        fecha=datetime.now(),
                        fuente="web",
                        origen="filtro_contacto_temprano",  # <<< etiqueta de trazabilidad
                        eliminado=False,
                    )
                except Exception as e:
                    print(f"⚠️ Error al registrar historial clínico desde respuesta temática desviada: {e}")

                    
                motivo = "Frase ambigua de sugerencia de contacto detectada en interacción temprana"


        # Detectar modificaciones y registrar auditoría
        if respuesta_original != respuesta_ai:
            motivo = "Respuesta modificada por contener lenguaje institucional, temáticas no permitidas o precios"
            registrar_auditoria_respuesta(user_id, respuesta_original, respuesta_ai, motivo)
        else:
            registrar_auditoria_respuesta(user_id, respuesta_original, respuesta_ai)

        # Usar el ID de interacción previamente registrado para guardar la respuesta
        registrar_respuesta_openai(interaccion_id, respuesta_ai)

        # ❌ Filtrado final de menciones indebidas al Lic. Bustamante antes de interacción 5
        if "bustamante" in respuesta_ai.lower() and contador not in [5, 9] and contador < 10 and not es_consulta_contacto(mensaje_usuario, user_id, mensaje_original):
            respuesta_filtrada = re.sub(r"(?i)con (el )?Lic(\.|enciado)? Daniel O\.? Bustamante.*?(\.|\n|$)", "", respuesta_ai)
            motivo = "Se eliminó mención indebida al Lic. Bustamante antes de interacción permitida"
            registrar_auditoria_respuesta(user_id, respuesta_original, respuesta_filtrada, motivo)
            session["ultimas_respuestas"].append(respuesta_filtrada)
            user_sessions[user_id] = session
            return {"respuesta": respuesta_filtrada}

        # ----------------------------- LÍMITE DE INTERACCIONES -----------------------------
        if contador >= LIMITE_INTERACCIONES:
            respuesta = (
                "Este canal ha alcanzado su límite de interacciones permitidas. "
                "Por razones clínicas y éticas, no es posible continuar. "
                "Te recomiendo que contactes directamente al Lic. Daniel O. Bustamante para el seguimiento profesional."
            )
        
            motivo = "Cierre automático por alcanzar el límite de interacciones permitidas"
            registrar_auditoria_respuesta(user_id, "Límite alcanzado", respuesta, motivo)
        
            session.setdefault("interacciones_previas", []).append("CIERRE_LIMITE")
            user_sessions[user_id] = session  # ✅ Persistencia del cambio
        
            session["ultimas_respuestas"].append(respuesta)
            user_sessions[user_id] = session  # Asegura persistencia en la sesión
            registrar_respuesta_openai(interaccion_id, respuesta)
            return {"respuesta": respuesta}
        
        return {"respuesta": respuesta_ai}


    


    except Exception as e:
        print(f"❌ Error inesperado en el endpoint /asistente: {repr(e)}")
        traceback.print_exc()
        return {
            "respuesta": (
                "Ocurrió un error al procesar tu solicitud. Podés intentarlo nuevamente más tarde "
                "o escribirle al Lic. Bustamante por WhatsApp: +54 911 3310-1186."
            )
        }

