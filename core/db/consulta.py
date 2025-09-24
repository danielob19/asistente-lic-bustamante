import psycopg2
from datetime import datetime, timedelta
from core.constantes import DATABASE_URL
from typing import Optional
from .conexion import ejecutar_consulta
from typing import List, Optional


def obtener_emociones_ya_registradas(user_id: str) -> set[str]:
    """
    Devuelve el conjunto de emociones registradas para el usuario `user_id`,
    combinando `emociones` ∪ `nuevas_emociones_detectadas` desde
    public.historial_clinico_usuario (solo registros no eliminados).
    """
    sql = """
        SELECT
            COALESCE(emociones, ARRAY[]::text[])                   AS emociones,
            COALESCE(nuevas_emociones_detectadas, ARRAY[]::text[]) AS nuevas
        FROM public.historial_clinico_usuario
        WHERE user_id = %s
          AND eliminado = false
    """
    filas = ejecutar_consulta(sql, (user_id,)) or []
    res: set[str] = set()
    for fila in filas:
        emos = (fila[0] if isinstance(fila, (list, tuple)) else fila.get("emociones")) or []
        news = (fila[1] if isinstance(fila, (list, tuple)) else fila.get("nuevas")) or []
        for e in emos:
            if e and isinstance(e, str):
                res.add(e.strip().lower())
        for e in news:
            if e and isinstance(e, str):
                res.add(e.strip().lower())
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
        FROM public.historial_clinico_usuario
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
                FROM public.historial_clinico_usuario
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
    Devuelve una lista de combinaciones emocionales registradas
    en historial_clinico_usuario en los últimos 'dias'.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        fecha_limite = datetime.now() - timedelta(days=dias)

        consulta = """
            SELECT DISTINCT emociones, fecha
            FROM public.historial_clinico_usuario
            WHERE fecha >= %s
              AND array_length(emociones, 1) > 1
            ORDER BY fecha DESC;
        """
        cursor.execute(consulta, (fecha_limite,))
        combinaciones = cursor.fetchall()
        conn.close()

        print(f"\n📋 Combinaciones emocionales registradas (últimos {dias} días):")
        for emociones, fecha in combinaciones:
            print(f" - {', '.join(emociones)} @ {fecha.strftime('%Y-%m-%d %H:%M')}")

        return combinaciones

    except Exception as e:
        print(f"❌ Error al obtener combinaciones emocionales: {e}")
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



# ===== Helpers agregados para memoria persistente y estadísticas globales =====

def obtener_historial_usuario(user_id: str, limite: int = 100):
    query = """
        SELECT
            id,
            user_id,
            fecha,
            emociones,
            nuevas_emociones_detectadas,
            cuadro_clinico_probable,
            interaccion_id
        FROM public.historial_clinico_usuario
        WHERE user_id = %s
          AND eliminado = false
        ORDER BY fecha DESC
        LIMIT %s
    """
    return ejecutar_consulta(query, (user_id, limite)) or []


def obtener_ultimo_registro_usuario(user_id: str):
    query = """
        SELECT
            id,
            user_id,
            fecha,
            emociones,
            nuevas_emociones_detectadas,
            cuadro_clinico_probable,
            interaccion_id
        FROM public.historial_clinico_usuario
        WHERE user_id = %s
          AND eliminado = false
        ORDER BY fecha DESC
        LIMIT 1
    """
    res = ejecutar_consulta(query, (user_id,))
    return res[0] if res else None


def estadistica_global_emocion_a_cuadro():
    """
    Devuelve filas (emocion TEXT, cuadro TEXT, c BIGINT) a partir de la memoria.
    Se usa solo como estadística/memoria; las etiquetas las define OpenAI.
    """
    query = """
        SELECT
            LOWER(e) AS emocion,
            LOWER(COALESCE(cuadro_clinico_probable, '')) AS cuadro,
            COUNT(*) AS c
        FROM public.historial_clinico_usuario
        CROSS JOIN LATERAL UNNEST(COALESCE(emociones, ARRAY[]::text[])) AS e
        WHERE eliminado = false
          AND COALESCE(cuadro_clinico_probable, '') <> ''
        GROUP BY 1, 2
        HAVING COUNT(*) >= 1
        ORDER BY c DESC
    """
    return ejecutar_consulta(query, ())



def obtener_ultima_interaccion_emocional(user_id: str) -> Optional[dict]:
    """
    Trae la última fila EMOCIONAL del usuario.
    Usa es_emocional=true para calzar con el índice parcial.
    """
    query = """
        SELECT
            id,
            user_id,
            fecha,
            emociones,
            nuevas_emociones_detectadas,
            cuadro_clinico_probable
        FROM public.historial_clinico_usuario
        WHERE user_id = %s
          AND COALESCE(eliminado, false) = false
          AND es_emocional = true
        ORDER BY fecha DESC
        LIMIT 1
    """
    rows = ejecutar_consulta(query, (user_id,))
    return rows[0] if rows else None



def registrar_interaccion_clinica(
    user_id: str,
    emociones: Optional[List[str]] = None,
    nuevas_emociones_detectadas: Optional[List[str]] = None,
    cuadro_clinico_probable: Optional[str] = None,
    respuesta_openai: Optional[str] = None,
    origen: str = "deteccion",        # ajustá si tenés otro valor por defecto
    fuente: str = "openai",
    eliminado: bool = False,
    tema: Optional[str] = None,
    sintomas: Optional[List[str]] = None,
    interaccion_id: Optional[int] = None,
) -> int:
    """
    Inserta una fila en public.historial_clinico_usuario y retorna el id generado.
    Solo usamos esta tabla para persistir el historial.
    """
    sql = """
        INSERT INTO public.historial_clinico_usuario
            (user_id, fecha, emociones, nuevas_emociones_detectadas,
             cuadro_clinico_probable, respuesta_openai, origen, fuente, eliminado,
             tema, sintomas, interaccion_id)
        VALUES
            (%s, NOW(), %s, %s,
             %s, %s, %s, %s, %s,
             %s, %s, %s)
        RETURNING id
    """
    params = (
        user_id,
        emociones if emociones else None,
        nuevas_emociones_detectadas if nuevas_emociones_detectadas else None,
        (cuadro_clinico_probable or None),
        (respuesta_openai or None),
        origen,
        fuente,
        eliminado,
        (tema or None),
        sintomas if sintomas else None,
        interaccion_id,
    )
    rows = ejecutar_consulta(sql, params)
    return rows[0]["id"]

