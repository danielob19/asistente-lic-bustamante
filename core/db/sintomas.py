import openai
import psycopg2
from core.constantes import DATABASE_URL


def registrar_sintoma(sintoma: str, estado_emocional: str = None):
    """
    Registra un síntoma en la base de datos con su estado emocional.
    Si no se proporciona, se clasifica automáticamente con OpenAI.
    """
    if not estado_emocional or not estado_emocional.strip():
        try:
            prompt = (
                f"Asigna un estado emocional clínicamente relevante a la siguiente emoción o síntoma: '{sintoma}'.\n\n"
                "Seleccioná un estado con base en categorías clínicas como trastornos, síndromes o patrones emocionales reconocidos.\n"
                "Si no corresponde a ninguno en particular, clasificá como 'Patrón emocional detectado'.\n"
                "Respondé exclusivamente con el nombre del estado, sin explicaciones.\n\n"
                "Ejemplos válidos:\n"
                "- Trastorno de ansiedad\n"
                "- Cuadro de depresión\n"
                "- Estrés postraumático\n"
                "- Baja autoestima\n"
                "- Desgaste emocional\n"
                "- Sentimientos de inutilidad\n"
                "- Insomnio crónico\n"
                "- Patrón emocional detectado"
            )

            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=50,
                temperature=0.0
            )

            estado_emocional = response.choices[0].message["content"].strip()

            if not estado_emocional:
                print(f"⚠️ OpenAI devolvió vacío. Se asignará 'Patrón emocional detectado' para '{sintoma}'.")
                estado_emocional = "Patrón emocional detectado"

            print(f"🧠 OpenAI asignó: '{estado_emocional}' para '{sintoma}'")

        except Exception as e:
            print(f"❌ Error al clasificar '{sintoma}' con OpenAI: {e}")
            estado_emocional = "Patrón emocional detectado"

    # Insertar o actualizar en la base
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO palabras_clave (sintoma, estado_emocional)
            VALUES (%s, %s)
            ON CONFLICT (sintoma) DO UPDATE SET estado_emocional = EXCLUDED.estado_emocional;
        """, (sintoma.strip().lower(), estado_emocional))
        conn.commit()
        conn.close()
        print(f"✅ Síntoma '{sintoma}' registrado con estado emocional '{estado_emocional}'.")
    except Exception as e:
        print(f"❌ Error al registrar síntoma '{sintoma}' en la base: {e}")


def actualizar_sintomas_sin_estado_emocional():
    """
    Busca síntomas en la base de datos que no tienen estado_emocional asignado,
    les solicita una clasificación clínica a OpenAI y los actualiza.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        cursor.execute("SELECT sintoma FROM palabras_clave WHERE estado_emocional IS NULL;")
        sintomas_pendientes = [row[0] for row in cursor.fetchall()]
        conn.close()

        if not sintomas_pendientes:
            print("✅ No hay síntomas pendientes de clasificación.")
            return

        print(f"🔍 Clasificando {len(sintomas_pendientes)} síntomas sin estado_emocional...")

        for sintoma in sintomas_pendientes:
            prompt = (
                f"Asigná un estado emocional clínico adecuado al siguiente síntoma: '{sintoma}'.\n\n"
                "Seleccioná un estado emocional clínico compatible con clasificaciones como: Trastorno de ansiedad, Depresión mayor, Estrés postraumático, "
                "Baja autoestima, Desgaste emocional, etc.\n\n"
                "Si el síntoma no se vincula a un estado clínico específico, respondé con: 'Patrón emocional detectado'.\n\n"
                "Respondé solo con el estado, sin explicaciones."
            )

            try:
                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=50,
                    temperature=0.0
                )

                estado_emocional = response["choices"][0]["message"]["content"].strip()
                print(f"📌 Estado emocional para '{sintoma}': {estado_emocional}")

                conn = psycopg2.connect(DATABASE_URL)
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE palabras_clave SET estado_emocional = %s WHERE sintoma = %s;",
                    (estado_emocional, sintoma)
                )
                conn.commit()
                conn.close()

            except Exception as e:
                print(f"⚠️ Error al clasificar o actualizar '{sintoma}': {e}")

    except Exception as e:
        print(f"❌ Error al conectar para actualizar síntomas: {e}")

def obtener_sintomas_existentes():
    """
    Devuelve todos los síntomas almacenados en la base de datos como un conjunto en minúsculas.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("SELECT LOWER(sintoma) FROM palabras_clave;")
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
        cursor.execute("SELECT LOWER(sintoma), estado_emocional FROM palabras_clave;")
        resultados = cursor.fetchall()
        conn.close()
        return resultados
    except Exception as e:
        print(f"❌ Error al obtener síntomas con estado emocional: {e}")
        return []


def obtener_coincidencias_sintomas_y_registrar(emociones):
    """
    Busca coincidencias exactas en la base de datos con las emociones detectadas.
    Si alguna no existe, se registra como síntoma nuevo y se actualiza su estado emocional.
    """
    if not emociones:
        return []

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        print("\n===== DEPURACIÓN SQL =====")
        print("Emociones detectadas:", emociones)

        # Buscar coincidencias exactas
        consulta = "SELECT sintoma, estado_emocional FROM palabras_clave WHERE sintoma = ANY(%s);"
        cursor.execute(consulta, (emociones,))
        resultados = cursor.fetchall()

        estados_emocionales = [r[1] for r in resultados]
        sintomas_encontrados = [r[0] for r in resultados]

        print("Síntomas en BD:", sintomas_encontrados)
        print("Estados emocionales encontrados:", estados_emocionales)

        # Detectar emociones no registradas y agregarlas
        emociones_nuevas = [e for e in emociones if e not in sintomas_encontrados]
        for emocion in emociones_nuevas:
            registrar_sintoma(emocion, None)

        conn.commit()
        conn.close()

        # Clasificación posterior
        actualizar_sintomas_sin_estado_emocional()

        return estados_emocionales if estados_emocionales else []

    except Exception as e:
        print(f"❌ Error al obtener o registrar síntomas: {e}")
        return []

