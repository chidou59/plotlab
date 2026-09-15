from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from .models import MARKER_OPTIONS, PlotStyleConfig


class PlotStyleDialog(tk.Toplevel):
    """Modal editor for publication figure parameters."""

    BG = "#EEF1EE"
    SURFACE = "#FFFFFF"
    INK = "#14231F"
    MUTED = "#66736E"
    BORDER = "#D8DFDA"
    ACCENT = "#1C6654"
    ERROR = "#B8403A"

    FIELD_GROUPS = (
        (
            "画布与输出",
            (
                ("图像宽度", "width_cm", "cm"),
                ("图像高度", "height_cm", "cm"),
                ("输出精度", "dpi", "DPI"),
            ),
        ),
        (
            "文字",
            (
                ("图表标题", "title_font_size", "pt"),
                ("坐标轴标题", "axis_font_size", "pt"),
                ("坐标刻度", "tick_font_size", "pt"),
                ("图例", "legend_font_size", "pt"),
            ),
        ),
        (
            "数据与坐标框",
            (
                ("数据点大小", "marker_size", "pt"),
                ("折线宽度", "data_line_width", "pt"),
                ("坐标框线宽", "axis_line_width", "pt"),
            ),
        ),
        (
            "网格与次刻度",
            (
                ("主网格线宽", "major_grid_width", "pt"),
                ("次网格线宽", "minor_grid_width", "pt"),
                ("次刻度分段数", "minor_divisions", "段"),
                ("次刻度长度", "minor_tick_length", "pt"),
            ),
        ),
    )

    INT_FIELDS = {"dpi", "minor_divisions"}
    MARKER_GLYPHS = {
        "o": "●",
        "s": "■",
        "^": "▲",
        "D": "◆",
        "v": "▼",
        "P": "✚",
        "X": "✖",
        "<": "◀",
        ">": "▶",
        "h": "⬢",
        "*": "★",
        "p": "⬟",
    }

    def __init__(
        self,
        parent: tk.Misc,
        current: PlotStyleConfig,
        on_apply: Callable[[PlotStyleConfig], None],
    ) -> None:
        super().__init__(parent)
        self.title("图像参数调整 · PlotLab")
        self.configure(bg=self.BG)
        self.resizable(False, False)
        self.transient(parent)
        self.on_apply = on_apply
        self.variables: dict[str, tk.StringVar] = {}
        self.show_minor_grid_var = tk.BooleanVar(value=current.show_minor_grid)
        self.show_title_var = tk.BooleanVar(value=current.show_title)
        self.use_color_var = tk.BooleanVar(value=current.use_color)
        self.marker_vars = {
            code: tk.BooleanVar(value=code in current.markers)
            for code, _label in MARKER_OPTIONS
        }
        self.error_var = tk.StringVar()

        self._build(current)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.grab_set()
        self.update_idletasks()
        self._center_on_parent(parent)
        self.focus_set()

    @staticmethod
    def _format_value(value: float | int) -> str:
        if isinstance(value, int):
            return str(value)
        return f"{value:g}"

    def _build(self, current: PlotStyleConfig) -> None:
        header = tk.Frame(self, bg=self.BG, padx=24, pady=18)
        header.pack(fill="x")
        tk.Label(
            header,
            text="图像参数调整",
            bg=self.BG,
            fg=self.INK,
            font=("Microsoft YaHei UI", 17, "bold"),
        ).pack(anchor="w")
        tk.Label(
            header,
            text="参数将在下一次生成时应用到预览和 PNG；尺寸单位采用论文排版常用的厘米。",
            bg=self.BG,
            fg=self.MUTED,
            font=("Microsoft YaHei UI", 9),
        ).pack(anchor="w", pady=(4, 0))

        body_shell = tk.Frame(
            self,
            bg=self.SURFACE,
            highlightthickness=1,
            highlightbackground=self.BORDER,
        )
        body_shell.pack(fill="both", padx=24)
        body_canvas = tk.Canvas(
            body_shell,
            bg=self.SURFACE,
            width=660,
            height=500,
            highlightthickness=0,
            borderwidth=0,
        )
        body_scrollbar = ttk.Scrollbar(
            body_shell,
            orient="vertical",
            command=body_canvas.yview,
        )
        body_canvas.configure(yscrollcommand=body_scrollbar.set)
        body_canvas.pack(side="left", fill="both", expand=True)
        body_scrollbar.pack(side="right", fill="y")

        body = tk.Frame(body_canvas, bg=self.SURFACE, padx=20, pady=18)
        body_window = body_canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind(
            "<Configure>",
            lambda _event: body_canvas.configure(scrollregion=body_canvas.bbox("all")),
        )
        body_canvas.bind(
            "<Configure>",
            lambda event: body_canvas.itemconfigure(body_window, width=event.width),
        )
        self.bind(
            "<MouseWheel>",
            lambda event: body_canvas.yview_scroll(int(-event.delta / 120), "units"),
        )
        body.grid_columnconfigure(0, weight=1, uniform="group")
        body.grid_columnconfigure(1, weight=1, uniform="group")

        for index, (title, fields) in enumerate(self.FIELD_GROUPS):
            group = tk.Frame(body, bg=self.SURFACE, padx=8, pady=6)
            group.grid(
                row=index // 2,
                column=index % 2,
                sticky="nsew",
                padx=(0, 12) if index % 2 == 0 else (12, 0),
                pady=(0, 12) if index < 2 else (12, 0),
            )
            group.grid_columnconfigure(1, weight=1)
            tk.Label(
                group,
                text=title,
                bg=self.SURFACE,
                fg=self.ACCENT,
                font=("Microsoft YaHei UI", 10, "bold"),
            ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 7))

            for row, (label, key, unit) in enumerate(fields, start=1):
                tk.Label(
                    group,
                    text=label,
                    bg=self.SURFACE,
                    fg=self.INK,
                    font=("Microsoft YaHei UI", 9),
                ).grid(row=row, column=0, sticky="w", pady=4)
                variable = tk.StringVar(value=self._format_value(getattr(current, key)))
                self.variables[key] = variable
                ttk.Entry(
                    group,
                    textvariable=variable,
                    style="PlotLab.TEntry",
                    width=10,
                    justify="right",
                ).grid(row=row, column=1, sticky="ew", padx=(12, 7), pady=3)
                tk.Label(
                    group,
                    text=unit,
                    bg=self.SURFACE,
                    fg=self.MUTED,
                    font=("Segoe UI", 8),
                    width=4,
                    anchor="w",
                ).grid(row=row, column=2, sticky="w")

            if title == "网格与次刻度":
                ttk.Checkbutton(
                    group,
                    text="显示淡灰色次网格线",
                    variable=self.show_minor_grid_var,
                ).grid(
                    row=len(fields) + 1,
                    column=0,
                    columnspan=3,
                    sticky="w",
                    pady=(8, 0),
                )

        display_options = tk.Frame(
            body,
            bg="#F6F8F6",
            padx=12,
            pady=9,
            highlightthickness=1,
            highlightbackground=self.BORDER,
        )
        display_options.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        tk.Label(
            display_options,
            text="显示与配色",
            bg="#F6F8F6",
            fg=self.ACCENT,
            font=("Microsoft YaHei UI", 9, "bold"),
        ).pack(side="left", padx=(0, 18))
        ttk.Checkbutton(
            display_options,
            text="包含图表标题",
            variable=self.show_title_var,
        ).pack(side="left", padx=(0, 18))
        ttk.Checkbutton(
            display_options,
            text="使用彩色系列",
            variable=self.use_color_var,
        ).pack(side="left")

        marker_library = tk.Frame(body, bg=self.SURFACE, pady=7)
        marker_library.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(11, 0))
        for column in range(6):
            marker_library.grid_columnconfigure(column, weight=1, uniform="marker")
        marker_header = tk.Frame(marker_library, bg=self.SURFACE)
        marker_header.grid(row=0, column=0, columnspan=6, sticky="ew", pady=(0, 6))
        tk.Label(
            marker_header,
            text="数据点形状库",
            bg=self.SURFACE,
            fg=self.ACCENT,
            font=("Microsoft YaHei UI", 10, "bold"),
        ).pack(side="left")
        tk.Label(
            marker_header,
            text="取消勾选即禁用；至少保留一种",
            bg=self.SURFACE,
            fg=self.MUTED,
            font=("Microsoft YaHei UI", 8),
        ).pack(side="left", padx=(10, 0))
        ttk.Button(
            marker_header,
            text="全选",
            style="Quiet.TButton",
            command=self._select_all_markers,
        ).pack(side="right")
        ttk.Button(
            marker_header,
            text="反选",
            style="Quiet.TButton",
            command=self._invert_markers,
        ).pack(side="right", padx=(0, 6))

        for index, (code, label) in enumerate(MARKER_OPTIONS):
            ttk.Checkbutton(
                marker_library,
                text=f"{self.MARKER_GLYPHS.get(code, code)} {label}",
                variable=self.marker_vars[code],
            ).grid(
                row=1 + index // 6,
                column=index % 6,
                sticky="w",
                padx=(0, 5),
                pady=3,
            )

        error_label = tk.Label(
            self,
            textvariable=self.error_var,
            bg=self.BG,
            fg=self.ERROR,
            font=("Microsoft YaHei UI", 9, "bold"),
            anchor="w",
        )
        error_label.pack(fill="x", padx=26, pady=(10, 0))

        actions = tk.Frame(self, bg=self.BG, padx=24, pady=16)
        actions.pack(fill="x")
        ttk.Button(
            actions,
            text="恢复论文默认值",
            style="Quiet.TButton",
            command=self._reset_defaults,
        ).pack(side="left")
        ttk.Button(
            actions,
            text="取消",
            style="Quiet.TButton",
            command=self.destroy,
        ).pack(side="right")
        ttk.Button(
            actions,
            text="应用参数",
            style="Accent.TButton",
            command=self._apply,
        ).pack(side="right", padx=(0, 9))

    def _read_config(self) -> PlotStyleConfig:
        values: dict[str, float | int | bool] = {}
        for key, variable in self.variables.items():
            text = variable.get().strip()
            if not text:
                raise ValueError("所有参数均不能为空")
            try:
                values[key] = int(text) if key in self.INT_FIELDS else float(text)
            except ValueError as error:
                raise ValueError(f"“{text}”不是有效数值") from error
        values["show_minor_grid"] = self.show_minor_grid_var.get()
        values["show_title"] = self.show_title_var.get()
        values["use_color"] = self.use_color_var.get()
        values["markers"] = tuple(
            code for code, _label in MARKER_OPTIONS if self.marker_vars[code].get()
        )
        return PlotStyleConfig(**values)  # type: ignore[arg-type]

    def _apply(self) -> None:
        try:
            config = self._read_config()
        except ValueError as error:
            self.error_var.set(str(error))
            self.bell()
            return
        self.on_apply(config)
        self.destroy()

    def _reset_defaults(self) -> None:
        defaults = PlotStyleConfig()
        for key, variable in self.variables.items():
            variable.set(self._format_value(getattr(defaults, key)))
        self.show_minor_grid_var.set(defaults.show_minor_grid)
        self.show_title_var.set(defaults.show_title)
        self.use_color_var.set(defaults.use_color)
        for code, _label in MARKER_OPTIONS:
            self.marker_vars[code].set(code in defaults.markers)
        self.error_var.set("")

    def _select_all_markers(self) -> None:
        for variable in self.marker_vars.values():
            variable.set(True)
        self.error_var.set("")

    def _invert_markers(self) -> None:
        for variable in self.marker_vars.values():
            variable.set(not variable.get())
        self.error_var.set("")

    def _center_on_parent(self, parent: tk.Misc) -> None:
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()
        x = max(0, parent_x + (parent_width - width) // 2)
        y = max(0, parent_y + (parent_height - height) // 2)
        self.geometry(f"+{x}+{y}")
