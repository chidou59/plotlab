from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from .preset_store import PlotPreset


class PresetPickerDialog(tk.Toplevel):
    """Choose and inspect a saved plot preset before applying it."""

    BG = "#EEF1EE"
    SURFACE = "#FFFFFF"
    INK = "#14231F"
    MUTED = "#66736E"
    BORDER = "#D8DFDA"
    ACCENT = "#1C6654"

    def __init__(
        self,
        parent: tk.Misc,
        presets: list[PlotPreset],
        on_apply: Callable[[PlotPreset], None],
    ) -> None:
        super().__init__(parent)
        self.title("套用设置 · PlotLab")
        self.configure(bg=self.BG)
        self.geometry("760x510")
        self.minsize(680, 450)
        self.transient(parent)
        self.presets = presets
        self.on_apply = on_apply
        self.detail_var = tk.StringVar(value="选择一套设置查看详情")
        self.title_detail_var = tk.StringVar()
        self.axis_detail_var = tk.StringVar()

        self._build()
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Return>", lambda _event: self._apply_selected())
        self.grab_set()
        self.update_idletasks()
        self._center_on_parent(parent)
        self.tree.focus_set()

    def _build(self) -> None:
        header = tk.Frame(self, bg=self.BG, padx=24, pady=18)
        header.pack(fill="x")
        tk.Label(
            header,
            text="套用一套设置",
            bg=self.BG,
            fg=self.INK,
            font=("Microsoft YaHei UI", 17, "bold"),
        ).pack(anchor="w")
        tk.Label(
            header,
            text="只套用标题、坐标轴、图型和图像参数；当前数据文件夹不会被改变。",
            bg=self.BG,
            fg=self.MUTED,
            font=("Microsoft YaHei UI", 9),
        ).pack(anchor="w", pady=(4, 0))

        body = tk.Frame(
            self,
            bg=self.SURFACE,
            padx=18,
            pady=18,
            highlightthickness=1,
            highlightbackground=self.BORDER,
        )
        body.pack(fill="both", expand=True, padx=24)
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        tree_frame = tk.Frame(body, bg=self.BORDER)
        tree_frame.grid(row=0, column=0, sticky="nsew")
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            tree_frame,
            columns=("name", "type", "size", "time"),
            show="headings",
            style="Data.Treeview",
            selectmode="browse",
        )
        headings = {
            "name": "设置名称",
            "type": "图型",
            "size": "图像尺寸",
            "time": "最近保存",
        }
        for key, label in headings.items():
            self.tree.heading(key, text=label)
        self.tree.column("name", width=220, minwidth=140, stretch=True)
        self.tree.column("type", width=70, minwidth=60, anchor="center", stretch=False)
        self.tree.column("size", width=130, minwidth=110, anchor="center", stretch=False)
        self.tree.column("time", width=135, minwidth=120, anchor="center", stretch=False)
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        for index, preset in enumerate(self.presets):
            timestamp = preset.updated_at.replace("T", " ")[:16]
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    preset.name,
                    "点图" if preset.plot_type == "scatter" else "折线图",
                    f"{preset.style.width_cm:g} × {preset.style.height_cm:g} cm",
                    timestamp,
                ),
            )
        self.tree.bind("<<TreeviewSelect>>", self._show_selected_details)
        self.tree.bind("<Double-1>", lambda _event: self._apply_selected())

        detail = tk.Frame(body, bg="#F6F8F6", padx=14, pady=10)
        detail.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        tk.Label(
            detail,
            textvariable=self.detail_var,
            bg="#F6F8F6",
            fg=self.ACCENT,
            font=("Microsoft YaHei UI", 9, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            detail,
            textvariable=self.title_detail_var,
            bg="#F6F8F6",
            fg=self.INK,
            font=("Microsoft YaHei UI", 9),
            anchor="w",
        ).pack(fill="x", pady=(4, 0))
        tk.Label(
            detail,
            textvariable=self.axis_detail_var,
            bg="#F6F8F6",
            fg=self.MUTED,
            font=("Microsoft YaHei UI", 8),
            anchor="w",
        ).pack(fill="x", pady=(3, 0))

        actions = tk.Frame(self, bg=self.BG, padx=24, pady=16)
        actions.pack(fill="x")
        ttk.Button(
            actions,
            text="取消",
            style="Quiet.TButton",
            command=self.destroy,
        ).pack(side="right")
        self.apply_button = ttk.Button(
            actions,
            text="套用所选设置",
            style="Accent.TButton",
            command=self._apply_selected,
            state="disabled",
        )
        self.apply_button.pack(side="right", padx=(0, 9))

        if self.presets:
            first = self.tree.get_children()[0]
            self.tree.selection_set(first)
            self.tree.focus(first)
            self._show_selected_details()

    def _selected_preset(self) -> PlotPreset | None:
        selection = self.tree.selection()
        if not selection:
            return None
        return self.presets[int(selection[0])]

    def _show_selected_details(self, _event: object | None = None) -> None:
        preset = self._selected_preset()
        if preset is None:
            self.apply_button.configure(state="disabled")
            return
        style = preset.style
        self.detail_var.set(
            f"{preset.name}  ·  {style.dpi} DPI  ·  "
            f"{'含标题' if style.show_title else '无标题'} / {'彩色' if style.use_color else '黑白'}  ·  "
            f"{len(style.markers)} 种点形"
        )
        self.title_detail_var.set(
            f"标题：{preset.title if style.show_title else '（不输出标题）'}"
        )
        self.axis_detail_var.set(f"X：{preset.x_label}    Y：{preset.y_label}")
        self.apply_button.configure(state="normal")

    def _apply_selected(self) -> None:
        preset = self._selected_preset()
        if preset is None:
            self.bell()
            return
        self.on_apply(preset)
        self.destroy()

    def _center_on_parent(self, parent: tk.Misc) -> None:
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        width = self.winfo_width()
        height = self.winfo_height()
        x = max(0, parent_x + (parent_width - width) // 2)
        y = max(0, parent_y + (parent_height - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
