#!/usr/bin/python3
# coding=utf-8

"""
模型与服务管理页面：服务配置 + 模型列表。
"""

import json
import threading
import tkinter as tk
from tkinter import messagebox
from urllib import error as _urllib_error
from urllib import request as _urllib_request

from .. import pages as _pages  # noqa: F401  # 确保父包已初始化
from ...config import load as cfg_load, update as cfg_update, replace as cfg_replace
from ...server import start as server_start, stop as server_stop, is_running as server_is_running
from ..models_dialog import ModelDialog
from ..theme import COLORS, default_font, n_ctx_label
from ..widgets import RoundedButton, SolidButton, draw_round_rect


class ManagePage(tk.Frame):
    """管理页：服务配置 + 模型列表。"""

    def __init__(self, parent, root):
        super().__init__(parent, bg=COLORS["bg_content"])
        self.root = root

        # 加载/卸载中按 model_name 标记，避免重复点击
        self._busy_models = set()

        # 主体两段卡片（直接铺满，不再单独大标题）
        body = tk.Frame(self, bg=COLORS["bg_content"])
        body.pack(fill=tk.BOTH, expand=True, padx=18, pady=18)

        self._build_server_card(body)
        self._build_models_card(body)

        # 首次刷新
        self._refresh_server_status()
        self._refresh_models()

    # ------------------ 服务配置卡片 ------------------
    def _build_server_card(self, parent):
        card_holder = tk.Frame(parent, bg=COLORS["bg_content"])
        card_holder.pack(fill=tk.X)

        canvas = tk.Canvas(card_holder, bg=COLORS["bg_content"], highlightthickness=0, height=170)
        canvas.pack(fill=tk.X)

        inner = tk.Frame(canvas, bg="white")

        # 标题
        tk.Label(
            inner, text="HTTP 服务",
            font=default_font(14, bold=True), bg="white", fg=COLORS["text"],
        ).grid(row=0, column=0, columnspan=5, sticky="w", padx=20, pady=(16, 12))

        # 占位：保留 status_pill 属性以兼容旧版刷新逻辑（但不再显示）。
        self.status_pill = None

        # host
        tk.Label(inner, text="监听地址", font=default_font(11),
                 bg="white", fg=COLORS["text_secondary"]).grid(
            row=1, column=0, sticky="w", padx=(20, 0), pady=6)
        self.host_var = tk.StringVar()
        self.host_entry = tk.Entry(
            inner, textvariable=self.host_var,
            font=default_font(11), width=20, relief=tk.FLAT,
            bg="#F7F7F7", highlightthickness=1,
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent"],
        )
        self.host_entry.grid(row=1, column=1, sticky="w", padx=10, pady=6)

        # port
        tk.Label(inner, text="监听端口", font=default_font(11),
                 bg="white", fg=COLORS["text_secondary"]).grid(
            row=1, column=2, sticky="w", padx=(20, 0), pady=6)
        self.port_var = tk.StringVar()
        self.port_entry = tk.Entry(
            inner, textvariable=self.port_var,
            font=default_font(11), width=10, relief=tk.FLAT,
            bg="#F7F7F7", highlightthickness=1,
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent"],
        )
        self.port_entry.grid(row=1, column=3, sticky="w", padx=10, pady=6)

        # 状态文字
        self.server_status_var = tk.StringVar(value="")
        tk.Label(
            inner, textvariable=self.server_status_var,
            font=default_font(10), bg="white", fg=COLORS["text_secondary"],
        ).grid(row=2, column=0, columnspan=4, sticky="w", padx=20, pady=(4, 0))

        # 启动/停止按钮
        self.toggle_btn = SolidButton(
            inner, text="启动服务", command=self._on_toggle_server,
            height=36, pad_x=22, bg=COLORS["accent"], hover_bg=COLORS["accent_dark"],
        )
        self.toggle_btn.grid(row=1, column=4, sticky="e", padx=(20, 20), pady=6)

        inner.columnconfigure(5, weight=1)

        # 加载默认配置
        cfg = cfg_load()
        self.host_var.set(cfg.get("server", {}).get("host", "127.0.0.1"))
        self.port_var.set(str(cfg.get("server", {}).get("port", 11435)))

        window = canvas.create_window(0, 0, window=inner, anchor="nw")

        def on_resize(event):
            canvas.delete("bg")
            draw_round_rect(
                canvas,
                0, 0, event.width, event.height,
                radius=12, fill="white", outline="",
                tags="bg",
            )
            canvas.tag_lower("bg")
            canvas.coords(window, 0, 0)
            canvas.itemconfigure(window, width=event.width)

        canvas.bind("<Configure>", on_resize)

    # ------------------ 模型列表卡片 ------------------
    def _build_models_card(self, parent):
        card_holder = tk.Frame(parent, bg=COLORS["bg_content"])
        card_holder.pack(fill=tk.BOTH, expand=True, pady=(14, 0))

        canvas = tk.Canvas(card_holder, bg=COLORS["bg_content"], highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)

        inner = tk.Frame(canvas, bg="white")

        # 标题行 + 新增按钮
        title_bar = tk.Frame(inner, bg="white")
        title_bar.grid(row=0, column=0, columnspan=5, sticky="we", padx=20, pady=(16, 12))
        tk.Label(
            title_bar, text="模型列表",
            font=default_font(14, bold=True), bg="white", fg=COLORS["text"],
        ).pack(side=tk.LEFT)
        RoundedButton(
            title_bar, text="新增模型", command=self._on_add_model,
            height=32, pad_x=16,
        ).pack(side=tk.RIGHT)

        # 表头
        header_row = tk.Frame(inner, bg="#FAFAFA", height=34)
        header_row.grid(row=1, column=0, columnspan=5, sticky="we", padx=20)
        header_row.pack_propagate(False)
        for txt, w, anchor in [
            ("模型名", 140, "w"),
            ("GGUF 路径", 320, "w"),
            ("上下文", 80, "w"),
            ("状态", 80, "w"),
            ("操作", 180, "e"),
        ]:
            # 显式用字面量转 anchor，避免 Pylance 把循环变量推断成 str
            if anchor == "e":
                tk.Label(
                    header_row, text=txt,
                    font=default_font(10), bg="#FAFAFA", fg=COLORS["text_secondary"],
                    width=w, anchor="e",
                ).pack(side=tk.LEFT, padx=6)
            else:
                tk.Label(
                    header_row, text=txt,
                    font=default_font(10), bg="#FAFAFA", fg=COLORS["text_secondary"],
                    width=w, anchor="w",
                ).pack(side=tk.LEFT, padx=6)

        self.list_container = tk.Frame(inner, bg="white")
        self.list_container.grid(row=2, column=0, columnspan=5, sticky="nsew", padx=20, pady=(0, 16))
        inner.rowconfigure(2, weight=1)
        inner.columnconfigure(0, weight=1)

        window = canvas.create_window(0, 0, window=inner, anchor="nw")

        def on_resize(event):
            canvas.delete("bg")
            draw_round_rect(
                canvas, 0, 0, event.width, event.height,
                radius=12, fill="white", outline="",
                tags="bg",
            )
            canvas.tag_lower("bg")
            canvas.coords(window, 0, 0)
            canvas.itemconfigure(window, width=event.width)
            canvas.config(height=event.height)
            inner.update_idletasks()
            canvas.config(scrollregion=canvas.bbox("all"))

        canvas.bind("<Configure>", on_resize)
        self._models_canvas = canvas

    # ------------------ 服务启停 ------------------
    def _on_toggle_server(self):
        if server_is_running():
            server_stop()
            self._refresh_server_status()
            self._refresh_models()
            return

        host = self.host_var.get().strip() or "127.0.0.1"
        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            self.server_status_var.set("端口必须是数字")
            return

        # 持久化
        cfg_update(server={"host": host, "port": port})

        thread, server = server_start(host, port)
        if server is None:
            self.server_status_var.set(f"启动失败：{host}:{port} 可能已被占用")
        else:
            self._refresh_server_status()

    def _refresh_server_status(self):
        if server_is_running():
            cfg = cfg_load()
            host = cfg.get("server", {}).get("host", "")
            port = cfg.get("server", {}).get("port", "")
            self.server_status_var.set(f"OpenAI 兼容 base_url：http://{host}:{port}/v1")
            self._set_toggle_button("停止服务", bg=COLORS["danger"], hover_bg="#D9363E")
        else:
            self.server_status_var.set("点「启动服务」开始监听 OpenAI 兼容接口")
            self._set_toggle_button("启动服务", bg=COLORS["accent"], hover_bg=COLORS["accent_dark"])

    def _set_toggle_button(self, text, bg, hover_bg):
        # 直接重建按钮
        try:
            self.toggle_btn.destroy()
        except Exception:
            pass
        self.toggle_btn = SolidButton(
            self.toggle_btn.master, text=text, command=self._on_toggle_server,
            height=36, pad_x=22, bg=bg, hover_bg=hover_bg,
        )
        self.toggle_btn.grid(row=1, column=4, sticky="e", padx=(20, 20), pady=6)

    # ------------------ 模型列表 ------------------
    def _refresh_models(self):
        # 清空
        for w in self.list_container.winfo_children():
            w.destroy()

        cfg = cfg_load()
        models = cfg.get("models", {}) or {}
        # 取已加载模型集合（多模型共存）
        loaded_set = self._fetch_loaded_models()

        if not models:
            tk.Label(
                self.list_container, text="暂无模型，点右上角「新增模型」开始",
                font=default_font(11), bg="white", fg=COLORS["text_muted"],
            ).pack(pady=24)
            return

        for i, name in enumerate(models.keys()):
            info = models[name] or {}
            row = tk.Frame(self.list_container, bg=("white" if i % 2 == 0 else "#FAFAFA"), height=44)
            row.pack(fill=tk.X)
            row.pack_propagate(False)

            tk.Label(
                row, text=name, font=default_font(11),
                bg=row.cget("bg"), fg=COLORS["text"],
                width=16, anchor="w",
            ).pack(side=tk.LEFT, padx=(12, 6))

            path = info.get("path", "")
            tk.Label(
                row, text=path, font=default_font(10),
                bg=row.cget("bg"), fg=COLORS["text_secondary"],
                width=42, anchor="w",
            ).pack(side=tk.LEFT, padx=6)

            n_ctx = int(info.get("n_ctx") or 0)
            tk.Label(
                row, text=n_ctx_label(n_ctx) if n_ctx else "auto",
                font=default_font(11),
                bg=row.cget("bg"), fg=COLORS["text"],
                width=8, anchor="w",
            ).pack(side=tk.LEFT, padx=6)

            is_loaded = name in loaded_set
            status_text = "已加载" if is_loaded else (
                "未加载" if not server_is_running() or not loaded_set else "未加载"
            )
            status_fg = COLORS["success"] if is_loaded else COLORS["text_muted"]
            tk.Label(
                row, text=status_text, font=default_font(11),
                bg=row.cget("bg"), fg=status_fg,
                width=8, anchor="w",
            ).pack(side=tk.LEFT, padx=6)

            ops = tk.Frame(row, bg=row.cget("bg"))
            ops.pack(side=tk.RIGHT, padx=(6, 12))

            edit_btn = RoundedButton(
                ops, text="编辑", height=26, pad_x=10,
                command=lambda n=name: self._on_edit_model(n),
            )
            edit_btn.pack(side=tk.LEFT, padx=2)

            delete_btn = RoundedButton(
                ops, text="删除", height=26, pad_x=10,
                command=lambda n=name: self._on_delete_model(n),
            )
            delete_btn.pack(side=tk.LEFT, padx=2)

            if server_is_running():
                if is_loaded:
                    load_btn = RoundedButton(
                        ops, text="卸载", height=26, pad_x=10,
                        border="#D9D9D9", fg=COLORS["danger"],
                        command=lambda n=name: self._on_unload(n),
                    )
                    load_btn.pack(side=tk.LEFT, padx=2)
                else:
                    disabled = name in self._busy_models
                    load_btn = RoundedButton(
                        ops, text=("加载中…" if disabled else "加载"),
                        height=26, pad_x=10,
                        command=lambda n=name: self._on_load(n),
                    )
                    if disabled:
                        load_btn.unbind("<Button-1>")
                        load_btn.config(cursor="arrow")
                    load_btn.pack(side=tk.LEFT, padx=2)
            else:
                tk.Label(
                    ops, text="(服务未启动)", font=default_font(9),
                    bg=row.cget("bg"), fg=COLORS["text_muted"],
                ).pack(side=tk.LEFT, padx=6)

    def _fetch_loaded_models(self):
        """通过 /health 拿到当前所有已加载的模型名集合。"""
        if not server_is_running():
            return set()
        try:
            cfg = cfg_load()
            host = cfg.get("server", {}).get("host", "127.0.0.1")
            port = cfg.get("server", {}).get("port", 11435)
            with _urllib_request.urlopen(f"http://{host}:{port}/health", timeout=1.0) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            names = payload.get("models") or []
            return set(names) if isinstance(names, list) else set()
        except (_urllib_error.URLError, OSError, ValueError):
            return set()

    # ------------------ 模型增删改 ------------------
    def _on_add_model(self):
        dlg = ModelDialog(self.root, title="新增模型")
        result = dlg.show()
        if not result:
            return
        cfg = cfg_load()
        # 重名处理
        name = result["name"]
        original = name
        suffix = 1
        while name in cfg["models"]:
            suffix += 1
            name = f"{original}-{suffix}"
        cfg["models"][name] = {"path": result["path"], "n_ctx": result["n_ctx"]}
        cfg_update(models=cfg["models"])
        self._refresh_models()

    def _on_edit_model(self, model_name):
        cfg = cfg_load()
        info = cfg["models"].get(model_name, {})
        dlg = ModelDialog(
            self.root, title=f"编辑模型 - {model_name}",
            initial={"name": model_name, "path": info.get("path", ""), "n_ctx": info.get("n_ctx", 8192)},
        )
        result = dlg.show()
        if not result:
            return
        new_name = result["name"]
        # 处理改名后与其它模型重名
        target_name = new_name
        if new_name != model_name and new_name in cfg["models"]:
            original = new_name
            suffix = 1
            while target_name in cfg["models"]:
                suffix += 1
                target_name = f"{original}-{suffix}"
        del cfg["models"][model_name]
        cfg["models"][target_name] = {"path": result["path"], "n_ctx": result["n_ctx"]}
        # 用 replace：整段覆盖 models，保证旧 model_name 被真正删掉
        cfg_replace(models=cfg["models"])
        self._refresh_models()

    def _on_delete_model(self, model_name):
        if not messagebox.askyesno("确认删除", f"确定删除模型「{model_name}」？", parent=self.root):
            return
        # 如已加载则先按 name 卸载（多模型共存下不能一键卸全部）
        if model_name in self._fetch_loaded_models():
            try:
                self._unload_remote(model_name)
            except Exception:
                pass
        cfg = cfg_load()
        if model_name in cfg["models"]:
            del cfg["models"][model_name]
        # 用 replace：整段覆盖 models，保证旧 model_name 被真正从磁盘删掉
        cfg_replace(models=cfg["models"])
        self._refresh_models()

    def _on_load(self, model_name):
        if not server_is_running():
            messagebox.showwarning("无法加载", "请先启动 HTTP 服务", parent=self.root)
            return
        cfg = cfg_load()
        info = cfg["models"].get(model_name)
        if not info:
            return
        # 先把 gguf 路径转交给服务端去加载（走 /v1/internal/load）
        self._busy_models.add(model_name)
        self._refresh_models()

        def worker():
            try:
                self._load_remote(model_name, info["path"], int(info.get("n_ctx") or 0))
            except Exception as e:
                err = str(e)
                self.root.after(
                    0,
                    lambda err=err: messagebox.showerror("加载失败", err, parent=self.root),
                )
            finally:
                self._busy_models.discard(model_name)
                self.root.after(0, self._refresh_models)

        threading.Thread(target=worker, daemon=True).start()

    def _on_unload(self, model_name):
        try:
            self._unload_remote(model_name)
        except Exception as e:
            messagebox.showerror("卸载失败", str(e), parent=self.root)
            return
        self._refresh_models()

    def _server_endpoint(self):
        cfg = cfg_load()
        host = cfg.get("server", {}).get("host", "127.0.0.1")
        port = cfg.get("server", {}).get("port", 11435)
        return host, port

    def _post_json(self, path, payload):
        host, port = self._server_endpoint()
        req = _urllib_request.Request(
            f"http://{host}:{port}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with _urllib_request.urlopen(req, timeout=300) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except _urllib_error.HTTPError as e:
            # 把服务端真实错误包成 RuntimeError 抛出，便于调用方捕获并展示。
            try:
                detail = e.read().decode("utf-8", errors="replace")
            except Exception:
                detail = ""
            raise RuntimeError(f"HTTP {e.code}: {detail}") from None

    def _load_remote(self, model_name, path, n_ctx):
        self._post_json("/v1/internal/load", {
            "model_name": model_name,
            "path": path,
            "n_ctx": n_ctx,
        })

    def _unload_remote(self, model_name):
        # 多模型共存：按 name 卸载；若 model_name 为空则请求服务端卸载全部。
        self._post_json("/v1/internal/unload", {"model_name": model_name} if model_name else {})
