# core/db/conexion.py
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from core.constantes import DATABASE_URL  # Debe estar seteada en tu entorno/constantes

logger = logging.getLogger(__name__)

def obtener_conexion(timeout: int = 5):
    """
    Abre una conexión a PostgreSQL con parámetros seguros para Render:
    - sslmode='require' (TLS obligatorio)
    - keepalives para conexiones más estables
    - connect_timeout para evitar cuelgues
    """
    return psycopg2.connect(
        dsn=DATABASE_URL,
        sslmode="require",          # Render: TLS obligatorio
        connect_timeout=timeout,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5,
    )


def ejecutar_consulta(query: str, params=None, commit: bool = False):
    """
    Ejecuta una consulta de forma segura.
    - SELECT: devuelve list[dict] (posiblemente vacía).
    - INSERT/UPDATE/DELETE con commit=True: devuelve True si se confirmó, False si falló.
    - Nunca propaga excepciones: loggea y devuelve [] / False según corresponda.
    """
    params = params or ()
    conn = None
    try:
        conn = obtener_conexion()
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
        logger.exception("DB query failed", extra={"query": query, "commit": commit})
        return False if commit else []
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                # No volver a lanzar excepciones en el cierre
                pass
