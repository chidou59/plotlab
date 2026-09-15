from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from .data_editor import DataEditorWindow
from .data_loader import load_folder
from .editable_data import EditableDataModel
from .models import LoadReport, PlotConfig, PlotStyleConfig
from .plotting import build_figure, export_png
from .preset_dialog import PresetPickerDialog
from .preset_store import PlotPreset, PresetNameConflict, PresetStore, PresetStoreError
from .style_dialog import PlotStyleDialog


class PlotterApp:
    BG = "#EEF1EE"
    SURFACE = "#FFFFFF"
    INK = "#14231F"
    MUTED = "#66736E"
    BORDER = "#D8DFDA"
    ACCENT = "#1C6654"
    ACCENT_DARK = "#145044"
    ACCENT_SOFT = "#E4F1EC"
    BLUE = "#2357A5"
    ERROR = "#B8403A"
    ERROR_SOFT = "#FBECEA"
    WARNING = "#A56A16"

    def __init__(self, root: tk.Tk, preset_store: PresetStore | None = None) -> None:
        self.root = root
        self.root.title("PlotLab · Excel 全自动画图器")
        self.root.geometry("1240x790")
        self.root.minsize(1080, 700)
        self.root.configure(bg=self.BG)

        self.folder: Path | None = None
        self.report: LoadReport | None = None
        self.output_path: Path | None = None
        self.figure = None
        self.figure_canvas: FigureCanvasTkAgg | None = None
        self.data_editor: DataEditorWindow | None = None
        self.busy = False
        self.operation: str | None = None
        self.plot_style = PlotStyleConfig()
        self.preset_store = preset_store or PresetStore()
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="plotlab")

        self.title_var = tk.StringVar()
        self.x_label_var = tk.StringVar()
        self.y_label_var = tk.StringVar()
        self.plot_type_var = tk.StringVar(value="scatter")
        self.folder_var = tk.StringVar(value="尚未选择数据文件夹")
        self.summary_var = tk.StringVar(value="等待选择文件夹")
        self.status_var = tk.StringVar(value="准备就绪")
        self.preview_meta_var = tk.StringVar(value="尚未生成图表")
        self.style_summary_var = tk.StringVar()
        self.generate_text_var = tk.StringVar()
        self.title_field_label_var = tk.StringVar()
        self._refresh_style_summary()

        self._configure_styles()
        self._build_ui()
        self._bind_shortcuts()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._poll_events)

    def _configure_styles(self) -> None:
        default_font = ("Microsoft YaHei UI", 10)
        self.root.option_add("*Font", default_font)
        self.root.option_add("*Entry.Font", ("Microsoft YaHei UI", 10))

        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "PlotLab.TEntry",
            padding=(11, 9),
            fieldbackground="#F8FAF8",
            foreground=self.INK,
            bordercolor=self.BORDER,
            lightcolor=self.BORDER,
            darkcolor=self.BORDER,
            insertcolor=self.INK,
        )
        style.map(
            "PlotLab.TEntry",
            bordercolor=[("focus", self.ACCENT)],
            lightcolor=[("focus", self.ACCENT)],
            darkcolor=[("focus", self.ACCENT)],
        )
        style.configure(
            "Accent.TButton",
            font=("Microsoft YaHei UI", 10, "bold"),
            padding=(18, 11),
            background=self.ACCENT,
            foreground="white",
            borderwidth=0,
        )
        style.map(
            "Accent.TButton",
            background=[("active", self.ACCENT_DARK), ("disabled", "#9BAAA4")],
            foreground=[("disabled", "#EDF1EF")],
        )
        style.configure(
            "Quiet.TButton",
            font=("Microsoft YaHei UI", 9),
            padding=(11, 8),
            background="#F5F7F5",
            foreground=self.INK,
            bordercolor=self.BORDER,
            lightcolor=self.BORDER,
            darkcolor=self.BORDER,
        )
        style.map("Quiet.TButton", background=[("active", self.ACCENT_SOFT)])
        style.configure(
            "PlotType.TRadiobutton",
            font=("Microsoft YaHei UI", 9, "bold"),
            padding=(15, 8),
            background="#F6F8F6",
            foreground=self.MUTED,
            indicatorcolor="#F6F8F6",
            indicatormargin=-18,
            bordercolor=self.BORDER,
            lightcolor=self.BORDER,
            darkcolor=self.BORDER,
            relief="flat",
        )
        style.map(
            "PlotType.TRadiobutton",
            background=[("selected", self.ACCENT_SOFT), ("active", "#EDF4F0")],
            foreground=[("selected", self.ACCENT)],
            bordercolor=[("selected", self.ACCENT)],
            lightcolor=[("selected", self.ACCENT)],
            darkcolor=[("selected", self.ACCENT)],
        )
        style.configure(
            "Data.Treeview",
            background="#FBFCFB",
            fieldbackground="#FBFCFB",
            foreground=self.INK,
            bordercolor=self.BORDER,
            rowheight=29,
            font=("Microsoft YaHei UI", 9),
        )
        style.configure(
            "Data.Treeview.Heading",
            background="#F0F4F1",
            foreground=self.MUTED,
            relief="flat",
            font=("Microsoft YaHei UI", 9, "bold"),
            padding=(7, 6),
        )
        style.map("Data.Treeview", background=[("selected", self.ACCENT_SOFT)])
        style.configure(
            "PlotLab.Horizontal.TProgressbar",
            background=self.ACCENT,
            troughcolor="#DDE5E0",
            borderwidth=0,
            lightcolor=self.ACCENT,
            darkcolor=self.ACCENT,
        )

    def _build_ui(self) -> None:
        header = tk.Frame(self.root, bg=self.BG, padx=28, pady=20)
        header.pack(fill="x")

        brand = tk.Frame(header, bg=self.BG)
        brand.pack(side="left")
        tk.Label(
            brand,
            text="PLOTLAB  /  EXCEL SERIES STUDIO",
            bg=self.BG,
            fg=self.ACCENT,
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w")
        tk.Label(
            brand,
            text="把一叠数据，变成一张好图。",
            bg=self.BG,
            fg=self.INK,
            font=("Microsoft YaHei UI", 20, "bold"),
        ).pack(anchor="w", pady=(3, 0))

        self.status_pill = tk.Label(
            header,
            text="  ●  准备就绪  ",
            bg=self.ACCENT_SOFT,
            fg=self.ACCENT,
            font=("Microsoft YaHei UI", 9, "bold"),
            padx=10,
            pady=6,
        )
        self.status_pill.pack(side="right", anchor="n", pady=5)

        preset_actions = tk.Frame(header, bg=self.BG)
        preset_actions.pack(side="right", anchor="n", padx=(0, 12), pady=3)
        self.save_preset_button = ttk.Button(
            preset_actions,
            text="保存设置",
            style="Quiet.TButton",
            command=self.save_current_preset,
        )
        self.save_preset_button.pack(side="left", padx=(0, 5))
        self.apply_preset_button = ttk.Button(
            preset_actions,
            text="套用设置",
            style="Quiet.TButton",
            command=self.open_preset_picker,
        )
        self.apply_preset_button.pack(side="left", padx=(5, 0))

        content = tk.Frame(self.root, bg=self.BG, padx=28, pady=0)
        content.pack(fill="both", expand=True)
        content.grid_columnconfigure(0, minsize=385)
        content.grid_columnconfigure(1, weight=1)
        content.grid_rowconfigure(0, weight=1)

        left = tk.Frame(content, bg=self.SURFACE, highlightthickness=1, highlightbackground=self.BORDER)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(2, weight=1)

        self._build_settings(left)
        self._build_folder_panel(left)
        self._build_readiness_panel(left)
        self._build_actions(left)

        right = tk.Frame(content, bg=self.SURFACE, highlightthickness=1, highlightbackground=self.BORDER)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)
        self._build_preview(right)

        footer = tk.Frame(self.root, bg=self.BG, padx=28, pady=12)
        footer.pack(fill="x")
        tk.Label(
            footer,
            textvariable=self.status_var,
            bg=self.BG,
            fg=self.MUTED,
            font=("Microsoft YaHei UI", 9),
            anchor="w",
        ).pack(side="left", fill="x", expand=True)
        tk.Label(
            footer,
            text="快捷键  Ctrl+O 选择文件夹   ·   F5 重新扫描   ·   Ctrl+Enter 生成",
            bg=self.BG,
            fg="#8A9691",
            font=("Microsoft YaHei UI", 8),
        ).pack(side="right")

    def _section_title(self, parent: tk.Widget, number: str, title: str, subtitle: str) -> tk.Frame:
        frame = tk.Frame(parent, bg=self.SURFACE)
        badge = tk.Label(
            frame,
            text=number,
            bg=self.INK,
            fg="white",
            width=3,
            pady=3,
            font=("Segoe UI", 8, "bold"),
        )
        badge.pack(side="left", anchor="n", padx=(0, 10))
        copy = tk.Frame(frame, bg=self.SURFACE)
        copy.pack(side="left", fill="x", expand=True)
        tk.Label(
            copy,
            text=title,
            bg=self.SURFACE,
            fg=self.INK,
            font=("Microsoft YaHei UI", 11, "bold"),
        ).pack(anchor="w")
        tk.Label(
            copy,
            text=subtitle,
            bg=self.SURFACE,
            fg=self.MUTED,
            font=("Microsoft YaHei UI", 8),
        ).pack(anchor="w", pady=(1, 0))
        return frame

    def _labeled_entry(
        self,
        parent: tk.Widget,
        label: str | tk.StringVar,
        variable: tk.StringVar,
    ) -> ttk.Entry:
        label_options: dict[str, object]
        if isinstance(label, tk.StringVar):
            label_options = {"textvariable": label}
        else:
            label_options = {"text": label}
        tk.Label(
            parent,
            bg=self.SURFACE,
            fg=self.MUTED,
            font=("Microsoft YaHei UI", 8, "bold"),
            **label_options,
        ).pack(anchor="w", pady=(8, 4))
        entry = ttk.Entry(parent, textvariable=variable, style="PlotLab.TEntry")
        entry.pack(fill="x")
        return entry

    def _build_settings(self, parent: tk.Frame) -> None:
        frame = tk.Frame(parent, bg=self.SURFACE, padx=20, pady=14)
        frame.grid(row=0, column=0, sticky="ew")
        self._section_title(frame, "01", "设置图表", "标题与坐标轴文字均为必填").pack(fill="x")
        self.title_entry = self._labeled_entry(frame, self.title_field_label_var, self.title_var)

        axis_row = tk.Frame(frame, bg=self.SURFACE)
        axis_row.pack(fill="x")
        axis_row.grid_columnconfigure(0, weight=1, uniform="axis")
        axis_row.grid_columnconfigure(1, weight=1, uniform="axis")
        x_box = tk.Frame(axis_row, bg=self.SURFACE)
        x_box.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        y_box = tk.Frame(axis_row, bg=self.SURFACE)
        y_box.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        self.x_entry = self._labeled_entry(x_box, "X 轴标题 *", self.x_label_var)
        self.y_entry = self._labeled_entry(y_box, "Y 轴标题 *", self.y_label_var)

        tk.Label(
            frame,
            text="成图类型",
            bg=self.SURFACE,
            fg=self.MUTED,
            font=("Microsoft YaHei UI", 8, "bold"),
        ).pack(anchor="w", pady=(10, 5))
        types = tk.Frame(frame, bg=self.SURFACE)
        types.pack(fill="x")
        for text, value in (("●  点图", "scatter"), ("—●—  折线图", "line")):
            ttk.Radiobutton(
                types,
                text=text,
                value=value,
                variable=self.plot_type_var,
                style="PlotType.TRadiobutton",
            ).pack(side="left", fill="x", expand=True, padx=(0, 6) if value == "scatter" else (6, 0))

        style_card = tk.Frame(
            frame,
            bg="#F6F8F6",
            highlightthickness=1,
            highlightbackground=self.BORDER,
            padx=11,
            pady=8,
        )
        style_card.pack(fill="x", pady=(11, 0))
        style_copy = tk.Frame(style_card, bg="#F6F8F6")
        style_copy.pack(side="left", fill="x", expand=True)
        tk.Label(
            style_copy,
            text="图像参数",
            bg="#F6F8F6",
            fg=self.INK,
            font=("Microsoft YaHei UI", 8, "bold"),
        ).pack(anchor="w")
        tk.Label(
            style_copy,
            textvariable=self.style_summary_var,
            bg="#F6F8F6",
            fg=self.MUTED,
            font=("Microsoft YaHei UI", 7),
        ).pack(anchor="w", pady=(2, 0))
        ttk.Button(
            style_card,
            text="调整参数",
            style="Quiet.TButton",
            command=self.open_style_dialog,
        ).pack(side="right", padx=(8, 0))

    def _build_folder_panel(self, parent: tk.Frame) -> None:
        frame = tk.Frame(parent, bg=self.SURFACE, padx=20, pady=15)
        frame.grid(row=1, column=0, sticky="ew")
        tk.Frame(frame, bg=self.BORDER, height=1).pack(fill="x", pady=(0, 15))
        self._section_title(frame, "02", "选择数据", "每个 Excel 文件会成为一个数据系列").pack(fill="x")

        folder_card = tk.Frame(
            frame,
            bg="#F6F8F6",
            highlightthickness=1,
            highlightbackground=self.BORDER,
            padx=12,
            pady=10,
        )
        folder_card.pack(fill="x", pady=(10, 0))
        tk.Label(
            folder_card,
            text="▣",
            bg="#F6F8F6",
            fg=self.ACCENT,
            font=("Segoe UI Symbol", 16),
        ).pack(side="left", padx=(0, 9))
        tk.Label(
            folder_card,
            textvariable=self.folder_var,
            bg="#F6F8F6",
            fg=self.MUTED,
            font=("Microsoft YaHei UI", 8),
            anchor="w",
            justify="left",
            wraplength=210,
        ).pack(side="left", fill="x", expand=True)
        self.choose_button = ttk.Button(
            folder_card,
            text="选择",
            style="Quiet.TButton",
            command=self.choose_folder,
        )
        self.choose_button.pack(side="right", padx=(8, 0))

    def _build_readiness_panel(self, parent: tk.Frame) -> None:
        frame = tk.Frame(parent, bg=self.SURFACE, padx=20, pady=4)
        frame.grid(row=2, column=0, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(2, weight=1)

        top = tk.Frame(frame, bg=self.SURFACE)
        top.grid(row=0, column=0, sticky="ew", pady=(7, 7))
        tk.Label(
            top,
            text="数据就绪状态",
            bg=self.SURFACE,
            fg=self.INK,
            font=("Microsoft YaHei UI", 9, "bold"),
        ).pack(side="left")
        self.summary_label = tk.Label(
            top,
            textvariable=self.summary_var,
            bg=self.SURFACE,
            fg=self.MUTED,
            font=("Microsoft YaHei UI", 8),
        )
        self.summary_label.pack(side="right")
        self.data_editor_button = ttk.Button(
            top,
            text="编辑汇总数据",
            style="Quiet.TButton",
            command=self.open_data_editor,
            state="disabled",
        )
        self.data_editor_button.pack(side="right", padx=(0, 9))

        self.progress = ttk.Progressbar(
            frame,
            mode="indeterminate",
            style="PlotLab.Horizontal.TProgressbar",
            maximum=100,
        )
        self.progress.grid(row=1, column=0, sticky="ew", pady=(0, 7))

        tree_frame = tk.Frame(frame, bg=self.BORDER)
        tree_frame.grid(row=2, column=0, sticky="nsew")
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)
        self.data_tree = ttk.Treeview(
            tree_frame,
            columns=("file", "state"),
            show="headings",
            style="Data.Treeview",
            selectmode="browse",
        )
        self.data_tree.heading("file", text="文件")
        self.data_tree.heading("state", text="检查结果")
        self.data_tree.column("file", width=145, minwidth=90, stretch=True)
        self.data_tree.column("state", width=155, minwidth=110, stretch=True)
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.data_tree.yview)
        self.data_tree.configure(yscrollcommand=scrollbar.set)
        self.data_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.data_tree.tag_configure("valid", foreground=self.ACCENT)
        self.data_tree.tag_configure("warning", foreground=self.WARNING)
        self.data_tree.tag_configure("error", foreground=self.ERROR)
        self.data_tree.insert("", "end", values=("—", "请选择文件夹"))

    def _build_actions(self, parent: tk.Frame) -> None:
        frame = tk.Frame(parent, bg=self.SURFACE, padx=20, pady=12)
        frame.grid(row=3, column=0, sticky="ew")
        self.generate_button = ttk.Button(
            frame,
            textvariable=self.generate_text_var,
            style="Accent.TButton",
            command=self.generate,
            state="disabled",
        )
        self.generate_button.pack(fill="x")
        tk.Label(
            frame,
            text="输出将自动保存到数据文件夹中的 results 目录",
            bg=self.SURFACE,
            fg=self.MUTED,
            font=("Microsoft YaHei UI", 8),
        ).pack(anchor="center", pady=(7, 0))

    def _build_preview(self, parent: tk.Frame) -> None:
        header = tk.Frame(parent, bg=self.SURFACE, padx=20, pady=15)
        header.grid(row=0, column=0, sticky="ew")
        tk.Label(
            header,
            text="图表预览",
            bg=self.SURFACE,
            fg=self.INK,
            font=("Microsoft YaHei UI", 11, "bold"),
        ).pack(side="left")
        tk.Label(
            header,
            textvariable=self.preview_meta_var,
            bg=self.SURFACE,
            fg=self.MUTED,
            font=("Microsoft YaHei UI", 8),
        ).pack(side="left", padx=(12, 0))
        self.open_button = ttk.Button(
            header,
            text="打开结果文件夹",
            style="Quiet.TButton",
            command=self.open_results,
            state="disabled",
        )
        self.open_button.pack(side="right")

        self.preview_host = tk.Frame(parent, bg="#F6F8F7", padx=14, pady=14)
        self.preview_host.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.preview_host.grid_columnconfigure(0, weight=1)
        self.preview_host.grid_rowconfigure(0, weight=1)

        self.placeholder = tk.Canvas(
            self.preview_host,
            bg="#FBFCFB",
            highlightthickness=1,
            highlightbackground=self.BORDER,
        )
        self.placeholder.grid(row=0, column=0, sticky="nsew")
        self.placeholder.bind("<Configure>", self._draw_placeholder)

    def _draw_placeholder(self, event: tk.Event) -> None:
        canvas = self.placeholder
        canvas.delete("all")
        width, height = max(event.width, 400), max(event.height, 300)
        left, right = width * 0.15, width * 0.80
        top, bottom = height * 0.18, height * 0.78
        canvas.create_line(left, top, left, bottom, fill="#B6C1BC", width=2)
        canvas.create_line(left, bottom, right, bottom, fill="#B6C1BC", width=2)
        for ratio in (0.25, 0.5, 0.75):
            y = top + (bottom - top) * ratio
            canvas.create_line(left, y, right, y, fill="#E1E6E3", dash=(3, 5))
        dots = (
            (0.12, 0.78, self.BLUE),
            (0.24, 0.63, self.ACCENT),
            (0.36, 0.69, "#D99A2B"),
            (0.47, 0.43, self.BLUE),
            (0.58, 0.52, "#B84272"),
            (0.72, 0.28, self.ACCENT),
            (0.84, 0.36, "#D55238"),
        )
        for x_ratio, y_ratio, color in dots:
            x = left + (right - left) * x_ratio
            y = top + (bottom - top) * y_ratio
            canvas.create_oval(x - 5, y - 5, x + 5, y + 5, fill=color, outline="white", width=1)
        canvas.create_text(
            width / 2,
            height * 0.43,
            text="等待数据",
            fill=self.INK,
            font=("Microsoft YaHei UI", 16, "bold"),
        )
        canvas.create_text(
            width / 2,
            height * 0.49,
            text="设置参数并选择包含 Excel 的文件夹",
            fill=self.MUTED,
            font=("Microsoft YaHei UI", 9),
        )

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Control-o>", lambda _event: self.choose_folder())
        self.root.bind("<F5>", lambda _event: self.rescan())
        self.root.bind("<Control-Return>", lambda _event: self.generate())

    def choose_folder(self) -> None:
        if self.busy:
            return
        selected = filedialog.askdirectory(title="选择包含 Excel 数据的文件夹")
        if not selected:
            return
        self.folder = Path(selected)
        self.folder_var.set(str(self.folder))
        self._load_selected_folder()

    def rescan(self) -> None:
        if self.folder is not None and not self.busy:
            self._load_selected_folder()

    def _load_selected_folder(self) -> None:
        if self.folder is None:
            return
        folder = self.folder
        self.report = None
        self._clear_tree()
        self.data_tree.insert("", "end", values=("扫描中…", "正在检查 Excel"))
        self.summary_var.set("正在扫描")
        self._set_busy(True, "load", "正在读取并检查 Excel 文件…")

        def task() -> None:
            try:
                self.events.put(("load_success", load_folder(folder)))
            except Exception as error:
                self.events.put(("load_error", error))

        self.executor.submit(task)

    def _clear_tree(self) -> None:
        for item in self.data_tree.get_children():
            self.data_tree.delete(item)

    def _handle_load_success(self, report: LoadReport) -> None:
        self.report = report
        self._populate_data_status(report)
        self._set_busy(False)
        if report.series:
            self._set_status(
                f"数据已就绪：{report.valid_file_count} 个有效文件，共 {report.total_points} 个数据点。",
                "success",
            )
            self.generate_button.configure(state="normal")
            self.data_editor_button.configure(state="normal")
            if self.data_editor is not None and self.data_editor.winfo_exists():
                self.data_editor._close()
            self.root.after(120, self.open_data_editor)
        else:
            self.data_editor_button.configure(state="disabled")
            self._set_status("没有找到可绘制的数据，请检查文件格式和前两列内容。", "error")

    def _populate_data_status(self, report: LoadReport) -> None:
        self._clear_tree()
        for item in report.series:
            details = f"✓ {item.valid_count} 个点"
            tag = "valid"
            if item.warnings:
                details += " · " + "；".join(item.warnings)
                tag = "warning"
            self.data_tree.insert("", "end", values=(item.source.name, details), tags=(tag,))
        for issue in report.issues:
            self.data_tree.insert(
                "",
                "end",
                values=(issue.source.name, f"跳过 · {issue.reason}"),
                tags=("error",),
            )

        if not report.scanned_files:
            self.data_tree.insert("", "end", values=("—", "未找到 Excel 文件"), tags=("error",))
        elif not report.series:
            self.data_tree.insert("", "end", values=("—", "没有可绘制的数据"), tags=("error",))

        invalid_count = len(report.issues)
        self.summary_var.set(
            f"{report.valid_file_count} 组 · {report.total_points} 点"
            + (f" · 跳过 {invalid_count}" if invalid_count else "")
        )

    def _handle_load_error(self, error: Exception) -> None:
        self.report = None
        self.data_editor_button.configure(state="disabled")
        self._clear_tree()
        self.data_tree.insert("", "end", values=("读取失败", str(error)), tags=("error",))
        self.summary_var.set("读取失败")
        self._set_busy(False)
        self._set_status(f"文件夹读取失败：{error}", "error")
        messagebox.showerror("读取失败", str(error), parent=self.root)

    def _validate_form(self) -> str | None:
        settings_error = self._validate_settings_fields()
        if settings_error:
            return settings_error
        if self.folder is None:
            return "请选择包含 Excel 数据的文件夹。"
        if self.report is None or not self.report.series:
            return "当前没有可绘制的数据，请选择文件夹或重新扫描。"
        return None

    def _validate_settings_fields(self) -> str | None:
        fields: list[tuple[str, str, ttk.Entry]] = []
        if self.plot_style.show_title:
            fields.append((self.title_var.get().strip(), "请输入图表标题。", self.title_entry))
        fields.extend(
            (
                (self.x_label_var.get().strip(), "请输入 X 轴标题。", self.x_entry),
                (self.y_label_var.get().strip(), "请输入 Y 轴标题。", self.y_entry),
            )
        )
        for value, message, widget in fields:
            if not value:
                widget.focus_set()
                return message
        return None

    def _current_plot_config(self) -> PlotConfig:
        return PlotConfig(
            title=self.title_var.get().strip(),
            x_label=self.x_label_var.get().strip(),
            y_label=self.y_label_var.get().strip(),
            plot_type=self.plot_type_var.get(),  # type: ignore[arg-type]
            style=self.plot_style,
        )

    def generate(self) -> None:
        if self.busy:
            return
        validation_error = self._validate_form()
        if validation_error:
            self._set_status(validation_error, "error")
            self.root.bell()
            return

        assert self.folder is not None and self.report is not None
        config = self._current_plot_config()
        series_items = list(self.report.series)
        folder = self.folder
        self._set_busy(True, "plot", "正在绘图并导出 300 DPI PNG…")

        def task() -> None:
            try:
                figure = build_figure(config, series_items)
                destination = export_png(figure, folder, config.title, config.dpi)
                self.events.put(("plot_success", (figure, destination, config, len(series_items))))
            except Exception as error:
                self.events.put(("plot_error", error))

        self.executor.submit(task)

    def _handle_plot_success(self, payload: object) -> None:
        figure, destination, config, series_count = payload  # type: ignore[misc]
        self._set_busy(False)
        self.output_path = destination
        self.preview_meta_var.set(
            f"{series_count} 个系列  ·  {'点图' if config.plot_type == 'scatter' else '折线图'}"
            f"  ·  {config.style.width_cm:g}×{config.style.height_cm:g} cm  ·  {config.dpi} DPI"
        )
        self._show_figure(figure)
        self.open_button.configure(state="normal")
        self._set_status(f"已生成：{destination}", "success")

    def _handle_plot_error(self, error: Exception) -> None:
        self._set_busy(False)
        self._set_status(f"生成失败：{error}", "error")
        messagebox.showerror("生成失败", str(error), parent=self.root)

    def _show_figure(self, figure: object) -> None:
        if self.figure_canvas is not None:
            self.figure_canvas.get_tk_widget().destroy()
        elif self.placeholder.winfo_exists():
            self.placeholder.destroy()
        if self.figure is not None and self.figure is not figure:
            self.figure.clear()
        self.figure = figure
        self.figure_canvas = FigureCanvasTkAgg(figure, master=self.preview_host)  # type: ignore[arg-type]
        self.figure_canvas.draw()
        widget = self.figure_canvas.get_tk_widget()
        widget.grid(row=0, column=0, sticky="nsew")
        widget.configure(highlightthickness=0)

    def open_results(self) -> None:
        if self.output_path is None:
            return
        try:
            os.startfile(self.output_path.parent)  # type: ignore[attr-defined]
        except OSError as error:
            messagebox.showerror("无法打开文件夹", str(error), parent=self.root)

    def open_data_editor(self) -> None:
        if self.busy:
            return
        if self.report is None or not self.report.series:
            self._set_status("请先选择包含有效 Excel 数据的文件夹。", "error")
            return
        if self.data_editor is not None and self.data_editor.winfo_exists():
            self.data_editor.lift()
            self.data_editor.focus_force()
            return
        self.data_editor = DataEditorWindow(
            self.root,
            self.report,
            self._current_plot_config,
            self._handle_edited_data,
            self._data_editor_closed,
        )

    def _handle_edited_data(self, model: EditableDataModel) -> None:
        if self.report is None:
            return
        self._populate_data_status(self.report)
        self.preview_meta_var.set(f"汇总数据已修改 · 修订 {model.revision} · 主图待重新生成")
        self._set_status(
            f"汇总数据已修改：{model.total_points} 个数据点；右侧工作台预览已实时更新。",
            "success",
        )

    def _data_editor_closed(self) -> None:
        self.data_editor = None

    def open_style_dialog(self) -> None:
        if self.busy:
            return
        PlotStyleDialog(self.root, self.plot_style, self._apply_plot_style)

    def save_current_preset(self) -> None:
        if self.busy:
            return
        validation_error = self._validate_settings_fields()
        if validation_error:
            self._set_status(validation_error, "error")
            self.root.bell()
            return

        name = simpledialog.askstring(
            "保存设置",
            "为这套设置命名：",
            initialvalue=(self.title_var.get().strip() or "无标题图设置")[:80],
            parent=self.root,
        )
        if name is None:
            return
        name = name.strip()
        if not name:
            self._set_status("设置名称不能为空。", "error")
            return

        config = self._current_plot_config()
        try:
            preset = self.preset_store.save_config(name, config)
        except PresetNameConflict:
            overwrite = messagebox.askyesno(
                "覆盖同名设置",
                f"设置方案“{name}”已经存在，是否用当前参数覆盖？",
                parent=self.root,
            )
            if not overwrite:
                return
            try:
                preset = self.preset_store.save_config(name, config, overwrite=True)
            except (PresetStoreError, ValueError) as error:
                self._show_preset_error(error)
                return
        except (PresetStoreError, ValueError) as error:
            self._show_preset_error(error)
            return

        self._set_status(f"设置方案“{preset.name}”已保存，可在下次制图时直接套用。", "success")

    def open_preset_picker(self) -> None:
        if self.busy:
            return
        try:
            presets = self.preset_store.load()
        except PresetStoreError as error:
            self._show_preset_error(error)
            return
        if not presets:
            messagebox.showinfo(
                "暂无设置方案",
                "还没有保存过设置。完成标题和图像参数调整后，点击“保存设置”即可创建。",
                parent=self.root,
            )
            return
        PresetPickerDialog(self.root, presets, self._apply_preset)

    def _apply_preset(self, preset: PlotPreset) -> None:
        config = preset.to_config()
        self.title_var.set(config.title)
        self.x_label_var.set(config.x_label)
        self.y_label_var.set(config.y_label)
        self.plot_type_var.set(config.plot_type)
        self.plot_style = config.style
        self._refresh_style_summary()
        self.preview_meta_var.set(f"已套用“{preset.name}” · 生成后刷新预览")
        self._set_status(
            f"已套用设置方案“{preset.name}”；数据文件夹保持不变，可继续修改或选择新数据。",
            "success",
        )

    def _show_preset_error(self, error: Exception) -> None:
        self._set_status(str(error), "error")
        messagebox.showerror("设置方案错误", str(error), parent=self.root)

    def _apply_plot_style(self, style: PlotStyleConfig) -> None:
        self.plot_style = style
        self._refresh_style_summary()
        self._set_status("图像参数已更新，将在下一次生成时应用。", "neutral")

    def _refresh_style_summary(self) -> None:
        style = self.plot_style
        minor_grid = "次网格开启" if style.show_minor_grid else "次网格关闭"
        title_mode = "含标题" if style.show_title else "无标题"
        color_mode = "彩色" if style.use_color else "黑白"
        self.title_field_label_var.set("图表标题 *" if style.show_title else "图表标题（当前不输出）")
        self.style_summary_var.set(
            f"{style.width_cm:g}×{style.height_cm:g} cm · {style.dpi} DPI · "
            f"{title_mode}/{color_mode} · {len(style.markers)} 种点形 · {minor_grid}"
        )
        self.generate_text_var.set(f"生成并导出 {style.dpi} DPI PNG")

    def _set_busy(self, busy: bool, operation: str | None = None, message: str = "") -> None:
        self.busy = busy
        self.operation = operation if busy else None
        if busy:
            self.progress.start(12)
            self.choose_button.configure(state="disabled")
            self.generate_button.configure(state="disabled")
            self.open_button.configure(state="disabled")
            self.save_preset_button.configure(state="disabled")
            self.apply_preset_button.configure(state="disabled")
            self.data_editor_button.configure(state="disabled")
            self.status_pill.configure(text="  ●  处理中  ", bg="#FFF3D9", fg=self.WARNING)
            self.status_var.set(message)
        else:
            self.progress.stop()
            self.progress.configure(value=0)
            self.choose_button.configure(state="normal")
            self.save_preset_button.configure(state="normal")
            self.apply_preset_button.configure(state="normal")
            if self.report is not None and self.report.series:
                self.data_editor_button.configure(state="normal")
            if self.report is not None and self.report.series:
                self.generate_button.configure(state="normal")
            if self.output_path is not None:
                self.open_button.configure(state="normal")

    def _set_status(self, message: str, kind: str = "neutral") -> None:
        self.status_var.set(message)
        if kind == "success":
            self.status_pill.configure(text="  ●  数据就绪  ", bg=self.ACCENT_SOFT, fg=self.ACCENT)
        elif kind == "error":
            self.status_pill.configure(text="  ●  需要检查  ", bg=self.ERROR_SOFT, fg=self.ERROR)
        else:
            self.status_pill.configure(text="  ●  准备就绪  ", bg=self.ACCENT_SOFT, fg=self.ACCENT)

    def _poll_events(self) -> None:
        try:
            while True:
                event, payload = self.events.get_nowait()
                if event == "load_success":
                    self._handle_load_success(payload)  # type: ignore[arg-type]
                elif event == "load_error":
                    self._handle_load_error(payload)  # type: ignore[arg-type]
                elif event == "plot_success":
                    self._handle_plot_success(payload)
                elif event == "plot_error":
                    self._handle_plot_error(payload)  # type: ignore[arg-type]
        except queue.Empty:
            pass
        if self.root.winfo_exists():
            self.root.after(100, self._poll_events)

    def _on_close(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()


def run_app() -> None:
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError("桌面界面必须在主线程启动")
    root = tk.Tk()
    PlotterApp(root)
    root.mainloop()
