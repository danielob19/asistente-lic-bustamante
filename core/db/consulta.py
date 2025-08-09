import psycopg2
from datetime import datetime, timedelta
from core.constantes import DATABASE_URL
from typing import Optional

def obtener_emociones_ya_registradas(user_id: str, interaccion_id: Optional[int] = None):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        if interaccion_id is not None:
            cur.execute("""
                SELECT emocion FROM emociones_detectadas
                WHERE user_id = %s AND contexto = %s
            """, (user_id, f"interacción {interaccion_id}"))
        else:
            cur.execute("""
                SELECT emocion FROM emociones_detectadas
                WHERE user_id = %s
            """, (user_id,))

        resultados = cur.fetchall()
        emociones = [r[0].lower().strip() for r in resultados]

        cur.close()
        conn.close()
        return emociones

    except Exception as e:
        print(f"❌ Error al obtener emociones ya registradas en la BD: {e}")
        return []




def obtener_sintomas_existentes() -> set[str]:
    """
    Retorna un set de 'síntomas/emociones' conocidos a partir de historial_clinico_usuario.
    Ya no usa la tabla palabras_clave.
    """
    try:
        with psycopg2.connect(DATABASE_URL) as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT LOWER(unnest(emociones))
                FROM historial_clinico_usuario
                WHERE emociones IS NOT NULL
            """)
            return {row[0] for row in cur.fetchall() if row and row[0]}
    except Exception as e:
        print(f"ℹ️ Cache de síntomas deshabilitada (usa historial_clinico_usuario): {e}")
        return set()





def obtener_sintomas_con_estado_emocional():
    """
    Devuelve una lista de tuplas (sintoma, cuadro_clinico_probable) a partir
    de historial_clinico_usuario. Si el cuadro es NULL, devuelve None.
    """
    try:
        import psycopg2
        from core.constantes import DATABASE_URL

        with psycopg2.connect(DATABASE_URL) as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT LOWER(s) AS sintoma,
                                LOWER(cuadro_clinico_probable) AS cuadro
                FROM historial_clinico_usuario
                CROSS JOIN LATERAL UNNEST(sintomas) AS s
                WHERE s IS NOT NULL AND s <> ''
                """
            )
            resultados = cursor.fetchall()
            # resultados: List[Tuple[str, Optional[str]]]
            return [(row[0], row[1]) for row in resultados]
    except Exception as e:
        print(f"❌ Error al obtener síntomas con estado emocional: {e}")
        return []



def obtener_combinaciones_no_registradas(dias=7):
    """
    Devuelve una lista de combinaciones emocionales detectadas por el bot
    pero que aún no tienen frase registrada. Filtra por los últimos 'dias'.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        fecha_limite = datetime.now() - timedelta(days=dias)

        consulta = """
            SELECT emocion_1, emocion_2, fecha 
            FROM combinaciones_no_registradas
            WHERE fecha >= %s
            ORDER BY fecha DESC;
        """
        cursor.execute(consulta, (fecha_limite,))
        combinaciones = cursor.fetchall()
        conn.close()

        print(f"\n📋 Combinaciones emocionales no registradas (últimos {dias} días):")
        for emocion_1, emocion_2, fecha in combinaciones:
            print(f" - {emocion_1} + {emocion_2} → {fecha.strftime('%Y-%m-%d %H:%M')}")

        return combinaciones

    except Exception as e:
        print(f"❌ Error al obtener combinaciones no registradas: {e}")
        return []

def es_saludo(texto: str) -> bool:
    """
    Detecta si el texto contiene un saludo inicial.
    """
    saludos = ["hola", "buenas", "buenos días", "buenas tardes", "buenas noches", "qué tal", "como estás", "cómo te va"]
    texto = texto.lower()
    return any(saludo in texto for saludo in saludos)


def es_cortesia(texto: str) -> bool:
    """
    Detecta si el texto contiene una expresión de cortesía o cierre amable.
    """
    expresiones = ["gracias", "muchas gracias", "muy amable", "te agradezco", "ok gracias", "buena jornada", "saludos"]
    texto = texto.lower()
    return any(expresion in texto for expresion in expresiones)


def contiene_expresion_administrativa(texto: str) -> bool:
    """
    Detecta si el texto contiene términos administrativos comunes.
    """
    frases_administrativas = ["arancel", "valor", "costo", "duración", "modalidad", "turno", "día y horario", "sesión", "forma de pago", "atención"]
    texto = texto.lower()
    return any(frase in texto for frase in frases_administrativas)

from core.db.conexion import ejecutar_consulta

def obtener_historial_clinico_usuario(user_id: str):
    query = """
        SELECT id, user_id, fecha, emociones, sintomas, tema,
               respuesta_openai, sugerencia, fase_evaluacion,
               interaccion_id, fuente, eliminado
        FROM historial_clinico_usuario
        WHERE user_id = %s AND eliminado = false
        ORDER BY fecha DESC
    """
    return ejecutar_consulta(query, (user_id,))
