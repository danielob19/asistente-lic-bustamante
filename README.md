# Asistente Lic. Bustamante

¡Bienvenido al **Asistente Lic. Bustamante**!  
Este proyecto es un asistente profesional diseñado para interactuar con usuarios mediante el modelo de **OpenAI**, analizar síntomas y entregar respuestas breves y profesionales.

## Descripción del Proyecto

El asistente:
- Responde profesionalmente a las consultas del usuario.
- Limita las respuestas a un máximo de **70 palabras**.
- Puede sugerir al usuario contactar al **Lic. Daniel O. Bustamante** si lo considera oportuno.

---

## Requisitos Previos

1. **Claves y Configuración Necesarias**:
   - Una **clave API válida de OpenAI**.
   - Variables de entorno configuradas para el proyecto.

---

## Archivos Principales

### `app.py`
Contiene el código principal de la aplicación **Flask**:
- **`GET /`**: Ruta de prueba básica.
- **`POST /asistente`**: Procesa mensajes, interactúa con el motor de IA y devuelve una respuesta al usuario.

### `requirements.txt`
Dependencias necesarias para ejecutar el proyecto:
- **Flask** y **Flask-CORS** – Servidor web y control de acceso.
- **OpenAI** – Interacción con el modelo de IA.
- **Python-dotenv** – Gestión de variables de entorno.
- **Requests**, **SQLAlchemy** – Utilidades de red y base de datos.

---

## Arquitectura del Proyecto

El asistente está organizado en capas:

- **Rutas (`routes/`)** → Controladores HTTP (por ejemplo, `asistente.py`).
- **Core (`core/`)**:
  - **`funciones_asistente.py`** – Lógica principal de respuesta.
  - **`funciones_clinicas.py`** – Procesamiento clínico.
  - **`inferencia_psicodinamica.py`** – Interpretación avanzada.
  - **`resumen_clinico.py`** – Generación de resúmenes.
  - **`utils_contacto.py`** – Recomendaciones de contacto.
  - **`utils_seguridad.py`** – Filtrado y seguridad.
- **Base de conocimiento (`base_de_conocimiento.json`)** → Datos predefinidos para respuestas.
- **Palabras clave (`palabras_clave_adaptada.csv`)** → Identificación rápida de temas relevantes.

---

## Despliegue

### Pasos para desplegar en Render
1. **Configura la aplicación**:
   - Fuente: Conecta tu repositorio de GitHub.
   - Comando de instalación:  
     ```bash
     pip install -r requirements.txt
     ```
   - Comando de inicio:  
     ```bash
     gunicorn app:app
     ```
2. **Configura variables de entorno**:
   - `OPENAI_API_KEY` → Tu clave de OpenAI.
3. **Despliega la aplicación**:
   - Render construirá y pondrá en línea tu asistente.

---

## Pruebas

### Probar ruta inicial
```bash
curl -X GET https://<tu-app>.onrender.com/
