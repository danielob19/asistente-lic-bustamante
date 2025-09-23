# core/db/utilidades.py

from core.constantes import DATABASE_URL
import psycopg2


def gestionar_combinacion_emocional(emocion1, emocion2):
    """
    Consulta la tabla 'disparadores_emocionales' para una frase clínica correspondiente a una combinación de emociones.
    Si no la encuentra, registra automáticamente la combinación en 'combinaciones_no_registradas'.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        consulta = """
            SELECT texto_disparador FROM disparadores_emocionales
            WHERE (emocion_1 = %s AND emocion_2 = %s)
               OR (emocion_1 = %s AND emocion_2 = %s)
            LIMIT 1;
        """
        cursor.execute(consulta, (emocion1, emocion2, emocion2, emocion1))
        resultado = cursor.fetchone()

        if resultado:
            conn.close()
            return resultado[0]

        print(f"🆕 Combinación emocional no registrada: {emocion1} + {emocion2}")
        cursor.execute("""
            INSERT INTO combinaciones_no_registradas (emocion_1, emocion_2)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING;
        """, (emocion1.lower(), emocion2.lower()))

        conn.commit()
        conn.close()
        return None

    except Exception as e:
        print(f"❌ Error al gestionar combinación emocional: {e}")
        return None



def init_db():
    """
    Crea las tablas necesarias si no existen (sin palabras_clave).
    Enfocado en el flujo actual centrado en historial_clinico_usuario.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # ------------------ Conversación base ------------------
        cur.execute("""
        CREATE TABLE IF NOT EXISTS interacciones (
            id           SERIAL PRIMARY KEY,
            user_id      TEXT NOT NULL,
            consulta     TEXT NOT NULL,
            fecha        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS respuestas_openai (
            id             SERIAL PRIMARY KEY,
            interaccion_id BIGINT,
            respuesta      TEXT NOT NULL,
            fecha          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Emociones detectadas por interacción (si la estás usando)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS emociones_detectadas (
            id        SERIAL PRIMARY KEY,
            user_id   TEXT NOT NULL,
            emocion   TEXT NOT NULL,
            fecha     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # ------------------ Motor clínico unificado ------------------
        cur.execute("""
        CREATE TABLE IF NOT EXISTS historial_clinico_usuario (
            id                           SERIAL PRIMARY KEY,
            user_id                      TEXT NOT NULL,
            fecha                        TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            emociones                    TEXT[],       -- emociones acumuladas en ese corte
            sintomas                     TEXT[],       -- si los usás
            tema                         TEXT,
            respuesta_openai             TEXT,
            sugerencia                   TEXT,
            fase_evaluacion              TEXT,
            fuente                       TEXT,         -- "db" | "openai" | etc
            eliminado                    BOOLEAN DEFAULT FALSE,
            interaccion_id               BIGINT,
            origen                       TEXT,
            cuadro_clinico_probable      TEXT,
            nuevas_emociones_detectadas  TEXT[],
            fecha_ultima_interaccion     TIMESTAMPTZ
        );
        """)

        # Índices útiles
        cur.execute("CREATE INDEX IF NOT EXISTS idx_hist_clinico_user ON historial_clinico_usuario(user_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_hist_clinico_fecha ON historial_clinico_usuario(fecha);")

        # ------------------ Disparadores / combinaciones ------------------
        cur.execute("""
        CREATE TABLE IF NOT EXISTS disparadores_emocionales (
            id                SERIAL PRIMARY KEY,
            emocion_1         TEXT NOT NULL,
            emocion_2         TEXT NOT NULL,
            texto_disparador  TEXT NOT NULL
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS combinaciones_no_registradas (
            id         SERIAL PRIMARY KEY,
            emocion_1  TEXT NOT NULL,
            emocion_2  TEXT NOT NULL,
            fecha      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # ------------------ Auditorías / logs ------------------
        cur.execute("""
        CREATE TABLE IF NOT EXISTS auditoria_input_original (
            id             SERIAL PRIMARY KEY,
            user_id        TEXT,
            input_original TEXT,
            fecha          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS auditoria_respuestas (
            id                 SERIAL PRIMARY KEY,
            user_id            TEXT,
            respuesta_original TEXT,
            respuesta_filtrada TEXT,
            motivo             TEXT,
            fecha              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS faq_similitud_logs (
            id        SERIAL PRIMARY KEY,
            user_id   TEXT,
            pregunta  TEXT,
            candidato TEXT,
            score     NUMERIC,
            fecha     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS primer_input_log (
            id     SERIAL PRIMARY KEY,
            user_id TEXT,
            input   TEXT,
            fecha   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        conn.commit()
        cur.close()
        conn.close()
        print("✅ init_db(): tablas verificadas/creadas correctamente (sin palabras_clave).")

    except Exception as e:
        print(f"❌ Error en init_db(): {e}")




def ejecutar_consulta(query, valores=None, commit=False):
    try:
        cursor = conn.cursor()
        cursor.execute(query, valores)
        if commit:
            conn.commit()
        try:
            return cursor.fetchall()
        except psycopg2.ProgrammingError:
            return None
    except Exception as e:
        print(f"🔴 Error en ejecutar_consulta: {e}")
        raise
    finally:
        cursor.close()
