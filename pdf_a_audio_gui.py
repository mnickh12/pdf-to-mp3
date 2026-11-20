#!/usr/bin/env python3
"""
pdf_a_audio_gui.py — Versión con ventana (sin terminal) de pdf_a_audio.py.

Abre el programa, elige un PDF, elige dónde guardar el MP3, y listo: genera
el audio con voz natural (voces neuronales de Microsoft Edge, necesita
internet) y deja botones para abrir el archivo o la carpeta cuando termina.

Reutiliza toda la lógica de pdf_a_audio.py (extraer_texto, limpiar_texto,
texto_a_audio_edge, texto_a_audio_gtts), así que ese archivo tiene que estar
en la misma carpeta.
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
    ErrorConversion,
    VOCES_EDGE,
    VOZ_EDGE_POR_DEFECTO,
    extraer_texto,
    limpiar_texto,
    texto_a_audio_edge,
    texto_a_audio_gtts,
)

# --------------------------------------------------------------------------
# Paleta de colores y tipografía
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

FUENTE_TITULO = ("Segoe UI Semibold", 18)
FUENTE_SUBTITULO = ("Segoe UI", 10)
FUENTE_NORMAL = ("Segoe UI", 10)
FUENTE_BOTON = ("Segoe UI Semibold", 11)
FUENTE_BOTON_SECUNDARIO = ("Segoe UI", 9)


def carpeta_descargas_o_escritorio() -> Path:
    escritorio = Path.home() / "Desktop"
    return escritorio if escritorio.is_dir() else Path.home()


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("PDF a audio")
        self.geometry("540x600")
        self.minsize(480, 560)
        self.configure(bg=COLOR_FONDO)

        self.ruta_pdf: Path | None = None
        self.ruta_salida: Path | None = None
        self.cola: queue.Queue[tuple[str, str]] = queue.Queue()
        self.convirtiendo = False

        self._configurar_estilo()
        self._construir_interfaz()
        self.after(100, self._revisar_cola)

    # ------------------------------------------------------------------
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

    def _tarjeta(self, padre: tk.Misc) -> tk.Frame:
        """Panel blanco con borde sutil, para agrupar visualmente secciones."""
        return tk.Frame(padre, bg=COLOR_TARJETA, highlightbackground=COLOR_BORDE,
                         highlightthickness=1, bd=0)

    # ------------------------------------------------------------------
    def _construir_interfaz(self) -> None:
        # --- Cabecera ---
        cabecera = tk.Frame(self, bg=COLOR_ACENTO)
        cabecera.pack(fill="x")
        tk.Label(cabecera, text="🎧  PDF a audio", font=FUENTE_TITULO,
                 bg=COLOR_ACENTO, fg="white").pack(anchor="w", padx=24, pady=(20, 2))
        tk.Label(cabecera, text="Convierte el texto de un PDF en un MP3 con voz natural",
                 font=FUENTE_SUBTITULO, bg=COLOR_ACENTO, fg="#DDE0FB").pack(
            anchor="w", padx=24, pady=(0, 18))

        cuerpo = tk.Frame(self, bg=COLOR_FONDO)
        cuerpo.pack(fill="both", expand=True, padx=20, pady=18)

        # --- Tarjeta: elegir archivo ---
        tarjeta_pdf = self._tarjeta(cuerpo)
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

        # --- Tarjeta: opciones ---
        tarjeta_opciones = self._tarjeta(cuerpo)
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
        ttk.Checkbutton(fila_voz, text="Hablar más despacio", variable=self.var_lenta,
                        ).pack(side="left", padx=14)

        tk.Label(interior_op, text="PÁGINAS (OPCIONAL)", font=("Segoe UI Semibold", 8),
                 bg=COLOR_TARJETA, fg=COLOR_TEXTO_SUAVE).grid(row=2, column=0, sticky="w")
        fila_paginas = tk.Frame(interior_op, bg=COLOR_TARJETA)
        fila_paginas.grid(row=3, column=0, columnspan=3, sticky="we", pady=(2, 0))
        tk.Label(fila_paginas, text="desde", font=FUENTE_NORMAL, bg=COLOR_TARJETA,
                 fg=COLOR_TEXTO).pack(side="left")
        self.var_pagina_inicio = tk.StringVar()
        tk.Entry(fila_paginas, textvariable=self.var_pagina_inicio, width=5,
                 relief="solid", bd=1, highlightthickness=0).pack(side="left", padx=(6, 14))
        tk.Label(fila_paginas, text="hasta", font=FUENTE_NORMAL, bg=COLOR_TARJETA,
                 fg=COLOR_TEXTO).pack(side="left")
        self.var_pagina_fin = tk.StringVar()
        tk.Entry(fila_paginas, textvariable=self.var_pagina_fin, width=5,
                 relief="solid", bd=1, highlightthickness=0).pack(side="left", padx=(6, 14))
        tk.Label(fila_paginas, text="(vacío = todo el documento)", font=("Segoe UI", 9),
                 bg=COLOR_TARJETA, fg=COLOR_TEXTO_SUAVE).pack(side="left")

        # --- Botón principal ---
        self.boton_convertir = ttk.Button(
            cuerpo, text="Convertir a MP3", style="Primario.TButton",
            state="disabled", command=self._elegir_salida_y_convertir,
        )
        self.boton_convertir.pack(fill="x", pady=(2, 16))

        # --- Progreso y estado ---
        self.barra = ttk.Progressbar(cuerpo, mode="indeterminate",
                                      style="Acento.Horizontal.TProgressbar")
        self.marco_estado = tk.Frame(cuerpo, bg=COLOR_FONDO)
        self.marco_estado.pack(fill="x")
        self.etiqueta_estado = tk.Label(
            self.marco_estado, text="", font=FUENTE_NORMAL, bg=COLOR_FONDO,
            fg=COLOR_TEXTO_SUAVE, wraplength=480, justify="left", anchor="w",
        )
        self.etiqueta_estado.pack(fill="x", ipady=6)

        # --- Botones finales ---
        marco_final = tk.Frame(cuerpo, bg=COLOR_FONDO)
        marco_final.pack(fill="x", pady=(10, 0))
        self.boton_abrir_archivo = ttk.Button(
            marco_final, text="▶  Reproducir MP3", style="Secundario.TButton",
            state="disabled", command=self._abrir_archivo,
        )
        self.boton_abrir_archivo.pack(side="left", padx=(0, 10))
        self.boton_abrir_carpeta = ttk.Button(
            marco_final, text="📁  Abrir carpeta", style="Secundario.TButton",
            state="disabled", command=self._abrir_carpeta,
        )
        self.boton_abrir_carpeta.pack(side="left")

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
        self.convirtiendo = True
        self.boton_convertir.config(state="disabled")
        self._set_botones_finales(habilitados=False)
        self.barra.pack(fill="x", pady=(0, 8))
        self.barra.start(12)
        self._set_estado("Empezando…")

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
        toca widgets directamente: todo pasa por la cola, que la ventana
        revisa periódicamente desde el hilo principal."""
        def progreso(mensaje: str) -> None:
            self.cola.put(("estado", mensaje))

        try:
            texto = extraer_texto(ruta_pdf, pagina_inicio, pagina_fin, progreso=progreso)
            texto = limpiar_texto(texto)
            if not texto.strip():
                raise ErrorConversion("El PDF no contiene texto que leer en el rango indicado.")
            progreso(f"Texto listo ({len(texto)} caracteres). Generando el audio…")
            try:
                ruta_final = texto_a_audio_edge(texto, ruta_salida, voz, lenta, progreso=progreso)
            except ErrorConversion:
                # Si el servicio de Microsoft falla (red, bloqueo...), se
                # intenta con Google Translate TTS como alternativa antes
                # de rendirse, en vez de dejar al usuario sin nada.
                progreso("La voz natural no respondió; probando con una voz alternativa…")
                idioma = "es" if voz.startswith("es-") else voz.split("-")[0]
                ruta_final = texto_a_audio_gtts(texto, ruta_salida, idioma, lenta, progreso=progreso)
            self.cola.put(("ok", str(ruta_final)))
        except ErrorConversion as e:
            self.cola.put(("error", str(e)))
        except Exception as e:  # red de seguridad: nunca dejar morir el hilo en silencio
            self.cola.put(("error", f"Error inesperado: {e}"))

    def _revisar_cola(self) -> None:
        try:
            while True:
                tipo, mensaje = self.cola.get_nowait()
                if tipo == "estado":
                    self._set_estado(mensaje)
                elif tipo == "ok":
                    self._terminar(exito=True, mensaje=f"Listo. Guardado en: {mensaje}", ruta=Path(mensaje))
                elif tipo == "error":
                    self._terminar(exito=False, mensaje=mensaje, ruta=None)
        except queue.Empty:
            pass
        self.after(100, self._revisar_cola)

    def _terminar(self, exito: bool, mensaje: str, ruta: Path | None) -> None:
        self.convirtiendo = False
        self.barra.stop()
        self.barra.pack_forget()
        self.boton_convertir.config(state="normal")
        self._set_estado(mensaje, modo="exito" if exito else "error")
        if exito and ruta is not None:
            self.ruta_salida = ruta
            self._set_botones_finales(habilitados=True)
        else:
            messagebox.showerror("No se pudo generar el audio", mensaje)

    def _set_estado(self, texto: str, modo: str = "normal") -> None:
        colores = {
            "normal": (COLOR_FONDO, COLOR_TEXTO_SUAVE),
            "exito": (COLOR_EXITO_FONDO, COLOR_EXITO),
            "error": (COLOR_ERROR_FONDO, COLOR_ERROR),
        }
        fondo, texto_color = colores[modo]
        self.marco_estado.config(bg=fondo)
        self.etiqueta_estado.config(text=texto, bg=fondo, fg=texto_color)

    def _set_botones_finales(self, habilitados: bool) -> None:
        estado = "normal" if habilitados else "disabled"
        self.boton_abrir_archivo.config(state=estado)
        self.boton_abrir_carpeta.config(state=estado)

    # ------------------------------------------------------------------
    def _abrir_archivo(self) -> None:
        if self.ruta_salida and self.ruta_salida.exists():
            _abrir_con_el_sistema(self.ruta_salida)

    def _abrir_carpeta(self) -> None:
        if self.ruta_salida and self.ruta_salida.exists():
            _abrir_con_el_sistema(self.ruta_salida.parent)


def _abrir_con_el_sistema(ruta: Path) -> None:
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(ruta))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            os.system(f'open "{ruta}"')
        else:
            os.system(f'xdg-open "{ruta}"')
    except Exception as e:
        messagebox.showerror("No se pudo abrir", str(e))


if __name__ == "__main__":
    App().mainloop()
