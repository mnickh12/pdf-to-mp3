# PDF a audio

## Qué incluye

- Interfaz gráfica sencilla: elegir PDF, elegir voz, convertir, guardar el MP3 donde quieras.
- Voz natural gratuita (voces neuronales de Microsoft Edge), con reserva automática a Google Translate TTS si esa falla.
- Elección de voz: español (hombre/mujer), español latino (hombre/mujer), inglés, francés, alemán, italiano, portugués.
- Opción de leer solo un rango de páginas del PDF.
- Versión de línea de comandos con un tercer motor 100% offline (sin internet).
- Avisa, en vez de fallar en silencio, si el PDF es un escaneo sin texto, o si ha tenido que recurrir a la voz de repuesto.

## Requisitos

- Python 3.10 o superior.
- Conexión a internet para la voz natural (ambos motores online la necesitan).

## Instalación

```bash
pip install -r requirements.txt
```

## Uso con ventana — pdf_a_audio_gui.py

```bash
python3 pdf_a_audio_gui.py
```

1. Elegir PDF → seleccionas el archivo.
2. Eliges la voz, si quieres que vaya más despacio, o un rango de páginas (opcional).
3. Convertir a MP3 → eliges dónde guardar el resultado.
4. Al terminar, Reproducir MP3 o Abrir carpeta.

Si la voz neuronal de Microsoft no responde, la app avisa en ámbar y usa una voz de repuesto (Google), que no distingue hombre/mujer.

## Uso por línea de comandos — pdf_a_audio.py

```bash
# Voz neuronal de Microsoft Edge, la más natural (recomendado, necesita internet)
python3 pdf_a_audio.py apuntes.pdf salida.mp3 --engine edge

# Google Translate TTS (necesita internet; a veces suena algo cortada)
python3 pdf_a_audio.py apuntes.pdf salida.mp3 --engine gtts

# 100% offline, con las voces instaladas en el sistema
python3 pdf_a_audio.py apuntes.pdf salida.wav

# Ver las voces instaladas en el sistema (solo para el motor offline)
python3 pdf_a_audio.py --list-voices

# Solo un rango de páginas, guardando también el texto extraído para revisarlo
python3 pdf_a_audio.py apuntes.pdf salida.mp3 --engine edge --pagina-inicio 3 --pagina-fin 10 --guardar-texto revision.txt
```

Todas las opciones: `python3 pdf_a_audio.py --help`

## Solución de problemas

**ModuleNotFoundError: No module named 'edge_tts'**
Falta instalar la dependencia: `pip install edge-tts` (o repite `pip install -r requirements.txt`).

**El aviso de estado sale en ámbar, no en verde**
Significa que la voz neuronal de Microsoft no respondió y se ha usado la de repuesto (Google). El propio mensaje indica el motivo del fallo (normalmente, conexión a internet).

**El PDF no genera ningún audio / avisa de que no hay texto**
Es probable que el PDF sea un escaneo (imágenes) sin capa de texto real debajo. Este programa no hace OCR.

## Licencia

MIT License — [mnickh12](https://github.com/mnickh12)
