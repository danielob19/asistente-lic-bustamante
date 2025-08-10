from datetime import datetime
from typing import List, Optional
import psycopg2
from core.db.conexion import ejecutar_consulta   # tu helper central
from core.constantes import DATABASE_URL         # si tu helper no usa pool global

def registrar_emocion_clinica(user_id: str, emocion: str, origen: str = "detección"):
    """
    Registra una emoción clínicamente relevante (como angustia, ansiedad, etc.)
    en la tabla historial_clinico_usuario.
    """

    try:
        consulta = """
        INSERT INTO historial_clinico_usuario (user_id, emociones, origen, fecha)
        VALUES (%s, %s, %s, %s)
        """
        # Convertimos la emoción en lista para el campo text[]
        valores = (
            user_id,
            [emocion],  # importante: lista para text[]
            origen,
            datetime.now()
        )

        ejecutar_consulta(consulta, valores)
        print(f"🧠 Emoción clínica registrada: {emocion}")

    except Exception as e:
        print(f"❌ Error al registrar emoción clínica: {e}")





def registrar_historial_clinico(
    user_id: str,
    *,
    # Campos principales
    fecha: datetime | None = None,
    emociones: list[str] | None = None,
    sintomas: list[str] | None = None,
    tema: str | None = None,
    respuesta_openai: str | None = None,
    sugerencia: str | None = None,
    fase_evaluacion: str | None = None,
    fuente: str = "seguimiento",

    # Vínculo con interacción y trazabilidad
    interaccion_id: int | str | None = None,
    origen: str = "modelo",

    # Clasificación / diagnóstico orientativo
    cuadro_clinico_probable: str | None = None,

    # Estado de sesión/último contacto
    nuevas_emociones_detectadas: list[str] | None = None,
    fecha_ultima_interaccion: datetime | None = None,

    # Borrado lógico
    eliminado: bool = False,

    # ---------- Alias de compatibilidad (migración) ----------
    # Si alguna llamada vieja pasa estos nombres, los mapeamos.
    clasificacion: str | None = None,   # alias de cuadro_clinico_probable
    motivo: str | None = None,          # alias de tema
) -> bool:
    """
    Inserta un registro en historial_clinico_usuario con la mayor cantidad
    de información disponible. Mantiene compatibilidad hacia atrás con
    parámetros alias (clasificacion/motivo).

    Devuelve True si se insertó OK, False si hubo error.
    """

    # Defaults seguros
    fecha = fecha or datetime.now()
    emociones = emociones or []
    sintomas = sintomas or []
    nuevas_emociones_detectadas = nuevas_emociones_detectadas or []

    # Compatibilidad de nombres
    if cuadro_clinico_probable is None and clasificacion:
        cuadro_clinico_probable = clasificacion
    if tema is None and motivo:
        tema = motivo

    # interaccion_id -> int o None
    interaccion_id_int = None
    if interaccion_id not in (None, ""):
        try:
            interaccion_id_int = int(interaccion_id)  # si viene str lo convertimos
        except (TypeError, ValueError):
            interaccion_id_int = None  # lo guardamos como NULL

    consulta = """
        INSERT INTO historial_clinico_usuario
        (
            user_id,
            fecha,
            emociones,
            sintomas,
            tema,
            respuesta_openai,
            sugerencia,
            fase_evaluacion,
            fuente,
            interaccion_id,
            origen,
            cuadro_clinico_probable,
            nuevas_emociones_detectadas,
            fecha_ultima_interaccion,
            eliminado
        )
        VALUES
        (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s
        )
    """

    valores = [
        user_id,
        fecha,
        emociones,
        sintomas,
        tema,
        respuesta_openai,
        sugerencia,
        fase_evaluacion,
        fuente,
        interaccion_id_int,
        origen,
        cuadro_clinico_probable,
        nuevas_emociones_detectadas,
        fecha_ultima_interaccion,
        eliminado,
    ]

    try:
        ejecutar_consulta(consulta, valores, commit=True)
        return True
    except Exception as e:
        print(f"[✖] Error al registrar historial clínico: {e}")
        return False




def registrar_emocion(user_id: str, emocion: str, *, interaccion_id: int | str | None = None):
    """
    En lugar de insertar en 'emociones_detectadas', agregamos un renglón en
    'historial_clinico_usuario' con la emoción detectada.
    """
    try:
        return registrar_historial_clinico(
            user_id=user_id,
            emociones=[emocion],
            sintomas=[],
            tema="patrón emocional detectado",
            sugerencia=None,
            fase_evaluacion="deteccion_emocion",
            fuente="detector",
            interaccion_id=interaccion_id,
            origen="detector_emociones",
            cuadro_clinico_probable=None,
            nuevas_emociones_detectadas=[emocion],
            eliminado=False,
        )
    except Exception as e:
        print(f"[✖] Error al registrar_emocion en historial_clinico_usuario: {e}")
        return False



def registrar_interaccion(user_id: str, consulta: str, mensaje_original: str = None):
    try:
        print("\n===== DEPURACIÓN - REGISTRO DE INTERACCIÓN =====")
        print(f"Intentando registrar interacción: user_id={user_id}")
        print(f"Consulta purificada: {consulta}")
        print(f"Mensaje original: {mensaje_original}")

        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'interacciones' AND column_name = 'mensaje_original';
        """)
        columna_existente = cursor.fetchone()

        if not columna_existente:
            print("⚠️ La columna 'mensaje_original' no existe. Creándola...")
            cursor.execute("ALTER TABLE interacciones ADD COLUMN mensaje_original TEXT;")
            conn.commit()

        cursor.execute("""
            INSERT INTO interacciones (user_id, consulta, mensaje_original) 
            VALUES (%s, %s, %s) RETURNING id;
        """, (user_id, consulta, mensaje_original))
        
        interaccion_id = cursor.fetchone()[0]
        conn.commit()
        conn.close()

        print(f"✅ Interacción registrada con éxito. ID asignado: {interaccion_id}\n")
        return interaccion_id

    except Exception as e:
        print(f"❌ Error al registrar interacción en la base de datos: {e}\n")
        return None


def registrar_respuesta_openai(interaccion_id: int, respuesta: str, user_id: str = None, respuesta_original: str = None):
    try:
        print("\n===== DEPURACIÓN - REGISTRO DE RESPUESTA OPENAI =====")
        print(f"Intentando registrar respuesta para interacción ID={interaccion_id}")

        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'interacciones' AND column_name = 'respuesta';
        """)
        columna_existente = cursor.fetchone()

        if not columna_existente:
            print("⚠️ La columna 'respuesta' no existe en la tabla 'interacciones'. Creándola...")
            cursor.execute("ALTER TABLE interacciones ADD COLUMN respuesta TEXT;")
            conn.commit()

        cursor.execute("""
            UPDATE interacciones 
            SET respuesta = %s 
            WHERE id = %s;
        """, (respuesta, interaccion_id))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Respuesta registrada con éxito para interacción ID={interaccion_id}\n")

        # 📝 Registro en auditoría si user_id y respuesta_original están disponibles
        if user_id and respuesta_original:
            registrar_auditoria_respuesta(
                user_id=user_id,
                interaccion_id=interaccion_id,
                respuesta_original=respuesta_original,
                respuesta_final=respuesta,
                motivo_modificacion="Respuesta generada y registrada automáticamente"
            )

    except Exception as e:
        print(f"❌ Error al registrar respuesta en la base de datos: {e}\n")


def registrar_auditoria_input_original(user_id: str, mensaje_original: str, mensaje_purificado: str, clasificacion: str = None):
    try:
        print("\n📋 Registrando input original y purificado en auditoría")
        print(f"👤 user_id: {user_id}")
        print(f"📝 Original: {mensaje_original}")
        print(f"🧼 Purificado: {mensaje_purificado}")
        print(f"🏷️ Clasificación: {clasificacion}")

        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auditoria_input_original (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                mensaje_original TEXT NOT NULL,
                mensaje_purificado TEXT NOT NULL,
                clasificacion TEXT,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cursor.execute("""
            INSERT INTO auditoria_input_original (
                user_id, mensaje_original, mensaje_purificado, clasificacion
            ) VALUES (%s, %s, %s, %s);
        """, (user_id, mensaje_original.strip(), mensaje_purificado.strip(), clasificacion))

        conn.commit()
        conn.close()
        print("✅ Auditoría registrada exitosamente.\n")

    except Exception as e:
        print(f"❌ Error al registrar auditoría del input original: {e}")


def registrar_similitud_semantica(user_id: str, consulta: str, pregunta_faq: str, similitud: float):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO faq_similitud_logs (user_id, consulta, pregunta_faq, similitud)
            VALUES (%s, %s, %s, %s);
        """, (user_id, consulta, pregunta_faq, similitud))

        conn.commit()
        conn.close()
        print(f"🧠 Similitud registrada con éxito (Score: {similitud}) para FAQ: '{pregunta_faq}'\n")

    except Exception as e:
        print(f"❌ Error al registrar similitud semántica: {e}")


def registrar_log_similitud(user_id: str, consulta: str, pregunta_faq: str, similitud: float):
    registrar_similitud_semantica(user_id, consulta, pregunta_faq, similitud)


def registrar_auditoria_respuesta(user_id: str, respuesta_original: str, respuesta_final: str, motivo_modificacion: str = None, interaccion_id: int = None):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auditoria_respuestas (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                interaccion_id INTEGER,
                respuesta_original TEXT NOT NULL,
                respuesta_final TEXT NOT NULL,
                motivo_modificacion TEXT,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cursor.execute("""
            INSERT INTO auditoria_respuestas (
                user_id, interaccion_id, respuesta_original, respuesta_final, motivo_modificacion
            ) VALUES (%s, %s, %s, %s, %s);
        """, (user_id, interaccion_id, respuesta_original.strip(), respuesta_final.strip(), motivo_modificacion))

        conn.commit()
        conn.close()
        print("📑 Auditoría registrada en auditoria_respuestas.")
    except Exception as e:
        print(f"❌ Error al registrar auditoría de respuesta: {e}")


def registrar_inferencia(user_id: str, interaccion_id: int, tipo: str, valor: str):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO inferencias_cerebro_simulado (user_id, interaccion_id, tipo, valor)
            VALUES (%s, %s, %s, %s);
        """, (user_id, interaccion_id, tipo, valor))

        conn.commit()
        conn.close()
        print(f"🧠 Inferencia registrada: [{tipo}] → {valor}")

    except Exception as e:
        print(f"❌ Error al registrar inferencia: {e}")
