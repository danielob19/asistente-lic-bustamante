import json
import re
import unicodedata
import string
from unidecode import unidecode
from typing import Dict, Any, Optional, List
import os
from datetime import datetime, timezone
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None


from core.db.conexion import ejecutar_consulta
from core.db.consulta import (
    registrar_interaccion_clinica,
    obtener_historial_usuario,
    obtener_ultimo_registro_usuario,
    estadistica_global_emocion_a_cuadro,
    obtener_ultima_interaccion_emocional,
)
from core.utils.generador_openai import generar_respuesta_con_openai
from core.utils.tiempo import delta_preciso_desde


THROTTLE_RECORDATORIO_SEG = int(os.getenv("THROTTLE_RECORDATORIO_SEG", "90"))




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
    FROM public.historial_clinico_usuario           -- ← con esquema
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






def armar_respuesta_humana(
    mensaje_usuario: str,
    emociones_openai: list[str] | None,
    cuadro_openai: str | None,
    recordatorio: str = "",
) -> str:
    partes: list[str] = []
    if recordatorio:
        partes.append(recordatorio)

    texto = mensaje_usuario or ""
    explicita = _es_expresion_explicita(texto)
    emociones = [e for e in (emociones_openai or []) if e]
    etiqu = _join_humano(emociones)

    # 1) Afirmaciones explícitas del usuario
    if emociones:
        if explicita:
            # Ej: “estoy muy angustiado” → afirmación
            partes.append(f"Decís que estás atravesando {etiqu}.")
        else:
            # Ej: “me borro de reuniones” → inferencia suave
            partes.append(f"Por lo que contás, podría estar apareciendo {etiqu}.")

    # 2) Cuadro probable (si no hubo emociones o para complementar)
    if cuadro_openai and (not emociones or not explicita):
        partes.append(f"También podría tratarse de {cuadro_openai}.")

    # 3) Heurística de evitación social si el texto lo sugiere
    if not emociones and _detecta_evitacion_social(texto):
        partes.append(
            "Notás que tendés a evitar reuniones o eventos; eso puede vincularse con incomodidad social o ansiedad en lo social."
        )

    # 4) Preguntas orientadas (variadas según foco)
    foco = (emociones[0] if emociones else (cuadro_openai or "")).lower()
    if "miedo" in foco:
        partes.append("¿Aparece más a la noche o al intentar dormir? ¿Qué pensás o imaginás justo antes?")
    elif "angust" in foco or "ansied" in foco:
        partes.append("¿En qué situaciones se intensifica más (trabajo, estudio, pareja)? ¿Qué notás en el cuerpo: opresión, taquicardia, nudo en el estómago?")
    elif "insomnio" in foco or ("dorm" in unidecode(texto.lower())):
        partes.append("¿Te cuesta conciliar, te despertás varias veces o te levantás muy temprano? ¿Usás pantallas en la cama o tomás mate/café de tarde-noche?")
    elif _detecta_evitacion_social(texto):
        partes.append("¿Qué temés que pase si asistís? ¿Qué hacés para calmarlo en el momento?")
    else:
        # fallback humano y breve
        citado = _citar_breve(texto)
        partes.append(f"Gracias por compartirlo. Sobre “{citado}”: ¿qué situaciones lo activan y qué notás en el cuerpo o en los pensamientos cuando aparece?")

    # 5) Cierre amable, sin repetir
    respuesta = " ".join(p for p in partes if p).strip()
    return respuesta




def _join_humano(items):
    """Une una lista en español: 'a', 'a y b', 'a, b y c'."""
    xs = [x for x in (items or []) if x]
    if not xs: return ""
    if len(xs) == 1: return xs[0]
    if len(xs) == 2: return f"{xs[0]} y {xs[1]}"
    return f"{', '.join(xs[:-1])} y {xs[-1]}"

def _citar_breve(texto: str, max_chars: int = 70) -> str:
    t = " ".join(str(texto or "").strip().strip('“”"\'').split())
    return (t[:max_chars] + "…") if len(t) > max_chars else t

def _es_texto_de_bot(t: str) -> bool:
    s = (t or "").lower()
    gatillos = ("me comentaste", "hace ", " hs", "¿ocurrió algo", "cuadro clínico probable", "gracias por contarlo")
    return any(g in s for g in gatillos)

def _es_expresion_explicita(msg: str) -> bool:
    """¿El/la usuario/a lo afirma en 1ª persona? (estoy, me siento, tengo, etc.)."""
    t = unidecode((msg or "").lower())
    pautas = ("estoy ", "me siento", "tengo ", "siento ", "me da ", "tengo miedo", "estoy muy", "estoy re ")
    return any(p in t for p in pautas)

def _detecta_evitacion_social(msg: str) -> bool:
    """Heurística suave para evitación social / fobia social."""
    t = unidecode((msg or "").lower())
    claves = ("evitar", "no ir", "excusa", "excusarme", "reunion", "reuniones", "evento", "eventos",
              "familia", "amigos", "gente", "multitud", "juntarme", "salir")
    return sum(k in t for k in claves) >= 2







def _nombre_dia_es(n: int) -> str:
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    return dias[n % 7]

def _nombre_mes_es(n: int) -> str:
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
             "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    return meses[(n - 1) % 12]

def fecha_humana_es(fecha: datetime) -> str:
    """
    Devuelve 'martes 5 de febrero de 2024 a las 19:45 hs' en TZ_LOCAL (default: America/Argentina/Buenos_Aires).
    """
    if not fecha:
        return ""
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=timezone.utc)

    tz_name = os.getenv("TZ_LOCAL", "America/Argentina/Buenos_Aires")
    try:
        fecha = fecha.astimezone(ZoneInfo(tz_name)) if ZoneInfo else fecha.astimezone(timezone.utc)
    except Exception:
        fecha = fecha.astimezone(timezone.utc)

    return f"{_nombre_dia_es(fecha.weekday())} {fecha.day} de {_nombre_mes_es(fecha.month)} de {fecha.year} a las {fecha.hour:02d}:{fecha.minute:02d} hs"







def construir_recordatorio_contextual(
    emociones_actuales: Optional[List[str]],
    cuadro_actual: Optional[str],
    ultima: Optional[dict],
    mensaje_actual: str = "",
) -> str:
    """
    Devuelve un recordatorio contextual, p. ej.:
    'Lo que traés ahora (miedo a la oscuridad) podría vincularse o sumarse a angustia
     que me comentaste el martes 5 de febrero de 2024 a las 19:45 hs (hace 7 meses y 3 días).
     ¿Ocurrió algo en este tiempo?'
    Requiere: helpers 'fecha_humana_es' y 'delta_preciso_desde'.
    Usa _citar_breve(mensaje_actual) si no hay emoción/cuadro detectado.
    """
    try:
        if not ultima:
            return ""

        fecha_ult = ultima.get("fecha")
        if not fecha_ult:
            return ""

        # Emociones previas (sin duplicados) + cuadro previo
        prev_emociones = list(
            dict.fromkeys(
                (ultima.get("emociones") or []) +
                (ultima.get("nuevas_emociones_detectadas") or [])
            )
        )
        cuadro_prev = (ultima.get("cuadro_clinico_probable") or "").strip()

        if prev_emociones:
            prev_lbl = ", ".join(prev_emociones)
        elif cuadro_prev:
            prev_lbl = cuadro_prev
        else:
            prev_lbl = "cómo te sentías"

        # Etiqueta actual: emociones -> cuadro -> cita del mensaje del usuario
        act_lbl = ""
        if emociones_actuales:
            act_lbl = ", ".join([e for e in emociones_actuales if e])
        elif cuadro_actual:
            act_lbl = (cuadro_actual or "").strip()
        elif mensaje_actual:
            # Requiere el helper _citar_breve(texto, max_chars=70)
            citado = _citar_breve(mensaje_actual)
            act_lbl = f"\"{citado}\""

        # Fecha absoluta + relativo
        fecha_txt = fecha_humana_es(fecha_ult)        # p. ej. 'martes 5 de febrero de 2024 a las 19:45 hs'
        rel_txt   = delta_preciso_desde(fecha_ult)    # p. ej. 'hace 7 meses y 3 días'

        if act_lbl:
            return (
                f"Lo que traés ahora ({act_lbl}) podría vincularse o sumarse a {prev_lbl} "
                f"que me comentaste el {fecha_txt} ({rel_txt}). ¿Ocurrió algo en este tiempo?"
            )
        else:
            return (
                f"Me habías comentado {prev_lbl} el {fecha_txt} ({rel_txt}). "
                f"¿Ocurrió algo desde entonces?"
            )

    except Exception as ex:
        print(f"⚠️ Error en construir_recordatorio_contextual: {ex}")
        return ""






def _openai_respuesta_terapeutica(mensaje_usuario: str, recordatorio: str) -> str:
    """
    Pide a OpenAI que redacte la respuesta clínica final en castellano rioplatense,
    natural y humana, integrando el recordatorio temporal si existe. Sin diagnósticos
    cerrados; 1–3 oraciones, con 1–2 preguntas abiertas.
    """
    # Contexto que le damos al modelo
    contexto = []
    if recordatorio:
        contexto.append(f"Recordatorio temporal (NO repetir literal, integrarlo con naturalidad): {recordatorio}")
    contexto.append(f"Mensaje del usuario: {mensaje_usuario}")
    contexto_txt = "\n".join(contexto)

    prompt = "\n".join([
        "Actuá como psicólogo clínico (tono humano, empático, rioplatense, usando 'vos').",
        "Objetivo: redactar UNA respuesta breve (1 a 3 oraciones) que acompañe y oriente.",
        "Reglas:",
        "- Si el usuario AFIRMA un estado (p.ej., 'estoy angustiado'), reconocelo como afirmación (p.ej., 'decís que estás angustiado'), no como sospecha.",
        "- Si NO lo afirma explícitamente, inferí prudentemente el malestar más probable (ansiedad, angustia, miedo, insomnio, evitación social, etc.).",
        "- Integrá el recordatorio temporal SOLO si lo proveo; no lo repitas textual, hilalo en la primera frase.",
        "- Evitá: 'te leo', tecnicismos, listados largos, diagnósticos cerrados.",
        "- Cerrá con 1 o 2 preguntas abiertas para explorar (situaciones, cuerpo/pensamientos, desde cuándo).",
        "- No ofrezcas teléfonos ni agenda; enfocá en lo clínico.",
        "",
        "Redactá directamente la respuesta final del terapeuta (sin encabezados).",
        "",
        "=== CONTEXTO ===",
        contexto_txt,
    ])

    try:
        texto = generar_respuesta_con_openai(prompt, temperatura=0.3, max_tokens=280)
        return (texto or "").strip()
    except Exception as ex:
        print(f"⚠️ _openai_respuesta_terapeutica falló: {ex}")
        # Fallback súper breve por si la API falla (no debería activarse casi nunca)
        return (
            "Gracias por contarlo. ¿En qué situaciones se intensifica más y qué notás en el cuerpo "
            "o en los pensamientos cuando aparece?"
        )










def _citar_breve(texto: str, max_chars: int = 70) -> str:
    t = " ".join(str(texto or "").split())
    return (t[:max_chars] + "…") if len(t) > max_chars else t




def procesar_clinico(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flujo clínico alineado a directiva:
      - OpenAI detecta emociones y cuadro probable en cada mensaje clínico.
      - Registrar novedades (emociones nuevas / cuadro) en public.historial_clinico_usuario.
      - Disparador (<10): si hay ≥2 coincidencias (sesión + historial + global) hacia el mismo cuadro → responder con
        resumen breve + 'Cuadro clínico probable', y no repetir en la sesión.
      - Reingreso producción: recordar emociones/cuadro previos si pasaron ≥60s y preguntar por emociones nuevas.
    """

    # --- Extraer inputs ---
    mensaje_original = input_data["mensaje_original"]
    mensaje_usuario = input_data["mensaje_usuario"]
    user_id = input_data["user_id"]
    session = input_data["session"]
    contador_raw = input_data.get("contador")
    try:
        contador = int(contador_raw) if contador_raw is not None else 1
    except Exception:
        contador = 1



    
    def _bootstrap_session_desde_db(user_id: str, session: dict) -> dict:
        """
        Reconstruye **mínimos** de sesión a partir del último registro en
        public.historial_clinico_usuario para que el asistente conserve memoria,
        aunque no haya sesión en RAM.
    
        Robusto frente a cambios de forma del row (tuple o dict).
        """
        def _get(row, key: str, idx: int, default=None):
            try:
                if isinstance(row, dict):
                    return row.get(key, default)
                # tupla/lista
                return row[idx] if (hasattr(row, "__len__") and len(row) > idx) else default
            except Exception:
                return default
    
        try:
            ult = obtener_ultimo_registro_usuario(user_id)
            if not ult:
                return session
    
            # Campos tolerantes a tupla/dict
            emociones_ult   = _get(ult, "emociones",        3, []) or []
            fecha_ult       = _get(ult, "fecha",            2, None)
            interaccion_ult = _get(ult, "interaccion_id",   6, None)
    
            # 1) Emociones detectadas
            if not session.get("emociones_detectadas"):
                session["emociones_detectadas"] = _limpiar_lista_str(emociones_ult)
    
            # 2) Última fecha (ISO)
            if not session.get("ultima_fecha") and fecha_ult:
                try:
                    if isinstance(fecha_ult, str):
                        # normalizamos (puede venir con 'Z')
                        from datetime import datetime
                        session["ultima_fecha"] = datetime.fromisoformat(fecha_ult.replace("Z", "")).isoformat()
                    else:
                        session["ultima_fecha"] = fecha_ult.isoformat()
                except Exception:
                    # si falla el parseo, guardamos tal cual
                    session["ultima_fecha"] = str(fecha_ult)
    
            # 3) Flag del disparador (por defecto False)
            session.setdefault("disparo_notificado", False)
    
            # 4) Contador de interacciones (si no viene en sesión)
            if not isinstance(session.get("contador_interacciones"), int):
                try:
                    base = int(interaccion_ult) if interaccion_ult is not None else 0
                    session["contador_interacciones"] = base + 1
                except Exception:
                    session["contador_interacciones"] = 1
    
        except Exception:
            # No bloquear el flujo clínico por errores de bootstrap
            pass
    
        return session

    
    session = _bootstrap_session_desde_db(user_id, session or {})


    # --- Utilidades locales ---
    def _limpiar_lista_str(xs):
        if not xs:
            return []
        return [re.sub(r"\s+", " ", x.strip().lower()) for x in xs if isinstance(x, str) and x.strip()]


    def _get_col(row, idx=None, key=None, default=None):
        """
        Accede de forma segura a una columna de un row que puede ser tupla/lista o dict.
        - Si es (list, tuple) usa `idx`
        - Si es dict usa `key`
        - Si falla, devuelve `default`
        """
        if isinstance(row, (list, tuple)):
            try:
                return row[idx]
            except Exception:
                return default
        if isinstance(row, dict):
            if key is not None and key in row:
                return row.get(key, default)
            return default
        return default


    def _parse_json_emociones(payload: str) -> tuple[list[str], str]:
        """
        Parsea con tolerancia y valida el esquema:
          {"emociones": [...0..4 strings minúsculas...], "cuadro_probable": "str"}
        Retorna (emociones, cuadro) o ([], "") si no es válido.
        """
        data = None
    
        # 1) Intento directo
        try:
            data = json.loads(payload)
        except Exception:
            pass
    
        # 2) Si vino texto con basura alrededor, extraemos el primer objeto {...}
        if not isinstance(data, dict):
            m = re.search(r"\{(?:.|\n)*\}", payload, flags=re.S)
            if m:
                try:
                    data = json.loads(m.group(0))
                except Exception:
                    data = None
    
        if not isinstance(data, dict):
            return [], ""
    
        # Normalización
        emos = data.get("emociones") or []
        if not isinstance(emos, list):
            emos = []
    
        emos_norm = []
        for e in emos:
            s = str(e).strip().lower()
            if s:
                emos_norm.append(s)
    
        # Únicas, máximo 4
        emos_norm = list(dict.fromkeys(emos_norm))[:4]
    
        cuadro = str(data.get("cuadro_probable") or "").strip().lower()
    
        # Validación mínima
        if any("," in x or "{" in x or "}" in x for x in emos_norm):
            return [], ""
        if not isinstance(cuadro, str):
            cuadro = ""
    
        return emos_norm, cuadro
    
    
    def _ask_openai_emociones_y_cuadro(texto_usuario: str) -> tuple[list[str], str]:
        """
        Pide a OpenAI emociones (0..4) y cuadro probable en JSON estricto.
        Nunca lanza excepción: si falla todo, retorna ([], "").
        100% OpenAI (sin depender de DB).
        """
        # Instrucción compacta y estricta
        prompt_base = "\n".join([
            "Analizá el siguiente mensaje clínico y devolvé EXCLUSIVAMENTE un JSON válido con este formato exacto:",
            "{",
            '  "emociones": ["...", "..."],',
            '  "cuadro_probable": "..."',
            "}",
            "",
            "Reglas (español de Argentina):",
            "- Solo JSON: sin explicaciones, sin texto antes/después, sin Markdown.",
            "- Tolerá faltas y variantes coloquiales (p. ej., 'agustiado' ≈ 'angustiado').",
            "- Emociones: 0 a 4 términos en minúsculas, sin duplicados, solo negativas/clinicamente relevantes.",
            "- Si el usuario expresa un malestar aunque sea con faltas, inferí la emoción más probable.",
            '- "cuadro_probable": síntesis prudente en minúsculas (p. ej.: "ansiedad", "estrés", "insomnio").',
            f"- TEXTO: {texto_usuario}",
        ])

    
        # Hasta 3 intentos: 1) solicitud normal, 2) refuerzo JSON-only, 3) reparador
        prompts = [
            prompt_base,
            prompt_base + "\nIMPORTANTE: respondé SOLO con el objeto JSON. Nada más.",
            (
                "Arreglá el siguiente contenido para que sea EXACTAMENTE un objeto JSON válido con claves "
                '"emociones" (lista de strings) y "cuadro_probable" (string). No agregues texto fuera del JSON.\n\n'
                f"CONTENIDO:\n{prompt_base}"
            ),
        ]
    
        # Reintentos de red/timeout: leve backoff
        for intento, p in enumerate(prompts, start=1):
            for _ in range(2):  # 2 reintentos por intento lógico
                try:
                    # Tu wrapper a OpenAI; usá temperature=0 para máxima exactitud
                    raw = generar_respuesta_con_openai(p, temperatura=0, max_tokens=200)
                    if not isinstance(raw, str):
                        raw = str(raw or "")
    
                    emociones, cuadro = _parse_json_emociones(raw)
                    if emociones or cuadro:
                        return emociones, cuadro
    
                    # Si no pudo parsear/validar, rompemos inner loop y probamos siguiente prompt
                    break
    
                except Exception as ex:
                    # network/timeout/rate-limit → reintento ligero
                    print(f"⚠️ intento {intento}: OpenAI falló: {ex}")
                    continue
    
        # Si llegamos acá, no conseguimos una salida válida
        return [], ""


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
            for e in (_get_col(r, 3, "emociones", []) or []):
                emos_hist.add((e or "").strip().lower())


        # Estadística global: emoción -> {cuadros}
        glob = estadistica_global_emocion_a_cuadro() or []
        map_emo_to_cuadro: dict[str, set] = {}
        for emocion, cuadro, c in glob:
            if not emocion or not cuadro:
                continue
            map_emo_to_cuadro.setdefault(emocion, set()).add((cuadro or "").strip().lower())
        
        # 🧰 Fallback local si la global está vacía (DB recién limpiada):
        # sembramos el mapa usando el historial del propio usuario
        if not map_emo_to_cuadro:
            try:
                hist = obtener_historial_usuario(user_id, limite=200) or []
                for r in hist:
                    cuadro_prev = (_get_col(r, 5, "cuadro_clinico_probable") or "").strip().lower()
                    if not cuadro_prev:
                        continue
                    for e in (_get_col(r, 3, "emociones", []) or []):
                        e = (e or "").strip().lower()
                        if not e:
                            continue
                        map_emo_to_cuadro.setdefault(e, set()).add(cuadro_prev)
                print(f"🧮 Seed local map_emo_to_cuadro → {len(map_emo_to_cuadro)} emociones")
            except Exception as ex:
                print(f"⚠️ No se pudo seedear map_emo_to_cuadro: {ex}")



        # --- Reconciliación entre OpenAI y votos por emociones (sesión + historial)
        objetivo_openai = (cuadro_openai or "").strip().lower()
        
        # Unión de emociones normalizadas de sesión + historial (ya tenés emos_hist arriba)
        union = set(_limpiar_lista_str(emociones_sesion)) | emos_hist
        
        # Conteo de cuadros posibles a partir de la unión de emociones
        counts = {}
        for e in union:
            for c in map_emo_to_cuadro.get(e, []):
                counts[c] = counts.get(c, 0) + 1
        
        # Elegimos objetivo final: si OpenAI empata o gana, se respeta; si pierde, va el más votado
        if counts:
            top = max(counts, key=counts.get)
            objetivo = objetivo_openai if counts.get(objetivo_openai, 0) >= counts[top] else top
        else:
            objetivo = objetivo_openai
        
        # Mini-log para depurar la reconciliación
        print(f"⚖️ Reconciliación de cuadro → openai='{objetivo_openai}', counts={counts}, elegido='{objetivo}'")
        
        # Inicialización como antes
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

    # emociones previas (sesión)
    emos_sesion_prev = set(_limpiar_lista_str(session.get("emociones_detectadas", [])))
    nuevas_emos = [e for e in emociones_openai if e not in emos_sesion_prev]
    
        
    # Unimos emociones de sesión + actuales para el cómputo
    emociones_union = list(set(_limpiar_lista_str(session.get("emociones_detectadas", [])) + emociones_openai))
    
    # Cálculo de coincidencias (con semilla y fallback ya implementados)
    votos, detalles, objetivo = _coincidencias_sesion_historial_global(
        user_id=user_id,
        emociones_sesion=emociones_union,
        cuadro_openai=cuadro_openai
    )
    
    # Reconciliación: si OpenAI no trajo cuadro, usamos el fallback (objetivo)
    cuadro_final = (objetivo or cuadro_openai or "").strip().lower()
    print(f"⚖️ Reconciliación de cuadro → openai='{cuadro_openai}', elegido='{cuadro_final}'")
    

    # 4) Contexto temporal emocional (siempre, contextual y humano)
    recordatorio = ""
    try:
        ultima = obtener_ultima_interaccion_emocional(user_id)   # ignora admins
        recordatorio = construir_recordatorio_contextual(
            emociones_actuales=emociones_openai,
            cuadro_actual=cuadro_openai,
            ultima=ultima,
            mensaje_actual=mensaje_usuario,  # <- NUEVO
        )
    except Exception as ex:
        print(f"⚠️ Error armando recordatorio contextual: {ex}")
    

    



    # Actualizar sesión
    session["emociones_detectadas"] = list(emos_sesion_prev.union(emociones_openai))
    session["ultima_fecha"] = ahora.isoformat()

    # 3) Disparador por coincidencias (<10 y aún no notificado)
    texto_out = ""
    if contador < 10 and cuadro_openai and not session.get("disparo_notificado", False):
        try:
            # Unimos emociones de sesión + previas de la sesión para el cómputo (sin duplicar)
            emociones_union = list(set(
                _limpiar_lista_str(session.get("emociones_detectadas", [])) +
                _limpiar_lista_str(emociones_openai)
            ))
    
            votos, detalles, objetivo = _coincidencias_sesion_historial_global(
                user_id=user_id,
                emociones_sesion=emociones_union,
                cuadro_openai=cuadro_openai,
            )
    
            if votos >= 2:
                partes = []
                if emociones_openai:
                    partes.append(f"Por lo que traés hoy se suma a lo previo y se observa {', '.join(emociones_openai)}.")
                partes.append(f"Cuadro clínico probable: {objetivo}.")
                partes.append(
                    "¿Podés ubicar cuándo se intensifica más (trabajo, noche, antes de dormir)? "
                    "¿Cambios en sueño, concentración o tensión corporal?"
                )
                texto_out = " ".join(partes)
    
                # Registrar explícitamente el suceso del disparador
                registrar_interaccion_clinica(
                    user_id=user_id,
                    emociones=emociones_openai or [],
                    nuevas_emociones_detectadas=nuevas_emos or [],
                    cuadro_clinico_probable=objetivo or None,
                    respuesta_openai=texto_out,  # lo que dijo el asistente en el disparador
                    origen="deteccion",
                    fuente="openai_disparo",
                    eliminado=False,
                    interaccion_id=contador
                )
                # Marcar flags en sesión para no repetir el disparador
                session["disparo_notificado"] = True
                session["disparo_cuadro"] = objetivo
    
        except Exception as ex:
            print(f"🔴 Error en disparador: {ex}")
    


    
    # 5) Respuesta clínica final (OpenAI plena). Si no hubo disparador armado:
    if not texto_out:
        texto_out = _openai_respuesta_terapeutica(
            mensaje_usuario=mensaje_usuario,
            recordatorio=recordatorio,  # “Hace X me comentaste…”
        )
    


    # 6) Salida FINAL (siempre devolvemos algo)
    if texto_out:
        # Ya incluye el recordatorio si correspondía
        texto_final = texto_out
    elif recordatorio:
        # Si no hubo texto_out, al menos devolvemos el recordatorio
        texto_final = recordatorio
    else:
        # Fallback humano y breve (sin el mensaje rígido)
        texto_final = (
            "Gracias por compartirlo. ¿En qué momentos se intensifica más "
            "y qué notás en el cuerpo o en los pensamientos cuando aparece?"
        )
    
    # Sanitizar espacios
    texto_final = " ".join(texto_final.split())
    
    # Registrar SIEMPRE la interacción final en historial_clinico_usuario
    try:
        registrar_interaccion_clinica(
            user_id=user_id,
            emociones=emociones_openai or [],
            nuevas_emociones_detectadas=nuevas_emos or [],   # <- mantiene solo lo nuevo
            cuadro_clinico_probable=cuadro_final or None,    # <- usa el reconciliado si existe
            respuesta_openai=texto_final,                    # <- lo que efectivamente se dijo
            origen="deteccion",
            fuente="openai",
            eliminado=False,
            interaccion_id=contador,
        )
    except Exception as ex:
        print(f"🔴 Error registrando interacción clínica: {ex}")
    
    return {
        "respuesta": texto_final,
        "session": session,
    }




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



