# Asistente Lic. Bustamante

Un asistente profesional basado en inteligencia artificial para ayudar a los usuarios a identificar y gestionar malestares emocionales, con integración de **OpenAI GPT-3.5-Turbo**, **Google Sheets** y **Flask**.

## Características
- Procesa síntomas reportados en un flujo conversacional.
- Integra datos a una hoja de cálculo en **Google Sheets** para análisis.
- Genera respuestas profesionales utilizando **OpenAI GPT-3.5-Turbo**.
- Desplegado en **Render** con soporte para solicitudes HTTP mediante **Flask**.

## Requisitos previos
- **Python 3.7 o superior.**
- Archivo de credenciales JSON para Google Sheets.
- Clave API de **OpenAI**.
- Hoja de cálculo en Google Sheets configurada como `Asistente_Lic_Bustamante` con la pestaña `tab2`.

## Instalación
### 1. Clonar el repositorio
```bash
git clone https://github.com/danielob19/asistente-lic-bustamante.git
cd asistente-lic-bustamante
