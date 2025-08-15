import openai
import re
import time
import unicodedata
import string
from typing import Dict, Any
from datetime import datetime
from datetime import datetime, timedelta  # ← añadimos timedelta para cálculos de reingreso


from core.utils.clinico_contexto import hay_contexto_clinico_anterior
from core.utils_contacto import obtener_mensaje_contacto
from core.funciones_asistente import detectar_emociones_negativas
from core.utils.generador_openai import generar_respuesta_con_openai
from core.constantes import CLINICO, CLINICO_CONTINUACION


from core.db.registro import (
    registrar_respuesta_openai,
    registrar_auditoria_respuesta,
    registrar_interaccion,
    registrar_emocion,
    registrar_emocion_clinica,
    registrar_historial_clinico,   # <- importante
)


from core.db.registro import registrar_historial_clinico

from core.db.sintomas import (
    registrar_sintoma,
    obtener_sintomas_existentes
)

from core.db.consulta import (
    obtener_emociones_ya_registradas,
    obtener_historial_clinico_usuario
)

from core.db.conexion import ejecutar_consulta  # Eliminado user_sessions

# Producción: considerar reingreso a partir de 60 segundos
REINGRESO_SEGUNDOS = 60

def armar_prompt_openai(historial_emociones, nuevas_emociones, ultima_interaccion, nombre_usuario=None):
    resumen = ""
    if historial_emociones:
        resumen += (
            f"El usuario {nombre_usuario or ''} ha consultado previamente por: "
            f"{', '.join(historial_emociones)}.\n"
        )
    if nuevas_emociones:
        resumen += (
            f"En esta interacción expresa: {', '.join(nuevas_emociones)}.\n"
        )
    if ultima_interaccion:
        resumen += f"Último comentario relevante del usuario: '{ultima_interaccion}'.\n"

    prompt = (
        "Sos un asistente clínico digital que acompaña a personas en situaciones emocionales delicadas. "
        "Analizá el siguiente contexto emocional, detectá patrones relevantes y sugerí con empatía posibles líneas de abordaje clínico, "
        "sin emitir diagnósticos tajantes ni frases genéricas.\n\n"
        f"{resumen}\n"
        "1. ¿Qué emociones/síntomas son predominantes en este usuario?\n"
        "2. ¿Cuál podría ser el cuadro o estado anímico principal? (Describilo con cautela, nunca de forma definitiva)\n"
        "3. Sugerí, de forma amable y profesional, si corresponde derivar al Lic. Daniel O. Bustamante, sin forzar la consulta.\n"
        "4. Sugerí en una línea, de modo orientativo y no definitivo, qué cuadro clínico podría estar predominando según la información, usando lenguaje comprensible para el usuario.\n"
        "Por favor, devolvé la respuesta en el siguiente formato JSON:\n"
        "{'emociones_predominantes': [], 'cuadro_clinico': '', 'mensaje_usuario': ''}"
    )
    return prompt




def armar_respuesta_usuario(respuesta_ia_json, emociones_actuales, nombre_usuario=None):
    texto_intro = ""
    if emociones_actuales:
        texto_intro = (
            f"Gracias por compartir lo que sentís. Hasta ahora mencionaste: {', '.join(emociones_actuales)}.\n"
        )
    mensaje_usuario = respuesta_ia_json.get("mensaje_usuario", "").strip()
    recomendacion = (
        "\nRecordá que este espacio no reemplaza la consulta con un profesional. "
        "Si lo deseás, podés escribirle al Lic. Daniel O. Bustamante para un acompañamiento más personalizado."
    )
    respuesta_final = f"{texto_intro}{mensaje_usuario}{recomendacion}"
    return respuesta_final




def normalizar_texto(texto: str) -> str:
    if not texto or not isinstance(texto, str):
        texto = ""
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("utf-8")
    texto = texto.translate(str.maketrans("", "", string.punctuation))
    return texto


def recuperar_historial_clinico(user_id, limite=5):
    query = """
    SELECT fecha, emociones, sintomas, tema, respuesta_openai, sugerencia, fase_evaluacion
    FROM historial_clinico_usuario
    WHERE user_id = %s AND eliminado = FALSE
    ORDER BY fecha DESC
    LIMIT %s
    """
    try:
        resultados = ejecutar_consulta(query, (user_id, limite))
        return resultados or []
    except Exception as e:
        print(f"🔴 Error al recuperar historial clínico: {e}")
        return []

def construir_resumen_historial(historial):
    """
    Construye un resumen seguro del historial clínico evitando KeyError.
    Soporta listas, tuplas y diccionarios.
    """
    temas = []
    for h in historial:
        # Si es lista o tupla y tiene al menos 4 elementos
        if isinstance(h, (list, tuple)) and len(h) > 3:
            if h[3]:
                temas.append(h[3])
        # Si es diccionario y contiene la clave 'tema'
        elif isinstance(h, dict) and "tema" in h:
            if h["tema"]:
                temas.append(h["tema"])

    return temas


# Diccionario de emociones clínicas observables
emociones_clinicas = {
    "angustia": ["angustiado", "angustia"],
    "ansiedad": ["ansioso", "ansiedad", "nervioso", "preocupado"],
    "estrés": ["estresado", "estrés"],
    "tristeza": ["triste", "deprimido", "bajoneado", "vacío"],
}

def detectar_emocion(texto: str) -> str | None:
    texto = texto.lower()
    for emocion, variantes in emociones_clinicas.items():
        for variante in variantes:
            if re.search(rf"\b{re.escape(variante)}\b", texto):
                return emocion
    return None







def procesar_clinico(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flujo clínico alineado a directiva:
      - OpenAI detecta emociones y cuadro probable en cada mensaje clínico.
      - Registrar novedades (emociones nuevas / cuadro) en public.historial_clinico_usuario.
      - Disparador (<10): si hay ≥2 coincidencias (sesión + historial + global) hacia el mismo cuadro → responder con
        resumen breve + 'Cuadro clínico probable', y no repetir en la sesión.
      - Reingreso producción: recordar emociones/cuadro previos si pasaron ≥60s y preguntar por emociones nuevas.
    """
    import json, re
    from datetime import datetime
    # Imports internos para evitar cambiar otros bloques
    from core.db.consulta import (
        obtener_historial_usuario,
        obtener_ultimo_registro_usuario,
        estadistica_global_emocion_a_cuadro,
    )
    from core.db.registro import registrar_novedad_openai
    from core.utils.generador_openai import generar_respuesta_con_openai

    # --- Extraer inputs ---
    mensaje_original = input_data["mensaje_original"]
    mensaje_usuario = input_data["mensaje_usuario"]
    user_id = input_data["user_id"]
    session = input_data["session"]
    contador = int(input_data["contador"])

    # --- Utilidades locales ---
    def _limpiar_lista_str(xs):
        if not xs:
            return []
        return [re.sub(r"\s+", " ", x.strip().lower()) for x in xs if isinstance(x, str) and x.strip()]

    def _ask_openai_emociones_y_cuadro(texto_usuario: str):
        prompt = (
            "Analizá el siguiente mensaje clínico de un usuario. "
            "Respondé en JSON con dos claves: "
            "{\"emociones\": [..], \"cuadro_probable\": \"...\"}. "
            "Reglas: solo emociones negativas/relevantes; si no hay, emociones=[] y cuadro_probable=\"\".\n\n"
            f"TEXTO: {texto_usuario}"
        )
        out = generar_respuesta_con_openai(prompt) or '{"emociones": [], "cuadro_probable": ""}'
        try:
            data = json.loads(out)
            emociones = _limpiar_lista_str(data.get("emociones", []))
            cuadro = (data.get("cuadro_probable") or "").strip().lower()
            return emociones, cuadro
        except Exception:
            # fallback robusto: separar por comas / saltos
            emos = [x.strip() for x in re.split(r"[,\n]", out) if x.strip()]
            return _limpiar_lista_str(emos), ""

    def _coincidencias_sesion_historial_global(user_id: str, emociones_sesion, cuadro_openai: str):
        """
        Cuenta coincidencias hacia el mismo cuadro combinando:
          - emociones de la sesión (nuevas)
          - emociones ya registradas en el historial del usuario
          - estadística global emoción→cuadro (solo memoria; no crea etiquetas)
        Devuelve (votos, detalles, cuadro_objetivo).
        """
        emociones_sesion = set(_limpiar_lista_str(emociones_sesion))
        # Historial propio
        hist = obtener_historial_usuario(user_id, limite=200)
        emos_hist = set()
        for r in hist:
            # r = (id, user_id, fecha, emociones, nuevas_emociones_detectadas, cuadro_clinico_probable, interaccion_id)
            for e in (r[3] or []):
                emos_hist.add((e or "").strip().lower())

        # Estadística global: emoción -> {cuadros}
        glob = estadistica_global_emocion_a_cuadro() or []
        map_emo_to_cuadro = {}
        for emocion, cuadro, c in glob:
            if not emocion or not cuadro:
                continue
            map_emo_to_cuadro.setdefault(emocion, set()).add(cuadro)

        objetivo = (cuadro_openai or "").strip().lower()
        votos = 0
        detalles = {"sesion": [], "historial": []}

        # Sesión
        for e in emociones_sesion:
            if objetivo and e in map_emo_to_cuadro and objetivo in map_emo_to_cuadro[e]:
                votos += 1
                detalles["sesion"].append(e)

        # Historial del usuario
        for e in emos_hist:
            if objetivo and e in map_emo_to_cuadro and objetivo in map_emo_to_cuadro[e]:
                votos += 1
                detalles["historial"].append(e)

        return votos, detalles, objetivo

    # --- Estado de sesión ---
    ahora = datetime.now()
    session.setdefault("emociones_detectadas", [])
    session.setdefault("disparo_notificado", False)
    session.setdefault("ultima_fecha", ahora.isoformat())

    # --- 1) Detectar con OpenAI ---
    emociones_openai, cuadro_openai = _ask_openai_emociones_y_cuadro(mensaje_usuario)

    # --- 2) Registrar novedades (memoria persistente única) ---
    emos_prev = set(_limpiar_lista_str(session.get("emociones_detectadas", [])))
    nuevas_emos = [e for e in emociones_openai if e not in emos_prev]

    if emociones_openai or cuadro_openai:
        registrar_novedad_openai(
            user_id=user_id,
            emociones=emociones_openai,
            nuevas_emociones_detectadas=nuevas_emos,
            cuadro_clinico_probable=cuadro_openai or None,
            interaccion_id=contador,
            fuente="openai",
        )

    # Actualizar sesión
    session["emociones_detectadas"] = list(emos_prev.union(emociones_openai))
    session["ultima_fecha"] = ahora.isoformat()

        # 3) Disparador por coincidencias (<10 y aún no notificado)
        texto_out = ""
        if contador < 10 and cuadro_openai and not session.get("disparo_notificado", False):
            # Contar coincidencias priorizando el cuadro devuelto por OpenAI
            # (usa la estadística global de la misma tabla como memoria)
            emociones_union = list(set(_limpiar_lista_str(session.get("emociones_detectadas", [])) + _limpiar_lista_str(emociones_openai)))
            votos, detalles, objetivo = _coincidencias_sesion_historial_global(
                user_id=user_id,
                emociones_sesion=emociones_union,
                cuadro_openai=cuadro_openai
            )
    
            if votos >= 2:
                resumen_breve = ""
                if emociones_openai:
                    resumen_breve += f"En esta interacción se identifican: {', '.join(emociones_openai)}. "
    
                texto_out = f"{resumen_breve}Cuadro clínico probable: **{objetivo}**."
    
                # Registrar explícitamente el suceso de disparo (además del registro previo de novedades)
                registrar_novedad_openai(
                    user_id=user_id,
                    emociones=session.get("emociones_detectadas", []),
                    nuevas_emociones_detectadas=[],
                    cuadro_clinico_probable=objetivo,
                    interaccion_id=contador,
                    fuente="openai_disparo"
                )
    
                # Bandera de sesión para no repetir el disparo
                session["disparo_notificado"] = True
                session["disparo_cuadro"] = objetivo


        # 4) Recordatorio al reconectar (si vuelve luego de un tiempo y trae contenido clínico)
        ultimo = obtener_ultimo_registro_usuario(user_id)
        recordatorio = ""
        if ultimo:
            fecha_ult = ultimo[2]
            try:
                if isinstance(fecha_ult, str):
                    # intento parseo básico ISO
                    fecha_ult_dt = datetime.fromisoformat(fecha_ult.replace("Z", ""))
                else:
                    fecha_ult_dt = fecha_ult
    
                delta = ahora - fecha_ult_dt
                seg = int(delta.total_seconds())
    
                if seg >= REINGRESO_SEGUNDOS and (emociones_openai or cuadro_openai):
                    emos_previas = _limpiar_lista_str(ultimo[3] or [])  # emociones
                    cuadro_prev = (ultimo[5] or "").strip().lower()     # cuadro
    
                    if emos_previas or cuadro_prev:
                        prev = ""
                        if emos_previas:
                            prev += f"Previo se registraron: {', '.join(emos_previas)}. "
                        if cuadro_prev:
                            prev += f"Se había estimado como probable: {cuadro_prev}. "
    
                        # Formato amigable del tiempo transcurrido
                        if seg < 3600:
                            mins = max(1, seg // 60)
                            trans = f"~{mins}m"
                        elif seg < 86400:
                            horas = seg // 3600
                            trans = f"~{horas}h"
                        else:
                            dias = seg // 86400
                            trans = f"~{dias}d"
    
                        recordatorio = (
                            f"{prev}Pasaron {trans} desde la última conversación. "
                            f"¿Aparecieron emociones nuevas?"
                        )
            except Exception:
                pass


    # --- 5) Respuesta base si no hubo disparador ---
    if not texto_out:
        base = []
        if emociones_openai:
            base.append(f"Se observan: {', '.join(emociones_openai)}.")
        if cuadro_openai:
            base.append(f"Cuadro clínico probable: {cuadro_openai}.")
        if not base:
            base.append("No aparecen elementos clínicos relevantes en este mensaje.")
        texto_out = " ".join(base)

    if recordatorio:
        texto_out = f"{texto_out}\n\n{recordatorio}"

    return {"respuesta": texto_out, "session": session}








# ==============================================================
# 📌 Obtener todas las emociones históricas de un usuario
# ==============================================================
from core.db.conexion import ejecutar_consulta
from sqlalchemy import text  # si quieres seguir usando SQL parametrizado

def obtener_emociones_usuario(user_id):
    """
    Devuelve una lista de emociones históricas para el usuario desde la DB.
    """
    try:
        query = """
            SELECT emocion
            FROM emociones_detectadas
            WHERE user_id = %s
        """
        resultados = ejecutar_consulta(query, (user_id,))
        return [row["emocion"] for row in resultados] if resultados else []
    except Exception as e:
        print(f"⚠️ Error en obtener_emociones_usuario: {e}")
        return []


# ==============================================================
# 📌 Guardar nueva emoción en DB
# ==============================================================
def guardar_emocion_en_db(user_id, emocion, clasificacion):
    """
    Inserta una emoción detectada y su clasificación en la DB.
    """
    try:
        query = """
            INSERT INTO emociones_detectadas (user_id, emocion, clasificacion, fecha)
            VALUES (%s, %s, %s, NOW())
        """
        ejecutar_consulta(query, (user_id, emocion, clasificacion), commit=True)
        print(f"💾 Emoción '{emocion}' registrada para el usuario {user_id}")
    except Exception as e:
        print(f"⚠️ Error al guardar emoción en DB: {e}")


# ==============================================================
# 📌 Clasificar cuadro clínico probable (puede usarse IA)
# ==============================================================
def clasificar_cuadro_clinico(emocion):
    """
    Clasifica la emoción detectada en un cuadro clínico probable.
    """
    clasificacion_map = {
        "ansiedad": "Posible cuadro de ansiedad generalizada",
        "tristeza": "Posible episodio depresivo",
        "miedo": "Posible cuadro de angustia",
        "insomnio": "Posible trastorno del sueño",
        "estres": "Posible cuadro de estrés crónico",
        "deprimido": "Posible episodio depresivo mayor",
        "soledad": "Posible aislamiento emocional"
    }
    return clasificacion_map.get(
        emocion.lower(),
        "Patrón emocional que requiere evaluación profesional por el Lic. Daniel O. Bustamante"
    )


# ==============================================================
# 📌 Determinar malestar predominante
# ==============================================================
def determinar_malestar_predominante(emociones):
    """
    Determina el malestar más frecuente en la lista de emociones.
    """
    from collections import Counter
    if not emociones:
        return None
    conteo = Counter(emociones)
    return conteo.most_common(1)[0][0]



