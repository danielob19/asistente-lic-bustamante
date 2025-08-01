import psycopg2
from datetime import datetime
from core.constantes import DATABASE_URL

from core.db.conexion import ejecutar_consulta  # Asegúrate de tener este import arriba

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


def registrar_historial_clinico_simple(user_id: str, clasificacion: str, motivo: str = "Seguimiento automatizado"):
    """
    Registra un evento de seguimiento clínico del usuario con la clasificación generada por el modelo.
    Compatible con la estructura actual de historial_clinico_usuario (emociones = text[]).
    """
    consulta = """
        INSERT INTO historial_clinico_usuario (user_id, emociones, tema, fuente, fecha, eliminado)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    valores = (
        user_id,
        [clasificacion],              # Guardar como lista para text[]
        motivo,                       # Usamos motivo como tema
        "seguimiento",                # Fuente
        datetime.now(),               # Fecha
        False                         # Eliminado
    )
    try:
        ejecutar_consulta(consulta, valores)
    except Exception as e:
        print(f"❌ Error al registrar historial clínico: {e}")


def registrar_emocion(emocion: str, contexto: str, user_id: str = None):
    try:
        print("\n======= 📌 REGISTRO DE EMOCIÓN DETECTADA =======")
        print(f"🧠 Emoción detectada: {emocion}")
        print(f"🧾 Contexto asociado: {contexto}")
        print(f"👤 Usuario: {user_id if user_id else 'No especificado'}")

        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'emociones_detectadas' AND column_name = 'user_id';
                """)
                tiene_user_id = bool(cursor.fetchone())

                if tiene_user_id and user_id:
                    cursor.execute(
                        "SELECT contexto FROM emociones_detectadas WHERE emocion = %s AND user_id = %s;",
                        (emocion.strip().lower(), user_id)
                    )
                else:
                    cursor.execute(
                        "SELECT contexto FROM emociones_detectadas WHERE emocion = %s;",
                        (emocion.strip().lower(),)
                    )

                resultado = cursor.fetchone()

                if resultado:
                    nuevo_contexto = f"{resultado[0]}; {contexto.strip()}"
                    if tiene_user_id and user_id:
                        cursor.execute(
                            "UPDATE emociones_detectadas SET contexto = %s WHERE emocion = %s AND user_id = %s;",
                            (nuevo_contexto, emocion.strip().lower(), user_id)
                        )
                    else:
                        cursor.execute(
                            "UPDATE emociones_detectadas SET contexto = %s WHERE emocion = %s;",
                            (nuevo_contexto, emocion.strip().lower())
                        )
                    print("🔄 Emoción existente. Contexto actualizado.")
                else:
                    if tiene_user_id and user_id:
                        cursor.execute(
                            "INSERT INTO emociones_detectadas (emocion, contexto, user_id) VALUES (%s, %s, %s);",
                            (emocion.strip().lower(), contexto.strip(), user_id)
                        )
                    else:
                        cursor.execute(
                            "INSERT INTO emociones_detectadas (emocion, contexto) VALUES (%s, %s);",
                            (emocion.strip().lower(), contexto.strip())
                        )
                    print("🆕 Nueva emoción registrada exitosamente.")

                conn.commit()
        print("===============================================\n")

    except Exception as e:
        print(f"❌ Error al registrar emoción '{emocion}': {e}")


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
