#!/usr/bin/python3
# coding=utf-8

"""
界面配色与尺寸常量。
"""

COLORS = {
    "bg_nav": "#F5F5F5",
    "bg_content": "#F5F5F5",
    "bg_card": "#FFFFFF",
    "text": "#333333",
    "text_secondary": "#666666",
    "text_muted": "#999999",
    "border": "#E5E5E5",
    "nav_border": "#E5E5E5",
    "nav_active_bg": "#2c2d32",
    "nav_active_text": "#FFFFFF",
    "accent": "#1890FF",
    "accent_dark": "#0F6FCF",
    "success": "#52C41A",
    "danger": "#FF4D4F",
    "user_bubble": "#E8E8E8",
    "user_text": "#1A1A1A",
    "send_btn_bg": "#1A1A1A",
}

# 导航卡片内边距与功能项尺寸
NAV_PAD = 12
NAV_ITEM_HEIGHT = 40
NAV_ITEM_GAP = 4

# 上下文窗口 n_ctx 离散档位（与截图 2 一致）
N_CTX_PRESETS = [4096, 8192, 16384, 32768, 65536, 131072, 262144]


def n_ctx_label(value: int) -> str:
    """把 n_ctx 值格式化为人类友好的字符串。"""
    if value <= 0:
        return "auto"
    if value >= 1024 and value % 1024 == 0:
        k = value // 1024
        return f"{k}k"
    return str(value)


def is_mac() -> bool:
    import platform
    return platform.system() == "Darwin"


def default_font(size: int = 10, bold: bool = False):
    """统一字体：macOS 用 PingFang SC，其它平台 fallback 到 Tk 默认。"""
    family = "PingFang SC" if is_mac() else "TkDefaultFont"
    import tkinter.font as tkfont
    return tkfont.Font(family=family, size=size, weight=("bold" if bold else "normal"))
