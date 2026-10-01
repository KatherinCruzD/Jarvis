import threading

import customtkinter as ctk

from core.asistente import PROVEEDORES, responder
from voz.hablar import hablar

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class VentanaJarvis(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Jarvis")
        self.geometry("800x600")
        self.minsize(500, 400)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Barra superior: título, selector de IA y interruptor de voz
        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 5))
        ctk.CTkLabel(
            barra, text="JARVIS", font=ctk.CTkFont(size=24, weight="bold")
        ).pack(side="left")
        self.selector = ctk.CTkOptionMenu(barra, values=list(PROVEEDORES.keys()))
        self.selector.set("local")
        self.selector.pack(side="right")

        self.voz_activa = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(barra, text="Voz", variable=self.voz_activa).pack(
            side="right", padx=15
        )

        # Zona de chat
        self.chat = ctk.CTkTextbox(
            self, wrap="word", font=ctk.CTkFont(size=15), state="disabled"
        )
        self.chat.grid(row=1, column=0, sticky="nsew", padx=15, pady=5)
        self.chat.tag_config("tu", foreground="#81C784")
        self.chat.tag_config("jarvis", foreground="#4FC3F7")

        # Zona de escritura
        entrada = ctk.CTkFrame(self, fg_color="transparent")
        entrada.grid(row=2, column=0, sticky="ew", padx=15, pady=(5, 15))
        entrada.grid_columnconfigure(0, weight=1)

        self.caja = ctk.CTkEntry(
            entrada, placeholder_text="Escribe tu mensaje...", height=40
        )
        self.caja.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.caja.bind("<Return>", lambda evento: self.enviar())

        self.boton_mic = ctk.CTkButton(
            entrada, text="Hablar", width=100, height=40, command=self.escuchar_voz
        )
        self.boton_mic.grid(row=0, column=1, padx=(0, 10))

        self.boton = ctk.CTkButton(
            entrada, text="Enviar", width=100, height=40, command=self.enviar
        )
        self.boton.grid(row=0, column=2)

        self.agregar_mensaje("Jarvis", "Hola, soy Jarvis. ¿En qué te ayudo?", "jarvis")

    def agregar_mensaje(self, quien, texto, etiqueta):
        self.chat.configure(state="normal")
        self.chat.insert("end", f"{quien}: ", etiqueta)
        self.chat.insert("end", f"{texto}\n\n")
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def enviar(self):
        texto = self.caja.get().strip()
        if not texto:
            return
        self.caja.delete(0, "end")
        self.agregar_mensaje("Tú", texto, "tu")
        self.boton.configure(state="disabled", text="Pensando...")

        proveedor = self.selector.get()
        con_voz = self.voz_activa.get()
        hilo = threading.Thread(
            target=self.pedir_respuesta,
            args=(texto, proveedor, con_voz),
            daemon=True,
        )
        hilo.start()

    def pedir_respuesta(self, texto, proveedor, con_voz):
        respuesta = responder(texto, proveedor)
        self.after(0, self.mostrar_respuesta, respuesta)
        if con_voz:
            hablar(respuesta)

    def mostrar_respuesta(self, respuesta):
        self.agregar_mensaje("Jarvis", respuesta, "jarvis")
        self.boton.configure(state="normal", text="Enviar")

    # --- Escuchar con el micrófono ---
    def escuchar_voz(self):
        self.boton_mic.configure(state="disabled", text="Escuchando...")
        threading.Thread(target=self.hilo_escuchar, daemon=True).start()

    def hilo_escuchar(self):
        try:
            from voz.escuchar import escuchar

            texto = escuchar()
        except Exception as error:
            texto = ""
            self.after(
                0,
                self.agregar_mensaje,
                "Jarvis",
                f"No pude usar el micrófono: {error}",
                "jarvis",
            )
        self.after(0, self.terminar_escucha, texto)

    def terminar_escucha(self, texto):
        self.boton_mic.configure(state="normal", text="Hablar")
        if texto:
            self.caja.insert(0, texto)
            self.enviar()