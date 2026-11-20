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
from typing import Callable


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
# Programa principal
# --------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convierte el texto de un PDF a un archivo de audio.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("pdf", nargs="?", help="Ruta del PDF de entrada")
    parser.add_argument("salida", nargs="?", help="Ruta del audio de salida (.wav para pyttsx3, .mp3 para gtts)")
    parser.add_argument("--engine", choices=["pyttsx3", "edge", "gtts"], default="pyttsx3",
                         help="Motor de voz: pyttsx3 (offline), edge (online, voz neuronal, recomendado) o gtts (online)")
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

        if not args.pdf or not args.salida:
            parser.error("hacen falta los argumentos 'pdf' y 'salida' (o usa --list-voices)")

        ruta_pdf = Path(args.pdf)
        if not ruta_pdf.is_file():
            sys.exit(f"No encuentro el archivo: {ruta_pdf}")

        print(f"Leyendo: {ruta_pdf.name}")
        texto = extraer_texto(ruta_pdf, args.pagina_inicio, args.pagina_fin)
        print()  # salto de línea tras el progreso en \r
        texto = limpiar_texto(texto)
        print(f"Texto extraído: {len(texto)} caracteres.")

        if args.guardar_texto:
            Path(args.guardar_texto).write_text(texto, encoding="utf-8")
            print(f"Texto guardado en: {args.guardar_texto}")

        salida = Path(args.salida)
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
