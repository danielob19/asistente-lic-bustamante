import psycopg2
from datetime import datetime, timedelta
from core.constantes import DATABASE_URL


def obtener_emociones_ya_registradas(user_id, interaccion_id):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("""
            SELECT emocion FROM emociones_detectadas
            WHERE user_id = %s AND contexto = %s
        """, (user_id, f"interacción {interaccion_id}"))
        resultados = cur.fetchall()
        emociones = [r[0].lower().strip() for r in resultados]
        cur.close()
        conn.close()
        return emociones
    except Exception as e:
        print(f"❌ Error al obtener emociones ya registradas en la BD: {e}")
        return []


def obtener_sintomas_existentes():
    """
    Devuelve un conjunto con todos los síntomas registrados, en minúsculas.
    Ideal para evitar duplicados o comparar de forma insensible a mayúsculas.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("SELECT LOWER(sintoma) FROM palabras_clave")
        sintomas = {row[0] for row in cursor.fetchall()}
        conn.close()
        return sintomas
    except Exception as e:
        print(f"❌ Error al obtener síntomas existentes: {e}")
        return set()


def obtener_sintomas_con_estado_emocional():
    """
    Devuelve una lista de tuplas (sintoma, estado_emocional) desde la base de datos.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("SELECT LOWER(sintoma), estado_emocional FROM palabras_clave")
        resultados = cursor.fetchall()
        conn.close()
        return resultados
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
