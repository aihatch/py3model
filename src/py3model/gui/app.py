#!/usr/bin/python3
# coding=utf-8

"""
py3model 可视化应用主窗口（仅管理界面，无左侧导航、无顶部标题）。
"""

import tkinter as tk

from .pages.manage_page import ManagePage
from .theme import COLORS


class Py3ModelApp:
    """py3model 可视化应用主窗口。"""

    def __init__(self, root):
        self.root = root
        self.root.title("py3model")
        self.root.geometry("1100x700")
        self.root.minsize(960, 600)

        self.current_page = None
        self.pages = {}

        self._build_ui()
        self.show_page("manage")
        # 启动定时器：定期刷新管理页与服务提示
        self._start_status_polling()

    def _build_ui(self):
        self.root.configure(bg=COLORS["bg_content"])

        # 内容区直接占满全窗口
        content_frame = tk.Frame(self.root, bg=COLORS["bg_content"])
        content_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.pages["manage"] = ManagePage(content_frame, self.root)

    def show_page(self, page_id):
        for pid, page in self.pages.items():
            if pid == page_id:
                page.pack(fill=tk.BOTH, expand=True)
            else:
                page.pack_forget()
        self.current_page = page_id

    def _start_status_polling(self):
        """每 2 秒检查一次服务端状态，刷新管理页与服务提示。"""

        def tick():
            try:
                manage = self.pages.get("manage")
                if manage is not None and self.current_page == "manage":
                    manage._refresh_server_status()
                    manage._refresh_models()
            except Exception:
                pass
            self.root.after(2000, tick)

        self.root.after(2000, tick)

    def on_close(self):
        """退出前清理：停服务 + 卸载模型。"""
        try:
            from ..server import stop as server_stop
            from ..gguf import unload as gguf_unload
            server_stop()
            gguf_unload()
        except Exception:
            pass


def main():
    root = tk.Tk()
    app = Py3ModelApp(root)

    # 居中
    root.update_idletasks()
    w = root.winfo_width()
    h = root.winfo_height()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    x = (sw - w) // 2
    y = (sh - h) // 2
    root.geometry(f"{w}x{h}+{x}+{y}")

    root.protocol("WM_DELETE_WINDOW", lambda: (app.on_close(), root.destroy()))
    root.mainloop()


if __name__ == "__main__":
    main()
