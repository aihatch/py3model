#!/usr/bin/python3
# coding=utf-8

"""
可复用的界面组件。
"""

import tkinter as tk
import tkinter.font as tkfont


def draw_round_rect(canvas, x1, y1, x2, y2, radius=12, **kwargs):
    """在 Canvas 上绘制圆角矩形。"""
    points = (
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1,
    )
    return canvas.create_polygon(points, smooth=True, **kwargs)


class RoundedButton(tk.Canvas):
    """圆角边框按钮：白底 + 浅灰圆角边框。"""

    def __init__(
        self,
        parent,
        text,
        command=None,
        height=36,
        bg="#FFFFFF",
        fg="#333333",
        border="#D0D0D0",
        hover_bg="#F7F7F7",
        font=None,
        radius=8,
        pad_x=16,
        active_bg=None,
        active_fg=None,
    ):
        if font is None:
            from .theme import default_font
            font = default_font(size=11)

        f = tkfont.Font(font=font)
        text_w = f.measure(text)
        width = max(text_w + pad_x * 2, 60)

        super().__init__(
            parent,
            width=width,
            height=height,
            bg=parent.cget("bg"),
            highlightthickness=0,
            cursor="hand2",
        )
        self.command = command
        self._bg = bg
        self._fg = fg
        self._border = border
        self._hover_bg = hover_bg
        self._active_bg = active_bg or bg
        self._active_fg = active_fg or fg
        self.text = text
        self.font = font
        self.radius = radius
        self._hover = False

        self._draw(self._bg)
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _draw(self, fill):
        self.delete("all")
        w = int(self.cget("width"))
        h = int(self.cget("height"))
        draw_round_rect(
            self,
            1, 1,
            w - 2, h - 2,
            radius=self.radius,
            fill=fill,
            outline=self._border,
            width=1,
        )
        self.create_text(
            w // 2, h // 2,
            text=self.text,
            fill=self._fg,
            font=self.font,
            anchor="center",
        )

    def _on_click(self, _event):
        if self.command:
            self.command()

    def _on_enter(self, _event):
        self._hover = True
        self._draw(self._hover_bg)

    def _on_leave(self, _event):
        self._hover = False
        self._draw(self._bg)


class SolidButton(tk.Canvas):
    """实色按钮（深色背景 + 白字），用于主操作如发送、启动。"""

    def __init__(
        self,
        parent,
        text,
        command=None,
        height=36,
        bg="#1A1A1A",
        fg="#FFFFFF",
        hover_bg="#333333",
        font=None,
        radius=18,
        pad_x=20,
    ):
        if font is None:
            from .theme import default_font
            font = default_font(size=11)

        f = tkfont.Font(font=font)
        text_w = f.measure(text)
        width = max(text_w + pad_x * 2, 60)

        super().__init__(
            parent,
            width=width,
            height=height,
            bg=parent.cget("bg"),
            highlightthickness=0,
            cursor="hand2",
        )
        self.command = command
        self._bg = bg
        self._fg = fg
        self._hover_bg = hover_bg
        self.text = text
        self.font = font
        self.radius = radius

        self._draw(self._bg)
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _draw(self, fill):
        self.delete("all")
        w = int(self.cget("width"))
        h = int(self.cget("height"))
        draw_round_rect(
            self,
            1, 1, w - 2, h - 2,
            radius=self.radius,
            fill=fill,
            outline="",
            width=0,
        )
        self.create_text(
            w // 2, h // 2,
            text=self.text,
            fill=self._fg,
            font=self.font,
            anchor="center",
        )

    def _on_click(self, _event):
        if self.command:
            self.command()

    def _on_enter(self, _event):
        self._draw(self._hover_bg)

    def _on_leave(self, _event):
        self._draw(self._bg)

    def set_text(self, text):
        self.text = text
        self._draw(self._bg)


class RoundedCard(tk.Canvas):
    """带白色填充与圆角边框的容器。子组件通过 create_window 放入。"""

    def __init__(self, parent, radius=12, **kwargs):
        super().__init__(
            parent,
            bg=parent.cget("bg"),
            highlightthickness=0,
            **kwargs,
        )
        self.radius = radius
        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, event):
        self.delete("bg")
        draw_round_rect(
            self,
            0, 0,
            event.width, event.height,
            radius=self.radius,
            fill="#FFFFFF",
            outline="",
            tags="bg",
        )
        self.tag_lower("bg")

    def add_window(self, x, y, widget, anchor="nw", **kwargs):
        return self.create_window(x, y, window=widget, anchor=anchor, **kwargs)
