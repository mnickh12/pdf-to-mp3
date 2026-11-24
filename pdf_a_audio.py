#!/usr/bin/env python3
"""
pdf_a_audio.py — Convierte el texto de un PDF a un archivo de audio.

Programa independiente, sin relación con ningún otro proyecto. Solo necesita
Python y un par de librerías (ver requirements.txt).

Tres motores de voz, a elegir con --engine:
  - pyttsx3 (por defecto): funciona SIN INTERNET, usa las voces instaladas
    en el propio sistema (en Windows, las de "Configuración > Hora e idioma
    > Voz"). Genera un .wav.
  - edge: voces neuronales de Microsoft Edge (gratis, sin cuenta ni API key;
    son las mismas del "Leer en voz alta" de Edge). Necesita CONEXIÓN A
    INTERNET. Lee el texto de corrido, sin los cortes artificiales que tiene
    gtts. Genera un .mp3. Es el motor recomendado para voz natural.
  - gtts: usa Google Translate TTS, necesita CONEXIÓN A INTERNET. Internamente
    trocea el texto en fragmentos muy cortos, lo que a veces se nota como
    pausas raras a mitad de frase. Se mantiene por compatibilidad. Genera .mp3.

Uso básico:
    python pdf_a_audio.py "apuntes.pdf" salida.wav
    python pdf_a_audio.py "apuntes.pdf" salida.mp3 --engine edge

Ver todas las opciones:
    python pdf_a_audio.py --help

Ver las voces instaladas en el sistema (para elegir con --voice):
    python pdf_a_audio.py --list-voices
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Callable


class ErrorConversion(Exception):
    """Error esperado (PDF protegido, sin texto, sin internet...). Se usa en
    vez de sys.exit() en las funciones reutilizables, para que tanto la CLI
    como la interfaz gráfica puedan capturarlo y mostrarlo a su manera (la
    CLI lo imprime y sale; la GUI lo muestra en un diálogo sin cerrarse)."""


# Función de progreso por defecto: imprime en la terminal (comportamiento de
# la CLI). La GUI pasa la suya propia para actualizar su etiqueta de estado.
ProgresoFn = Callable[[str], None]


def _progreso_consola(mensaje: str) -> None:
    print(mensaje, end="\r", flush=True)


# --------------------------------------------------------------------------
# Extracción de texto del PDF
# --------------------------------------------------------------------------
def extraer_texto(
    ruta_pdf: Path,
    pagina_inicio: int | None,
    pagina_fin: int | None,
    progreso: ProgresoFn = _progreso_consola,
) -> str:
    """Extrae el texto del PDF, página a página, informando del progreso."""
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ErrorConversion(
            "Falta la librería 'pypdf'. Instálala con:\n"
            "    pip install pypdf"
        )

    try:
        lector = PdfReader(str(ruta_pdf))
    except Exception as e:
        raise ErrorConversion(f"No se pudo abrir el PDF: {e}")

    if lector.is_encrypted:
        try:
            lector.decrypt("")  # algunos PDF solo tienen restricciones, sin contraseña real
        except Exception:
            raise ErrorConversion(
                "El PDF está protegido con contraseña. Quítale la protección antes "
                "de convertirlo (por ejemplo, abriéndolo en un lector y guardando una "
                "copia sin contraseña)."
            )

    total = len(lector.pages)
    inicio = max(1, pagina_inicio or 1)
    fin = min(total, pagina_fin or total)
    if inicio > fin:
        raise ErrorConversion(f"Rango de páginas inválido: el PDF tiene {total} páginas.")

    partes: list[str] = []
    paginas_vacias = 0
    for i in range(inicio - 1, fin):
        progreso(f"Leyendo página {i + 1}/{fin}...")
        try:
            texto_pagina = lector.pages[i].extract_text() or ""
        except Exception:
            texto_pagina = ""
        if not texto_pagina.strip():
            paginas_vacias += 1
        partes.append(texto_pagina)

    if paginas_vacias == (fin - inicio + 1):
        raise ErrorConversion(
            "No se ha podido extraer texto de ninguna página del rango indicado.\n"
            "Es muy probable que este PDF sea un escaneo (imágenes) sin capa de texto.\n"
            "Este programa no hace OCR: necesitarías pasarlo antes por una herramienta de "
            "reconocimiento de texto (OCR) para generar un PDF con texto real."
        )
    if paginas_vacias:
        progreso(f"Aviso: {paginas_vacias} página(s) del rango no tenían texto extraíble (se omiten).")

    return "\n".join(partes)


def limpiar_texto(texto: str) -> str:
    """Limpieza básica para que la voz suene mejor: junta palabras cortadas
    por guion al saltar de línea, colapsa saltos de línea y espacios sueltos."""
    texto = re.sub(r"-\n(?=\w)", "", texto)          # palabra-\nsiguiente -> palabrasiguiente
    texto = re.sub(r"[ \t]*\n[ \t]*", " ", texto)     # saltos de línea -> espacio
    texto = re.sub(r"\s{2,}", " ", texto)             # varios espacios -> uno
    return texto.strip()


# --------------------------------------------------------------------------
# Motor offline: pyttsx3 (voces instaladas en el sistema)
# --------------------------------------------------------------------------
def listar_voces_pyttsx3() -> None:
    try:
        import pyttsx3
    except ImportError:
        raise ErrorConversion("Falta la librería 'pyttsx3'. Instálala con:\n    pip install pyttsx3")

    motor = pyttsx3.init()
    voces = motor.getProperty("voices")
    if not voces:
        print("No se ha encontrado ninguna voz instalada en el sistema.")
        return
    print(f"Voces disponibles ({len(voces)}):\n")
    for i, v in enumerate(voces):
        idiomas = getattr(v, "languages", None) or ""
        print(f"  [{i}] {v.name}  (id interno: {v.id})  {idiomas}")
    print("\nUsa --voice <número> para elegir una, por ejemplo: --voice 1")


def texto_a_audio_pyttsx3(
    texto: str, salida: Path, voz: int | None, velocidad: int, volumen: float,
    progreso: ProgresoFn = _progreso_consola,
) -> Path:
    try:
        import pyttsx3
    except ImportError:
        raise ErrorConversion("Falta la librería 'pyttsx3'. Instálala con:\n    pip install pyttsx3")

    motor = pyttsx3.init()

    voces = motor.getProperty("voices")
    if voz is not None:
        if not (0 <= voz < len(voces)):
            raise ErrorConversion(f"--voice {voz} no es válido. Hay {len(voces)} voces (usa --list-voices para verlas).")
        motor.setProperty("voice", voces[voz].id)
    else:
        # Intento automático de usar una voz en español si hay alguna instalada
        for v in voces:
            nombre = (v.name or "").lower()
            idiomas = " ".join(getattr(v, "languages", []) or []).lower()
            if "spanish" in nombre or "español" in nombre or "es_" in idiomas or "es-" in idiomas:
                motor.setProperty("voice", v.id)
                break

    motor.setProperty("rate", velocidad)
    motor.setProperty("volume", max(0.0, min(1.0, volumen)))

    if salida.suffix.lower() != ".wav":
        progreso(f"Aviso: con --engine pyttsx3 la salida siempre es .wav; se usará '{salida.with_suffix('.wav')}'.")
        salida = salida.with_suffix(".wav")

    progreso(f"Generando audio (offline) en: {salida}")
    motor.save_to_file(texto, str(salida))
    motor.runAndWait()
    return salida


# --------------------------------------------------------------------------
# Motor online: gTTS (Google Translate TTS)
# --------------------------------------------------------------------------
def texto_a_audio_gtts(
    texto: str, salida: Path, idioma: str, velocidad_lenta: bool,
    progreso: ProgresoFn = _progreso_consola,
) -> Path:
    try:
        from gtts import gTTS
    except ImportError:
        raise ErrorConversion("Falta la librería 'gTTS'. Instálala con:\n    pip install gTTS")

    if salida.suffix.lower() != ".mp3":
        progreso(f"Aviso: con --engine gtts la salida siempre es .mp3; se usará '{salida.with_suffix('.mp3')}'.")
        salida = salida.with_suffix(".mp3")

    # gTTS tiene un límite práctico de texto por petición; lo troceamos por
    # tamaño (respetando puntos para no cortar frases) y unimos los audios.
    trozos = _trocear_texto(texto, max_chars=4500)
    progreso(f"Generando audio (requiere internet) en {len(trozos)} parte(s)...")

    archivos_temporales: list[Path] = []
    try:
        for i, trozo in enumerate(trozos, 1):
            progreso(f"Generando audio: parte {i}/{len(trozos)}...")
            tts = gTTS(text=trozo, lang=idioma, slow=velocidad_lenta)
            if len(trozos) == 1:
                tts.save(str(salida))
                return salida
            temporal = salida.with_name(f"{salida.stem}.part{i}.mp3")
            tts.save(str(temporal))
            archivos_temporales.append(temporal)
        _unir_mp3(archivos_temporales, salida)
        return salida
    except ErrorConversion:
        raise
    except Exception as e:
        raise ErrorConversion(
            f"Fallo generando el audio con gTTS: {e}\n"
            "Comprueba tu conexión a internet; este motor necesita contactar con Google Translate."
        )
    finally:
        for f in archivos_temporales:
            f.unlink(missing_ok=True)


def _trocear_texto(texto: str, max_chars: int) -> list[str]:
    if len(texto) <= max_chars:
        return [texto]
    trozos, actual = [], ""
    for frase in re.split(r"(?<=[.!?])\s+", texto):
        if len(actual) + len(frase) + 1 > max_chars and actual:
            trozos.append(actual.strip())
            actual = ""
        actual += frase + " "
    if actual.strip():
        trozos.append(actual.strip())
    return trozos


def _unir_mp3(partes: list[Path], salida: Path) -> None:
    """Concatena varios mp3 en uno solo. Un mp3 es, en la práctica, varios
    frames consecutivos, así que unir los bytes en orden funciona bien aquí
    (son todos generados por la misma librería y configuración)."""
    with open(salida, "wb") as out:
        for p in partes:
            out.write(p.read_bytes())


# --------------------------------------------------------------------------
# Motor online recomendado: voces neuronales de Microsoft Edge (edge-tts)
# --------------------------------------------------------------------------
# Un puñado de voces en español e inglés, pensadas para elegir por nombre
# sencillo en la interfaz; "edge-tts --list-voices" en una terminal da el
# listado completo si se quieren más idiomas o voces.
VOCES_EDGE = {
    "Español (mujer)": "es-ES-ElviraNeural",
    "Español (hombre)": "es-ES-AlvaroNeural",
    "Español latino (mujer)": "es-MX-DaliaNeural",
    "Español latino (hombre)": "es-MX-JorgeNeural",
    "Inglés (mujer)": "en-US-AvaNeural",
    "Inglés (hombre)": "en-US-AndrewNeural",
    "Francés (mujer)": "fr-FR-DeniseNeural",
    "Alemán (mujer)": "de-DE-KatjaNeural",
    "Italiano (mujer)": "it-IT-ElsaNeural",
    "Portugués (mujer)": "pt-PT-RaquelNeural",
}
VOZ_EDGE_POR_DEFECTO = "Español (hombre)"


def texto_a_audio_edge(
    texto: str, salida: Path, voz: str, velocidad_lenta: bool,
    progreso: ProgresoFn = _progreso_consola,
) -> Path:
    try:
        import edge_tts
    except ImportError:
        raise ErrorConversion("Falta la librería 'edge-tts'. Instálala con:\n    pip install edge-tts")

    if salida.suffix.lower() != ".mp3":
        progreso(f"Aviso: con --engine edge la salida siempre es .mp3; se usará '{salida.with_suffix('.mp3')}'.")
        salida = salida.with_suffix(".mp3")

    progreso("Generando audio (requiere internet, voz neuronal de Microsoft Edge)...")

    import asyncio

    async def _generar() -> None:
        comunicador = edge_tts.Communicate(texto, voz, rate="-15%" if velocidad_lenta else "+0%")
        await comunicador.save(str(salida))

    try:
        asyncio.run(_generar())
    except Exception as e:
        raise ErrorConversion(
            f"Fallo generando el audio con las voces de Microsoft Edge: {e}\n"
            "Comprueba tu conexión a internet; este motor necesita contactar con el "
            "servicio de voz de Microsoft Edge (no hace falta tener el navegador Edge abierto)."
        )

    if not salida.exists() or salida.stat().st_size == 0:
        raise ErrorConversion(
            "El servicio de voz no devolvió ningún audio. Vuelve a intentarlo; si persiste, "
            "prueba con --engine gtts."
        )
    return salida


# --------------------------------------------------------------------------
# Audio -> texto (transcripción), con Whisper en local (sin internet una vez
# descargado el modelo la primera vez)
# --------------------------------------------------------------------------
IDIOMAS_TRANSCRIPCION = {
    "Detectar automáticamente": None,
    "Español": "es",
    "Inglés": "en",
    "Francés": "fr",
    "Alemán": "de",
    "Italiano": "it",
    "Portugués": "pt",
}

# tiny/base/small: cuanto más grande, más preciso pero más lento y más RAM.
TAMANOS_MODELO_TRANSCRIPCION = {
    "Rápido": "tiny",
    "Equilibrado": "base",
    "Preciso": "small",
}
TAMANO_MODELO_POR_DEFECTO = "Equilibrado"

# El modelo se descarga de internet LA PRIMERA VEZ que se usa cada tamaño
# (unos 75-500 MB según el tamaño) y se queda guardado en el equipo; las
# siguientes veces ya no hace falta conexión. Se cachea en memoria durante la
# ejecución del programa para no recargarlo en cada conversión.
_MODELOS_WHISPER_CARGADOS: dict[str, Any] = {}


def _cargar_modelo_whisper(tamano: str, progreso: ProgresoFn) -> Any:
    if tamano in _MODELOS_WHISPER_CARGADOS:
        return _MODELOS_WHISPER_CARGADOS[tamano]
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise ErrorConversion("Falta la librería 'faster-whisper'. Instálala con:\n    pip install faster-whisper")

    progreso(f"Cargando el modelo de transcripción ({tamano})... la primera vez puede tardar, y necesita internet.")
    try:
        modelo = WhisperModel(tamano, device="cpu", compute_type="int8")
    except Exception as e:
        raise ErrorConversion(
            f"No se pudo cargar el modelo de transcripción: {e}\n"
            "La primera vez que se usa cada modelo hace falta conexión a internet para descargarlo "
            "(se queda guardado para las siguientes veces)."
        )
    _MODELOS_WHISPER_CARGADOS[tamano] = modelo
    return modelo


def audio_a_texto(
    ruta_audio: Path,
    idioma: str | None,
    tamano_modelo: str,
    progreso: ProgresoFn = _progreso_consola,
) -> str:
    """Transcribe un archivo de audio (mp3, wav, m4a, ogg...) a texto."""
    modelo = _cargar_modelo_whisper(tamano_modelo, progreso)

    progreso("Analizando el audio...")
    try:
        segmentos, info = modelo.transcribe(str(ruta_audio), language=idioma, vad_filter=True)
    except Exception as e:
        raise ErrorConversion(
            f"No se pudo leer el audio: {e}\n"
            "Comprueba que el archivo no esté dañado y que su formato sea uno habitual (mp3, wav, m4a, ogg)."
        )

    duracion = max(info.duration, 0.001)
    partes: list[str] = []
    try:
        for seg in segmentos:
            partes.append(seg.text.strip())
            minutos, segs = divmod(int(seg.end), 60)
            tmin, tsegs = divmod(int(duracion), 60)
            progreso(f"Transcribiendo... {minutos:02d}:{segs:02d} / {tmin:02d}:{tsegs:02d}")
    except Exception as e:
        raise ErrorConversion(f"Fallo durante la transcripción: {e}")

    texto = " ".join(p for p in partes if p)
    if not texto.strip():
        raise ErrorConversion(
            "No se ha reconocido ninguna voz en el audio. Comprueba que el archivo tenga "
            "contenido hablado y un volumen razonable."
        )
    return texto


# --------------------------------------------------------------------------
# Texto -> PDF
# --------------------------------------------------------------------------
def texto_a_pdf(texto: str, salida: Path, titulo: str, progreso: ProgresoFn = _progreso_consola) -> Path:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except ImportError:
        raise ErrorConversion("Falta la librería 'reportlab'. Instálala con:\n    pip install reportlab")

    if salida.suffix.lower() != ".pdf":
        progreso(f"Aviso: la salida siempre es .pdf; se usará '{salida.with_suffix('.pdf')}'.")
        salida = salida.with_suffix(".pdf")

    progreso("Generando el PDF...")

    estilos = getSampleStyleSheet()
    estilo_titulo = estilos["Title"]
    estilo_cuerpo = estilos["BodyText"]
    estilo_cuerpo.fontSize = 11
    estilo_cuerpo.leading = 16

    # Whisper devuelve el texto como un bloque continuo; se trocea en
    # "párrafos" de unas pocas frases para que no sea un único muro de texto.
    frases = re.split(r"(?<=[.!?])\s+", texto.strip())
    parrafos: list[str] = []
    actual: list[str] = []
    for frase in frases:
        actual.append(frase)
        if len(actual) >= 5:
            parrafos.append(" ".join(actual))
            actual = []
    if actual:
        parrafos.append(" ".join(actual))

    # Los textos van por XML-escaping básico, ya que reportlab interpreta
    # algunos caracteres (<, >, &) como si fueran etiquetas.
    def escapar(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    elementos = [Paragraph(escapar(titulo), estilo_titulo), Spacer(1, 0.6 * cm)]
    for p in parrafos:
        elementos.append(Paragraph(escapar(p), estilo_cuerpo))
        elementos.append(Spacer(1, 0.3 * cm))

    try:
        doc = SimpleDocTemplate(
            str(salida), pagesize=A4,
            leftMargin=2.2 * cm, rightMargin=2.2 * cm, topMargin=2.2 * cm, bottomMargin=2.2 * cm,
        )
        doc.build(elementos)
    except Exception as e:
        raise ErrorConversion(f"No se pudo generar el PDF: {e}")

    return salida


# --------------------------------------------------------------------------
# Programa principal
# --------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convierte el texto de un PDF a un archivo de audio.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("entrada", nargs="?", help="PDF de entrada (--modo pdf2mp3) o audio de entrada (--modo mp32pdf)")
    parser.add_argument("salida", nargs="?", help="Audio de salida (--modo pdf2mp3) o PDF de salida (--modo mp32pdf)")
    parser.add_argument("--modo", choices=["pdf2mp3", "mp32pdf"], default="pdf2mp3",
                         help="pdf2mp3: PDF -> audio (por defecto). mp32pdf: audio -> PDF (transcripción)")
    parser.add_argument("--engine", choices=["pyttsx3", "edge", "gtts"], default="pyttsx3",
                         help="[pdf2mp3] Motor de voz: pyttsx3 (offline), edge (online, voz neuronal, recomendado) o gtts (online)")
    parser.add_argument("--whisper-model", choices=list(TAMANOS_MODELO_TRANSCRIPCION.values()), default="base",
                         help="[mp32pdf] Tamaño del modelo de transcripción: tiny (rápido), base (equilibrado) o small (preciso)")
    parser.add_argument("--transcribe-lang", default=None,
                         help="[mp32pdf] Idioma del audio (es, en, fr...); vacío = detectar automáticamente")
    parser.add_argument("--titulo", default=None,
                         help="[mp32pdf] Título del PDF generado; por defecto, el nombre del archivo de audio")
    parser.add_argument("--pagina-inicio", type=int, default=None, help="Primera página a leer (1 = primera)")
    parser.add_argument("--pagina-fin", type=int, default=None, help="Última página a leer")
    parser.add_argument("--voice", type=int, default=None,
                         help="Índice de la voz a usar con pyttsx3 (ver --list-voices)")
    parser.add_argument("--rate", type=int, default=175, help="Velocidad del habla con pyttsx3 (palabras/min aprox.)")
    parser.add_argument("--volume", type=float, default=1.0, help="Volumen con pyttsx3, entre 0.0 y 1.0")
    parser.add_argument("--lang", default="es", help="Idioma para gtts (es, en, fr...)")
    parser.add_argument("--slow", action="store_true", help="Con gtts, hablar más despacio")
    parser.add_argument("--guardar-texto", metavar="ARCHIVO.txt", default=None,
                         help="Además del audio, guarda el texto extraído en un .txt (útil para revisar qué se leyó)")
    parser.add_argument("--list-voices", action="store_true",
                         help="Lista las voces instaladas en el sistema (para pyttsx3) y termina")
    args = parser.parse_args()

    try:
        if args.list_voices:
            listar_voces_pyttsx3()
            return

        if not args.entrada or not args.salida:
            parser.error("hacen falta los argumentos de entrada y salida (o usa --list-voices)")

        ruta_entrada = Path(args.entrada)
        if not ruta_entrada.is_file():
            sys.exit(f"No encuentro el archivo: {ruta_entrada}")
        salida = Path(args.salida)

        if args.modo == "mp32pdf":
            print(f"Transcribiendo: {ruta_entrada.name}")
            texto = audio_a_texto(ruta_entrada, args.transcribe_lang, args.whisper_model)
            print()
            print(f"Texto transcrito: {len(texto)} caracteres.")
            if args.guardar_texto:
                Path(args.guardar_texto).write_text(texto, encoding="utf-8")
                print(f"Texto guardado en: {args.guardar_texto}")
            texto_a_pdf(texto, salida, args.titulo or ruta_entrada.stem)
            print()
        else:
            print(f"Leyendo: {ruta_entrada.name}")
            texto = extraer_texto(ruta_entrada, args.pagina_inicio, args.pagina_fin)
            print()  # salto de línea tras el progreso en \r
            texto = limpiar_texto(texto)
            print(f"Texto extraído: {len(texto)} caracteres.")

            if args.guardar_texto:
                Path(args.guardar_texto).write_text(texto, encoding="utf-8")
                print(f"Texto guardado en: {args.guardar_texto}")

            if args.engine == "pyttsx3":
                texto_a_audio_pyttsx3(texto, salida, args.voice, args.rate, args.volume)
            elif args.engine == "edge":
                texto_a_audio_edge(texto, salida, VOCES_EDGE[VOZ_EDGE_POR_DEFECTO], args.slow)
            else:
                texto_a_audio_gtts(texto, salida, args.lang, args.slow)
            print()  # salto de línea tras el progreso en \r

    except ErrorConversion as e:
        sys.exit(str(e))

    print("Listo.")


if __name__ == "__main__":
    main()
