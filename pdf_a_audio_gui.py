#!/usr/bin/env python3
"""
pdf_a_audio_gui.py — Versión con ventana (sin terminal) de pdf_a_audio.py.

Al abrirse muestra un menú con las dos direcciones:
  - PDF a MP3: convierte el texto de un PDF en un audio con voz natural
    (voces neuronales de Microsoft Edge, necesita internet).
  - MP3 a PDF: transcribe un archivo de audio y genera un PDF con el texto
    (Whisper en local; la primera vez que se usa cada modelo necesita
    internet para descargarlo, luego funciona sin conexión).

Reutiliza toda la lógica de pdf_a_audio.py, que tiene que estar en la misma
carpeta.
"""
from __future__ import annotations

import os
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from pdf_a_audio import (
    IDIOMAS_TRANSCRIPCION,
    TAMANO_MODELO_POR_DEFECTO,
    TAMANOS_MODELO_TRANSCRIPCION,
    VOCES_EDGE,
    VOZ_EDGE_POR_DEFECTO,
    ErrorConversion,
    audio_a_texto,
    extraer_texto,
    limpiar_texto,
    texto_a_audio_edge,
    texto_a_audio_gtts,
    texto_a_pdf,
)

# --------------------------------------------------------------------------
# Paleta de colores y tipografía (compartida por todas las pantallas)
# --------------------------------------------------------------------------
COLOR_FONDO = "#F4F5F9"
COLOR_TARJETA = "#FFFFFF"
COLOR_BORDE = "#E3E5EC"
COLOR_TEXTO = "#1F2430"
COLOR_TEXTO_SUAVE = "#6B7280"
COLOR_ACENTO = "#4F46E5"
COLOR_ACENTO_HOVER = "#4338CA"
COLOR_ACENTO_SUAVE = "#EEF0FD"
COLOR_EXITO = "#15803D"
COLOR_EXITO_FONDO = "#EAF7EE"
COLOR_ERROR = "#B91C1C"
COLOR_ERROR_FONDO = "#FCEAEA"
COLOR_AVISO = "#92400E"
COLOR_AVISO_FONDO = "#FEF3E2"

FUENTE_TITULO = ("Segoe UI Semibold", 18)
FUENTE_SUBTITULO = ("Segoe UI", 10)
FUENTE_NORMAL = ("Segoe UI", 10)
FUENTE_BOTON = ("Segoe UI Semibold", 11)
FUENTE_BOTON_SECUNDARIO = ("Segoe UI", 9)
FUENTE_TARJETA_MENU = ("Segoe UI Semibold", 13)


def carpeta_descargas_o_escritorio() -> Path:
    escritorio = Path.home() / "Desktop"
    return escritorio if escritorio.is_dir() else Path.home()


def tarjeta(padre: tk.Misc) -> tk.Frame:
    """Panel blanco con borde sutil, para agrupar visualmente secciones."""
    return tk.Frame(padre, bg=COLOR_TARJETA, highlightbackground=COLOR_BORDE,
                     highlightthickness=1, bd=0)


def abrir_con_el_sistema(ruta: Path) -> None:
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(ruta))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            os.system(f'open "{ruta}"')
        else:
            os.system(f'xdg-open "{ruta}"')
    except Exception as e:
        messagebox.showerror("No se pudo abrir", str(e))


def colocar_estado(marco_estado: tk.Frame, etiqueta_estado: tk.Label, texto: str, modo: str = "normal") -> None:
    colores = {
        "normal": (COLOR_FONDO, COLOR_TEXTO_SUAVE),
        "exito": (COLOR_EXITO_FONDO, COLOR_EXITO),
        "error": (COLOR_ERROR_FONDO, COLOR_ERROR),
        "aviso": (COLOR_AVISO_FONDO, COLOR_AVISO),
    }
    fondo, texto_color = colores[modo]
    marco_estado.config(bg=fondo)
    etiqueta_estado.config(text=texto, bg=fondo, fg=texto_color)


# ==========================================================================
# Ventana principal: solo monta el estilo y cambia entre pantallas
# ==========================================================================
class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("PDF a audio")
        self.geometry("540x640")
        self.minsize(480, 580)
        self.configure(bg=COLOR_FONDO)

        self._configurar_estilo()

        self.contenedor = tk.Frame(self, bg=COLOR_FONDO)
        self.contenedor.pack(fill="both", expand=True)

        self.pantallas: dict[str, tk.Frame] = {}
        for Clase in (MenuFrame, PdfAMp3Frame, Mp3APdfFrame):
            pantalla = Clase(self.contenedor, self)
            self.pantallas[Clase.__name__] = pantalla
            pantalla.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.mostrar_pantalla("MenuFrame")

    def mostrar_pantalla(self, nombre: str) -> None:
        self.pantallas[nombre].tkraise()

    def _configurar_estilo(self) -> None:
        estilo = ttk.Style(self)
        # 'clam' es el único tema de ttk que respeta de verdad los colores
        # personalizados en Windows (el tema nativo ignora la mayoría).
        estilo.theme_use("clam")

        estilo.configure("TCombobox", fieldbackground="white", background="white",
                          arrowsize=14, padding=4)
        estilo.configure("TCheckbutton", background=COLOR_TARJETA, font=FUENTE_NORMAL)

        estilo.configure(
            "Primario.TButton", font=FUENTE_BOTON, foreground="white",
            background=COLOR_ACENTO, borderwidth=0, focusthickness=0, padding=(16, 12),
        )
        estilo.map(
            "Primario.TButton",
            background=[("disabled", "#C7C9D9"), ("active", COLOR_ACENTO_HOVER)],
            foreground=[("disabled", "#8D8FA3")],
        )

        estilo.configure(
            "Secundario.TButton", font=FUENTE_BOTON_SECUNDARIO, foreground=COLOR_TEXTO,
            background=COLOR_TARJETA, borderwidth=1, focusthickness=0, padding=(10, 8),
        )
        estilo.map(
            "Secundario.TButton",
            background=[("disabled", COLOR_TARJETA), ("active", "#F3F4F6")],
            foreground=[("disabled", "#B6B8C3")],
            bordercolor=[("!disabled", COLOR_BORDE)],
        )

        estilo.configure(
            "Acento.Horizontal.TProgressbar", troughcolor=COLOR_ACENTO_SUAVE,
            background=COLOR_ACENTO, bordercolor=COLOR_ACENTO_SUAVE,
            lightcolor=COLOR_ACENTO, darkcolor=COLOR_ACENTO, thickness=6,
        )


# ==========================================================================
# Pantalla 1: menú de inicio
# ==========================================================================
class MenuFrame(tk.Frame):
    def __init__(self, padre: tk.Misc, controlador: App) -> None:
        super().__init__(padre, bg=COLOR_FONDO)
        self.controlador = controlador

        cabecera = tk.Frame(self, bg=COLOR_ACENTO)
        cabecera.pack(fill="x")
        tk.Label(cabecera, text="🎧  PDF a audio", font=FUENTE_TITULO,
                 bg=COLOR_ACENTO, fg="white").pack(anchor="w", padx=24, pady=(20, 2))
        tk.Label(cabecera, text="Elige qué quieres convertir",
                 font=FUENTE_SUBTITULO, bg=COLOR_ACENTO, fg="#DDE0FB").pack(
            anchor="w", padx=24, pady=(0, 18))

        cuerpo = tk.Frame(self, bg=COLOR_FONDO)
        cuerpo.pack(fill="both", expand=True, padx=24, pady=28)

        self._tarjeta_menu(
            cuerpo, icono="📄 → 🔊", titulo="PDF a MP3",
            descripcion="Convierte el texto de un PDF en un audio con voz natural.",
            comando=lambda: controlador.mostrar_pantalla("PdfAMp3Frame"),
        ).pack(fill="x", pady=(0, 16))

        self._tarjeta_menu(
            cuerpo, icono="🔊 → 📄", titulo="MP3 a PDF",
            descripcion="Transcribe un audio y genera un PDF con el texto.",
            comando=lambda: controlador.mostrar_pantalla("Mp3APdfFrame"),
        ).pack(fill="x")

    def _tarjeta_menu(self, padre: tk.Misc, icono: str, titulo: str, descripcion: str, comando) -> tk.Widget:
        marco = tarjeta(padre)
        interior = tk.Frame(marco, bg=COLOR_TARJETA, cursor="hand2")
        interior.pack(fill="x", padx=22, pady=22)

        tk.Label(interior, text=icono, font=("Segoe UI", 22), bg=COLOR_TARJETA).pack(side="left", padx=(0, 18))
        texto = tk.Frame(interior, bg=COLOR_TARJETA)
        texto.pack(side="left", fill="x", expand=True)
        tk.Label(texto, text=titulo, font=FUENTE_TARJETA_MENU, bg=COLOR_TARJETA,
                 fg=COLOR_TEXTO, anchor="w").pack(fill="x")
        tk.Label(texto, text=descripcion, font=FUENTE_NORMAL, bg=COLOR_TARJETA,
                 fg=COLOR_TEXTO_SUAVE, anchor="w", wraplength=320, justify="left").pack(fill="x", pady=(2, 0))
        tk.Label(interior, text="›", font=("Segoe UI", 20), bg=COLOR_TARJETA, fg=COLOR_ACENTO).pack(side="right")

        # Toda la tarjeta es clicable, no solo un botón pequeño
        for widget in (marco, interior, texto, *interior.winfo_children(), *texto.winfo_children()):
            widget.bind("<Button-1>", lambda _e: comando())
        return marco


# ==========================================================================
# Fragmentos de interfaz comunes a las dos pantallas de conversión
# ==========================================================================
class PantallaConversionBase(tk.Frame):
    """Esqueleto compartido: cabecera con botón de volver, cuerpo con
    scroll implícito, progreso y estado. Las subclases rellenan el cuerpo
    y definen su propio hilo de trabajo."""

    def __init__(self, padre: tk.Misc, controlador: App, icono_titulo: str, titulo: str, subtitulo: str) -> None:
        super().__init__(padre, bg=COLOR_FONDO)
        self.controlador = controlador
        self.convirtiendo = False
        self.ruta_salida: Path | None = None
        self.cola: queue.Queue[tuple[str, str, str]] = queue.Queue()

        cabecera = tk.Frame(self, bg=COLOR_ACENTO)
        cabecera.pack(fill="x")
        fila_titulo = tk.Frame(cabecera, bg=COLOR_ACENTO)
        fila_titulo.pack(fill="x", padx=16, pady=(14, 2))
        tk.Button(
            fila_titulo, text="←  Menú", font=FUENTE_BOTON_SECUNDARIO,
            bg=COLOR_ACENTO, fg="white", activebackground=COLOR_ACENTO_HOVER,
            activeforeground="white", bd=0, cursor="hand2",
            command=lambda: controlador.mostrar_pantalla("MenuFrame"),
        ).pack(side="left")

        tk.Label(cabecera, text=f"{icono_titulo}  {titulo}", font=FUENTE_TITULO,
                 bg=COLOR_ACENTO, fg="white").pack(anchor="w", padx=24, pady=(4, 2))
        tk.Label(cabecera, text=subtitulo, font=FUENTE_SUBTITULO,
                 bg=COLOR_ACENTO, fg="#DDE0FB").pack(anchor="w", padx=24, pady=(0, 18))

        self.cuerpo = tk.Frame(self, bg=COLOR_FONDO)
        self.cuerpo.pack(fill="both", expand=True, padx=20, pady=18)

        self.after(100, self._revisar_cola)

    # -- piezas reutilizables para que cada subclase las use al construir su cuerpo --
    def _crear_barra_y_estado(self, padre: tk.Misc) -> None:
        self.barra = ttk.Progressbar(padre, mode="indeterminate", style="Acento.Horizontal.TProgressbar")
        self.marco_estado = tk.Frame(padre, bg=COLOR_FONDO)
        self.marco_estado.pack(fill="x")
        self.etiqueta_estado = tk.Label(
            self.marco_estado, text="", font=FUENTE_NORMAL, bg=COLOR_FONDO,
            fg=COLOR_TEXTO_SUAVE, wraplength=480, justify="left", anchor="w",
        )
        self.etiqueta_estado.pack(fill="x", ipady=6)

    def _crear_botones_finales(self, padre: tk.Misc, texto_boton_archivo: str) -> None:
        marco_final = tk.Frame(padre, bg=COLOR_FONDO)
        marco_final.pack(fill="x", pady=(10, 0))
        self.boton_abrir_archivo = ttk.Button(
            marco_final, text=texto_boton_archivo, style="Secundario.TButton",
            state="disabled", command=self._abrir_archivo,
        )
        self.boton_abrir_archivo.pack(side="left", padx=(0, 10))
        self.boton_abrir_carpeta = ttk.Button(
            marco_final, text="📁  Abrir carpeta", style="Secundario.TButton",
            state="disabled", command=self._abrir_carpeta,
        )
        self.boton_abrir_carpeta.pack(side="left")

    def _set_estado(self, texto: str, modo: str = "normal") -> None:
        colocar_estado(self.marco_estado, self.etiqueta_estado, texto, modo)

    def _set_botones_finales(self, habilitados: bool) -> None:
        estado = "normal" if habilitados else "disabled"
        self.boton_abrir_archivo.config(state=estado)
        self.boton_abrir_carpeta.config(state=estado)

    def _marcar_en_curso(self, boton_accion: ttk.Button) -> None:
        self.convirtiendo = True
        boton_accion.config(state="disabled")
        self._set_botones_finales(habilitados=False)
        self.barra.pack(fill="x", pady=(0, 8))
        self.barra.start(12)
        self._set_estado("Empezando…")

    def _revisar_cola(self) -> None:
        try:
            while True:
                tipo, mensaje, extra = self.cola.get_nowait()
                if tipo == "estado":
                    self._set_estado(mensaje)
                elif tipo == "ok":
                    texto_final = f"Listo. Guardado en: {mensaje}"
                    if extra:
                        texto_final += f"\n\n{extra}"
                    self._terminar(exito=True, mensaje=texto_final, ruta=Path(mensaje), con_aviso=bool(extra))
                elif tipo == "error":
                    self._terminar(exito=False, mensaje=mensaje, ruta=None, con_aviso=False)
        except queue.Empty:
            pass
        self.after(100, self._revisar_cola)

    def _terminar(self, exito: bool, mensaje: str, ruta: Path | None, con_aviso: bool) -> None:
        self.convirtiendo = False
        self.barra.stop()
        self.barra.pack_forget()
        self._al_terminar_rehabilitar_boton_accion()
        modo = "error" if not exito else ("aviso" if con_aviso else "exito")
        self._set_estado(mensaje, modo=modo)
        if exito and ruta is not None:
            self.ruta_salida = ruta
            self._set_botones_finales(habilitados=True)
        else:
            messagebox.showerror("No se pudo generar el resultado", mensaje)

    def _al_terminar_rehabilitar_boton_accion(self) -> None:
        raise NotImplementedError

    def _abrir_archivo(self) -> None:
        if self.ruta_salida and self.ruta_salida.exists():
            abrir_con_el_sistema(self.ruta_salida)

    def _abrir_carpeta(self) -> None:
        if self.ruta_salida and self.ruta_salida.exists():
            abrir_con_el_sistema(self.ruta_salida.parent)


# ==========================================================================
# Pantalla 2: PDF -> MP3 (la que ya existía)
# ==========================================================================
class PdfAMp3Frame(PantallaConversionBase):
    def __init__(self, padre: tk.Misc, controlador: App) -> None:
        super().__init__(
            padre, controlador, icono_titulo="📄→🔊", titulo="PDF a MP3",
            subtitulo="Convierte el texto de un PDF en un MP3 con voz natural",
        )
        self.ruta_pdf: Path | None = None
        self._construir_cuerpo()

    def _construir_cuerpo(self) -> None:
        cuerpo = self.cuerpo

        tarjeta_pdf = tarjeta(cuerpo)
        tarjeta_pdf.pack(fill="x", pady=(0, 14))
        interior_pdf = tk.Frame(tarjeta_pdf, bg=COLOR_TARJETA)
        interior_pdf.pack(fill="x", padx=18, pady=16)
        self.etiqueta_pdf = tk.Label(
            interior_pdf, text="Ningún PDF seleccionado", font=FUENTE_NORMAL,
            bg=COLOR_TARJETA, fg=COLOR_TEXTO_SUAVE, anchor="w",
        )
        self.etiqueta_pdf.pack(side="left", fill="x", expand=True)
        ttk.Button(interior_pdf, text="Elegir PDF", style="Secundario.TButton",
                   command=self._elegir_pdf).pack(side="right")

        tarjeta_opciones = tarjeta(cuerpo)
        tarjeta_opciones.pack(fill="x", pady=(0, 14))
        interior_op = tk.Frame(tarjeta_opciones, bg=COLOR_TARJETA)
        interior_op.pack(fill="x", padx=18, pady=16)

        tk.Label(interior_op, text="VOZ", font=("Segoe UI Semibold", 8),
                 bg=COLOR_TARJETA, fg=COLOR_TEXTO_SUAVE).grid(row=0, column=0, sticky="w")
        fila_voz = tk.Frame(interior_op, bg=COLOR_TARJETA)
        fila_voz.grid(row=1, column=0, columnspan=3, sticky="we", pady=(2, 14))
        self.var_voz = tk.StringVar(value=VOZ_EDGE_POR_DEFECTO)
        ttk.Combobox(fila_voz, textvariable=self.var_voz, values=list(VOCES_EDGE),
                     state="readonly", width=24).pack(side="left")
        self.var_lenta = tk.BooleanVar(value=False)
        ttk.Checkbutton(fila_voz, text="Hablar más despacio", variable=self.var_lenta).pack(side="left", padx=14)

        tk.Label(interior_op, text="PÁGINAS (OPCIONAL)", font=("Segoe UI Semibold", 8),
                 bg=COLOR_TARJETA, fg=COLOR_TEXTO_SUAVE).grid(row=2, column=0, sticky="w")
        fila_paginas = tk.Frame(interior_op, bg=COLOR_TARJETA)
        fila_paginas.grid(row=3, column=0, columnspan=3, sticky="we", pady=(2, 0))
        tk.Label(fila_paginas, text="desde", font=FUENTE_NORMAL, bg=COLOR_TARJETA, fg=COLOR_TEXTO).pack(side="left")
        self.var_pagina_inicio = tk.StringVar()
        tk.Entry(fila_paginas, textvariable=self.var_pagina_inicio, width=5,
                 relief="solid", bd=1, highlightthickness=0).pack(side="left", padx=(6, 14))
        tk.Label(fila_paginas, text="hasta", font=FUENTE_NORMAL, bg=COLOR_TARJETA, fg=COLOR_TEXTO).pack(side="left")
        self.var_pagina_fin = tk.StringVar()
        tk.Entry(fila_paginas, textvariable=self.var_pagina_fin, width=5,
                 relief="solid", bd=1, highlightthickness=0).pack(side="left", padx=(6, 14))
        tk.Label(fila_paginas, text="(vacío = todo el documento)", font=("Segoe UI", 9),
                 bg=COLOR_TARJETA, fg=COLOR_TEXTO_SUAVE).pack(side="left")

        self.boton_convertir = ttk.Button(
            cuerpo, text="Convertir a MP3", style="Primario.TButton",
            state="disabled", command=self._elegir_salida_y_convertir,
        )
        self.boton_convertir.pack(fill="x", pady=(2, 16))

        self._crear_barra_y_estado(cuerpo)
        self._crear_botones_finales(cuerpo, "▶  Reproducir MP3")

    def _al_terminar_rehabilitar_boton_accion(self) -> None:
        self.boton_convertir.config(state="normal")

    # ------------------------------------------------------------------
    def _elegir_pdf(self) -> None:
        elegido = filedialog.askopenfilename(
            title="Elige el PDF a convertir",
            initialdir=str(carpeta_descargas_o_escritorio()),
            filetypes=[("Archivos PDF", "*.pdf")],
        )
        if not elegido:
            return
        self.ruta_pdf = Path(elegido)
        self.etiqueta_pdf.config(text=self.ruta_pdf.name, fg=COLOR_TEXTO)
        self.boton_convertir.config(state="normal")
        self._set_estado("")
        self._set_botones_finales(habilitados=False)

    def _leer_rango_paginas(self) -> tuple[int | None, int | None] | None:
        def leer(valor: str) -> int | None:
            valor = valor.strip()
            return int(valor) if valor else None

        try:
            return leer(self.var_pagina_inicio.get()), leer(self.var_pagina_fin.get())
        except ValueError:
            messagebox.showerror("Páginas no válidas", "Las páginas deben ser números enteros (o dejarse en blanco).")
            return None

    def _elegir_salida_y_convertir(self) -> None:
        if self.convirtiendo or self.ruta_pdf is None:
            return
        rango = self._leer_rango_paginas()
        if rango is None:
            return

        salida = filedialog.asksaveasfilename(
            title="Guardar audio como…",
            initialdir=str(carpeta_descargas_o_escritorio()),
            initialfile=self.ruta_pdf.stem + ".mp3",
            defaultextension=".mp3",
            filetypes=[("Audio MP3", "*.mp3")],
        )
        if not salida:
            return
        self.ruta_salida = Path(salida)
        self._iniciar_conversion(rango[0], rango[1])

    def _iniciar_conversion(self, pagina_inicio: int | None, pagina_fin: int | None) -> None:
        self._marcar_en_curso(self.boton_convertir)
        voz = VOCES_EDGE[self.var_voz.get()]
        lenta = self.var_lenta.get()
        hilo = threading.Thread(
            target=self._trabajo_conversion,
            args=(self.ruta_pdf, self.ruta_salida, pagina_inicio, pagina_fin, voz, lenta),
            daemon=True,
        )
        hilo.start()

    def _trabajo_conversion(
        self, ruta_pdf: Path, ruta_salida: Path,
        pagina_inicio: int | None, pagina_fin: int | None,
        voz: str, lenta: bool,
    ) -> None:
        """Se ejecuta en un hilo aparte para no congelar la ventana. Nunca
        toca widgets directamente: todo pasa por la cola."""
        def progreso(mensaje: str) -> None:
            self.cola.put(("estado", mensaje, ""))

        try:
            texto = extraer_texto(ruta_pdf, pagina_inicio, pagina_fin, progreso=progreso)
            texto = limpiar_texto(texto)
            if not texto.strip():
                raise ErrorConversion("El PDF no contiene texto que leer en el rango indicado.")
            progreso(f"Texto listo ({len(texto)} caracteres). Generando el audio…")
            try:
                ruta_final = texto_a_audio_edge(texto, ruta_salida, voz, lenta, progreso=progreso)
                aviso_voz = ""
            except ErrorConversion as e:
                # Si el servicio de Microsoft falla (red, bloqueo...), se
                # intenta con Google Translate TTS como alternativa. Google
                # solo tiene una voz por idioma, así que se avisa bien claro.
                progreso("La voz neuronal de Microsoft no respondió; probando con una voz alternativa…")
                idioma = "es" if voz.startswith("es-") else voz.split("-")[0]
                ruta_final = texto_a_audio_gtts(texto, ruta_salida, idioma, lenta, progreso=progreso)
                aviso_voz = (
                    f" ⚠️ La voz de Microsoft Edge no respondió, así que se ha usado una voz de "
                    f"repuesto (Google), que no permite elegir entre hombre/mujer. Motivo: {e}"
                )
            self.cola.put(("ok", str(ruta_final), aviso_voz))
        except ErrorConversion as e:
            self.cola.put(("error", str(e), ""))
        except Exception as e:
            self.cola.put(("error", f"Error inesperado: {e}", ""))


# ==========================================================================
# Pantalla 3: MP3 -> PDF (nueva)
# ==========================================================================
class Mp3APdfFrame(PantallaConversionBase):
    EXTENSIONES_AUDIO = [("Archivos de audio", "*.mp3 *.wav *.m4a *.ogg *.flac *.aac"), ("Todos los archivos", "*.*")]

    def __init__(self, padre: tk.Misc, controlador: App) -> None:
        super().__init__(
            padre, controlador, icono_titulo="🔊→📄", titulo="MP3 a PDF",
            subtitulo="Transcribe un audio y genera un PDF con el texto",
        )
        self.ruta_audio: Path | None = None
        self._construir_cuerpo()

    def _construir_cuerpo(self) -> None:
        cuerpo = self.cuerpo

        tarjeta_audio = tarjeta(cuerpo)
        tarjeta_audio.pack(fill="x", pady=(0, 14))
        interior_audio = tk.Frame(tarjeta_audio, bg=COLOR_TARJETA)
        interior_audio.pack(fill="x", padx=18, pady=16)
        self.etiqueta_audio = tk.Label(
            interior_audio, text="Ningún audio seleccionado", font=FUENTE_NORMAL,
            bg=COLOR_TARJETA, fg=COLOR_TEXTO_SUAVE, anchor="w",
        )
        self.etiqueta_audio.pack(side="left", fill="x", expand=True)
        ttk.Button(interior_audio, text="Elegir audio", style="Secundario.TButton",
                   command=self._elegir_audio).pack(side="right")

        tarjeta_opciones = tarjeta(cuerpo)
        tarjeta_opciones.pack(fill="x", pady=(0, 14))
        interior_op = tk.Frame(tarjeta_opciones, bg=COLOR_TARJETA)
        interior_op.pack(fill="x", padx=18, pady=16)

        tk.Label(interior_op, text="IDIOMA DEL AUDIO", font=("Segoe UI Semibold", 8),
                 bg=COLOR_TARJETA, fg=COLOR_TEXTO_SUAVE).grid(row=0, column=0, sticky="w")
        fila_idioma = tk.Frame(interior_op, bg=COLOR_TARJETA)
        fila_idioma.grid(row=1, column=0, columnspan=3, sticky="we", pady=(2, 14))
        self.var_idioma = tk.StringVar(value="Español")
        ttk.Combobox(fila_idioma, textvariable=self.var_idioma, values=list(IDIOMAS_TRANSCRIPCION),
                     state="readonly", width=24).pack(side="left")

        tk.Label(interior_op, text="PRECISIÓN", font=("Segoe UI Semibold", 8),
                 bg=COLOR_TARJETA, fg=COLOR_TEXTO_SUAVE).grid(row=2, column=0, sticky="w")
        fila_modelo = tk.Frame(interior_op, bg=COLOR_TARJETA)
        fila_modelo.grid(row=3, column=0, columnspan=3, sticky="we", pady=(2, 0))
        self.var_modelo = tk.StringVar(value=TAMANO_MODELO_POR_DEFECTO)
        ttk.Combobox(fila_modelo, textvariable=self.var_modelo, values=list(TAMANOS_MODELO_TRANSCRIPCION),
                     state="readonly", width=16).pack(side="left")
        tk.Label(fila_modelo, text="(más precisión = más lento)", font=("Segoe UI", 9),
                 bg=COLOR_TARJETA, fg=COLOR_TEXTO_SUAVE).pack(side="left", padx=10)

        self.boton_transcribir = ttk.Button(
            cuerpo, text="Transcribir a PDF", style="Primario.TButton",
            state="disabled", command=self._elegir_salida_y_convertir,
        )
        self.boton_transcribir.pack(fill="x", pady=(2, 16))

        self._crear_barra_y_estado(cuerpo)
        self._crear_botones_finales(cuerpo, "📖  Abrir PDF")

        tk.Label(
            cuerpo, font=("Segoe UI", 9), bg=COLOR_FONDO, fg=COLOR_TEXTO_SUAVE, wraplength=480,
            justify="left", anchor="w",
            text="La primera vez que se usa cada nivel de precisión, hace falta internet para "
                 "descargar el modelo de transcripción (una sola vez; luego funciona sin conexión).",
        ).pack(fill="x", pady=(14, 0))

    def _al_terminar_rehabilitar_boton_accion(self) -> None:
        self.boton_transcribir.config(state="normal")

    # ------------------------------------------------------------------
    def _elegir_audio(self) -> None:
        elegido = filedialog.askopenfilename(
            title="Elige el audio a transcribir",
            initialdir=str(carpeta_descargas_o_escritorio()),
            filetypes=self.EXTENSIONES_AUDIO,
        )
        if not elegido:
            return
        self.ruta_audio = Path(elegido)
        self.etiqueta_audio.config(text=self.ruta_audio.name, fg=COLOR_TEXTO)
        self.boton_transcribir.config(state="normal")
        self._set_estado("")
        self._set_botones_finales(habilitados=False)

    def _elegir_salida_y_convertir(self) -> None:
        if self.convirtiendo or self.ruta_audio is None:
            return

        salida = filedialog.asksaveasfilename(
            title="Guardar transcripción como…",
            initialdir=str(carpeta_descargas_o_escritorio()),
            initialfile=self.ruta_audio.stem + ".pdf",
            defaultextension=".pdf",
            filetypes=[("Documento PDF", "*.pdf")],
        )
        if not salida:
            return
        self.ruta_salida = Path(salida)
        self._iniciar_conversion()

    def _iniciar_conversion(self) -> None:
        self._marcar_en_curso(self.boton_transcribir)
        idioma = IDIOMAS_TRANSCRIPCION[self.var_idioma.get()]
        modelo = TAMANOS_MODELO_TRANSCRIPCION[self.var_modelo.get()]
        hilo = threading.Thread(
            target=self._trabajo_conversion,
            args=(self.ruta_audio, self.ruta_salida, idioma, modelo),
            daemon=True,
        )
        hilo.start()

    def _trabajo_conversion(self, ruta_audio: Path, ruta_salida: Path, idioma: str | None, modelo: str) -> None:
        """Se ejecuta en un hilo aparte para no congelar la ventana. Nunca
        toca widgets directamente: todo pasa por la cola."""
        def progreso(mensaje: str) -> None:
            self.cola.put(("estado", mensaje, ""))

        try:
            texto = audio_a_texto(ruta_audio, idioma, modelo, progreso=progreso)
            progreso(f"Texto transcrito ({len(texto)} caracteres). Generando el PDF…")
            ruta_final = texto_a_pdf(texto, ruta_salida, ruta_audio.stem, progreso=progreso)
            self.cola.put(("ok", str(ruta_final), ""))
        except ErrorConversion as e:
            self.cola.put(("error", str(e), ""))
        except Exception as e:
            self.cola.put(("error", f"Error inesperado: {e}", ""))


if __name__ == "__main__":
    App().mainloop()
