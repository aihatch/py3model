#!/usr/bin/python3
# coding=utf-8

"""
新增/编辑模型弹窗。
"""

import os
import re
import tkinter as tk
from tkinter import filedialog

from .theme import COLORS, N_CTX_PRESETS, default_font, n_ctx_label
from .widgets import RoundedButton, SolidButton


class ModelDialog(tk.Toplevel):
    """新增或编辑模型的模态弹窗。"""

    def __init__(self, parent, title="新增模型", initial=None):
        super().__init__(parent)
        self.transient(parent)
        self.title(title)
        self.configure(bg="#F5F7FA")
        self.resizable(False, False)

        self._result = None
        self._initial = initial or {}
        self._ctx_index = 4  # 默认 32k
        # 初始化 n_ctx 索引
        init_n_ctx = int(self._initial.get("n_ctx") or 8192)
        if init_n_ctx in N_CTX_PRESETS:
            self._ctx_index = N_CTX_PRESETS.index(init_n_ctx)
        else:
            # 取最接近的预设
            best = 0
            best_diff = abs(N_CTX_PRESETS[0] - init_n_ctx)
            for i, v in enumerate(N_CTX_PRESETS):
                d = abs(v - init_n_ctx)
                if d < best_diff:
                    best = i
                    best_diff = d
            self._ctx_index = best

        self._build_ui()

        self.update_idletasks()
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()
        # 居中
        master = parent
        px = master.winfo_rootx()
        py = master.winfo_rooty()
        pw = master.winfo_width()
        ph = master.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        self.grab_set()
        self.focus_force()

    def _build_ui(self):
        outer = tk.Frame(self, bg="#F5F7FA", padx=16, pady=16)
        outer.pack(fill=tk.BOTH, expand=True)

        # 标题
        tk.Label(
            outer, text="模型信息",
            font=default_font(15, bold=True), bg="#F5F7FA", fg=COLORS["text"],
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        # 模型名
        tk.Label(outer, text="模型名", font=default_font(11),
                 bg="#F5F7FA", fg=COLORS["text_secondary"]).grid(
            row=1, column=0, sticky="w", pady=8
        )
        self.name_var = tk.StringVar(value=self._initial.get("name", ""))
        name_entry = tk.Entry(
            outer, textvariable=self.name_var,
            font=default_font(11), width=36,
            relief=tk.FLAT, bg="white",
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent"],
        )
        name_entry.grid(row=1, column=1, columnspan=2, sticky="we", pady=8, padx=(10, 0))

        # GGUF 文件路径
        tk.Label(outer, text="GGUF 文件", font=default_font(11),
                 bg="#F5F7FA", fg=COLORS["text_secondary"]).grid(
            row=2, column=0, sticky="w", pady=8
        )
        path_frame = tk.Frame(outer, bg="#F5F7FA")
        path_frame.grid(row=2, column=1, sticky="we", pady=8, padx=(10, 0))
        self.path_var = tk.StringVar(value=self._initial.get("path", ""))
        path_entry = tk.Entry(
            path_frame, textvariable=self.path_var,
            font=default_font(11), width=30,
            relief=tk.FLAT, bg="white",
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent"],
        )
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        RoundedButton(
            path_frame, text="选择…",
            command=self._on_choose_file,
            height=28, pad_x=12,
        ).pack(side=tk.LEFT, padx=(8, 0))

        # 上下文（n_ctx）选择 - 离散档位胶囊
        tk.Label(outer, text="上下文", font=default_font(11),
                 bg="#F5F7FA", fg=COLORS["text_secondary"]).grid(
            row=3, column=0, sticky="nw", pady=(12, 8)
        )
        ctx_frame = tk.Frame(outer, bg="#F5F7FA")
        ctx_frame.grid(row=3, column=1, columnspan=2, sticky="w", pady=(12, 8), padx=(10, 0))

        self._ctx_buttons = []
        for i, v in enumerate(N_CTX_PRESETS):
            btn = tk.Label(
                ctx_frame, text=n_ctx_label(v),
                font=default_font(10),
                bg="white", fg=COLORS["text"],
                padx=10, pady=4, cursor="hand2",
                relief=tk.FLAT,
            )
            btn.pack(side=tk.LEFT, padx=(0, 6))
            btn.bind("<Button-1>", lambda _e, idx=i: self._select_ctx(idx))
            self._ctx_buttons.append(btn)

        outer.columnconfigure(1, weight=1)
        self._select_ctx(self._ctx_index)

        # 错误提示
        self._err_var = tk.StringVar(value="")
        tk.Label(
            outer, textvariable=self._err_var,
            font=default_font(10),
            bg="#F5F7FA", fg=COLORS["danger"],
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(6, 0))

        # 底部按钮
        btn_bar = tk.Frame(outer, bg="#F5F7FA")
        btn_bar.grid(row=5, column=0, columnspan=3, sticky="e", pady=(16, 0))
        RoundedButton(
            btn_bar, text="取消", command=self._on_cancel,
            height=32, pad_x=16,
        ).pack(side=tk.RIGHT, padx=(8, 0))
        SolidButton(
            btn_bar, text="确定", command=self._on_submit,
            height=32, pad_x=20, bg=COLORS["accent"], hover_bg=COLORS["accent_dark"],
        ).pack(side=tk.RIGHT)

    def _select_ctx(self, idx):
        self._ctx_index = idx
        for i, btn in enumerate(self._ctx_buttons):
            if i == idx:
                btn.config(bg=COLORS["text"], fg="white")
            else:
                btn.config(bg="white", fg=COLORS["text"])

    def _on_choose_file(self):
        path = filedialog.askopenfilename(
            title="选择 GGUF 文件",
            filetypes=[("GGUF 模型", "*.gguf"), ("所有文件", "*.*")],
            parent=self,
        )
        if not path:
            return
        self.path_var.set(path)
        # 若模型名为空，自动用文件名（去后缀）填充
        if not self.name_var.get().strip():
            base = os.path.basename(path)
            base = re.sub(r"\.gguf$", "", base, flags=re.IGNORECASE)
            self.name_var.set(base)

    def _on_submit(self):
        name = self.name_var.get().strip()
        path = self.path_var.get().strip()
        if not name:
            self._err_var.set("请填写模型名")
            return
        if not path:
            self._err_var.set("请选择 GGUF 文件")
            return
        if not os.path.exists(path):
            self._err_var.set("文件不存在，请重新选择")
            return
        n_ctx = N_CTX_PRESETS[self._ctx_index]
        self._result = {"name": name, "path": path, "n_ctx": n_ctx}
        self.destroy()

    def _on_cancel(self):
        self._result = None
        self.destroy()

    def show(self):
        self.wait_window()
        return self._result
