# core/db/utilidades.py

from core.constantes import DATABASE_URL
from core.db.conexion import ejecutar_consulta as ejecutar_consulta_db
import psycopg2


def gestionar_combinacion_emocional(emocion1, emocion2):
    """
    Devuelve la frase clínica para la combinación (emocion1, emocion2).
    Si no existe, registra la combinación en 'combinaciones_no_registradas'.
    Nunca rompe: ante error devuelve "".
    """
    try:
        # 1) Intentar frase ya cargada (nombres de columnas según tu tabla)
        sel = """
            SELECT texto_disparador
            FROM disparadores_emocionales
            WHERE (emocion_1 = %s AND emocion_2 = %s)
               OR (emocion_1 = %s AND emocion_2 = %s)
            LIMIT 1;
        """
        rows = ejecutar_consulta_db(sel, (emocion1, emocion2, emocion2, emocion1)) or []
        if rows:
            # RealDictCursor → dict. Si en tu tabla el campo se llama distinto, dejamos fallback.
            frase = (rows[0] or {}).get("texto_disparador") or (rows[0] or {}).get("frase")
            if frase:
                return frase

        # 2) Si no existe, registrar la combinación (best effort, no rompe si falla)
        ins = """
            INSERT INTO combinaciones_no_registradas (emocion_1, emocion_2)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING;
        """
        _ = ejecutar_consulta_db(ins, (str(emocion1).lower(), str(emocion2).lower()), commit=True)

        return ""  # default seguro si no hay frase configurada

    except Exception as e:
        print(f"⚠️ gestionar_combinacion_emocional falló: {e}")
        return ""




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
    return ejecutar_consulta_db(query, valores, commit)

