import psycopg2
from psycopg2.extras import RealDictCursor
from core.constantes import DATABASE_URL

def ejecutar_consulta(query, params=None, commit=False):
    conn = None
    resultados = None
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            if commit:
                conn.commit()
            else:
                try:
                    resultados = cursor.fetchall()
                except psycopg2.ProgrammingError:
                    resultados = None
    except Exception as e:
        print(f"❌ Error en ejecutar_consulta: {e}")
    finally:
        if conn:
            conn.close()
    return resultados
