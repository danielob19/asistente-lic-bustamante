# core/db/utilidades.py

import psycopg2
from config import DATABASE_URL

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
    Crea las tablas necesarias si no existen en PostgreSQL.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS palabras_clave (
                id SERIAL PRIMARY KEY,
                sintoma TEXT UNIQUE NOT NULL,
                cuadro TEXT NOT NULL
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interacciones (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                consulta TEXT NOT NULL,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS emociones_detectadas (
                id SERIAL PRIMARY KEY,
                emocion TEXT NOT NULL,
                contexto TEXT NOT NULL,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS faq_similitud_logs (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                consulta TEXT NOT NULL,
                pregunta_faq TEXT NOT NULL,
                similitud FLOAT NOT NULL,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inferencias_cerebro_simulado (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                interaccion_id INTEGER NOT NULL,
                tipo TEXT NOT NULL,
                valor TEXT NOT NULL,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        conn.commit()
        conn.close()
        print("Base de datos inicializada en PostgreSQL.")

    except Exception as e:
        print(f"Error al inicializar la base de datos: {e}")
