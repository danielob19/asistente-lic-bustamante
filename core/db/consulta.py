import psycopg2
from datetime import datetime, timedelta
from core.constantes import DATABASE_URL
from typing import Optional
from .conexion import ejecutar_consulta


def obtener_emociones_ya_registradas(user_id: str) -> set[str]:
    """
    Devuelve el set de emociones ya registradas en historial_clinico_usuario, combinando
    'emociones' y 'nuevas_emociones_detectadas'.
    """
    sql = """
        SELECT COALESCE(emociones, '{}') AS emociones,
               COALESCE(nuevas_emociones_detectadas, '{}') AS nuevas
        FROM historial_clinico_usuario
        WHERE user_id = %s
    """
    filas = ejecutar_consulta(sql, (user_id,))
    res = set()
    for f in filas or []:
        for e in f.get("emociones", []) or []:
            res.add(e)
        for e in f.get("nuevas", []) or []:
            res.add(e)
    return res


def obtener_sintomas_existentes(user_id: str | None = None) -> set[str]:
    """
    Si alguna parte del código pregunta 'sintomas existentes', los tomamos de la misma tabla.
    """
    params = ()
    where = ""
    if user_id:
        where = "WHERE user_id = %s"
        params = (user_id,)

    sql = f"""
        SELECT COALESCE(sintomas, '{{}}') AS sintomas
        FROM historial_clinico_usuario
        {where}
    """
    filas = ejecutar_consulta(sql, params)
    res = set()
    for f in filas or []:
        for s in f.get("sintomas", []) or []:
            res.add(s)
    return res





def obtener_sintomas_con_estado_emocional() -> list[tuple[str, str]]:
    # Derivación mínima desde historial (sin clasificar):
    try:
        with psycopg2.connect(DATABASE_URL) as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT LOWER(unnest(emociones)) AS sintoma
                FROM historial_clinico_usuario
                WHERE emociones IS NOT NULL
            """)
            sintomas = [row[0] for row in cur.fetchall() if row and row[0]]
            # No hay “estado_emocional” en esta tabla: devolvemos etiqueta genérica
            return [(s, "patrón emocional detectado") for s in sintomas]
    except Exception as e:
        print(f"ℹ️ No se pudo derivar sintomas/estado desde historial: {e}")
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
