#!/usr/bin/python3
# coding=utf-8

"""
GET /v1/models
返回当前已加载的模型列表，OpenAI 兼容。
"""

import json
import time
from http.server import BaseHTTPRequestHandler

from ...gguf import is_loaded, get_current_list


def register(router):
    def handle(_handler: BaseHTTPRequestHandler):
        items = []
        if is_loaded():
            for name in get_current_list():
                items.append({
                    "id": name,
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "py3model",
                })
        payload = {
            "object": "list",
            "data": items,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return 200, body, "application/json; charset=utf-8"

    router.add("GET", "/v1/models", handle)
