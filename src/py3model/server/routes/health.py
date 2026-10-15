#!/usr/bin/python3
# coding=utf-8

"""
GET /health
返回服务健康状态和模型加载状态。
"""

import json
from http.server import BaseHTTPRequestHandler

from ...gguf import is_loaded, get_current, get_current_list


def register(router):
    """注册到路由器。"""

    def handle(_handler: BaseHTTPRequestHandler):
        loaded = get_current_list()
        payload = {
            "status": "ok",
            "model_loaded": is_loaded(),
            "model": get_current(),  # 兼容旧字段：第一个已加载
            "models": loaded,         # 新字段：全部已加载
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return 200, body, "application/json; charset=utf-8"

    router.add("GET", "/health", handle)
