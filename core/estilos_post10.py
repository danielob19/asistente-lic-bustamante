# core/estilos_post10.py

import random

CIERRES_BASICOS = [
    "Como indiqué antes, no puedo continuar.",
    "La conversación ha llegado a su fin.",
    "No tengo más recursos que ofrecerte aquí.",
    "Como mencioné antes, ya he concluido esta conversación.",
    "No puedo avanzar más en esta vía.",
    "He alcanzado mi límite de intervención."
]

RECORDATORIOS_PROFESIONALES = [
    "Te sugiero que lo consultes con el Lic. Daniel O. Bustamante para una mejor orientación.",
    "Recordá que el Lic. Bustamante podría ayudarte con mayor profundidad.",
    "Te recuerdo que sería recomendable que consultes al Lic. Daniel O. Bustamante para continuar.",
    "Una evaluación clínica directa con el Lic. Bustamante sería lo más indicado."
]

HIPOTESIS_PSICODINAMICAS = [
    "A veces estos sentimientos aparecen como defensa frente a un temor más profundo.",
    "Este tipo de vivencias podrían vincularse con experiencias tempranas no resueltas.",
    "Quizás haya una parte de vos que busca protección frente a una amenaza emocional no identificada.",
    "En ocasiones, el retraimiento puede funcionar como escudo ante vínculos que generan ambivalencia."
]

def seleccionar_estilo_clinico_variable():
    respuesta = random.choice(CIERRES_BASICOS)

    if random.choice([1, 2, 3]) == 1:
        recordatorio = random.choice(RECORDATORIOS_PROFESIONALES)
        respuesta += " " + recordatorio

    if random.choice([1, 2, 3, 4]) == 1:
        hipotesis = random.choice(HIPOTESIS_PSICODINAMICAS)
        respuesta += " " + hipotesis

    return respuesta
