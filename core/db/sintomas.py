# core/db/sintomas.py

from typing import Iterable, List, Tuple, Set
import psycopg2
from psycopg2.extras import RealDictCursor
from core.constantes import DATABASE_URL


def _get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


# ---------------------------------------------------------------------
# API mantenida (reimplementada sobre historial_clinico_usuario)
# ---------------------------------------------------------------------

def registrar_sintoma(
    sintoma: str,
    estado_emocional: str | None = None,
    *,
    user_id: str | None = None,
    interaccion_id: int | None = None,
    fuente: str = "sintomas.py"
) -> None:
    """
    Guarda un 'sintoma' como término observado dentro de historial_clinico_usuario.
    - estado_emocional, si viene, se guarda en 'cuadro_clinico_probable' (texto).
    - El término se agrega al array 'emociones' (si preferís 'sintomas', cámbialo abajo).
    """
    sintoma = (sintoma or "").strip().lower()
    if not sintoma:
        return

    try:
        with _get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO historial_clinico_usuario
                  (user_id, fecha, emociones, sintomas, cuadro_clinico_probable, fuente, interaccion_id)
                VALUES
                  (%s, NOW(),
                   ARRAY[%s]::text[],           -- guardamos en 'emociones' por compatibilidad
                   ARRAY[]::text[],             -- si quisieras usar 'sintomas', duplicá aquí también
                   %s,
                   %s,
                   %s)
                """,
                (user_id, sintoma, estado_emocional, fuente, interaccion_id),
            )
    except Exception as e:
        print(f"[sintomas.registrar_sintoma] Error: {e}")


def obtener_sintomas_existentes() -> Set[str]:
    """
    Devuelve un set con TODOS los términos observados históricamente
    (de columnas emociones y sintomas), en minúsculas.
    """
    try:
        with _get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                WITH terms AS (
                  SELECT LOWER(UNNEST(COALESCE(emociones, ARRAY[]::text[]))) AS t
                  FROM historial_clinico_usuario
                  UNION ALL
                  SELECT LOWER(UNNEST(COALESCE(sintomas,  ARRAY[]::text[]))) AS t
                  FROM historial_clinico_usuario
                )
                SELECT DISTINCT t FROM terms WHERE t <> '';
                """
            )
            rows = cur.fetchall()
            return {row["t"] for row in rows}
    except Exception as e:
        print(f"[sintomas.obtener_sintomas_existentes] Error: {e}")
        return set()


def obtener_sintomas_con_estado_emocional() -> List[Tuple[str, str | None]]:
    """
    Devuelve pares (termino, cuadro_clinico_probable).
    Toma términos de emociones+sintomas y los asocia con el último
    'cuadro_clinico_probable' no nulo registrado junto a ese término (si existe).
    """
    try:
        with _get_conn() as conn, conn.cursor() as cur:
            # Unimos términos y nos quedamos con el cuadro de la fila más reciente que lo contiene
            cur.execute(
                """
                WITH flat AS (
                  SELECT
                    id,
                    fecha,
                    LOWER(UNNEST(COALESCE(emociones, ARRAY[]::text[]))) AS termino,
                    cuadro_clinico_probable
                  FROM historial_clinico_usuario
                  UNION ALL
                  SELECT
                    id,
                    fecha,
                    LOWER(UNNEST(COALESCE(sintomas, ARRAY[]::text[]))) AS termino,
                    cuadro_clinico_probable
                  FROM historial_clinico_usuario
                ),
                ranked AS (
                  SELECT
                    termino,
                    cuadro_clinico_probable,
                    ROW_NUMBER() OVER (PARTITION BY termino ORDER BY fecha DESC, id DESC) AS rk
                  FROM flat
                  WHERE termino <> ''
                )
                SELECT termino, cuadro_clinico_probable
                FROM ranked
                WHERE rk = 1;
                """
            )
            rows = cur.fetchall()
            return [(row["termino"], row["cuadro_clinico_probable"]) for row in rows]
    except Exception as e:
        print(f"[sintomas.obtener_sintomas_con_estado_emocional] Error: {e}")
        return []




