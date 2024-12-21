import openai
import sqlite3
import random
from collections import Counter

class Chatbot:
    def __init__(self, db_path, openai_api_key):
        self.db_path = db_path
        self.interaction_count = 0
        self.responses_variations = [
            "Gracias por tu paciencia. Por favor, continúa compartiendo cómo te sientes.",
            "Entendido, cuéntame más sobre cómo te estás sintiendo.",
            "Aprecio que compartas esto conmigo. ¿Qué más puedes decirme?",
            "Es útil saber esto. Por favor, sigue describiendo cómo te sientes.",
        ]
        openai.api_key = openai_api_key

    def connect_db(self):
        return sqlite3.connect(self.db_path)

    def detect_emotions(self, text):
        keywords = ["fracasado", "ansioso", "angustia"]  # Ejemplo de palabras clave
        detected = [word for word in text.lower().split() if word in keywords]
        return detected

    def update_db_with_new_emotions(self, emotions):
        with self.connect_db() as conn:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS emociones (emocion TEXT UNIQUE)")
            for emotion in emotions:
                try:
                    cursor.execute("INSERT INTO emociones (emocion) VALUES (?)", (emotion,))
                except sqlite3.IntegrityError:
                    pass
            conn.commit()

    def check_existing_emotions(self, emotions):
        with self.connect_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT emocion FROM emociones")
            existing = {row[0] for row in cursor.fetchall()}
        return [emotion for emotion in emotions if emotion in existing]

    def generate_response(self, prompt):
        try:
            response = openai.Completion.create(
                engine="text-davinci-003",
                prompt=prompt,
                max_tokens=150,
                temperature=0.7
            )
            return response.choices[0].text.strip()
        except Exception as e:
            return "Lo siento, hubo un problema generando una respuesta. Por favor, intenta nuevamente."

    def respond(self, user_input):
        self.interaction_count += 1
        detected_emotions = self.detect_emotions(user_input)
        existing_emotions = self.check_existing_emotions(detected_emotions)

        if detected_emotions:
            self.update_db_with_new_emotions([e for e in detected_emotions if e not in existing_emotions])

        if self.interaction_count < 5:
            prompt = f"Un usuario dice: '{user_input}'. Responde de manera profesional y empática."
            return self.generate_response(prompt)

        elif self.interaction_count == 5:
            if existing_emotions:
                return ("En base a los s\u00edntomas referidos ({0}), pareciera tratarse de una afecci\u00f3n o cuadro relacionado con un cuadro de angustia. Por lo que te sugiero contactar al Lic. Daniel O. Bustamante, un profesional especializado, al WhatsApp +54 911 3310-1186. ".format(", ".join(existing_emotions)))
            else:
                return "Agradezco tu tiempo. Por favor, contacta a un profesional para obtener una evaluaci\u00f3n m\u00e1s completa."

        elif self.interaction_count == 6:
            return "Si bien debo concluir nuestra conversaci\u00f3n, no obstante te sugiero contactar al Lic. Daniel O. Bustamante, un profesional especializado, al WhatsApp +54 911 3310-1186. Un saludo."

        else:
            return "Gracias por confiar en m\u00ed. Espero que obtengas la ayuda que necesitas."

# Uso del chatbot
chatbot = Chatbot("/mnt/data/palabras_clave.db", "tu_openai_api_key")

while True:
    user_input = input("Usuario: ")
    if user_input.lower() in ["salir", "adios"]:
        print("Chatbot: Hasta luego. ¡Cuida de ti!")
        break
    response = chatbot.respond(user_input)
    print(f"Chatbot: {response}")
