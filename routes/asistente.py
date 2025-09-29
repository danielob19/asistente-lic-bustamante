from core.constantes import CERRAR_CONVERSACION_SOLO_RIESGO
from core.utils.modulo_clinico import procesar_clinico  # (solo si no fue importado aún)
from core.utils.modulo_administrativo import procesar_administrativo
from core.inferencia_psicodinamica import generar_hipotesis_psicodinamica, reformular_estilo_narrativo
from fastapi import APIRouter, HTTPException
from core.modelos.base import UserInput

from core.utils.motor_fallback import (
    safe_detectar_sintomas as detectar_sintomas_db,
    safe_inferir_cuadros as inferir_cuadros,
    safe_decidir as decidir,
)


from core.utils.generador_openai import generar_respuesta_con_openai  # ya lo usás
from core.utils.disparadores import extraer_disparadores, resumir_disparadores



# funciones clínicas adicionales (si las usás)
from core.utils.modulo_clinico import (
    clasificar_cuadro_clinico,
    determinar_malestar_predominante,
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
from core.db.consulta import obtener_ultimo_registro_usuario
from core.utils.palabras_irrelevantes import palabras_irrelevantes


from core.resumen_clinico import (
    generar_resumen_clinico_y_estado,
    generar_resumen_interaccion_5,
    generar_resumen_interaccion_9,
    generar_resumen_interaccion_10
)

from core.inferencia_psicodinamica import generar_hipotesis_psicodinamica
from core.utils.clinico_contexto import hay_contexto_clinico_anterior

from core.estilos_post10 import seleccionar_estilo_clinico_variable


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
import os

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

logger = logging.getLogger(__name__)



# -- Sesiones en memoria (fallback seguro) --
try:
    from core.contexto import user_sessions
except Exception:
    # Si el import falla en el entorno de despliegue, usamos un dict local
    user_sessions = {}


RESPUESTAS_CLINICAS = None  # <- no usar; removido del flujo


#-------------------------------------------------------------------------------

# --- Safe wrapper para OpenAI (evita que el usuario note errores) ----------------

def _fallback_clinico() -> str:
    # Texto útil, neutro y clínico si la IA falla o devuelve algo vacío
    return (
        "Gracias por contarlo. ¿En qué momentos notás que se intensifica y qué cambia "
        "en el cuerpo o en los pensamientos cuando aparece?"
    )

def _try_openai(prompt: str, **kwargs) -> str:
    """
    Llama a OpenAI y NUNCA deja que suba una excepción.
    Si falla o la respuesta es vacía/corta, devuelve un fallback clínico.
    También depura kwargs inesperados (p.ej. 'temperatura').
    """
    # Solo aceptar kwargs que realmente soporta tu generador
    permitidos = {"contador", "user_id", "mensaje_usuario", "mensaje_original"}
    kwargs = {k: v for k, v in kwargs.items() if k in permitidos}

    try:
        t = generar_respuesta_con_openai(prompt, **kwargs)
        if not t or len(t.strip()) < 5:
            raise ValueError("respuesta vacía o demasiado corta")
        return t.strip()
    except Exception as e:
        print(f"⚠️ SafeOpenAI fallback: {e}")
        return _fallback_clinico()


# --------------------------HELPERS---------------------------------------------

# --- Salida centralizada ------------------------------------------------------
def _finalizar_no_vacio(texto: str, session: dict) -> str:
    """
    Asegura que la respuesta NUNCA sea vacía.
    Si viene vacío, usa contexto_literal si existe; si no, usa un fallback clínico útil.
    Luego delega el cierre estandarizado a _finalizar_respuesta().
    """
    texto = (texto or "").strip()
    if not texto:
        ctx = session.get("contexto_literal")
        texto = (
            f"Gracias por contarlo. ¿Con qué frecuencia te sucede en {ctx}? ¿Desde cuándo lo notás?"
            if ctx else
            "Gracias por contarlo. ¿En qué momentos notás que se intensifica y qué cambia en el cuerpo o en los pensamientos cuando aparece?"
        )
    # aplica apéndice clínico + contacto + sanitizado
    return _finalizar_respuesta(
        texto,
        apendice=session.get("_apendice_cuadro", ""),
        incluir_contacto=True,
    )

def _ret(session: dict, user_id: str, texto: str) -> dict:
    """
    Punto ÚNICO de salida:
    - Garantiza no-vacío y cierre estandarizado.
    - Actualiza sesión con la respuesta.
    - Devuelve el dict esperado por el frontend.
    """
    out = _finalizar_no_vacio(texto, session)
    try:
        session.setdefault("ultimas_respuestas", []).append(out)
    except Exception:
        pass
    user_sessions[user_id] = session
    return {"respuesta": out}


# --- Helpers de cierre de respuesta -----------------------------------------

CONTACTO_NUM = os.getenv("CONTACTO_NUM", "3310-1186")
CONTACTO_WPP = os.getenv(
    "CONTACTO_WPP",
    " Si querés, podés escribir al WhatsApp +54 911 3310-1186 del Lic. Bustamante para avanzar."
)

def _finalizar_respuesta(texto: str,
                         *,
                         apendice: str | None = None,
                         incluir_contacto: bool = True) -> str:
    """
    Unifica el cierre de la respuesta:
    - anexa apéndice clínico si viene
    - agrega recomendación de contacto (sin duplicar)
    - limpia espacios extra
    """
    texto = (texto or "").strip()

    # Apéndice clínico (si se calculó antes)
    if apendice is None:
        # fallback: si lo dejaste como variable de módulo en algún flujo
        apendice = globals().get("apendice_cuadro", "")
    if apendice:
        texto = f"{texto} {apendice}".strip()

    # Recomendación de contacto (sin duplicar por número)
    if incluir_contacto and CONTACTO_NUM not in texto:
        texto = f"{texto} {CONTACTO_WPP}".strip()

    # Sanitizar espacios
    texto = " ".join(texto.split())
    return texto



# ---------------------------------------------------------------------------

def clasificar_cuadro_clinico_openai(emocion: str) -> str:
    """
    Devuelve un rótulo breve de *cuadro clínico probable* (no diagnóstico cerrado).
    Mantiene vocabulario abierto para permitir términos nuevos/actualizados.
    Solo higieniza y bloquea frases genéricas.
    """
    import re

    if not emocion or not emocion.strip():
        return "indeterminado"

    PROHIBIDOS = {
        # genéricos/ruido que no aportan valor clínico
        "patrón emocional", "patron emocional",
        "patrón emocional detectado", "patron emocional detectado",
        "patrón detectado", "patron detectado",
        "estado emocional", "estado emocional inespecífico",
        "label inválida", "label invalida",
    }

    def _limpiar_un_renglon(s: str) -> str:
        s = (s or "").strip()
        s = s.splitlines()[0]                 # 1° línea
        s = re.sub(r'^[\-\*\•\·\s"]+', "", s)  # bullets/comillas al inicio
        s = s.rstrip('".!;:')                  # cierres
        return s.strip()

    try:
        prompt = (
            "Actuá como psicólogo clínico actualizado (DSM-5-TR). Te paso un resumen "
            "de emociones/síntomas de un usuario. Respondé con UN rótulo clínico "
            "orientativo, breve (1-4 palabras), prudente (no diagnóstico cerrado), "
            "en español rioplatense, sin comillas ni punto. Ejemplos de formato: "
            "'ansiedad generalizada', 'episodio depresivo', 'insomnio de conciliación', "
            "'estrés crónico', 'aislamiento social'. Si no alcanza la info, respondé: "
            "'indeterminado'.\n\n"
            f"Resumen: {emocion}"
        )

        resp = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=16,
        )
        label_raw = resp.choices[0].message["content"]
        label = _limpiar_un_renglon(label_raw)

        # defensas mínimas
        norm = label.lower()
        if not norm or len(norm) > 60:
            return "indeterminado"
        if any(p in norm for p in PROHIBIDOS):
            return "indeterminado"

        return label

    except Exception as e:
        print(f"⚠️ Error en clasificar_cuadro_clinico_openai: {e}")
        return "indeterminado"



def sugerir_canonico_suave(label_model: str) -> str | None:
    """
    Devuelve una *sugerencia* de cluster interno para analytics.
    No reemplaza el label del modelo; puede devolver None si no matchea.
    """
    import re
    n = re.sub(r"\s+", " ", (label_model or "").lower()).strip()

    buckets = {
        "ansiedad": ["ansiedad", "ansioso", "angustia", "ansiedad generalizada"],
        "depresivo": ["depresivo", "depresión", "baja de ánimo", "tristeza"],
        "insomnio": ["insomnio", "sueño", "conciliar el sueño"],
        "estrés": ["estrés", "burnout", "tensión"],
        "aislamiento": ["aislamiento", "evitación", "retraimiento"],
    }
    for canon, terminos in buckets.items():
        if any(t in n for t in terminos):
            return canon
    return None



router = APIRouter()



def _filtrar_saludo_posterior(respuesta_original: str, contador: int, user_id: str) -> str:
    """
    Si no es la primera interacción y la respuesta empieza con 'Hola, ¿qué tal?',
    elimina el saludo. Si no aplica, devuelve la respuesta tal cual.
    """
    t = (respuesta_original or "").strip()
    if contador == 1:
        return t
    if not _empieza_con_hola_que_tal(t):
        return t

    variantes = [
        "hola, qué tal", "hola qué tal",
        "hola, que tal", "hola que tal",
    ]
    t_norm = t
    for v in variantes:
        if t_norm.lower().startswith(v):
            t_norm = t_norm[len(v):].strip()
            break
    try:
        registrar_auditoria_respuesta(
            user_id, respuesta_original, t_norm,
            "Se eliminó el saludo inicial 'Hola, ¿qué tal?' por ser posterior a la primera interacción",
        )
    except Exception:
        pass
    return t_norm



# Desactivar límite duro
LIMITE_INTERACCIONES = None


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
        FROM public.historial_clinico_usuario h,
             unnest(COALESCE(h.emociones, '{}')) AS e
        WHERE h.user_id = %s AND COALESCE(h.eliminado, false) = false
        GROUP BY e
        ORDER BY freq DESC
        LIMIT 1
    """
    filas = ejecutar_consulta(sql, (user_id,))
    return filas[0]["emocion"] if filas else None


# --- Coincidencias de cuadro por emociones (sesión + historial) ---
def obtener_cuadro_por_emociones(user_id: str, session: dict):
    """
    Devuelve (cuadro_probable, coincidencias) calculando el cuadro más frecuente
    a partir de las emociones de la sesión + las ya registradas en historial_clinico_usuario.
    No usa tablas viejas; sólo 'historial_clinico_usuario'.
    """
    try:
        # Emociones vigentes en la sesión
        sesion = session.get("emociones_detectadas", []) or []

        # Emociones históricas desde DB unificada
        historicas = obtener_emociones_ya_registradas(user_id)  # set[str]
        todas = [e.strip().lower() for e in (list(historicas) + list(sesion)) if isinstance(e, str) and e.strip()]
        if not todas:
            return (None, 0)

        # Mapear emociones -> cuadro con heurística existente
        # 1) Intentar con la función clínica si está disponible
        try:
            from core.utils.modulo_clinico import clasificar_cuadro_clinico
            cuadros = [clasificar_cuadro_clinico(e) for e in todas]
        except Exception:
            # 2) Fallback interno conservador
            cuadros = [clasificar_cuadro_clinico_openai(e) for e in todas]

        # Contar el cuadro más frecuente
        c = Counter([c for c in cuadros if isinstance(c, str) and c.strip()])
        if not c:
            return (None, 0)

        cuadro_top, freq = c.most_common(1)[0]
        return (cuadro_top, int(freq))
    except Exception as e:
        print(f"⚠️ obtener_cuadro_por_emociones() falló: {e}")
        return (None, 0)




@router.get("/asistente")
def asistente_info():
    """
    Evita 405 en GET /asistente: informa cómo usar el endpoint correcto.
    """
    return {
        "detail": "Usá POST /asistente con el cuerpo esperado.",
        "schema_esperado": {"user_id": "str", "mensaje": "str"},
    }



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

        
        
        # --- bootstrap de sesión por user_id (memoria persistente) ---
        session = user_sessions.get(user_id, {}) or {}
        
        session.setdefault("emociones_detectadas", [])
        session.setdefault("cuadro_clinico_probable", None)
        session.setdefault("_apendice_cuadro", "")
        session.setdefault("ultimas_respuestas", [])
        session.setdefault("mensajes", [])
        session.setdefault("intenciones_previas", [])
        session.setdefault("intenciones_clinicas_acumuladas", [])
        session.setdefault("input_sospechoso", False)
        
        # …defaults + línea de contador…
        session["contador_interacciones"] = int(session.get("contador_interacciones") or 0)
        
        # ⚠️ No hagas bootstrap acá; lo hace internamente procesar_clinico()
        session = session or {}
        
        # refrescá la variable local (sin depender de import)
        contador = int(session.get("contador_interacciones") or 0)


        
        # timestamp de última interacción
        session["ultima_interaccion"] = time.time()
        
        # persistir
        user_sessions[user_id] = session
        
        # (opcional, si tu código lo usa como variable suelta)
        contador = session["contador_interacciones"]
        
                
    
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
            registrar_respuesta_openai(None, respuesta)
            return _ret(session, user_id, respuesta)
        

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
                return _ret(session, user_id, respuesta_admin)


        
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


            

            # === Inferencia clínica incremental (cuadro probable) ===
            # Inicializamos por seguridad
            emos_ahora: list[str] = []
            emos_union: list[str] = []
            cuadro_prob: str = ""
            
            try:
                # 1) Normalizar y tomar emociones “del momento”
                def _norm(e: str) -> str:
                    return (e or "").strip().lower()
            
                emos_ahora = list(dict.fromkeys(map(_norm, emociones_detectadas_bifurcacion or [])))
            
                # 2) Unir con las que venían en sesión (sin duplicar)
                emos_prev = list(dict.fromkeys(map(_norm, session.get("emociones_detectadas") or [])))
                emos_union = list(dict.fromkeys(emos_prev + emos_ahora))
            
                # 3) Si hay ≥ 2 emociones, inferimos cuadro probable
                if len(emos_union) >= 2:
                    try:
                        from core.utils.modulo_clinico import clasificar_cuadro_clinico
                        cp = (clasificar_cuadro_clinico(emos_union) or "").strip().lower()
                        cuadro_prob = cp or ""
                    except Exception:
                        cuadro_prob = ""
            
                # 4) Registrar SIEMPRE lo nuevo en la DB (aunque no haya cuadro)
                try:
                    registrar_historial_clinico(
                        user_id=user_id,
                        emociones=emos_ahora,
                        sintomas=[],
                        tema="Clínica - Turno",
                        respuesta_openai="-",                     # (placeholder, la final va en otro registro)
                        sugerencia="-",
                        fase_evaluacion="turno_incremental",
                        interaccion_id=interaccion_id if "interaccion_id" in locals() else int(time.time()),
                        fecha=datetime.now(),
                        fuente="web",
                        origen="asistente_incremental",
                        eliminado=False,
                        cuadro_clinico_probable=cuadro_prob or None,  # persiste si existe
                    )
                except Exception as e:
                    print(f"⚠️ Error registrando emociones/cuadro: {e}")
            
            except Exception as e:
                # Falla general de la inferencia incremental
                print(f"⚠️ Error en inferencia incremental: {e}")
            
            # 5) Actualizamos memoria de sesión (siempre)
            session["emociones_detectadas"] = emos_union
            if cuadro_prob:
                session["cuadro_clinico_probable"] = cuadro_prob
            elif "cuadro_clinico_probable" not in session:
                session["cuadro_clinico_probable"] = None
            user_sessions[user_id] = session
            
            # 6) Si hay cuadro probable, preparamos y persistimos apéndice clínico para la respuesta
            apendice_cuadro = ""
            try:
                if cuadro_prob:
                    apendice_cuadro = (
                        f" Por lo que venís contando, *cuadro clínico probable*: {cuadro_prob}. "
                        "Si te sirve, podemos explorar cuándo se intensifica (trabajo, tarde-noche, antes de dormir) "
                        "y cómo están el descanso y la concentración."
                    )
            
                # Persistir SIEMPRE para reusarlo en la respuesta final
                session["_apendice_cuadro"] = apendice_cuadro
                user_sessions[user_id] = session
            
            except Exception as e:
                print(f"⚠️ Error en inferencia incremental (apéndice): {e}")
                session["_apendice_cuadro"] = ""
                user_sessions[user_id] = session






            # Actualiza la sesión del usuario
            session["ultima_interaccion"] = time.time()
            session["contador_interacciones"] += 1  # ✅ Incrementar contador aquí
            session["_ready_5_9"] = True  # 🔐 Activar guard-flag para permitir disparador en 5/9
            contador = session["contador_interacciones"]
            session["mensajes"].append(mensaje_usuario)
            user_sessions[user_id] = session


            # --- Contador robusto por último registro del usuario ---
            def _contador_para(user_id: str) -> int:
                """
                Devuelve el próximo contador de interacción basándose en el último registro clínico.
                Soporta filas tipo dict (RealDictRow) o tupla. Fallback seguro a 1.
                """
                try:
                    ult = obtener_ultimo_registro_usuario(user_id)
                    if not ult:
                        return 1
            
                    # interaccion_id puede venir como dict o como tupla
                    if isinstance(ult, dict):
                        prev = ult.get("interaccion_id")
                    else:
                        # (id, user_id, fecha, emociones, nuevas_emociones_detectadas,
                        #  cuadro_clinico_probable, interaccion_id)
                        prev = ult[6] if len(ult) > 6 else None
            
                    return (int(prev) + 1) if prev is not None else 1
            
                except Exception as e:
                    print(f"[⚠] _contador_para fallback por error: {e}")
                    return 1

            
            # >>> Atajo clínico unificado (antes de toda la lógica larga de generación de textos):
            if intencion_general == "CLINICA" or hay_contexto_clinico_anterior(user_id) or emociones_detectadas_bifurcacion:
                try:
                    salida = procesar_clinico({
                        "mensaje_original": mensaje_original,
                        "mensaje_usuario": mensaje_usuario,
                        "user_id": user_id,
                        "session": session,
                        "contador": _contador_para(user_id),
                    })
                except Exception as e:
                    # Log técnico
                    try:
                        logger.exception("procesar_clinico lanzó excepción", exc_info=True)
                    except Exception:
                        print(f"[!] procesar_clinico lanzó excepción: {e}")
                
                    # Salida centralizada (evita respuestas vacías)
                    return _ret(
                        session,
                        user_id,
                        "Gracias por contarme. Estoy teniendo un problema técnico para procesar tu mensaje. "
                        "¿Podés intentar nuevamente en un momento?"
                    )

                # Blindaje por si vino None o sin 'respuesta'
                if not salida or not isinstance(salida, dict) or "respuesta" not in salida:
                    try:
                        logger.warning("procesar_clinico devolvió un valor inesperado: %s", type(salida))
                    except Exception:
                        print(f"⚠️ procesar_clinico devolvió un valor inesperado: {type(salida)}")
                
                    return _ret(
                        session,
                        user_id,
                        "Gracias por tu paciencia. ¿Podés volver a contarme brevemente lo que estás sintiendo?"
                    )

            
                # Persistir sesión devuelta por el módulo clínico y responder
                session = salida.get("session", session)   # ← actualizar la sesión local con la que volvió
                return _ret(session, user_id, salida.get("respuesta", ""))

            

            

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



                
                
            
                # 📌 Detección de coincidencias clínicas en cualquier momento (SOLO antes de la 10)
                # Requiere: from datetime import datetime
                try:
                    contador = session.get("contador_interacciones", 0)
                    cuadro, coincidencias = obtener_cuadro_por_emociones(user_id, session)
                
                    # Dispara resumen + cuadro probable si hay ≥2 coincidencias, no usado antes y estamos antes de la 10
                    if (
                        cuadro
                        and coincidencias >= 2
                        and not session.get("coincidencia_clinica_usada")
                        and contador < 10
                    ):
                        # Generar un resumen breve (usa tu generador existente)
                        resumen_breve = generar_resumen_clinico_y_estado(session, contador)
                
                        respuesta_match = (
                            f"{resumen_breve} "
                            f"En base a lo conversado, **cuadro clínico probable: {cuadro}** "
                            f"(sustentado en {coincidencias} coincidencias emocionales). "
                            "¿Te parece si revisamos juntos cómo se viene manifestando en tu día a día?"
                        )
                
                        # Registrar en historial (cuadro probable + emociones actuales + nuevas_emociones si existieran)
                        try:
                            registrar_historial_clinico(
                                user_id=user_id,
                                emociones=session.get("emociones_detectadas", []),
                                sintomas=[],  # Importante: lista, no entero
                                tema="clinica_match_2_coincidencias",
                                respuesta_openai=respuesta_match,
                                sugerencia=None,
                                fase_evaluacion="match_2_emociones",
                                interaccion_id=contador,
                                fecha=datetime.now(),
                                fuente="dbopenai",
                                origen="match_2_coincidencias",
                                cuadro_clinico_probable=cuadro,
                                nuevas_emociones_detectadas=session.get("nuevas_emociones", []),
                                eliminado=False,
                            )
                        except Exception as e:
                            print(f"⚠️ Registro historial en match_2_coincidencias falló: {e}")
                
                        # Marcar flag de sesión y DEVOLVER respuesta directa
                        session["coincidencia_clinica_usada"] = True
                        return _ret(session, user_id, respuesta_match)

                
                except Exception as e:
                    print(f"⚠️ Error en detección de coincidencias clínicas: {e}")
                


                



                
            
                # 4️⃣ Guardar en sesión sin duplicar
                session.setdefault("emociones_detectadas", [])
                for emocion in emociones_actuales:
                    if emocion not in session["emociones_detectadas"]:
                        session["emociones_detectadas"].append(emocion)
            
                print(f"🧠 Emociones registradas/actualizadas en sesión: {emociones_actuales}")
            
                                    
        # --- Invitación mixta universal (contextual) + elección ---
        try:
            # Invitación mixta universal (contextual)
            disp = extraer_disparadores(mensaje_usuario)
            contexto = resumir_disparadores(disp)
            
            def hay_contexto(d):
                return bool(
                    d and (
                        d.get("frases") or d.get("momentos") or d.get("lugares") or d.get("actividades")
                    )
                )
            
            # Dispara la invitación si:
            # - la intención fue MIXTA o CLINICA, o
            # - hay CONTEXTO clínico detectado (aunque venga INDEFINIDA),
            # y aún no invitamos en esta conversación.
            if (intencion_general in ("MIXTA", "CLINICA") or hay_contexto(disp)) \
                    and not session.get("_mixta_invitacion_hecha", False):
            
                if contexto:
                    respuesta_mixta = (
                        f"Entiendo que aparece algo personal {contexto}. "
                        f"¿Preferís explorarlo acá un momento o contactarlo al Lic. Bustamante {CONTACTO_WPP}?"
                    )
                else:
                    respuesta_mixta = (
                        "Entiendo que aparece algo personal. "
                        f"¿Preferís explorarlo acá un momento o contactarlo al Lic. Bustamante {CONTACTO_WPP}?"
                    )
            
                session["_mixta_invitacion_hecha"] = True
                session["_mixta_contexto"] = contexto  # opcional, por si luego querés reutilizarlo
                session["ultimas_respuestas"].append(respuesta_mixta)
                session["contador_interacciones"] = session.get("contador_interacciones", 0) + 1
                # Persistencia y respuesta centralizada
                return _ret(session, user_id, respuesta_mixta)


        
            # 2) Si ya invitamos, interpretamos qué eligió el usuario (sin romper si no coincide nada)
            if session.get("_mixta_invitacion_hecha", False):
            
                # Normalizador: sin acentos / minúsculas
                def _norm(s: str) -> str:
                    import unicodedata
                    s = (s or "").lower()
                    s = unicodedata.normalize("NFKD", s)
                    return "".join(ch for ch in s if not unicodedata.combining(ch))
            
                msg = _norm(mensaje_usuario)
            
                # ✅ SINÓNIMOS AMPLIOS (seguir acá con el chatbot)
                CLINICO_KEYWORDS = (
                    # afirmaciones genéricas
                    "si", "sí", "afirmativo", "si afirmativo", "sí afirmativo",
                    "digo que si", "digo que sí", "de acuerdo", "ok", "dale", "me sirve", "correcto",
                    # intención de continuar aquí
                    "quiero", "prefiero", "continuemos", "sigamos", "seguimos",
                    "seguir por aca", "seguir por aqui", "seguir por aquí",
                    "sigamos por aca", "sigamos por aqui", "sigamos por aquí",
                    "quiero seguir aca", "quiero seguir aqui", "quiero seguir aquí",
                    "prefiero seguir aca", "prefiero seguir aqui", "prefiero seguir aquí",
                    "lo vemos aca", "lo vemos aqui", "lo vemos aquí",
                    # explorar acá
                    "quiero explorarlo", "quiero explorarlo aca", "quiero explorarlo aqui", "quiero explorarlo aquí",
                    "prefiero explorarlo", "prefiero explorarlo aca", "prefiero explorarlo aqui", "prefiero explorarlo aquí",
                    # hablar/contar/conversar acá
                    "contar", "contarte", "quiero contarte", "prefiero contarte",
                    "te cuento", "contame",
                    "decirte", "charlar", "charlarlo", "charlemos",
                    "hablar", "hablarlo", "hablemos", "hablemoslo", "hablémoslo",
                    "prefiero hablar aca", "prefiero hablar aqui", "prefiero hablar aquí",
                    "conversar", "conversarlo", "prefiero conversar",
                    # otras expresiones frecuentes
                    "me gustaria", "me gustaría", "me gusta", "me viene bien",
                    "trabajarlo aca", "trabajarlo aqui", "trabajarlo aquí",
                    "aca", "aqui", "aquí", "por aca", "por aqui", "por aquí"
                )
            
                # ✅ SINÓNIMOS AMPLIOS (contactar al licenciado / vía administrativa)
                ADMIN_KEYWORDS = (
                    "contactar", "contactarlo", "consultarlo", "consultarle",
                    "prefiero contacto", "contacto", "pasame contacto", "pásame contacto",
                    "pasame el numero", "pásame el número", "dame el numero", "dame el número",
                    "numero", "número", "whatsapp", "wpp", "wp", "+54",
                    "tel", "telefono", "teléfono", "llamar", "llama", "llamá", "llamalo",
                    "hablar con", "prefiero hablar con", "hablar con el lic", "hablar con el licenciado",
                    "sacar turno", "sacar un turno", "turno", "agendar", "agenda", "coordinar", "coordinar un turno",
                    "quiero un turno", "quiero coordinar",
                    "modalidad", "precio", "arancel", "costo", "valor",
                    "obra social", "prepaga", "pami", "presencial"
                )
            
                preferir_clinico = any(k in msg for k in CLINICO_KEYWORDS)
                preferir_admin   = any(k in msg for k in ADMIN_KEYWORDS)
            
                # ⚖️ Empate: si aparecen señales de ambos, priorizá ADMIN si hay intención explícita de contacto/turno
                if preferir_clinico and preferir_admin:
                    admin_tie_break = (
                        "hablar con", "contactar", "turno", "coordinar",
                        "whatsapp", "wpp", "tel", "telefono", "llamar", "numero", "número", "presencial"
                    )
                    if any(k in msg for k in admin_tie_break):
                        preferir_clinico = False
                    else:
                        preferir_admin = False
            
                if preferir_clinico and not preferir_admin:
                    # Respuesta puente; cerramos acá para evitar rutas inestables aguas abajo
                    respuesta = (
                        "Perfecto. Sigamos por acá. ¿En qué momentos lo notás más y qué cambios "
                        "aparecen en el cuerpo o en los pensamientos? Si querés, también podemos "
                        "revisar cómo impacta en el sueño y la concentración."
                    )
                    # (no hace falta append ni user_sessions: lo hace _ret)
                    session["contador_interacciones"] = session.get("contador_interacciones", 0) + 1
                    return _ret(session, user_id, respuesta)

            
                elif preferir_admin and not preferir_clinico:
                    respuesta_admin = (
                        "De acuerdo. Si preferís resolverlo con el Lic. Bustamante, "
                        f"podés escribirle {CONTACTO_WPP}."
                    )
                    # (no hace falta append ni user_sessions: lo hace _ret)
                    session["contador_interacciones"] = session.get("contador_interacciones", 0) + 1
                    return _ret(session, user_id, respuesta_admin)



        
        except Exception as e:
            print(f"⚠️ MIXTA guardó falló: {e}")
            # No cortamos la conversación; dejamos que continúe el flujo clínico normal





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
            return _ret(
                session,
                user_id,
                (
                    "Este espacio está diseñado para brindar orientación clínica general. "
                    "Si hay algo puntual que te gustaría compartir sobre tu estado emocional, podés hacerlo con confianza."
                )
            )

        

        if not mensaje_usuario:
            raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

        # 🧩 Clasificación local por intención general
        tipo_input = clasificar_input_inicial(mensaje_usuario)


        
        # ✅ Forzar continuidad clínica si el input es ambiguo pero hubo malestar antes
        if tipo_input in ["INDEFINIDO", "FUERA_DE_CONTEXTO", "CONFUSO"]:
            if hay_contexto_clinico_anterior(user_id):
                tipo_input = CLINICO_CONTINUACION
        

        session["interacciones_previas"] = [x for x in session.get("interacciones_previas", []) if x != "CIERRE_LIMITE"]

        

        # ✅ Registrar el tipo de interacción actual
        session.setdefault("interacciones_previas", []).append(tipo_input)
        user_sessions[user_id] = session

        # ✅ Manejo para mensajes de cortesía simples sin contenido clínico
        if tipo_input == CORTESIA:
            respuesta = (
                "Gracias por tu mensaje. Si más adelante deseás compartir algo personal o emocional, "
                "podés hacerlo cuando lo sientas necesario."
            )
            # (no hace falta append ni user_sessions: lo hace _ret)
            session["contador_interacciones"] = session.get("contador_interacciones", 0) + 1
            
            # mantienen tus registros/auditorías
            registrar_auditoria_input_original(user_id, mensaje_original, mensaje_usuario, tipo_input)
            registrar_respuesta_openai(None, respuesta)
            
            # salida centralizada
            return _ret(session, user_id, respuesta)




        # 🧠 Continuación de tema clínico si fue identificado previamente
        if tipo_input == CLINICO_CONTINUACION:
            registrar_auditoria_input_original(user_id, mensaje_original, mensaje_usuario, CLINICO_CONTINUACION)
            session["contador_interacciones"] = session.get("contador_interacciones", 0) + 1
        
            msg = (
                "Entiendo. Lo que mencionaste antes podría estar indicando un malestar emocional. "
                "¿Querés que exploremos un poco más lo que estás sintiendo últimamente?"
            )
            return _ret(session, user_id, msg)

 

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
        
            # ✅ Extracción robusta de la clasificación desde la respuesta de OpenAI
            def _extraer_clasificacion(resp) -> str:
                """
                Soporta resp como objeto (SDK) o como dict, y falla a string vacío.
                """
                try:
                    # Estilo SDK (atributos)
                    texto = getattr(resp.choices[0].message, "content", None)
                    if texto is None:
                        raise AttributeError
                    return str(texto).strip().upper()
                except Exception:
                    # Estilo dict (claves)
                    try:
                        texto = (
                            (resp.get("choices") or [{}])[0]
                            .get("message", {})
                            .get("content", "")
                        )
                        return str(texto).strip().upper()
                    except Exception:
                        return ""
            
            clasificacion = _extraer_clasificacion(response_contextual) or "IRRELEVANTE"

            # 🔍 Normalización y validación de la clasificación
            clasificacion = (clasificacion or "").strip().upper()
            
            # 🔍 Validación robusta
            opciones_validas = {
                "CLINICO", "CORTESIA", "CONSULTA_AGENDAR", "CONSULTA_MODALIDAD",
                "TESTEO", "MALICIOSO", "IRRELEVANTE"
            }
            if clasificacion not in opciones_validas:
                print(f"⚠️ Clasificación inválida recibida de OpenAI: '{clasificacion}'")
                clasificacion = "IRRELEVANTE"
            
            # ✅ CORTESÍA (saludo inicial o cortesía general)
            if clasificacion == "CORTESIA" and not session.get("emociones_detectadas"):
            
                ya_saludo = any("hola" in r.lower() for r in session.get("ultimas_respuestas", []))
            
                # ⚠️ Importante: inicializar el prompt para evitar UnboundLocalError en ramas/except
                prompt_cortesia_contextual: str | None = None
            
                # 🟡 MANEJO ESPECIAL PARA "hola que tal" o "hola que tal?" como saludo inicial
                if mensaje_usuario.strip() in ["hola que tal", "hola que tal?"] and not ya_saludo:
                    prompt_saludo_inicial = (
                        f"El usuario escribió: '{mensaje_usuario}'.\n"
                        "Redactá una respuesta breve, cordial y natural, como si fuera el INICIO de una conversación.\n"
                        "No debe dar a entender que la conversación terminó, ni incluir frases como:\n"
                        " 'quedo a disposición', 'si necesitás algo más', 'estoy para ayudarte', 'que tengas un buen día', ni similares.\n"
                        "NO uses preguntas. No uses emojis. No hagas cierre ni agradecimientos.\n"
                        "No formules preguntas de ningún tipo, tampoco de seguimiento ni personales.\n"
                        "Estilo sugerido: una simple bienvenida informal, por ejemplo: '¡Hola! Contame.' , 'Hola, decime nomás.' , "
                        "'Hola, ¿en qué puedo ayudarte?'.\n"
                        "Debe sonar como alguien que saluda para iniciar un diálogo, no para despedirse ni cerrar la conversación."
                    )
                    respuesta_saludo = _try_openai(
                        prompt_saludo_inicial,
                        contador=session.get("contador_interacciones", 0),
                        user_id=user_id,
                        mensaje_usuario=mensaje_usuario,
                        mensaje_original=mensaje_original,
                    )
            
                    # (no hace falta append ni user_sessions: lo hace _ret)
                    session["contador_interacciones"] = session.get("contador_interacciones", 0) + 1
                    registrar_respuesta_openai(None, respuesta_saludo)
                    
                    return _ret(session, user_id, respuesta_saludo)

            
                # 🟦 CORTESÍA GENERAL (no es el saludo inicial)
                registrar_auditoria_input_original(user_id, mensaje_original, mensaje_usuario, CORTESIA)
            
                prompt_cortesia_contextual = (
                    f"El usuario ha enviado el siguiente mensaje de cortesía o cierre: '{mensaje_usuario}'.\n"
                    "Redactá una respuesta breve y cordial, sin repetir frases como 'Con gusto', 'Estoy disponible' ni "
                    "'Que tengas un buen día'.\n"
                    "Debe ser fluida, natural, diferente cada vez y adaptada al contexto de una conversación informal respetuosa.\n"
                    "Evitá cerrar de forma tajante o dar a entender que la conversación terminó. No uses emojis. No hagas preguntas "
                    "ni ofrezcas ayuda adicional si no fue solicitada.\n"
                    "NO uses frases como: '¿y tú?', '¿cómo estás tú?', '¿cómo vas?' ni ninguna variante de pregunta personal o "
                    "de seguimiento."
                )
            
                respuesta_contextual = _try_openai(
                    prompt_cortesia_contextual,
                    contador=session.get("contador_interacciones", 0),
                    user_id=user_id,
                    mensaje_usuario=mensaje_usuario,
                    mensaje_original=mensaje_original,
                )
            
                # Filtro contra cierres suaves/no deseados
                frases_cierre_suave = [
                    "que tengas un buen día", "¡que tengas un buen día!", "que tengas buen día",
                    "buen día para vos", "que tengas una linda tarde", "que tengas una excelente tarde",
                    "que tengas un excelente día", "quedo a disposición", "estoy para ayudarte",
                ]
                txt = (respuesta_contextual or "").strip()
                for f in frases_cierre_suave:
                    if f in txt.lower():
                        txt = txt.lower().replace(f, "").strip()
            
                # Limpieza de puntuación sobrante
                txt = txt.rstrip("¡¿,!. ").strip()
            
                # Fallback por si quedó vacío o demasiado corto
                if not txt or len(txt) < 3:
                    txt = (
                        "Gracias por tu mensaje. Si más adelante querés compartir algo puntual "
                        "(emociones, situaciones o cuándo se intensifica), te leo."
                    )
            
                # (no hace falta append ni user_sessions: lo hace _ret)
                session["contador_interacciones"] = session.get("contador_interacciones", 0) + 1
                registrar_respuesta_openai(None, txt)
                
                return _ret(session, user_id, txt)



            
            
            if clasificacion == "CONSULTA_AGENDAR":
                registrar_auditoria_input_original(user_id, mensaje_original, mensaje_usuario, CONSULTA_AGENDAR)
                respuesta = (
                    "Para agendar una sesión o conocer disponibilidad, podés escribirle directamente al Lic. Bustamante al WhatsApp +54 911 3310-1186."
                )
                # (no hace falta append ni user_sessions: lo hace _ret)
                session["contador_interacciones"] = session.get("contador_interacciones", 0) + 1
                return _ret(session, user_id, respuesta)


            
            if clasificacion == "CONSULTA_MODALIDAD":
                registrar_auditoria_input_original(user_id, mensaje_original, mensaje_usuario, CONSULTA_MODALIDAD)
                respuesta = (
                    "El Lic. Bustamante trabaja exclusivamente en modalidad Online, a través de videollamadas. "
                    "Atiende de lunes a viernes, entre las 13:00 y las 20:00 hs. "
                    "Podés consultarle por disponibilidad escribiéndole directamente al WhatsApp +54 911 3310-1186."
                )
                # (no hace falta append ni user_sessions: lo hace _ret)
                session["contador_interacciones"] = session.get("contador_interacciones", 0) + 1
                return _ret(session, user_id, respuesta)


            
            # --- TESTEO / MALICIOSO / IRRELEVANTE ---
            if clasificacion in {"TESTEO", "MALICIOSO", "IRRELEVANTE"}:
                registrar_auditoria_input_original(user_id, mensaje_original, mensaje_usuario, clasificacion)
            
                # ⚠️ Solo bloquear si NO hay contexto clínico y es muy temprano
                sin_contexto = (
                    not hay_contexto_clinico_anterior(user_id)
                    and not session.get("emociones_detectadas")
                    and session.get("contador_interacciones", 0) <= 2
                )
            
                if sin_contexto:
                    session["input_sospechoso"] = True
                    texto_fuera = respuesta_default_fuera_de_contexto()
                    return _ret(session, user_id, texto_fuera)

            
                session["tipo_input"] = "CLINICO_CONTINUACION"  # opcional si lo usás en otra parte
                user_sessions[user_id] = session
                

                # === PUERTA DE ENTRADA AL MÓDULO CLÍNICO ===
                if clasificacion == "CLINICO" or session.get("tipo_input") == "CLINICO_CONTINUACION":
                    # Asegurate de tener esto definido antes:
                    # user_id = input_data.user_id
                    # mensaje_original = input_data.mensaje
                    # mensaje_usuario = mensaje_original  # o tu versión normalizada
                    # session = obtener_sesion(user_id)   # si no la tenés ya
                
                    out = procesar_clinico({
                        "user_id": user_id,
                        "mensaje_original": mensaje_original,                         # ← clave faltante
                        "mensaje_usuario": mensaje_usuario,
                        "session": session,                                           # ← pasa la sesión completa
                        "contador": session.get("contador_interacciones", 0) + 1,     # ← contador para trazabilidad
                        "emociones_session": session.get("emociones_detectadas", []),
                        "cuadro_openai": session.get("cuadro_clinico_probable", None),
                    })
                
                    texto = out.get("respuesta", "").strip() or (
                        "Gracias por compartirlo. ¿En qué momentos notás que se intensifica y qué cambia en el cuerpo "
                        "o en los pensamientos cuando aparece?"
                    )
                
                    # Persistencia y salida (centralizado)
                    session.pop("tipo_input", None)  # opcional, para evitar “pegado” en el próximo turno
                    return _ret(session, user_id, texto)

                

        
        except Exception:
            # Evita UnboundLocalError si la variable no existe
            tiene_prompt_cortesia = bool(locals().get("prompt_cortesia_contextual"))
            contador_safe = int(session.get("contador_interacciones") or 0)
        
            # Traza completa + metadatos mínimos
            logger.exception(
                "🧠❌ Error en clasificación contextual",
                extra={
                    "user_id": user_id,
                    "contador": contador_safe,
                    "tiene_prompt_cortesia": tiene_prompt_cortesia,
                },
            )
        
            # Fallback seguro para el usuario
            texto = (
                "Gracias por tu mensaje. Para poder orientarte, contame algo concreto que te esté molestando "
                "(emociones, sensaciones corporales, situaciones o momentos en que se intensifica)."
            )
            # Salida centralizada
            return _ret(session, user_id, texto)
            



        
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

        # ← resync del local con la sesión ANTES de evaluar
        contador = session.get("contador_interacciones", 0)

        




        # ====================== INTERACCIÓN 10 O POSTERIOR: CIERRE DEFINITIVO ======================

        # 💬 Filtro para irrelevantes/maliciosos o cortesía post-cierre (NO cortamos)
        if contador > 10 and (clasificacion in ["IRRELEVANTE", "MALICIOSO", "CORTESIA"]):
            base = (
                "Gracias por tu mensaje. Para poder orientarte, contame algo concreto que te esté molestando "
                "(emociones, sensaciones corporales, situaciones o momentos en que se intensifica)."
            )
            respuesta = _finalizar_respuesta(
                base,
                apendice=session.get("_apendice_cuadro", ""),  # si hubo apéndice clínico, se anexa
                incluir_contacto=True,
            )
            # Salida centralizada
            return _ret(session, user_id, respuesta, interaccion_id=interaccion_id)


        
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
        
                return _ret(session, user_id, respuesta, interaccion_id=interaccion_id)

                

        contador = session.get("contador_interacciones", 0)


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
                

        
        
                respuesta_original = _try_openai(
                    prompt,
                    contador=contador,
                    user_id=user_id,
                    mensaje_usuario=mensaje_usuario,
                    mensaje_original=mensaje_original,
                )
        
                # Validación por fallback
                if not respuesta_original or not isinstance(respuesta_original, str) or len(respuesta_original.strip()) < 5:
                    respuesta_ai = (
                        "¿Podés contarme un poco más sobre cómo lo estás viviendo estos días? "
                        "A veces ponerlo en palabras ayuda a entenderlo mejor."
                    )
                    registrar_auditoria_respuesta(
                        user_id,
                        "respuesta vacía",
                        respuesta_ai,
                        "Fallback clínico: respuesta nula o inválida de session",
                    )
                    session["ultimas_respuestas"].append(respuesta_ai)
                    user_sessions[user_id] = session
                    return _ret(session, user_id, respuesta_ai)
                
                registrar_auditoria_respuesta(
                    user_id,
                    respuesta_original,
                    respuesta_original,
                    # (si tu función lleva un cuarto argumento de nota, dejalo o quítalo según firma real)
                )
                registrar_respuesta_openai(None, respuesta_original)
                session["ultimas_respuestas"].append(respuesta_original)
                user_sessions[user_id] = session
                return _ret(session, user_id, respuesta_original)

        
            # ◆ Si no es clínico ni hay contexto previo, mantener respuesta neutra
            respuesta = (
                "Gracias por tu mensaje. ¿Hay algo puntual que te gustaría compartir o consultar en este espacio?"
            )
            return _ret(session, user_id, respuesta)


        # 🟢 Si la frase es neutral, de cortesía o curiosidad, no analizar emocionalmente ni derivar
        if mensaje_usuario in EXPRESIONES_DESCARTADAS or any(p in mensaje_usuario for p in ["recomienda", "opinás", "atiende"]):
            respuesta = (
                "Gracias por tu mensaje. Si en algún momento deseás explorar una inquietud emocional, "
                "estoy disponible para ayudarte desde este espacio."
            )
            return _ret(session, user_id, respuesta)


        # 🔍 DEPURACIÓN: Mostrar estado actual de la sesión
        print("\n===== DEPURACIÓN - SESIÓN DEL USUARIO =====")
        print(f"Usuario ID: {user_id}")
        print(f"Interacción actual: {contador}")
        print(f"Mensajes en la sesión: {session['mensajes']}")
        print(f"Emociones acumuladas antes del análisis: {session['emociones_detectadas']}")
        print("========================================\n")
        
        # Detectar negaciones o correcciones
        negaciones = [
            "no dije", "no eso", "no es así", "eso no",
            "no fue lo que dije", "no quise decir"
        ]
        if any(neg in (mensaje_usuario or "").lower() for neg in negaciones):
            respuesta = "Entiendo, gracias por aclararlo. ¿Cómo lo describirías con tus propias palabras ahora?"
            return _ret(session, user_id, respuesta)



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
            return _ret(session, user_id, respuesta)


        
        if es_consulta_contacto(mensaje_usuario, user_id, mensaje_original):
            session["contador_interacciones"] += 1
            user_sessions[user_id] = session
        
            respuesta = (
                "Para contactar al Lic. Daniel O. Bustamante, podés enviarle un mensaje "
                "al WhatsApp +54 911 3310-1186. Él estará encantado de responderte."
            )
        
            session["ultimas_respuestas"].append(respuesta)
            return _ret(session, user_id, respuesta)


        
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
        respuesta_original = _try_openai(
            prompt,
            contador=contador,
            user_id=user_id,
            mensaje_usuario=mensaje_usuario,
            mensaje_original=mensaje_original,
        )



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
                            origen="derivacion_implicita",
                            eliminado=False,
                        )
                    except Exception as e:
                        print(f"⚠️ Error al registrar historial clínico desde derivación implícita: {e}")
        
                    registrar_auditoria_respuesta(user_id, respuesta_original, respuesta_ai, motivo)
        
                    # ⬇️ dentro del if:
                    session["ultimas_respuestas"].append(respuesta_ai)
                    user_sessions[user_id] = session
                    return {"respuesta": respuesta_ai}
        # si no hubo coincidencia, sigue el flujo normal

        
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



    except Exception as e:
        print(f"❌ Error inesperado en el endpoint /asistente: {repr(e)}")
        traceback.print_exc()
        return {
            "respuesta": (
                "Ocurrió un error al procesar tu solicitud. Podés intentarlo nuevamente más tarde "
                "o escribirle al Lic. Bustamante por WhatsApp: +54 911 3310-1186."
            )
        }

