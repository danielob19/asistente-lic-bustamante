# core/db/conexion.py
import psycopg2
from psycopg2.extras import RealDictCursor
from core.constantes import DATABASE_URL
import logging

logger = logging.getLogger(__name__)

def ejecutar_consulta(query: str, params=None, commit: bool = False):
    """
    Ejecuta una consulta segura:
    - Nunca propaga excepciones (evita 500).
    - SELECT: devuelve list[dict] (posiblemente vacía).
    - INSERT/UPDATE/DELETE con commit=True: devuelve True si se confirmó, False si falló.
    """
    params = params or ()
    try:
        # Ajusta sslmode si tu proveedor lo exige (por ej. 'require')
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=5)  # , sslmode="require"
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                if commit:
                    return True
                try:
                    rows = cur.fetchall()
                except psycopg2.ProgrammingError:
                    rows = []
                return rows or []
    except Exception:
        # Log estructurado + stack trace
        logger.exception("ejecutar_consulta falló", extra={
            "query": query,
            "commit": commit,
        })
        return False if commit else []
