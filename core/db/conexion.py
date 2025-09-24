# core/db/conexion.py
import psycopg2
from psycopg2.extras import RealDictCursor
from core.constantes import DATABASE_URL

def ejecutar_consulta(query, params=None, commit=False):
    """
    Ejecuta una consulta segura:
    - Nunca propaga excepciones (evita 500).
    - Para SELECT: devuelve lista (posiblemente vacía).
    - Para INSERT/UPDATE/DELETE con commit=True: devuelve True si se confirmó, False si falló.
    """
    conn = None
    cur = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(query, params or ())
        if commit:
            conn.commit()
            return True
        try:
            rows = cur.fetchall()
        except psycopg2.ProgrammingError:
            rows = []
        return rows or []
    except Exception as e:
        # Loguea pero NO rompe el request
        print(f"🔴 ejecutar_consulta falló: {e}")
        return False if commit else []
    finally:
        try:
            if cur is not None:
                cur.close()
        except Exception:
            pass
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass
