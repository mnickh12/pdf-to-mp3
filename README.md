# PDF a audio

Programa independiente que convierte entre PDF y audio en las dos direcciones. Hay dos formas de usarlo: con ventana (recomendado) o por línea de comandos.

## Qué incluye

- Ventana de inicio con dos opciones: **PDF a MP3** y **MP3 a PDF**.
- **PDF a MP3**: voz natural gratuita (voces neuronales de Microsoft Edge), con reserva automática a Google Translate TTS si esa falla. Elección de voz: español (hombre/mujer), español latino (hombre/mujer), inglés, francés, alemán, italiano, portugués.
- **MP3 a PDF**: transcribe un audio (mp3, wav, m4a, ogg, flac, aac) a texto con Whisper en local, y genera un PDF con ese texto. Tres niveles de precisión (rápido/equilibrado/preciso).
- Opción de leer solo un rango de páginas del PDF (en la dirección PDF a MP3).
- Versión de línea de comandos con un motor 100% offline para PDF a MP3 (sin internet).
- Avisa, en vez de fallar en silencio, si el PDF es un escaneo sin texto, si el audio no tiene voz reconocible, o si ha tenido que recurrir a la voz de repuesto.

## Requisitos

- Python 3.10 o superior.
- Conexión a internet: siempre para la voz natural (PDF a MP3); solo la primera vez que se usa cada nivel de precisión de transcripción (MP3 a PDF), para descargar el modelo (luego funciona sin conexión).

## Instalación

```bash
pip install -r requirements.txt
```

## Uso con ventana — `pdf_a_audio_gui.py`

```bash
python3 pdf_a_audio_gui.py
```

Se abre un menú para elegir la dirección:

**PDF a MP3**
1. Elegir PDF → seleccionas el archivo.
2. Eliges la voz, si quieres que vaya más despacio, o un rango de páginas (opcional).
3. Convertir a MP3 → eliges dónde guardar el resultado.
4. Reproducir MP3 o Abrir carpeta.

**MP3 a PDF**
1. Elegir audio → seleccionas el archivo.
2. Eliges el idioma del audio (o detección automática) y el nivel de precisión.
3. Transcribir a PDF → eliges dónde guardar el resultado.
4. Abrir PDF o Abrir carpeta.

El botón "← Menú" de cada pantalla vuelve al principio.

## Uso por línea de comandos — `pdf_a_audio.py`

```bash
# PDF -> audio, voz neuronal de Microsoft Edge (recomendado, necesita internet)
python3 pdf_a_audio.py apuntes.pdf salida.mp3 --engine edge

# PDF -> audio, Google Translate TTS (necesita internet; a veces suena algo cortada)
python3 pdf_a_audio.py apuntes.pdf salida.mp3 --engine gtts

# PDF -> audio, 100% offline, con las voces instaladas en el sistema
python3 pdf_a_audio.py apuntes.pdf salida.wav

# Audio -> PDF (transcripción), detectando el idioma
python3 pdf_a_audio.py grabacion.mp3 transcripcion.pdf --modo mp32pdf

# Audio -> PDF, forzando idioma y precisión
python3 pdf_a_audio.py grabacion.mp3 transcripcion.pdf --modo mp32pdf --transcribe-lang es --whisper-model small

# Ver las voces instaladas en el sistema (solo para el motor offline de PDF a MP3)
python3 pdf_a_audio.py --list-voices

# Solo un rango de páginas de un PDF, guardando también el texto extraído
python3 pdf_a_audio.py apuntes.pdf salida.mp3 --engine edge --pagina-inicio 3 --pagina-fin 10 --guardar-texto revision.txt
```

Todas las opciones: `python3 pdf_a_audio.py --help`

## Solución de problemas

**`ModuleNotFoundError: No module named 'edge_tts'` (o `faster_whisper`, `reportlab`)**
Falta instalar esa dependencia: `pip install <nombre>` (o repite `pip install -r requirements.txt`).

**El aviso de estado sale en ámbar, no en verde (PDF a MP3)**
Significa que la voz neuronal de Microsoft no respondió y se ha usado la de repuesto (Google). El propio mensaje indica el motivo.

**`open() got an unexpected keyword argument 'metadata_errors'` (MP3 a PDF)**
Incompatibilidad entre `faster-whisper` y una versión demasiado nueva de `av` (PyAV). Solución: `pip install "av<19"` (ya viene fijado así en `requirements.txt`).

**"No se ha reconocido ninguna voz en el audio" (MP3 a PDF)**
El archivo no tiene contenido hablado reconocible, o el volumen es muy bajo. Prueba con un nivel de precisión mayor o comprueba el archivo.

**La primera transcripción con un nivel de precisión tarda mucho / pide internet**
Es normal: cada nivel (rápido/equilibrado/preciso) descarga su modelo la primera vez que se usa. Las siguientes veces ya no hace falta conexión ni espera.

**El PDF de entrada no genera ningún audio / avisa de que no hay texto**
Es probable que sea un escaneo (imágenes) sin capa de texto real debajo. Este programa no hace OCR.

## Licencia

MIT License — [mnickh12](https://github.com/mnickh12)
