import os
import time
import openai

# ✅ Configurar la API key aquí, donde se usa
openai.api_key = os.getenv("OPENAI_API_KEY")

def generar_respuesta_con_openai(
    prompt: str,
    contador: int = None,
    user_id: str = None,
    mensaje_usuario: str = None,
    mensaje_original: str = None,
) -> str | None:
    """
    Wrapper estable para ChatCompletion:
    - temperature=0
    - max_tokens≈200 (latencia/costo bajos, formato más estricto)
    - reintentos con backoff ante errores/transitorios
    - si corta por longitud, reintenta con cupo mayor
    """

    # Podés sobreescribir el modelo por env si querés
    modelo = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

    MAX_TOKENS_PRIMARY = 200
    MAX_TOKENS_FALLBACK = 400
    TIMEOUT_SECONDS = 12
    RETRIES = 2  # cantidad de reintentos ante fallo (además del intento inicial)

    for intento in range(RETRIES + 1):
        try:
            respuesta = openai.ChatCompletion.create(
                model=modelo,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=MAX_TOKENS_PRIMARY,
                n=1,
                request_timeout=TIMEOUT_SECONDS,
            )

            choice = respuesta.choices[0]
            contenido = (choice.message.content or "").strip()

            # Si se quedó corto por tokens, damos un segundo intento con más cupo
            if choice.get("finish_reason") == "length":
                try:
                    respuesta2 = openai.ChatCompletion.create(
                        model=modelo,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0,
                        max_tokens=MAX_TOKENS_FALLBACK,
                        n=1,
                        request_timeout=TIMEOUT_SECONDS,
                    )
                    contenido = (respuesta2.choices[0].message.content or "").strip()
                except Exception as e_len:
                    print(f"⚠️ Reintento por length falló: {e_len}")

            # Log opcional
            try:
                print(f"🧠 OpenAI respondió (contador={contador}) → {contenido}")
            except Exception:
                pass

            return contenido or None

        except Exception as e:
            # Error transitorio (timeout / rate-limit / red, etc.) → backoff y reintento
            print(f"⚠️ OpenAI intento {intento + 1} falló: {e}")
            # backoff exponencial suave
            sleep_s = 0.5 * (2**intento)
            time.sleep(sleep_s)

    # Si todos los intentos fallaron
    print("[ERROR OPENAI] agotados intentos")
    return None
