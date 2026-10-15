#!/usr/bin/python3
# coding=utf-8

"""
HTTP 服务入口。

提供：
  - start(host, port): 后台线程启动 ThreadingHTTPServer
             返回 (thread, server)，失败返回 (None, None)
  - stop(): 关闭并回收
  - is_running(): 当前是否正在监听
  - status(): 返回当前状态 dict: {running, host, port, error}
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# 状态机
_state_lock = threading.RLock()
_server = None
_thread = None
_status = {
    "running": False,
    "host": "",
    "port": 0,
    "error": "",
}


class _Router:
    """简易路由：按 (method, path) 匹配 handler。"""

    def __init__(self):
        self._routes = {}  # (method, path) -> handler

    def add(self, method, path, handler):
        self._routes[(method.upper(), path)] = handler

    def resolve(self, method, path):
        return self._routes.get((method.upper(), path))


def _build_router() -> "_Router":
    router = _Router()
    from .routes import chat, completion, health, internal, models
    health.register(router)
    models.register(router)
    internal.register(router)
    chat.register(router)
    completion.register(router)
    return router


def _make_handler_cls(router: "_Router"):
    """闭包构造 Handler 类，router 通过闭包注入，避免类属性 None 的类型歧义。"""

    class _Handler(BaseHTTPRequestHandler):
        # 静默 BaseHTTPRequestHandler 默认的 stderr 日志
        def log_message(self, format, *args):  # noqa: A002
            return

        def do_GET(self):  # noqa: N802
            self._dispatch("GET")

        def do_POST(self):  # noqa: N802
            self._dispatch("POST")

        def _dispatch(self, method):
            handler = router.resolve(method, self.path)
            if handler is None:
                self._respond(404, {"error": f"not found: {method} {self.path}"}, "application/json")
                return
            try:
                result = handler(self)
            except Exception as e:
                self._respond(500, {"error": f"server error: {e}"}, "application/json")
                return
            if result is not None:
                status, body, ctype = result
                self._respond(status, body, ctype)

        def _respond(self, status, body, content_type="application/json"):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False).encode("utf-8")
            elif isinstance(body, str):
                body = body.encode("utf-8")
            if not isinstance(body, bytes):
                body = str(body).encode("utf-8")
            try:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Headers", "*")
                self.send_header("Access-Control-Allow-Methods", "*")
                self.end_headers()
                self.wfile.write(body)
            except Exception:
                pass

    return _Handler


def start(host: str, port: int):
    """启动 HTTP 服务（后台线程）。

    Returns:
        (thread, server) 成功；或 (None, None) 失败
    """
    global _server, _thread, _status

    with _state_lock:
        if _status["running"]:
            return _thread, _server

        handler_cls = _make_handler_cls(_build_router())

        try:
            server = ThreadingHTTPServer((host, port), handler_cls)
        except OSError as e:
            _status["error"] = str(e)
            return None, None

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        _server = server
        _thread = thread
        _status = {
            "running": True,
            "host": host,
            "port": port,
            "error": "",
        }
        return thread, server


def stop() -> None:
    global _server, _thread, _status
    with _state_lock:
        if _server is not None:
            try:
                _server.shutdown()
                _server.server_close()
            except Exception:
                pass
        _server = None
        _thread = None
        _status = {
            "running": False,
            "host": "",
            "port": 0,
            "error": "",
        }


def is_running() -> bool:
    with _state_lock:
        return _status["running"]


def status() -> dict:
    with _state_lock:
        return dict(_status)
