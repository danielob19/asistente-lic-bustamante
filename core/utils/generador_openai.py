import os
import time
import openai
from typing import Optional

# ✅ Configurar la API key aquí, donde se usa
openai.api_key = os.getenv("OPENAI_API_KEY")

# core/utils/generador_openai.py

def generar_respuesta_con_openai(
    prompt: str,
    contador: int | None = None,
    user_id: str | None = None,
    mensaje_usuario: str | None = None,
    mensaje_original: str | None = None,
    # ✅ nuevos kwargs tolerados
    temperatura: float | None = None,
    max_tokens: int | None = None,
) -> str | None:
    """
    Wrapper estable para ChatCompletion:
    - temperature configurable (default 0.0)
    - max_tokens configurable (default 200; fallback 400)
    - reintentos con backoff
    """

    modelo = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

    temp = 0.0 if temperatura is None else float(temperatura)
    MAX_TOKENS_PRIMARY = 200 if max_tokens is None else int(max_tokens)
    MAX_TOKENS_FALLBACK = max(400, MAX_TOKENS_PRIMARY)
    TIMEOUT_SECONDS = 12
    RETRIES = 2

    for intento in range(RETRIES + 1):
        try:
            respuesta = openai.ChatCompletion.create(
                model=modelo,
                messages=[{"role": "user", "content": prompt}],
                temperature=temp,
                max_tokens=MAX_TOKENS_PRIMARY,
                n=1,
                request_timeout=TIMEOUT_SECONDS,
            )
            choice = respuesta.choices[0]
            contenido = (choice.message.content or "").strip()

            # Si cortó por tokens, segundo intento con más cupo
            if choice.get("finish_reason") == "length":
                try:
                    respuesta2 = openai.ChatCompletion.create(
                        model=modelo,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=temp,
                        max_tokens=MAX_TOKENS_FALLBACK,
                        n=1,
                        request_timeout=TIMEOUT_SECONDS,
                    )
                    contenido = (respuesta2.choices[0].message.content or "").strip()
                except Exception as e_len:
                    print(f"⚠️ Reintento por length falló: {e_len}")

            try:
                print(f"🧠 OpenAI respondió (contador={contador}) → {contenido}")
            except Exception:
                pass

            return contenido or None

        except Exception as e:
            print(f"⚠️ OpenAI intento {intento + 1} falló: {e}")
            time.sleep(0.5 * (2 ** intento))

    print("[ERROR OPENAI] agotados intentos")
    return None
