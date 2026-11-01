"""ClipHistory: a small, memory-only Windows clipboard history."""

from __future__ import annotations

import ctypes
import sys
import threading
import tkinter as tk
from collections import deque
from ctypes import wintypes
from datetime import datetime


MAX_ITEMS = 100
MAX_CHARS = 10_000
POLL_MS = 500
HOTKEY_ID = 1
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
VK_V = 0x56

BG = "#ffffff"
SIDEBAR = "#f5f7fa"
SURFACE = "#ffffff"
SURFACE_RAISED = "#f1f4f8"
SURFACE_SELECTED = "#eaf2fc"
TEXT = "#1d2939"
MUTED = "#718096"
ACCENT = "#3478d4"
BORDER = "#e3e9f0"
STATUS_TEXT = "#27836b"
STATUS_ACTIVE_BG = "#eaf5f0"
STATUS_PAUSED_BG = "#fff4e5"
STATUS_PAUSED_TEXT = "#94651f"
NAV_SELECTED = "#e7effa"

PALETTES = {
    "claro": {
        "BG": "#ffffff", "SIDEBAR": "#f5f7fa", "SURFACE": "#ffffff",
        "SURFACE_RAISED": "#f1f4f8", "SURFACE_SELECTED": "#eaf2fc",
        "TEXT": "#1d2939", "MUTED": "#718096", "ACCENT": "#3478d4",
        "BORDER": "#e3e9f0", "STATUS_TEXT": "#27836b",
        "STATUS_ACTIVE_BG": "#eaf5f0", "STATUS_PAUSED_BG": "#fff4e5",
        "STATUS_PAUSED_TEXT": "#94651f", "NAV_SELECTED": "#e7effa",
    },
    "escuro": {
        "BG": "#111722", "SIDEBAR": "#171f2b", "SURFACE": "#141b26",
        "SURFACE_RAISED": "#1c2634", "SURFACE_SELECTED": "#1b3048",
        "TEXT": "#e8edf5", "MUTED": "#95a3b5", "ACCENT": "#66a5f5",
        "BORDER": "#2b3748", "STATUS_TEXT": "#72c49c",
        "STATUS_ACTIVE_BG": "#18352b", "STATUS_PAUSED_BG": "#392f20",
        "STATUS_PAUSED_TEXT": "#e3bd74", "NAV_SELECTED": "#203149",
    },
}


def apply_palette(name: str) -> None:
    global BG, SIDEBAR, SURFACE, SURFACE_RAISED, SURFACE_SELECTED
    global TEXT, MUTED, ACCENT, BORDER, STATUS_TEXT, STATUS_ACTIVE_BG
    global STATUS_PAUSED_BG, STATUS_PAUSED_TEXT, NAV_SELECTED
    globals().update(PALETTES[name])


class ClipHistoryApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.items: deque[str] = deque(maxlen=MAX_ITEMS)
        self.paused = False
        self.last_clipboard = ""
        self.query = tk.StringVar()
        self.search_placeholder = True
        self.theme_name = "claro"
        apply_palette(self.theme_name)
        self.status = "Captura ativa"
        self.timestamps: dict[str, datetime] = {}
        self.hotkey_thread_id: int | None = None
        self.hotkey_registered = False
        self.selected_value: str | None = None
        self.visible_values: list[str] = []
        self.rows: list[tuple[str, tk.Frame]] = []
        self.nav_buttons: dict[str, tk.Button] = {}

        self.root.title("ClipHistory")
        self.root.geometry("720x540")
        self.root.minsize(560, 420)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self._hide_window)
        self._build_ui()
        self.root.bind("<Control-f>", lambda _event: self.search_entry.focus_set())
        self.root.bind("<Escape>", lambda _event: self.root.iconify())
        self.root.bind("<Return>", lambda _event: self._copy_selected())
        self.query.trace_add("write", lambda *_args: self._refresh_list())
        self.root.after(POLL_MS, self._poll_clipboard)

        if sys.platform == "win32":
            threading.Thread(target=self._hotkey_loop, daemon=True).start()
        else:
            self.status = "Atalho global disponível apenas no Windows"

    def _build_ui(self) -> None:
        main = tk.Frame(self.root, bg=BG)
        main.pack(fill="both", expand=True, padx=24, pady=20)
        header = tk.Frame(main, bg=BG)
        header.pack(fill="x", pady=(0, 18))
        title_block = tk.Frame(header, bg=BG)
        title_block.pack(side="left")
        tk.Label(title_block, text="ClipHistory", bg=BG, fg=TEXT,
                 font=("Segoe UI", 16, "bold")).pack(anchor="w")
        tk.Label(title_block, text="O que você copiou por último", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(3, 0))
        chip_bg = STATUS_PAUSED_BG if self.paused else STATUS_ACTIVE_BG
        chip_fg = STATUS_PAUSED_TEXT if self.paused else STATUS_TEXT
        self.status_chip = tk.Frame(header, bg=BG)
        self.status_chip.pack(side="right", pady=8)
        self.status_dot = tk.Label(self.status_chip, text="●", bg=BG, fg=chip_fg,
                                   font=("Segoe UI", 8))
        self.status_dot.pack(side="left", padx=(0, 6))
        self.status_label = tk.Label(self.status_chip,
                                     text="Pausado" if self.paused else "Capturando",
                                     bg=BG, fg=chip_fg, font=("Segoe UI", 9))
        self.status_label.pack(side="left")

        search_card = tk.Frame(main, bg=SURFACE_RAISED, padx=11, pady=9)
        search_card.pack(fill="x", pady=(0, 16))
        self.search_entry = tk.Entry(
            search_card, textvariable=self.query, bg=SURFACE_RAISED, fg=TEXT,
            insertbackground=ACCENT, selectbackground=SURFACE_SELECTED,
            selectforeground=TEXT, relief="flat", bd=0,
            font=("Segoe UI", 10),
        )
        self.search_entry.pack(fill="x", expand=True)
        if self.search_placeholder:
            self.search_entry.insert(0, "Buscar no histórico...")
            self.search_entry.configure(fg=MUTED)
        else:
            self.search_entry.configure(fg=TEXT)
        self.search_entry.bind("<FocusIn>", self._clear_search_placeholder)
        self.search_entry.bind("<FocusOut>", self._restore_search_placeholder)

        section = tk.Frame(main, bg=BG)
        section.pack(fill="x", pady=(0, 8))
        tk.Label(section, text="Recentes", bg=BG, fg=TEXT,
                 font=("Segoe UI", 12, "bold")).pack(side="left")
        self.count_label = tk.Label(section, text="0 itens", bg=BG, fg=MUTED,
                                    font=("Segoe UI", 9))
        self.count_label.pack(side="left", padx=(8, 0), pady=(2, 0))
        self.clear_button = tk.Button(
            section, text="Limpar", command=self._clear,
            bg=BG, fg=MUTED, activebackground=BG, activeforeground=TEXT,
            relief="flat", bd=0, cursor="hand2", font=("Segoe UI", 9),
        )
        self.clear_button.pack(side="right")

        history_shell = tk.Frame(main, bg=BG)
        self.canvas = tk.Canvas(history_shell, bg=BG, highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(history_shell, orient="vertical", command=self.canvas.yview,
                                  bg=BG, troughcolor=BG, activebackground=BORDER,
                                  relief="flat", bd=0, width=10)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.list_frame = tk.Frame(self.canvas, bg=BG)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        self.list_frame.bind("<Configure>", self._sync_scroll_region)
        self.canvas.bind("<Configure>", self._resize_list_frame)
        self.canvas.bind("<Enter>", lambda _event: self.canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.canvas.bind("<Leave>", lambda _event: self.canvas.unbind_all("<MouseWheel>"))
        self.empty_label = tk.Label(
            self.list_frame, text="Ainda não tem nada por aqui.\nCopie qualquer texto e ele aparece nesta lista.",
            bg=BG, fg=MUTED, justify="left", anchor="w", font=("Segoe UI", 10), pady=20,
        )
        detail_box = tk.Frame(main, bg=SURFACE_RAISED, padx=10, pady=7)
        self.detail_text = tk.Text(
            detail_box, height=2, wrap="word", bg=SURFACE_RAISED, fg=TEXT,
            insertbackground=ACCENT, relief="flat", bd=0,
            font=("Segoe UI", 9), padx=2, pady=2,
        )
        self.detail_text.pack(fill="x", expand=True)
        self.detail_text.insert("1.0", "Selecione um item para ver o texto completo.")
        self.detail_text.configure(state="disabled")
        self.detail_size = tk.Label(main, text="", bg=BG, fg=MUTED, font=("Segoe UI", 8))
        self.detail_time = tk.Label(main, text="", bg=BG, fg=MUTED, font=("Segoe UI", 8))
        controls = tk.Frame(main, bg=BG)
        self.copy_button = tk.Button(
            controls, text="Copiar", command=self._copy_selected,
            bg=ACCENT, fg="#ffffff", activebackground="#2867bc", activeforeground="#ffffff",
            relief="flat", bd=0, cursor="hand2", font=("Segoe UI", 9),
            padx=16, pady=8,
        )
        self.copy_button.pack(side="left")
        self.pause_button = tk.Button(
            controls, text="Pausar", command=self._toggle_pause,
            bg=SURFACE_RAISED, fg=TEXT, activebackground=SURFACE_SELECTED, activeforeground=TEXT,
            relief="flat", bd=0, cursor="hand2", font=("Segoe UI", 9),
            padx=14, pady=8,
        )
        self.pause_button.pack(side="left", padx=(10, 0))
        tk.Button(controls, text="Configurações", command=self._show_settings,
                  bg=SURFACE_RAISED, fg=TEXT, activebackground=SURFACE_SELECTED,
                  activeforeground=TEXT, relief="flat", bd=0, cursor="hand2",
                  font=("Segoe UI", 9), padx=14, pady=8).pack(side="right")
        self.footer_status = tk.Label(main, text=self.status, bg=BG, fg=MUTED,
                                      anchor="w", font=("Segoe UI", 8))

        self.footer_status.pack(side="bottom", fill="x", pady=(7, 0))
        controls.pack(side="bottom", fill="x", pady=(12, 0))
        detail_box.pack(side="bottom", fill="x", pady=(10, 0))
        history_shell.pack(fill="both", expand=True)

    def _add_nav(self, key: str, text: str, command: object) -> None:
        button = tk.Button(
            self.sidebar, text=text, command=command, anchor="w",
            bg=SIDEBAR, fg=TEXT, activebackground=NAV_SELECTED, activeforeground=ACCENT,
            relief="flat", bd=0, cursor="hand2", font=("Segoe UI", 9),
            padx=18, pady=12,
        )
        button.pack(fill="x", padx=(8, 0), pady=2)
        self.nav_buttons[key] = button

    def _set_navigation(self, active: str) -> None:
        for key, button in self.nav_buttons.items():
            selected = key == active
            button.configure(
                bg=NAV_SELECTED if selected else SIDEBAR,
                fg=ACCENT if selected else TEXT,
                font=("Segoe UI", 9, "bold" if selected else "normal"),
            )

    def _activate_history(self) -> None:
        self._set_navigation("history")
        self._set_search_value("")
        self.search_entry.focus_set()

    def _activate_search(self) -> None:
        self._set_navigation("search")
        self.search_entry.focus_set()
        if self.search_placeholder:
            self._clear_search_placeholder()

    def _set_search_value(self, value: str) -> None:
        self.search_placeholder = False
        self.search_entry.delete(0, tk.END)
        self.search_entry.configure(fg=TEXT)
        self.search_entry.insert(0, value)

    def _clear_search_placeholder(self, _event: tk.Event | None = None) -> None:
        if self.search_placeholder:
            self.search_placeholder = False
            self.search_entry.delete(0, tk.END)
            self.search_entry.configure(fg=TEXT)

    def _restore_search_placeholder(self, _event: tk.Event | None = None) -> None:
        if not self.search_entry.get():
            self.search_placeholder = True
            self.search_entry.insert(0, "Buscar no histórico...")
            self.search_entry.configure(fg=MUTED)

    def _detail_row(self, parent: tk.Widget, label: str, value: str) -> tk.Label:
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", padx=18, pady=8)
        tk.Label(row, text=label, bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w")
        result = tk.Label(row, text=value, bg=BG, fg=TEXT, font=("Segoe UI", 10))
        result.pack(anchor="w", pady=(2, 0))
        return result

    def _update_detail(self, value: str | None) -> None:
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", tk.END)
        if value is None:
            self.detail_text.insert("1.0", "Selecione um item para ver o texto completo.")
            self.detail_size.configure(text="—")
            self.detail_time.configure(text="—")
        else:
            self.detail_text.insert("1.0", value)
            self.detail_size.configure(text=f"{len(value):,} caracteres".replace(",", "."))
            copied_at = self.timestamps.get(value)
            self.detail_time.configure(text=copied_at.strftime("%H:%M") if copied_at else "—")
        self.detail_text.configure(state="disabled")

    def _show_settings(self) -> None:
        self._set_navigation("settings")
        dialog = tk.Toplevel(self.root)
        dialog.title("Configurações · ClipHistory")
        dialog.geometry("390x390")
        dialog.resizable(False, False)
        dialog.configure(bg=BG)
        dialog.transient(self.root)
        tk.Label(dialog, text="Configurações", bg=BG, fg=TEXT,
                 font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=24, pady=(22, 8))
        tk.Label(
            dialog,
            text="O histórico fica somente na memória e é apagado quando você fecha o app. Nada é enviado pela rede.",
            bg=BG, fg=MUTED, justify="left", wraplength=365,
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=24, pady=(0, 20))
        tk.Label(dialog, text="Aparência", bg=BG, fg=TEXT,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=24, pady=(0, 7))
        theme_var = tk.StringVar(value=self.theme_name)
        for value, label, description in (
            ("claro", "Claro", "Fundo branco e detalhes azuis."),
            ("escuro", "Escuro", "Fundo escuro com texto claro."),
        ):
            choice = tk.Radiobutton(
                dialog, text=f"{label}  ·  {description}", variable=theme_var,
                value=value, command=lambda selected=value: self._change_theme(selected, dialog),
                bg=BG, fg=TEXT, selectcolor=BG, activebackground=BG,
                activeforeground=TEXT, anchor="w", justify="left",
                font=("Segoe UI", 9), padx=0,
            )
            choice.pack(anchor="w", fill="x", padx=24, pady=3)
        tk.Button(dialog, text="Limpar histórico", command=lambda: (self._clear(), dialog.destroy()),
                  bg=SURFACE_RAISED, fg=TEXT, activebackground=SURFACE_SELECTED, relief="flat",
                  bd=0, cursor="hand2", font=("Segoe UI", 9), padx=14, pady=9).pack(anchor="w", padx=24)
        footer = tk.Frame(dialog, bg=BG)
        footer.pack(fill="x", padx=24, pady=16)
        tk.Button(footer, text="Sair do ClipHistory", command=lambda: (dialog.destroy(), self.close()),
                  bg=BG, fg=MUTED, activebackground=BG, activeforeground=STATUS_PAUSED_TEXT,
                  relief="flat", bd=0, cursor="hand2", font=("Segoe UI", 9)).pack(side="left")
        tk.Button(footer, text="Fechar", command=dialog.destroy, bg=ACCENT, fg="#ffffff",
                  activebackground="#2867bc", relief="flat", bd=0, cursor="hand2",
                  font=("Segoe UI", 9), padx=18, pady=9).pack(side="right")

    def _change_theme(self, name: str, dialog: tk.Toplevel) -> None:
        dialog.destroy()
        self.theme_name = name
        if self.search_placeholder:
            self.query.set("")
        apply_palette(name)
        self.root.configure(bg=BG)
        for child in self.root.winfo_children():
            child.destroy()
        self._build_ui()
        self._refresh_list()

    def _sync_scroll_region(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _resize_list_frame(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.canvas_window, width=event.width)
        wrap_width = max(300, event.width - 70)
        for _value, row in self.rows:
            for child in row.winfo_children():
                if isinstance(child, tk.Label):
                    child.configure(wraplength=wrap_width)

    def _on_mousewheel(self, event: tk.Event) -> None:
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _poll_clipboard(self) -> None:
        if not self.paused:
            try:
                value = self.root.clipboard_get()
            except tk.TclError:
                value = ""
            if value and value != self.last_clipboard and len(value) <= MAX_CHARS:
                self.last_clipboard = value
                self.items.appendleft(value)
                self.timestamps[value] = datetime.now()
                current_items = set(self.items)
                self.timestamps = {
                    text: copied_at for text, copied_at in self.timestamps.items()
                    if text in current_items
                }
                self._refresh_list()
        self.root.after(POLL_MS, self._poll_clipboard)

    def _refresh_list(self) -> None:
        term = "" if self.search_placeholder else self.query.get().casefold()
        self.visible_values = [value for value in self.items if not term or term in value.casefold()]
        if self.selected_value not in self.visible_values:
            self.selected_value = self.visible_values[0] if self.visible_values else None
        self.empty_label.pack_forget()
        for child in self.list_frame.winfo_children():
            if child is not self.empty_label:
                child.destroy()
        self.rows.clear()
        count = len(self.visible_values)
        self.count_label.configure(text=f"{count} {'item' if count == 1 else 'itens'}")
        if not self.visible_values:
            if self.items:
                self.empty_label.configure(text="Nenhum resultado\n\nTente buscar por outro texto.")
            else:
                self.empty_label.configure(text="Seu histórico está vazio\n\nCopie um texto e ele vai aparecer aqui.")
            self.empty_label.pack(fill="x", expand=True)
            self._update_detail(None)
            return

        for index, value in enumerate(self.visible_values):
            is_selected = value == self.selected_value
            row_bg = SURFACE_SELECTED if is_selected else BG
            row = tk.Frame(
                self.list_frame, bg=row_bg,
                cursor="hand2", padx=10, pady=8,
            )
            row.pack(fill="x", pady=1)
            preview = " ".join(value.splitlines()).strip()
            if len(preview) > 220:
                preview = preview[:217] + "..."
            title = tk.Label(row, text=preview or "(texto vazio)", bg=row_bg, fg=TEXT,
                             anchor="w", justify="left", wraplength=max(300, self.canvas.winfo_width() - 70),
                             font=("Segoe UI", 9))
            title.pack(fill="x")
            meta = tk.Frame(row, bg=row_bg)
            meta.pack(fill="x", pady=(7, 0))
            tk.Label(meta, text=f"Texto · {len(value):,} caracteres".replace(",", "."),
                     bg=row_bg, fg=ACCENT if is_selected else MUTED,
                     font=("Segoe UI", 8)).pack(side="left")
            copied_at = self.timestamps.get(value)
            time_label = copied_at.strftime("%H:%M") if copied_at else ""
            tk.Label(meta, text=time_label,
                     bg=row_bg, fg=MUTED, font=("Segoe UI", 8)).pack(side="right")
            for widget in (row, title, meta, *meta.winfo_children()):
                widget.bind("<Button-1>", lambda _event, item=value: self._select_item(item))
                widget.bind("<Double-Button-1>", lambda _event, item=value: self._copy_value(item))
            self.rows.append((value, row))
        self._update_detail(self.selected_value)

    def _select_item(self, value: str) -> None:
        self.selected_value = value
        for row_value, row in self.rows:
            selected = row_value == value
            color = SURFACE_SELECTED if selected else BG
            row.configure(bg=color)
            children = row.winfo_children()
            for child in children:
                child.configure(bg=color)
                for index, grandchild in enumerate(child.winfo_children()):
                    grandchild.configure(bg=color)
                    if child is not children[0]:
                        grandchild.configure(fg=ACCENT if selected and index == 0 else MUTED)
        self._update_detail(value)

    def _selected_value(self) -> str | None:
        return self.selected_value if self.selected_value in self.visible_values else None

    def _copy_selected(self) -> None:
        value = self._selected_value()
        if value is None:
            return
        self._copy_value(value)

    def _copy_value(self, value: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(value)
        self.root.update()
        self.last_clipboard = value
        self.status = "Copiado para a área de transferência"
        self.footer_status.configure(text=self.status, fg=ACCENT)

    def _toggle_pause(self) -> None:
        self.paused = not self.paused
        self.pause_button.configure(text="Retomar captura" if self.paused else "Pausar captura")
        self.status = "Captura pausada" if self.paused else "Captura ativa"
        self.footer_status.configure(text=self.status, fg=STATUS_PAUSED_TEXT if self.paused else MUTED)
        chip_bg = STATUS_PAUSED_BG if self.paused else STATUS_ACTIVE_BG
        chip_fg = STATUS_PAUSED_TEXT if self.paused else STATUS_TEXT
        self.status_chip.configure(bg=BG)
        self.status_dot.configure(bg=BG, fg=chip_fg)
        self.status_label.configure(text="Captura pausada" if self.paused else "Captura ativa",
                                    bg=BG, fg=chip_fg)
        if not self.paused:
            try:
                self.last_clipboard = self.root.clipboard_get()
            except tk.TclError:
                self.last_clipboard = ""

    def _clear(self) -> None:
        self.items.clear()
        self.timestamps.clear()
        self.selected_value = None
        self._refresh_list()
        self._update_detail(None)
        self.status = "Histórico limpo"
        self.footer_status.configure(text=self.status, fg=MUTED)

    def _hide_window(self) -> None:
        self.root.withdraw()

    def _show_window(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _hotkey_loop(self) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self.hotkey_thread_id = kernel32.GetCurrentThreadId()
        if not user32.RegisterHotKey(None, HOTKEY_ID, MOD_CONTROL | MOD_SHIFT, VK_V):
            self.root.after(0, lambda: self.footer_status.configure(
                text="Atalho ocupado; use a janela", fg=STATUS_PAUSED_TEXT
            ))
            return
        self.hotkey_registered = True
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                self.root.after(0, self._show_window)
        user32.UnregisterHotKey(None, HOTKEY_ID)

    def close(self) -> None:
        self.items.clear()
        if sys.platform == "win32" and self.hotkey_thread_id:
            ctypes.windll.user32.PostThreadMessageW(self.hotkey_thread_id, WM_QUIT, 0, 0)
        self.root.destroy()


def main() -> None:
    if sys.platform != "win32":
        print("ClipHistory requer Windows.")
        raise SystemExit(1)
    root = tk.Tk()
    ClipHistoryApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
