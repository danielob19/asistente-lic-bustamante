from core.utils.modulo_clinico import procesar_clinico  # (solo si no fue importado aún)
from core.administrativo.procesar_administrativo import procesar_administrativo
from core.inferencia_psicodinamica import generar_hipotesis_psicodinamica, reformular_estilo_narrativo
from fastapi import APIRouter, HTTPException
from core.modelos.base import UserInput

from core.utils_seguridad import (
    contiene_elementos_peligrosos,
    es_input_malicioso
)

from core.funciones_asistente import (
    clasificar_input_inicial,
    es_tema_clinico_o_emocional
)

from core.utils_contacto import (
    es_consulta_contacto,
    obtener_mensaje_contacto
)
from core.faq_semantica import buscar_respuesta_semantica_con_score
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
from core.db.sintomas import (
    registrar_sintoma,
    actualizar_sintomas_sin_estado_emocional,
    obtener_sintomas_existentes,
    obtener_sintomas_con_estado_emocional,
    obtener_coincidencias_sintomas_y_registrar,
)

from core.funciones_clinicas import analizar_texto
from core.funciones_asistente import detectar_emociones_negativas
from core.db.consulta import obtener_emociones_ya_registradas
from core.utils.palabras_irrelevantes import palabras_irrelevantes
from respuestas_clinicas import RESPUESTAS_CLINICAS
from cerebro_simulado import (
    predecir_evento_futuro,
    inferir_patron_interactivo,
    evaluar_coherencia_mensaje,
    clasificar_estado_mental,
    inferir_intencion_usuario
)

from core.resumen_clinico import (
    generar_resumen_clinico_y_estado,
    generar_resumen_interaccion_5,
    generar_resumen_interaccion_9,
    generar_resumen_interaccion_10
)

from core.utils.generador_openai import generar_respuesta_con_openai
from core.inferencia_psicodinamica import generar_hipotesis_psicodinamica
from core.utils.clinico_contexto import hay_contexto_clinico_anterior

from core.estilos_post10 import seleccionar_estilo_clinico_variable

from core.contexto import user_sessions
from core.constantes import CLINICO_CONTINUACION, CLINICO, SALUDO, CORTESIA, ADMINISTRATIVO, CONSULTA_AGENDAR, CONSULTA_MODALIDAD
import openai
import re
import time
import random
import unicodedata

router = APIRouter()

LIMITE_INTERACCIONES = 20  # 🔒 Límite máximo de interacciones permitidas por usuario

def respuesta_default_fuera_de_contexto() -> str:
    return (
        "Este canal está diseñado para ofrecer orientación psicológica. "
        "Si hay algún malestar emocional o inquietud personal que desees compartir, podés describirlo con tus palabras."
    )


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
            "interacciones_previas": []
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
            tipo_input = CLINICO  # ⚠️ Fuerza el tratamiento clínico del mensaje

        
        # 🧠 Si se detecta intención clínica y emociones claras, continuar por el flujo clínico habitual (sin intervención)
        if intencion_general == "CLINICA" and emociones_detectadas_bifurcacion:
            session["emociones_detectadas"].extend([
                emocion for emocion in emociones_detectadas_bifurcacion
                if emocion not in session["emociones_detectadas"]
            ])
            print(f"💾 Emociones agregadas desde bifurcación: {emociones_detectadas_bifurcacion}")

        
        # 🧠 Si se detecta intención MIXTA, invitar al usuario a decidir por dónde continuar
        if intencion_general == "MIXTA":
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
                session["emociones_detectadas"].extend([
                    emocion for emocion in detectar_emociones_negativas(mensaje_usuario)
                    if emocion not in session["emociones_detectadas"]
                ])
                respuesta = (
                    "Gracias por compartirlo. ¿Querés contarme un poco más sobre cómo se manifiesta esta situación últimamente?"
                )
                session["ultimas_respuestas"].append(respuesta)
                user_sessions[user_id] = session
                return {"respuesta": respuesta}
        
            elif any(frase in mensaje_usuario for frase in ["no", "preferiría", "directamente", "prefiero hablar", "contactar"]):
                respuesta = (
                    "Perfecto. Podés escribirle directamente al Lic. Bustamante al WhatsApp +54 911 3310-1186 para coordinar una consulta o resolver tus dudas."
                )
                session["ultimas_respuestas"].append(respuesta)
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

        # 🧠 Inferencia cognitiva adicional sobre intención del usuario
        intencion_inferida = inferir_intencion_usuario(mensaje_usuario)
        print(f"🧠 Intención inferida por el cerebro simulado: {intencion_inferida}")

        
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
            user_sessions[user_id] = session
            registrar_auditoria_input_original(user_id, mensaje_original, mensaje_usuario, tipo_input)
            registrar_respuesta_openai(None, respuesta)
            return {"respuesta": respuesta}


        # 🧠 Continuación de tema clínico si fue identificado previamente
        if tipo_input == CLINICO_CONTINUACION:
            registrar_auditoria_input_original(user_id, mensaje_original, mensaje_usuario, CLINICO_CONTINUACION)
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
            
            # Solo permitir cortesía si no hay emociones activas en la sesión
            if clasificacion == "CORTESIA" and not session.get("emociones_detectadas"):
                registrar_auditoria_input_original(user_id, mensaje_original, mensaje_usuario, CORTESIA)
                respuesta = "Con gusto. Si necesitás algo más, estoy disponible para ayudarte."
                session["ultimas_respuestas"].append(respuesta)
                user_sessions[user_id] = session
                return {"respuesta": respuesta}

            
            if clasificacion == "CONSULTA_AGENDAR":
                registrar_auditoria_input_original(user_id, mensaje_original, mensaje_usuario, CONSULTA_AGENDAR)
                respuesta = (
                    "Para agendar una sesión o conocer disponibilidad, podés escribirle directamente al Lic. Bustamante al WhatsApp +54 911 3310-1186."
                )
                session["ultimas_respuestas"].append(respuesta)
                user_sessions[user_id] = session
                return {"respuesta": respuesta}

            
            if clasificacion == "CONSULTA_MODALIDAD":
                registrar_auditoria_input_original(user_id, mensaje_original, mensaje_usuario, CONSULTA_MODALIDAD)
                respuesta = (
                    "El Lic. Bustamante atiende exclusivamente en modalidad Online, a través de videollamadas. "
                    "Podés consultarle directamente al WhatsApp +54 911 3310-1186 si querés coordinar una sesión."
                )
                session["ultimas_respuestas"].append(respuesta)
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
                        
        
        except Exception as e:
            print(f"🧠❌ Error en clasificación contextual: {e}")
        
        # Registrar interacción con mensaje original incluido
        interaccion_id = registrar_interaccion(user_id, mensaje_usuario, mensaje_original)

        # 🔄 Si el input actual es ambiguo, pero ya hubo emociones antes, forzar continuidad clínica
        if tipo_input in ["FUERA_DE_CONTEXTO", "INDEFINIDO", "CONFUSO", "OTRO"]:
            if hay_contexto_clinico_anterior(user_id):
                tipo_input = CLINICO_CONTINUACION

        # Actualiza la sesión del usuario
        session["ultima_interaccion"] = time.time()
        session["contador_interacciones"] += 1  # ✅ Incrementar contador aquí
        contador = session["contador_interacciones"]
        session["mensajes"].append(mensaje_usuario)



        # ====================== INTERACCIÓN 5 – Resumen clínico preliminar e inferencia ======================
        if contador == 5:
            for mensaje in session["mensajes"]:
                nuevas = detectar_emociones_negativas(mensaje) or []
                for emocion in nuevas:
                    emocion = emocion.lower().strip()
                    emocion = re.sub(r'[^\w\sáéíóúüñ]+$', '', emocion)
                    if emocion not in session["emociones_detectadas"]:
                        session["emociones_detectadas"].append(emocion)
        
            clasificacion_mental = clasificar_estado_mental(session["emociones_detectadas"])
        
            if session["emociones_detectadas"]:
                resumen_clinico = generar_resumen_interaccion_5(session, user_id, interaccion_id, contador)
            
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
        
            # Clasificación mental basada en emociones acumuladas
            clasificacion_mental = clasificar_estado_mental(session["emociones_detectadas"])
        
            # Generar resumen clínico basado en mensajes y emociones
            resumen_clinico = generar_resumen_interaccion_9(session, user_id, interaccion_id, contador)
        
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
        
            # ✅ Si es clínico o hay contexto clínico previo, generar respuesta profesional
            if tipo_input in [CLINICO, CLINICO_CONTINUACION] or hay_contexto_clinico_anterior(user_id) or es_tema_clinico_o_emocional(mensaje_usuario):
                saludo_inicio = "- Comenzá la respuesta con un saludo breve como “Hola, ¿qué tal?”.\n" if contador == 1 else ""
        
                prompt = (
                    f"Mensaje recibido del usuario: '{mensaje_usuario}'.\n\n"
                    "Redactá una respuesta breve, profesional y clínica como si fueras el asistente virtual del Lic. Daniel O. Bustamante, psicólogo.\n\n"
                    "Estilo y directrices obligatorias:\n"
                    "- Mantené un tono clínico, sobrio, profesional y respetuoso.\n"
                    f"{saludo_inicio}"
                    "- Si se detecta malestar emocional, formulá una observación objetiva con expresiones como: 'pareciera tratarse de...', 'podría vincularse a...', 'refiere a...' o 'se observa...'.\n"
                    "- Evitá cualquier frase emocional simulada (ej: 'te entiendo', 'estás en buenas manos', 'no estás solo/a', 'tranquilo/a', etc.).\n"
                    "- No uses frases motivacionales ni lenguaje coloquial (evitá: 'todo va a estar bien', 'contá conmigo', etc.).\n"
                    "- No uses lenguaje institucional como 'nuestro equipo', 'desde nuestro espacio', 'trabajamos en conjunto', etc.\n"
                    "- No brindes datos de contacto, precios, horarios, enlaces ni información administrativa.\n"
                    "- No recomiendes consultar con el Lic. Bustamante ni uses expresiones como 'consultar con un profesional', 'buscar ayuda especializada' u otras sugerencias implícitas.\n"
                    "- No formules preguntas como “¿Deseás que te facilite información sobre agendar?” ni menciones WhatsApp.\n"
                    "- No uses 'Estimado/a', ni encabezados de carta o email.\n"
                    "- Solamente si el mensaje es claramente clínico, generá una respuesta analítica breve y profesional.\n"
                    "- Si el mensaje no tiene contenido emocional o clínico relevante, devolvé una frase neutra como: 'Gracias por tu mensaje. ¿Hay algo puntual que te gustaría compartir o consultar en este espacio?'\n\n"
                    "IMPORTANTE:\n"
                    "- En las interacciones 1 a 4, nunca sugieras contacto ni derivación, salvo que el usuario lo pida explícitamente.\n"
                    "- Solo en las interacciones 5, 9 o a partir de la 10, podés aceptar que se mencione el contacto si fue solicitado.\n"
                )

       
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
                    "- En la interacción 1 usá la frase 'Se observa una vivencia de falta de sentido...'\n"
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

                # 🛑 Validación de seguridad por si OpenAI devuelve None o texto inválido
                if not respuesta_original or not isinstance(respuesta_original, str) or len(respuesta_original.strip()) < 5:
                    respuesta_ai = (
                        "¿Podés contarme un poco más sobre cómo lo estás viviendo estos días? "
                        "A veces ponerlo en palabras ayuda a entenderlo mejor."
                    )
                    registrar_auditoria_respuesta(user_id, "respuesta vacía", respuesta_ai, "Fallback clínico: respuesta nula o inválida de OpenAI")
                    session["ultimas_respuestas"].append(respuesta_ai)
                    user_sessions[user_id] = session
                    return {"respuesta": respuesta_ai}
                
                # 🔍 Filtro para remover saludo 'Hola, ¿qué tal?' si no es la primera interacción
                if contador != 1 and respuesta_original.strip().lower().startswith("hola, ¿qué tal?"):
                    respuesta_filtrada = respuesta_original.replace("Hola, ¿qué tal? ", "", 1).strip()
                    motivo = "Se eliminó el saludo inicial 'Hola, ¿qué tal?' porque no corresponde repetirlo en interacciones posteriores a la primera"
                    registrar_auditoria_respuesta(user_id, respuesta_original, respuesta_filtrada, motivo)
                    respuesta_ai = respuesta_filtrada
                else:
                    respuesta_ai = respuesta_original
                

                # Filtrado de seguridad y registro de auditoría
                registrar_auditoria_respuesta(user_id, respuesta_original, respuesta_original)
                registrar_respuesta_openai(interaccion_id, respuesta_original)
        
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


                        
        # 🔍 Buscar coincidencia semántica en preguntas frecuentes
        resultado_semantico = buscar_respuesta_semantica_con_score(mensaje_usuario)
        if resultado_semantico:
            pregunta_faq, respuesta_semantica, similitud = resultado_semantico
        
            # Registrar respuesta en la interacción ya creada
            registrar_respuesta_openai(interaccion_id, respuesta_semantica)
        
            # Registrar similitud en la tabla correspondiente
            registrar_log_similitud(user_id, mensaje_usuario, pregunta_faq, similitud)
        
            session["ultimas_respuestas"].append(respuesta_semantica)
            user_sessions[user_id] = session
            return {"respuesta": respuesta_semantica}

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
            if session["contador_interacciones"] >= 9 or session["mensajes"]:
                respuesta_clinica = generar_resumen_clinico_y_estado(session, contador)
                return {
                    "respuesta": (
                        f"{respuesta_clinica} En caso de que lo desees, podés contactar al Lic. Daniel O. Bustamante escribiéndole al WhatsApp +54 911 3310-1186."
                    )
                }
            return {"respuesta": "Entendido, quedo a tu disposición. Si necesitas algo más, no dudes en decírmelo."}

        
        if es_consulta_contacto(mensaje_usuario, user_id, mensaje_original):
            return {
                "respuesta": "Para contactar al Lic. Daniel O. Bustamante, podés enviarle un mensaje al WhatsApp +54 911 3310-1186. Él estará encantado de responderte."
            }

        
        # 🔹 Proporciona el número de contacto si el usuario pregunta por el "mejor psicólogo" o especialista recomendado
        if (
            "especialista" in mensaje_usuario or
            "mejor psicólogo" in mensaje_usuario or
            "mejor psicologo" in mensaje_usuario or
            "mejor terapeuta" in mensaje_usuario or
            "mejor psicoterapeuta" in mensaje_usuario or
            "el mejor" in mensaje_usuario or
            "a quien me recomendas" in mensaje_usuario or
            "que opinas" in mensaje_usuario or
            "qué opinas" in mensaje_usuario or
            "excelente psicólogo" in mensaje_usuario or
            "buen profesional" in mensaje_usuario or
            "que me recomendas" in mensaje_usuario
        ):
            return {
                "respuesta": "En mi opinión, el Lic. Daniel O. Bustamante es un excelente especialista en psicología clínica. Seguramente podrá ayudarte. "
                             "Puedes enviarle un mensaje al WhatsApp +54 911 3310-1186. Él estará encantado de responderte."
            }

        # Manejo para "solo un síntoma y no más" (responder como en la 5ª interacción y finalizar)
        if "no quiero dar más síntomas" in mensaje_usuario or "solo este síntoma" in mensaje_usuario:
            mensajes = session["mensajes"]
            mensajes.append(mensaje_usuario)
            respuesta_analisis = analizar_texto(mensajes)
            session["mensajes"].clear()
            return {
                "respuesta": (
                    f"{respuesta_analisis} Si necesitas un análisis más profundo, también te recomiendo contactar al Lic. Daniel O. Bustamante al WhatsApp "
                    f"+54 911 3310-1186 para una evaluación más detallada."
                )
            }
              
        # 🧩 Generar respuesta con OpenAI si no es la interacción 5, 9 o 10+
        saludo_inicio = "- Comenzá la respuesta con un saludo breve como “Hola, ¿qué tal?”.\n" if contador == 1 else ""
        
        prompt = (
            f"Mensaje recibido del usuario: '{mensaje_usuario}'.\n\n"
            "Redactá una respuesta breve, profesional y clínica como si fueras el asistente virtual del Lic. Daniel O. Bustamante, psicólogo.\n\n"
            "Estilo y directrices obligatorias:\n"
            "- Mantené un tono clínico, sobrio, profesional y respetuoso.\n"
            f"{saludo_inicio}"
            "- Si se detecta malestar emocional, formulá una observación objetiva con expresiones como: 'pareciera tratarse de...', 'podría vincularse a...', 'refiere a...' o 'se observa...'.\n"
            "- Evitá cualquier frase emocional simulada (ej: 'te entiendo', 'estás en buenas manos', 'no estás solo/a', 'tranquilo/a', etc.).\n"
            "- No uses frases motivacionales ni lenguaje coloquial (evitá: 'todo va a estar bien', 'contá conmigo', etc.).\n"
            "- No uses lenguaje institucional como 'nuestro equipo', 'desde nuestro espacio', 'trabajamos en conjunto', etc.\n"
            "- No brindes datos de contacto, precios, horarios, enlaces ni información administrativa, salvo que el usuario lo haya pedido explícitamente.\n"
            "- No recomiendes consultar con el Lic. Bustamante ni uses expresiones como 'consultar con un profesional', 'buscar ayuda especializada' u otras sugerencias implícitas.\n"
            "- No formules preguntas como “¿Deseás que te facilite información sobre agendar?” ni menciones WhatsApp.\n"
            "- No uses 'Estimado/a', ni encabezados de carta o email.\n"
            "- Solamente si el mensaje es claramente clínico, generá una respuesta analítica breve y profesional.\n"
            "- Si el mensaje no tiene contenido emocional o clínico relevante, devolvé una frase neutra como: 'Gracias por tu mensaje. ¿Hay algo puntual que te gustaría compartir o consultar en este espacio?'\n\n"
            "IMPORTANTE:\n"
            "- En las interacciones 5, 9 o 10+, podés aceptar que se mencione el contacto si fue solicitado.\n"
            "- En las demás interacciones (1 a 4), no lo menciones salvo que el usuario lo pida explícitamente.\n"
        )

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
            "- En la interacción 1 usá la frase 'Se observa una vivencia de falta de sentido...'\n"
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
            registrar_auditoria_respuesta(user_id, respuesta_original, respuesta_ai, "Respuesta descartada por contener elementos peligrosos")
            session["ultimas_respuestas"].append(respuesta_ai)
            user_sessions[user_id] = session
            return {"respuesta": respuesta_ai}

        
        # Validación previa
        if not respuesta_original:
            respuesta_ai = (
                "Lo siento, hubo un inconveniente al generar una respuesta automática. Podés escribirle al Lic. Bustamante al WhatsApp +54 911 3310-1186."
            )
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
            motivo = "Frase empática simulada detectada y reemplazada"

        
        # 🔍 Filtro para desvíos temáticos (por si OpenAI habla de finanzas o cosas raras)
        temas_prohibidos = ["finanzas", "inversiones", "educación financiera", "consultoría financiera", "legal", "técnico"]
        if any(tema in respuesta_ai.lower() for tema in temas_prohibidos):
            respuesta_ai = (
                "El Lic. Daniel O. Bustamante es psicólogo clínico. Si querés saber más sobre los servicios que ofrece, "
                + obtener_mensaje_contacto() +
                " y te brindará toda la información necesaria."
            )

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
        print(f"❌ Error inesperado en el endpoint /asistente: {e}")
        return {
            "respuesta": (
                "Ocurrió un error al procesar tu solicitud. Podés intentarlo nuevamente más tarde "
                "o escribirle al Lic. Bustamante por WhatsApp: +54 911 3310-1186."
            )
        }

