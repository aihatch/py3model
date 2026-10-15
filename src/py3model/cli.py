#!/usr/bin/python3
# coding=utf-8

"""
py3model 命令行入口：直接弹出可视化窗口。
"""

import sys


def main() -> int:
    try:
        from .gui import main as gui_main
    except ImportError as e:
        print(f"[py3model] 启动可视化界面失败：{e}", file=sys.stderr)
        return 1

    gui_main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
