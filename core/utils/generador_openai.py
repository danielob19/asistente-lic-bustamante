import os
import time
import openai
from typing import Optional

# ✅ Configurar la API key aquí, donde se usa
openai.api_key = os.getenv("OPENAI_API_KEY")

def generar_respuesta_con_openai(
    prompt: str,
    contador: int | None = None,
    user_id: str | None = None,
    mensaje_usuario: str | None = None,
    mensaje_original: str | None = None,
    *,
    temperature: float | None = None,   # nuevo: parámetro oficial en inglés
    max_tokens: int | None = None,      # nuevo: permite override de tokens
    **kwargs,                           # nuevo: tolera kwargs extra (compat futura)
) -> str | None:
    """
    Wrapper estable para ChatCompletion:
    - Acepta 'temperature' y el alias 'temperatura' (compat en español).
    - Reintentos con backoff ante fallos transitorios.
    - Si corta por longitud, reintenta con más cupo de tokens.
    """

    # Alias compatible para llamadas antiguas: 'temperatura='
    if temperature is None:
        temperature = kwargs.pop("temperatura", None)

    # Defaults si no pasan nada
    if temperature is None:
        temperature = 0.2  # antes usabas 0; podés volver a 0 si preferís ese estilo
    MAX_TOKENS_PRIMARY = max_tokens or 200
    MAX_TOKENS_FALLBACK = max(400, MAX_TOKENS_PRIMARY * 2)  # mantiene tu 400 por defecto

    # Podés sobreescribir el modelo por env si querés
    modelo = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

    TIMEOUT_SECONDS = 12
    RETRIES = 2  # cantidad de reintentos ante fallo (además del intento inicial)

    for intento in range(RETRIES + 1):
        try:
            respuesta = openai.ChatCompletion.create(
                model=modelo,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=MAX_TOKENS_PRIMARY,
                n=1,
                request_timeout=TIMEOUT_SECONDS,
            )

            choice = respuesta.choices[0]
            # robusto: soporte atributo/clave indistintamente
            try:
                contenido = (choice.message["content"] if isinstance(choice.message, dict) else choice.message.content).strip()
            except Exception:
                # fallback súper conservador
                contenido = (getattr(choice, "text", "") or "").strip()

            # ¿cortó por longitud? reintentamos con más cupo
            finish_reason = getattr(choice, "finish_reason", None)
            if not finish_reason:
                try:
                    finish_reason = choice.get("finish_reason")
                except Exception:
                    pass

            if finish_reason == "length":
                try:
                    respuesta2 = openai.ChatCompletion.create(
                        model=modelo,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=temperature,
                        max_tokens=MAX_TOKENS_FALLBACK,
                        n=1,
                        request_timeout=TIMEOUT_SECONDS,
                    )
                    choice2 = respuesta2.choices[0]
                    try:
                        contenido = (choice2.message["content"] if isinstance(choice2.message, dict) else choice2.message.content).strip()
                    except Exception:
                        contenido = (getattr(choice2, "text", "") or "").strip()
                except Exception as e_len:
                    print(f"⚠️ Reintento por length falló: {e_len}")

            # Log opcional
            try:
                print(f"🧠 OpenAI respondió (contador={contador}) → {contenido}")
            except Exception:
                pass

            return contenido or None

        except Exception as e:
            print(f"⚠️ OpenAI intento {intento + 1} falló: {e}")
            time.sleep(0.5 * (2 ** intento))  # backoff exponencial suave

    print("[ERROR OPENAI] agotados intentos")
    return None
