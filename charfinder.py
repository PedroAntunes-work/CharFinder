from __future__ import annotations

"""CharFinder desktop application."""

import ctypes
import math
import sys
import tkinter as tk
import tkinter.font as tkfont
import unicodedata
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from xml_analyzer import (
    Analysis,
    Finding,
    XmlEncodingError,
    analyze_file,
    exception_catalog_path,
    load_effective_exception_catalog,
    replacement_bytes,
    save_corrected_copy,
    save_exception_rule,
)


APP_ICON_FILENAME = "CharFinder.ico"
APP_VERSION = "0.1.0"


def resource_path(filename: str) -> Path:
    """Return an application resource path in source and PyInstaller builds."""
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return base_path / "assets" / filename

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    DND_FILES = None
    TkinterDnD = None


COLORS = {
    "window": "#FFFFFF",
    "surface": "#FFFFFF",
    "panel": "#F8FAFC",
    "panel_alt": "#E2E8F0",
    "line": "#CBD5E1",
    "text": "#0F172A",
    "muted": "#475569",
    "blue": "#2563EB",
    "blue_hover": "#1D4ED8",
    "green": "#15803D",
    "amber": "#B45309",
    "amber_bg": "#FEF3C7",
    "red": "#B91C1C",
    "disabled_text": "#64748B",
    "disabled": "#E2E8F0",
    "button_hover": "#F1F5F9",
    "heading_bg": "#F1F5F9",
}

FONTS = {
    "title": ("Segoe UI Semibold", 20),
    "subtitle": ("Segoe UI", 11),
    "body": ("Segoe UI", 10),
    "caption": ("Segoe UI", 9),
    "brand": ("Segoe UI Semibold", 17),
    "panel_title": ("Segoe UI Semibold", 11),
    "bold_body": ("Segoe UI Semibold", 10),
    "bold_caption": ("Segoe UI Semibold", 9),
    "icon": ("Segoe UI Symbol", 17),
}


def plural(count: int, singular: str, plural_form: str) -> str:
    return singular if count == 1 else plural_form


def _enable_windows_dpi_awareness() -> None:
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass


def create_root() -> tk.Tk:
    _enable_windows_dpi_awareness()
    if TkinterDnD is not None:
        return TkinterDnD.Tk()
    return tk.Tk()


def _rounded_rectangle_points(width: int, height: int, radius: int) -> list[float]:
    points: list[float] = []
    for center_x, center_y, start_angle in (
        (width - radius, radius, -90),
        (width - radius, height - radius, 0),
        (radius, height - radius, 90),
        (radius, radius, 180),
    ):
        for step in range(9):
            angle = math.radians(start_angle + step * 90 / 8)
            points.extend(
                (
                    center_x + radius * math.cos(angle),
                    center_y + radius * math.sin(angle),
                )
            )
    return points


class RoundedButton(tk.Canvas):
    def __init__(
        self,
        master: tk.Misc,
        text: str,
        command: Callable[[], None],
        *,
        primary: bool = False,
        enabled: bool = True,
        borderless: bool = False,
        canvas_background: str = COLORS["surface"],
    ) -> None:
        self._text = text
        self._command = command
        self._primary = primary
        self._enabled = enabled
        self._borderless = borderless
        self._hovered = False
        self._font = tkfont.Font(root=master, font=FONTS["bold_body"])
        self._width = self._font.measure(text) + 36
        self._height = max(38, self._font.metrics("linespace") + 18)
        super().__init__(
            master,
            width=self._width,
            height=self._height,
            background=canvas_background,
            borderwidth=0,
            highlightthickness=0,
            takefocus=self._enabled,
        )
        self._shape = self.create_polygon(
            *_rounded_rectangle_points(self._width, self._height, 10),
            smooth=False,
        )
        self._label = self.create_text(
            self._width / 2,
            self._height / 2,
            text=text,
            font=self._font,
        )
        self.bind("<Configure>", self._redraw)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._invoke)
        self.bind("<Return>", self._invoke)
        self.bind("<space>", self._invoke)
        self.bind("<FocusIn>", self._redraw)
        self.bind("<FocusOut>", self._redraw)
        self._redraw()

    def _redraw(self, _event: tk.Event | None = None) -> None:
        width = max(self.winfo_width(), self._width)
        height = max(self.winfo_height(), self._height)
        radius = min(10, height // 2)
        if not self._enabled:
            fill = COLORS["disabled"] if self._primary else COLORS["panel_alt"]
            outline = fill
            foreground = COLORS["disabled_text"]
        elif self._primary:
            fill = COLORS["blue_hover"] if self._hovered else COLORS["blue"]
            outline = fill
            foreground = COLORS["surface"]
        else:
            fill = COLORS["button_hover"] if self._hovered else COLORS["surface"]
            outline = fill if self._borderless else COLORS["line"]
            foreground = COLORS["text"]
        if self._enabled and self.focus_get() is self and not self._borderless:
            outline = COLORS["blue"]
        self.coords(self._shape, *_rounded_rectangle_points(width, height, radius))
        self.itemconfigure(self._shape, fill=fill, outline=outline, width=1)
        self.coords(self._label, width / 2, height / 2)
        self.itemconfigure(self._label, fill=foreground)

    def _on_enter(self, _event: tk.Event) -> None:
        self._hovered = True
        self._redraw()

    def _on_leave(self, _event: tk.Event) -> None:
        self._hovered = False
        self._redraw()

    def _invoke(self, _event: tk.Event) -> str:
        if self._enabled:
            self.focus_set()
            self._command()
        return "break"

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow", takefocus=enabled)
        self._redraw()


class AnalisadorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"CharFinder v{APP_VERSION}")
        self.app_icon = ImageTk.PhotoImage(Image.open(resource_path(APP_ICON_FILENAME)))
        self.root.iconphoto(True, self.app_icon)
        self.root.configure(bg=COLORS["window"])
        self._center_window()
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)

        self.current_path: Path | None = None
        self.analysis: Analysis | None = None
        self.replacements: dict[int, str] = {}
        self.custom_replacements: set[int] = set()
        self.save_exception_var = tk.BooleanVar(value=False)
        self.exception_catalog: dict[tuple[str, str | None], tuple[str, str]] = {}
        self.findings_by_iid: dict[str, Finding] = {}
        self.iid_by_offset: dict[int, str] = {}
        self.file_var = tk.StringVar(value="Nenhum arquivo selecionado")
        self.file_size_var = tk.StringVar()
        self.file_error_var = tk.StringVar()
        self.replacement_var = tk.StringVar()
        self.replacement_var.trace_add("write", self._update_correction_preview)
        self.replacement_mode_var = tk.StringVar(value="suggestion")
        self.status_var = tk.StringVar(value="Selecione um arquivo .xml para começar")
        self.analysis_text = ""
        self.path_tooltip: tk.Toplevel | None = None

        self._configure_styles()
        self._build_shell()
        self.root.bind("<Return>", self._on_enter_key)
        self.root.bind("<Escape>", self._on_escape_key)
        self.root.bind("<Alt-Left>", self._on_escape_key)
        self.root.bind("<Control-s>", self._on_save_key)
        self.root.bind("<Control-S>", self._on_save_key)
        self._show_start_screen()

    def _center_window(self) -> None:
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        width = min(1000, max(820, screen_width - 100))
        height = min(700, max(580, screen_height - 100))
        width = min(width, screen_width - 20)
        height = min(height, screen_height - 60)
        self._window_height = height
        self.root.minsize(min(820, width), min(580, height))
        self.root.state("zoomed")

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            ".",
            background=COLORS["surface"],
            foreground=COLORS["text"],
            font=FONTS["body"],
        )
        style.configure("TFrame", background=COLORS["surface"])
        style.configure("Panel.TFrame", background=COLORS["panel"])
        style.configure("TLabel", background=COLORS["surface"], foreground=COLORS["text"])
        style.configure("Muted.TLabel", foreground=COLORS["muted"])
        style.configure("Title.TLabel", font=FONTS["title"])
        style.configure("Subtitle.TLabel", font=FONTS["subtitle"], foreground=COLORS["muted"])
        style.configure("PanelTitle.TLabel", background=COLORS["panel"], font=FONTS["panel_title"])
        style.configure(
            "Replacement.TEntry",
            fieldbackground=COLORS["surface"],
            foreground=COLORS["text"],
            insertcolor=COLORS["text"],
            bordercolor=COLORS["line"],
            lightcolor=COLORS["line"],
            darkcolor=COLORS["line"],
            padding=7,
        )
        style.map(
            "Replacement.TEntry",
            bordercolor=[("focus", COLORS["line"])],
            lightcolor=[("focus", COLORS["line"])],
            darkcolor=[("focus", COLORS["line"])],
        )
        style.configure(
            "TCheckbutton",
            background=COLORS["surface"],
            foreground=COLORS["text"],
            font=FONTS["body"],
        )
        style.map("TCheckbutton", background=[("active", COLORS["surface"])])
        style.configure(
            "Panel.TCheckbutton",
            background=COLORS["panel"],
            foreground=COLORS["text"],
            font=FONTS["bold_body"],
        )
        style.map("Panel.TCheckbutton", background=[("active", COLORS["panel"])])
        style.configure(
            "Treeview",
            background=COLORS["surface"],
            fieldbackground=COLORS["surface"],
            foreground=COLORS["text"],
            bordercolor=COLORS["line"],
            rowheight=28,
            font=FONTS["caption"],
        )
        style.configure(
            "Treeview.Heading",
            background=COLORS["heading_bg"],
            foreground=COLORS["muted"],
            font=FONTS["bold_caption"],
            padding=7,
        )
        style.map(
            "Treeview",
            background=[("selected", COLORS["blue"])],
            foreground=[("selected", COLORS["surface"])],
        )
        style.configure("Horizontal.TProgressbar", troughcolor=COLORS["panel_alt"], background=COLORS["blue"])
        style.configure(
            "Panel.TRadiobutton",
            background=COLORS["panel"],
            foreground=COLORS["text"],
            font=FONTS["body"],
        )
        style.map("Panel.TRadiobutton", background=[("active", COLORS["panel"])])
        style.configure("InlineError.TLabel", foreground=COLORS["red"])
        style.configure("InlineWarning.TLabel", foreground=COLORS["amber"])
        style.configure("InlineSuccess.TLabel", foreground=COLORS["green"])

    def _build_shell(self) -> None:
        self.shell = ttk.Frame(self.root)
        self.shell.pack(fill="both", expand=True)
        self.shell.columnconfigure(0, weight=1)
        self.shell.rowconfigure(4, weight=1)
        header = ttk.Frame(self.shell, padding=(24, 17, 24, 14))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)
        self._draw_logo(header)
        titles = ttk.Frame(header)
        titles.grid(row=0, column=1, sticky="w", padx=(12, 0))
        ttk.Label(titles, text="CharFinder", font=FONTS["brand"]).pack(anchor="w")
        ttk.Label(
            titles,
            text="Diagnóstico e correção assistida de arquivos",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(1, 0))
        self.local_badge = ttk.Label(
            header,
            text="🔒 Processamento local",
            foreground=COLORS["green"],
            padding=(12, 7),
        )
        self.local_badge.grid(row=0, column=2, sticky="e", pady=5)
        ttk.Separator(self.shell).grid(row=1, column=0, sticky="ew")

        self.steps_frame = ttk.Frame(self.shell, padding=(28, 11))
        self.steps_frame.grid(row=2, column=0, sticky="ew")
        self.step_labels: list[ttk.Label] = []
        self.step_titles = ("Selecionar arquivo", "Analisar e revisar", "Salvar cópia")
        for index, title in enumerate(self.step_titles):
            label = ttk.Label(self.steps_frame, text=f"{index + 1}. {title}", foreground=COLORS["muted"])
            label.pack(side="left")
            self.step_labels.append(label)
            if index < 2:
                ttk.Label(self.steps_frame, text="----------------", foreground=COLORS["line"]).pack(
                    side="left", padx=11
                )
        ttk.Separator(self.shell).grid(row=3, column=0, sticky="ew")

        self.content = ttk.Frame(self.shell, padding=(24, 14, 24, 10))
        self.content.grid(row=4, column=0, sticky="nsew")
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)

        self.actions_frame = ttk.Frame(self.shell, padding=(24, 8))
        self.actions_frame.grid(row=5, column=0, sticky="ew")
        self.actions_frame.columnconfigure(0, weight=1)
        ttk.Separator(self.shell).grid(row=6, column=0, sticky="ew")
        self.footer = ttk.Frame(self.shell, padding=(18, 7))
        self.footer.grid(row=7, column=0, sticky="ew")
        self.footer.columnconfigure(0, weight=1)
        ttk.Label(
            self.footer,
            textvariable=self.status_var,
            style="Muted.TLabel",
        ).grid(row=0, column=0, sticky="w")
        self.action_message = ttk.Label(
            self.actions_frame,
            text="",
            style="Muted.TLabel",
        )
        self.action_message.grid(row=0, column=0, sticky="w")
        self.buttons_frame = ttk.Frame(self.actions_frame)
        self.buttons_frame.grid(row=0, column=1, sticky="e")

    def _draw_logo(self, parent: ttk.Frame) -> None:
        logo_image = Image.open(resource_path(APP_ICON_FILENAME)).resize((42, 42), Image.LANCZOS)
        self.header_logo = ImageTk.PhotoImage(logo_image)
        ttk.Label(parent, image=self.header_logo, background=COLORS["surface"]).grid(row=0, column=0)

    def _clear_content(self) -> None:
        for child in self.content.winfo_children():
            child.destroy()

    def _set_actions(
        self,
        secondary_text: str,
        secondary_command: Callable[[], None],
        secondary_enabled: bool,
        primary_text: str,
        primary_command: Callable[[], None],
        primary_enabled: bool,
        message: str = "",
        message_style: str = "Muted.TLabel",
    ) -> None:
        for child in self.buttons_frame.winfo_children():
            child.destroy()
        self.action_message.configure(text=message, style=message_style)
        self.secondary_button = RoundedButton(
            self.buttons_frame,
            secondary_text,
            secondary_command,
            enabled=secondary_enabled,
        )
        self.primary_button = RoundedButton(
            self.buttons_frame,
            primary_text,
            primary_command,
            primary=True,
            enabled=primary_enabled,
        )
        self.primary_button.pack(side="right")
        self.secondary_button.pack(side="right", padx=(0, 8))

    def _show_path_tooltip(self, event: tk.Event) -> None:
        if self.current_path is None:
            return
        self._hide_path_tooltip()
        tooltip = tk.Toplevel(self.root)
        tooltip.wm_overrideredirect(True)
        tooltip.wm_geometry(f"+{event.x_root + 12}+{event.y_root + 12}")
        tk.Label(
            tooltip,
            text=str(self.current_path),
            background=COLORS["text"],
            foreground=COLORS["surface"],
            padx=8,
            pady=5,
            font=FONTS["caption"],
        ).pack()
        self.path_tooltip = tooltip

    def _hide_path_tooltip(self, _event: tk.Event | None = None) -> None:
        if self.path_tooltip is not None:
            self.path_tooltip.destroy()
            self.path_tooltip = None

    def _clear_selection(self) -> None:
        self.current_path = None
        self.file_var.set("Nenhum arquivo selecionado")
        self.file_size_var.set("")
        self.file_error_var.set("")
        self.status_var.set("Selecione um arquivo .xml para começar")
        self._show_start_screen()

    def _set_step(self, active: int) -> None:
        for index, label in enumerate(self.step_labels, start=1):
            title = self.step_titles[index - 1]
            if index < active:
                text = f"✓ {index}. {title}"
            else:
                text = f"{index}. {title}"
            label.configure(
                text=text,
                foreground=COLORS["blue"] if index == active else (
                    COLORS["green"] if index < active else COLORS["muted"]
                ),
                font=FONTS["bold_body"] if index == active else FONTS["body"],
            )

    def _on_enter_key(self, _event: tk.Event) -> str:
        if getattr(self, "screen", 1) == 1:
            if self.analyze_button._enabled:
                self._analyze_selected()
        elif hasattr(self, "tree") and self.tree.selection():
            self._set_custom_replacement()
        elif hasattr(self, "save_button") and self.save_button._enabled:
            self._save_copy()
        return "break"

    def _on_escape_key(self, _event: tk.Event) -> str:
        if getattr(self, "screen", 1) == 2:
            self._show_start_screen()
        return "break"

    def _on_save_key(self, _event: tk.Event) -> str:
        if getattr(self, "screen", 1) == 2:
            self._save_copy()
        return "break"

    def _show_start_screen(self) -> None:
        self._clear_content()
        self.screen = 1
        self._set_step(1)
        self._set_actions(
            "Limpar seleção",
            self._clear_selection,
            self.current_path is not None,
            "Analisar arquivo",
            self._analyze_selected,
            self.current_path is not None,
        )
        self.analyze_button = self.primary_button
        self.status_var.set(
            "Arquivo pronto para análise"
            if self.current_path is not None
            else "Selecione um arquivo .xml para começar"
        )
        self.content.rowconfigure(0, weight=0)
        self.content.rowconfigure(5, weight=1)

        ttk.Label(
            self.content,
            text="Importe seu arquivo .xml",
            style="Title.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            self.content,
            text="O arquivo original permanece intacto.",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(5, 12))

        drop_zone = tk.Frame(
            self.content,
            bg=COLORS["panel"],
            highlightbackground=COLORS["line"],
            highlightthickness=1,
            height=min(170, max(120, self.root.winfo_height() - 430)),
        )
        drop_zone.grid(row=2, column=0, sticky="ew")
        drop_zone.pack_propagate(False)
        drop_zone.columnconfigure(0, weight=1)
        drop_zone.rowconfigure(0, weight=1)
        drop_inner = ttk.Frame(drop_zone, style="Panel.TFrame", padding=12)
        drop_inner.grid(row=0, column=0, sticky="nsew")
        drop_inner.columnconfigure(0, weight=1)
        drop_text = "Arraste o arquivo aqui" if DND_FILES is not None else "Selecione um arquivo"
        upload_icon = tk.Canvas(
            drop_inner,
            width=40,
            height=40,
            background=COLORS["panel"],
            borderwidth=0,
            highlightthickness=0,
            takefocus=False,
        )
        upload_icon.grid(row=0, column=0, pady=(0, 4))
        upload_icon.create_line(
            12, 26, 12, 30, 28, 30, 28, 26,
            fill=COLORS["blue"],
            width=2,
            capstyle=tk.ROUND,
            joinstyle=tk.ROUND,
        )
        upload_icon.create_line(
            20, 25, 20, 9, 14, 15, 20, 9, 26, 15,
            fill=COLORS["blue"],
            width=2,
            capstyle=tk.ROUND,
            joinstyle=tk.ROUND,
        )
        ttk.Label(
            drop_inner,
            text=drop_text,
            style="PanelTitle.TLabel",
        ).grid(row=1, column=0, pady=(0, 4))
        if DND_FILES is not None:
            ttk.Label(drop_inner, text="ou", style="Muted.TLabel").grid(
                row=2, column=0, pady=(0, 4)
            )
        RoundedButton(
            drop_inner,
            "Escolher arquivo",
            self._choose_file,
        ).grid(row=3, column=0, pady=(0, 5))
        ttk.Label(
            drop_inner,
            text="Formato aceito: .xml",
            style="Muted.TLabel",
        ).grid(row=4, column=0)

        if DND_FILES is not None:
            drop_zone.drop_target_register(DND_FILES)
            drop_zone.dnd_bind("<<Drop>>", self._on_drop)
            drop_inner.drop_target_register(DND_FILES)
            drop_inner.dnd_bind("<<Drop>>", self._on_drop)

        self.file_card = ttk.Frame(self.content, style="Panel.TFrame", padding=(12, 9))
        self.file_card.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self.file_card.columnconfigure(1, weight=1)
        if self.current_path is not None:
            ttk.Label(self.file_card, text="📄", font=FONTS["icon"]).grid(
                row=0, column=0, rowspan=2, padx=(0, 10)
            )
            name_label = ttk.Label(
                self.file_card,
                text=self.current_path.name,
                font=FONTS["bold_body"],
            )
            name_label.grid(row=0, column=1, sticky="w")
            name_label.bind("<Enter>", self._show_path_tooltip)
            name_label.bind("<Leave>", self._hide_path_tooltip)
            ttk.Label(
                self.file_card,
                textvariable=self.file_size_var,
                style="Muted.TLabel",
            ).grid(row=1, column=1, sticky="w")
            change_label = ttk.Label(
                self.file_card,
                text="Trocar arquivo",
                foreground=COLORS["blue"],
                cursor="hand2",
            )
            change_label.grid(row=0, column=2, rowspan=2, padx=(12, 0))
            change_label.bind("<Button-1>", lambda _event: self._choose_file())

        ttk.Label(
            self.content,
            textvariable=self.file_error_var,
            style="InlineError.TLabel",
            wraplength=900,
        ).grid(row=4, column=0, sticky="w", pady=(8, 0))

    def _choose_file(self) -> None:
        selected = filedialog.askopenfilename(
            title="Selecionar arquivo XML",
            filetypes=(("Arquivos XML", "*.xml"), ("Todos os arquivos", "*.*")),
        )
        if selected:
            self._set_file(Path(selected))

    def _on_drop(self, event: tk.Event) -> str:
        try:
            paths = self.root.tk.splitlist(event.data)
            if paths:
                self._set_file(Path(paths[0]))
        except (tk.TclError, IndexError) as exc:
            self.file_error_var.set(f"⚠ Não foi possível ler o caminho do arquivo: {exc}")
            self.status_var.set("Falha ao selecionar o arquivo.")
        return "break"

    def _set_file(self, path: Path) -> None:
        self.current_path = None
        self.file_var.set("Nenhum arquivo selecionado")
        self.file_size_var.set("")
        if path.suffix.lower() != ".xml":
            self.file_error_var.set("⚠ Formato inválido. Selecione um arquivo .xml.")
            self._show_start_screen()
            self.status_var.set("Falha ao selecionar o arquivo.")
            return
        try:
            if not path.is_file():
                raise OSError("O caminho selecionado não é um arquivo.")
            with path.open("rb"):
                size = path.stat().st_size
        except OSError as exc:
            self.file_error_var.set(f"⚠ Não foi possível ler o arquivo: {exc}")
            self._show_start_screen()
            self.status_var.set("Falha ao selecionar o arquivo.")
            return
        self.current_path = path
        self.file_var.set(str(path))
        self.file_size_var.set(
            f"{size / (1024 * 1024):.2f} MB"
            if size >= 1024 * 1024
            else f"{size / 1024:.1f} KB"
        )
        self.file_error_var.set("")
        self.status_var.set("Arquivo pronto para análise")
        self._show_start_screen()

    def _analyze_selected(self) -> None:
        if self.current_path is None:
            return
        try:
            self.exception_catalog = load_effective_exception_catalog()
            self.analysis = analyze_file(self.current_path, exception_catalog=self.exception_catalog)
        except (OSError, ValueError) as exc:
            self.file_error_var.set(f"⚠ Não foi possível analisar o arquivo: {exc}")
            self._show_start_screen()
            self.status_var.set("Falha ao analisar o arquivo.")
            return
        self.replacements = {}
        self.custom_replacements.clear()
        self._show_results()

    def _show_results(self) -> None:
        assert self.analysis is not None
        self._clear_content()
        self.screen = 2
        self._set_step(2)
        self.analysis_text = self.analysis.data[self.analysis.bom_length :].decode(
            self.analysis.codec
        )
        available_height = self.root.winfo_height()
        if available_height <= 1:
            available_height = self._window_height

        header = ttk.Frame(self.content)
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="Revise os caracteres encontrados", style="Title.TLabel").grid(
            row=0, column=0, columnspan=4, sticky="w"
        )
        ttk.Label(
            header,
            text="O arquivo original permanece intacto.",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(3, 6))
        ttk.Label(
            header, text="Arquivo:", font=FONTS["bold_body"]
        ).grid(row=2, column=0, sticky="w")
        ttk.Label(header, text=self.analysis.path.name).grid(row=2, column=1, sticky="w", padx=(4, 16))
        ttk.Label(header, text="Codificação:", font=FONTS["bold_body"]).grid(
            row=2, column=2, sticky="w"
        )
        ttk.Label(header, text=self.analysis.encoding).grid(row=2, column=3, sticky="w", padx=(4, 0))

        if self.analysis.parse_error:
            parse_text = f"XML não interpretado integralmente: {self.analysis.parse_error}"
            parse_style = "InlineWarning.TLabel"
        else:
            parse_text = "✓ Estrutura XML reconhecida"
            parse_style = "InlineSuccess.TLabel"
        ttk.Label(
            header,
            text=parse_text,
            style=parse_style,
            wraplength=1000,
        ).grid(row=3, column=0, columnspan=4, sticky="w", pady=(5, 0))

        if not self.analysis.findings:
            empty_state = ttk.Frame(
                self.content,
                style="Panel.TFrame",
                padding=(18, 16),
            )
            empty_state.grid(row=1, column=0, sticky="ew", pady=(16, 0))
            ttk.Label(
                empty_state,
                text="✓ Nenhum caractere que exija revisão foi encontrado",
                style="PanelTitle.TLabel",
            ).pack(anchor="w")
            ttk.Label(
                empty_state,
                text="A cópia corrigida será idêntica ao arquivo original.",
                style="Muted.TLabel",
                wraplength=900,
            ).pack(anchor="w", pady=(5, 0))
            self.content.rowconfigure(2, weight=1)
            self._set_actions(
                "← Voltar",
                self._show_start_screen,
                True,
                "Salvar cópia do XML",
                self._save_copy,
                True,
                "Arquivo pronto para copiar",
                "InlineSuccess.TLabel",
            )
            self.save_button = self.primary_button
            self.status_var.set("Análise concluída sem ocorrências para revisar.")
            return

        self.content.rowconfigure(2, minsize=110, weight=1)
        self._build_result_actions()
        suggestion_bar = ttk.Frame(self.content, style="Panel.TFrame", padding=(9, 5))
        suggestion_bar.grid(row=1, column=0, sticky="ew", pady=(8, 7))
        self.counter_label = ttk.Label(suggestion_bar, style="PanelTitle.TLabel")
        self.counter_label.pack(side="left")
        self.accept_button = RoundedButton(
            suggestion_bar,
            "Aceitar todas as sugestões",
            self._accept_all_suggestions,
        )
        self.accept_button.pack(side="right")

        table_frame = ttk.Frame(self.content)
        table_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 7))
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        columns = ("status", "line", "character", "code", "path", "replacement")
        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
            height=max(4, min(6, (available_height - 560) // 28)),
        )
        headings = {
            "status": ("Status", 58),
            "line": ("Linha", 58),
            "character": ("Caractere", 82),
            "code": ("Código", 82),
            "path": ("Elemento XML", 250),
            "replacement": ("Substituição", 175),
        }
        for column, (title, width) in headings.items():
            self.tree.heading(column, text=title)
            self.tree.column(
                column,
                width=width,
                minwidth=48 if column in {"status", "line", "character", "code"} else 100,
                stretch=column in {"path", "replacement"},
                anchor="center" if column in {"status", "line", "character", "code"} else "w",
            )
        self.tree.tag_configure("pending", background=COLORS["amber_bg"], foreground=COLORS["amber"])
        self.tree.tag_configure("resolved", background=COLORS["surface"], foreground=COLORS["text"])
        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")

        self.findings_by_iid = {}
        self.iid_by_offset = {}
        self.char_index_by_iid = {}
        for index, finding in enumerate(self.analysis.findings):
            iid = str(index)
            self.findings_by_iid[iid] = finding
            self.iid_by_offset[finding.offset] = iid
            self.char_index_by_iid[iid] = self._byte_offset_to_char_index(finding.offset)
            replacement = self.replacements.get(finding.offset)
            resolved = replacement is not None
            replacement_text = self._replacement_label(finding, replacement)
            display_char = self._display_character(finding)
            self.tree.insert(
                "",
                "end",
                iid=iid,
                tags=("resolved" if resolved else "pending",),
                values=(
                    "✓" if resolved else "⚠",
                    f"{finding.line:,}".replace(",", "."),
                    display_char,
                    finding.codepoint,
                    self._shorten_path(finding.path or ""),
                    replacement_text,
                ),
            )
        self.tree.bind("<<TreeviewSelect>>", self._on_finding_selected)
        self._build_details_panel()
        self._build_replacement_editor()
        self._update_save_state()
        self._select_next_pending()

    @staticmethod
    def _display_character(finding: Finding) -> str:
        character = finding.character
        if character.isprintable():
            return character
        codepoint = ord(character)
        if codepoint <= 0x1F or codepoint == 0x7F:
            return chr(0x2400 + codepoint)
        if finding.description != finding.codepoint and finding.description.isprintable():
            return finding.description
        return "\uFFFD"

    def _shorten_path(self, path: str, max_length: int = 42) -> str:
        if len(path) <= max_length:
            return path
        parts = path.split("/")
        shortened = ""
        for part in reversed(parts):
            candidate = f"{part}/{shortened}" if shortened else part
            if len(candidate) + 2 > max_length:
                break
            shortened = candidate
        return f"…/{shortened}" if shortened else f"…{path[-max_length + 1:]}"

    def _byte_offset_to_char_index(self, offset: int) -> int:
        assert self.analysis is not None
        byte_offset = self.analysis.bom_length
        for index, character in enumerate(self.analysis_text):
            if byte_offset == offset:
                return index
            byte_offset += len(character.encode(self.analysis.codec))
        return len(self.analysis_text)

    @staticmethod
    def _character_description(finding: Finding) -> str:
        character = finding.description if finding.suggestion_note in {"Possível incompatibilidade de codificação", "Caractere desconhecido — considere salvar uma exceção"} else finding.character
        value = ord(character[0]) if character else 0
        category = unicodedata.category(character[0]) if character else ""
        if category == "Cc":
            group = "C0" if value <= 0x1F else "C1" if value <= 0x9F else ""
            return f"Caractere de controle ({group})" if group else "Caractere de controle"
        return unicodedata.name(character[0], f"Caractere sem nome ({finding.codepoint})")

    @staticmethod
    def _suggestion_reason(finding: Finding) -> str:
        if finding.suggestion_note == "Possível incompatibilidade de codificação":
            name = unicodedata.name(finding.description, "")
            if "EM DASH" in name:
                return "Provável travessão (Windows-1252)"
            if "EN DASH" in name:
                return "Provável travessão curto (Windows-1252)"
            if name:
                return f"Provável {name.lower()} (Windows-1252)"
        return finding.suggestion_note or "Sem sugestão automática"

    def _build_details_panel(self) -> None:
        self.details_panel = ttk.Frame(self.content, style="Panel.TFrame", padding=(10, 8))
        self.details_panel.grid(row=3, column=0, sticky="ew", pady=(0, 7))
        self.details_panel.columnconfigure(0, weight=1)
        ttk.Label(
            self.details_panel,
            text="Detalhes da ocorrência",
            style="PanelTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        self.preview = tk.Text(
            self.details_panel,
            height=2,
            wrap="word",
            background=COLORS["surface"],
            foreground=COLORS["text"],
            relief="flat",
            padx=6,
            pady=5,
            font=FONTS["caption"],
            takefocus=False,
        )
        self.preview.grid(row=1, column=0, sticky="ew", pady=(5, 4))
        self.preview.tag_configure(
            "finding",
            background=COLORS["amber_bg"],
            foreground=COLORS["text"],
            font=FONTS["bold_caption"],
        )
        self.detail_metadata = ttk.Label(
            self.details_panel,
            style="Muted.TLabel",
            wraplength=1000,
        )
        self.detail_metadata.grid(row=2, column=0, sticky="w")

    @staticmethod
    def _printable_context(value: str) -> str:
        return "".join(
            character
            if character.isprintable() or character in "\r\n\t"
            else f"[{ord(character):04X}]"
            for character in value
        )

    def _selected_finding_context(self) -> tuple[Finding, int, int, int] | None:
        selected = self.tree.selection()
        if not selected:
            return None
        iid = selected[0]
        finding = self.findings_by_iid[iid]
        index = self.char_index_by_iid[iid]
        start = max(0, index - 30)
        end = min(len(self.analysis_text), index + len(finding.character) + 30)
        return finding, index, start, end

    def _update_details(self, iid: str) -> None:
        finding = self.findings_by_iid[iid]
        index = self.char_index_by_iid[iid]
        start = max(0, index - 30)
        end = min(len(self.analysis_text), index + len(finding.character) + 30)
        selected = self.analysis_text[index : index + len(finding.character)]
        after = self.analysis_text[index + len(finding.character) : end]

        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("end", self._printable_context(self.analysis_text[start:index]))
        self.preview.insert("end", self._printable_context(selected), "finding")
        self.preview.insert("end", self._printable_context(after))
        self.preview.configure(state="disabled")
        self.detail_metadata.configure(
            text=(
                f"{self._character_description(finding)} · {finding.codepoint} · "
                f"Byte {finding.offset:,} · Elemento: {finding.path or 'não identificado'} · "
                f"{self._suggestion_reason(finding)}"
            )
        )

    @staticmethod
    def _replacement_label(finding: Finding, replacement: str | None) -> str:
        if replacement is None:
            if finding.suggested is None:
                return "Defina a substituição"
            if finding.suggested == "":
                return "Sugestão: remover"
            if finding.suggested == " ":
                return 'Sugestão: " "'
            return f"Sugestão: {finding.suggested}"
        if replacement == "":
            return "Remover caractere"
        if replacement == " ":
            return "Espaço comum (U+0020)"
        return f"Substituir por: {replacement}"

    def _accept_all_suggestions(self) -> None:
        if self.analysis is None:
            return
        for finding in self.analysis.findings:
            if finding.offset not in self.replacements and finding.suggested is not None:
                self.replacements[finding.offset] = finding.suggested
        self._refresh_replacement_labels()
        self._update_save_state()
        self._select_next_pending()

    def _refresh_replacement_labels(self) -> None:
        if self.analysis is None:
            return
        for finding in self.analysis.findings:
            iid = self.iid_by_offset.get(finding.offset)
            if iid is not None:
                replacement = self.replacements.get(finding.offset)
                self.tree.set(iid, "status", "✓" if replacement is not None else "⚠")
                self.tree.set(
                    iid,
                    "replacement",
                    self._replacement_label(finding, replacement),
                )
                self.tree.item(iid, tags=("resolved" if replacement is not None else "pending",))

    def _select_next_pending(self, current_iid: str | None = None) -> None:
        if self.analysis is None or not self.analysis.findings:
            return
        pending = [
            self.iid_by_offset[finding.offset]
            for finding in self.analysis.findings
            if finding.offset not in self.replacements
        ]
        if pending:
            if current_iid in pending:
                start = pending.index(current_iid) + 1
                target = pending[start] if start < len(pending) else pending[0]
            else:
                target = pending[0]
            self.tree.selection_set(target)
            self.tree.focus(target)
            self.tree.see(target)
            self._on_finding_selected(None)
        else:
            self.tree.selection_remove(self.tree.selection())
            self._set_replacement_panel_enabled(False)
            self.save_button.focus_set()

    def _build_replacement_editor(self) -> None:
        editor = ttk.Frame(self.content, style="Panel.TFrame", padding=(12, 10))
        editor.grid(row=4, column=0, sticky="ew")
        ttk.Label(
            editor,
            text="Definir substituição",
            style="PanelTitle.TLabel",
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 5))
        self.suggestion_radio = ttk.Radiobutton(
            editor,
            text="Usar sugestão",
            variable=self.replacement_mode_var,
            value="suggestion",
            style="Panel.TRadiobutton",
            command=self._update_replacement_editor_state,
        )
        self.suggestion_radio.grid(row=1, column=0, sticky="w")
        self.suggestion_value = ttk.Label(editor, style="Muted.TLabel")
        self.suggestion_value.grid(row=1, column=1, columnspan=2, sticky="w", padx=(4, 0))
        self.custom_radio = ttk.Radiobutton(
            editor,
            text="Substituir por:",
            variable=self.replacement_mode_var,
            value="custom",
            style="Panel.TRadiobutton",
            command=self._update_replacement_editor_state,
        )
        self.custom_radio.grid(row=2, column=0, sticky="w")
        self.replacement_entry = ttk.Entry(
            editor,
            textvariable=self.replacement_var,
            style="Replacement.TEntry",
            width=20,
        )
        self.replacement_entry.grid(row=2, column=1, sticky="w", padx=(4, 12))
        self.remove_radio = ttk.Radiobutton(
            editor,
            text="Remover o caractere",
            variable=self.replacement_mode_var,
            value="remove",
            style="Panel.TRadiobutton",
            command=self._update_replacement_editor_state,
        )
        self.remove_radio.grid(row=3, column=0, sticky="w", columnspan=2)
        self.save_exception_check = ttk.Checkbutton(
            editor,
            text="Salvar esta regra De-Para no catálogo local",
            variable=self.save_exception_var,
            style="Panel.TCheckbutton",
        )
        self.save_exception_check.grid(row=4, column=0, columnspan=3, sticky="w", pady=(4, 0))
        self.apply_button = RoundedButton(
            editor,
            "Aplicar",
            self._set_custom_replacement,
        )
        self.apply_button.grid(row=3, column=2, sticky="e")
        ttk.Label(
            editor,
            text="Catálogo local: " + str(exception_catalog_path()),
            style="Muted.TLabel",
            wraplength=900,
        ).grid(row=5, column=0, columnspan=3, sticky="w", pady=(5, 0))
        ttk.Label(
            editor,
            text="Prévia da correção",
            style="PanelTitle.TLabel",
        ).grid(row=6, column=0, columnspan=3, sticky="w", pady=(10, 0))
        self.correction_preview = tk.Text(
            editor,
            height=2,
            wrap="word",
            background=COLORS["surface"],
            foreground=COLORS["text"],
            relief="flat",
            padx=6,
            pady=5,
            font=FONTS["caption"],
            takefocus=False,
            state="disabled",
        )
        self.correction_preview.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(5, 0))
        self.replacement_controls = (
            self.suggestion_radio,
            self.custom_radio,
            self.remove_radio,
            self.replacement_entry,
            self.save_exception_check,
        )
        self._set_replacement_panel_enabled(False)

    def _on_finding_selected(self, _event: tk.Event) -> None:
        selected = self.tree.selection()
        if not selected:
            self._set_replacement_panel_enabled(False)
            return
        iid = selected[0]
        finding = self.findings_by_iid[iid]
        self._update_details(iid)
        self.save_exception_var.set(False)
        replacement = self.replacements.get(finding.offset, finding.suggested)
        if finding.offset in self.replacements and finding.offset in self.custom_replacements:
            self.replacement_mode_var.set("custom")
            self.replacement_var.set(replacement or "")
        elif finding.suggested is not None:
            self.replacement_mode_var.set("suggestion")
            self.replacement_var.set(finding.suggested or "")
        else:
            self.replacement_mode_var.set("custom")
            self.replacement_var.set("")
        self.suggestion_value.configure(
            text=self._replacement_label(finding, None)
        )
        self._set_replacement_panel_enabled(True, finding.suggested is not None)
        self._update_replacement_editor_state()

    def _set_replacement_panel_enabled(self, enabled: bool, has_suggestion: bool = True) -> None:
        if not hasattr(self, "replacement_controls"):
            return
        for control in self.replacement_controls:
            control.configure(state="normal" if enabled else "disabled")
        self.suggestion_radio.configure(
            state="normal" if enabled and has_suggestion else "disabled"
        )
        self.apply_button.set_enabled(enabled)

    def _update_replacement_editor_state(self) -> None:
        if not hasattr(self, "replacement_entry"):
            return
        self.replacement_entry.configure(
            state="normal" if self.replacement_mode_var.get() == "custom" else "disabled"
        )
        self._update_correction_preview()

    def _preview_replacement(self, finding: Finding) -> str:
        mode = self.replacement_mode_var.get()
        if mode == "suggestion":
            return finding.suggested or ""
        if mode == "remove":
            return ""
        return self.replacement_var.get()

    def _update_correction_preview(self, *_args: object) -> None:
        if not hasattr(self, "correction_preview"):
            return
        context = self._selected_finding_context()
        self.correction_preview.configure(state="normal")
        self.correction_preview.delete("1.0", "end")
        if context is not None:
            finding, index, start, end = context
            corrected_context = (
                self.analysis_text[start:index]
                + self._preview_replacement(finding)
                + self.analysis_text[index + len(finding.character) : end]
            )
            self.correction_preview.insert("end", self._printable_context(corrected_context))
        self.correction_preview.configure(state="disabled")

    def _set_custom_replacement(self) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        finding = self.findings_by_iid[selected[0]]
        mode = self.replacement_mode_var.get()
        if mode == "suggestion":
            replacement = finding.suggested
            if replacement is None:
                return
        elif mode == "remove":
            replacement = ""
        else:
            replacement = self.replacement_var.get()
        if replacement == "" and mode == "custom":
            messagebox.showinfo(
                "Substituição vazia",
                "Digite o novo valor ou escolha “Remover o caractere”.",
            )
            return
        try:
            replacement_bytes(replacement, self.analysis.codec)  # type: ignore[union-attr]
            if self.save_exception_var.get():
                save_exception_rule(
                    finding.character,
                    finding.raw_hex,
                    replacement,
                )
                self.exception_catalog = load_effective_exception_catalog()
        except (OSError, ValueError) as exc:
            messagebox.showwarning("Substituição não permitida", str(exc))
            return

        self.replacements[finding.offset] = replacement
        if mode == "custom":
            self.custom_replacements.add(finding.offset)
        else:
            self.custom_replacements.discard(finding.offset)
        self._refresh_replacement_labels()
        self._update_save_state()
        self._select_next_pending(selected[0])

    def _build_result_actions(self) -> None:
        self._set_actions(
            "← Voltar",
            self._show_start_screen,
            True,
            "Salvar cópia corrigida",
            self._save_copy,
            False,
        )
        self.save_button = self.primary_button
        self._update_save_state()

    def _update_save_state(self) -> None:
        if not hasattr(self, "save_button") or self.analysis is None:
            return
        if not self.analysis.findings:  # type: ignore[union-attr]
            self.save_button.set_enabled(True)
            self.status_var.set("Análise concluída sem ocorrências para revisar.")
            self.action_message.configure(
                text="Arquivo pronto para copiar",
                style="InlineSuccess.TLabel",
            )
            return
        unresolved = [
            finding
            for finding in self.analysis.findings  # type: ignore[union-attr]
            if finding.offset not in self.replacements
        ]
        resolved = len(self.analysis.findings) - len(unresolved)
        if getattr(self, "counter_label", None) is not None and self.counter_label.winfo_exists():
            self.counter_label.configure(
                text=f"{resolved} de {len(self.analysis.findings)} resolvidos"
            )
        if getattr(self, "accept_button", None) is not None and self.accept_button.winfo_exists():
            has_pending_suggestions = any(
                finding.offset not in self.replacements and finding.suggested is not None
                for finding in self.analysis.findings
            )
            self.accept_button.set_enabled(has_pending_suggestions)
        if unresolved:
            self.save_button.set_enabled(False)
            count = len(unresolved)
            noun = plural(count, "caractere", "caracteres")
            self.status_var.set(f"{resolved} de {len(self.analysis.findings)} resolvidos")
            self.action_message.configure(
                text=f"{count} {noun} sem substituição definida",
                style="InlineWarning.TLabel",
            )
        else:
            self.save_button.set_enabled(True)
            self.status_var.set(
                f"{len(self.analysis.findings)} de {len(self.analysis.findings)} resolvidos"
            )
            self.action_message.configure(
                text="Tudo pronto para salvar",
                style="InlineSuccess.TLabel",
            )

    def _save_copy(self) -> None:
        if self.analysis is None or self.current_path is None:
            return
        if not self.analysis.findings:
            destination = filedialog.asksaveasfilename(
                title="Salvar cópia do XML",
                defaultextension=self.current_path.suffix,
                initialfile=f"{self.current_path.stem}_copia{self.current_path.suffix}",
                filetypes=[("Arquivos XML", "*.xml"), ("Todos os arquivos", "*.*")],
            )
            if not destination:
                return
            try:
                save_corrected_copy(self.analysis, {}, destination)
            except (OSError, ValueError, XmlEncodingError) as exc:
                messagebox.showerror("Falha ao salvar cópia", str(exc))
                return
            messagebox.showinfo("Cópia salva", f"A cópia foi salva em:\n{destination}")
            return
        unresolved = sum(
            finding.offset not in self.replacements
            for finding in self.analysis.findings
        )
        if unresolved:
            noun = plural(unresolved, "caractere", "caracteres")
            adjective = "pendente" if unresolved == 1 else "pendentes"
            messagebox.showwarning(
                "Revisão incompleta",
                f"Defina a substituição para {unresolved} {noun} {adjective} antes de salvar.",
            )
            return
        destination = filedialog.asksaveasfilename(
            title="Salvar XML corrigido",
            initialdir=str(self.current_path.parent),
            initialfile=f"{self.current_path.stem}_corrigido{self.current_path.suffix}",
            defaultextension=".xml",
            filetypes=(("Arquivos XML", "*.xml"),),
        )
        if not destination:
            return
        try:
            saved_path = save_corrected_copy(
                self.analysis,
                self.replacements,
                destination,
            )
        except (OSError, ValueError) as exc:
            messagebox.showerror("Não foi possível salvar a cópia", str(exc))
            return
        self._set_step(3)
        self.status_var.set(f"Cópia salva: {saved_path}")
        messagebox.showinfo(
            "Cópia corrigida salva",
            f"A cópia foi salva em:\n{saved_path}\n\nO arquivo original não foi alterado.",
        )


def main() -> None:
    root = create_root()
    AnalisadorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
