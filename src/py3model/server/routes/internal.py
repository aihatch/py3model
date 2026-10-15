#!/usr/bin/python3
# coding=utf-8

"""
非标准 OpenAI 接口（仅供 GUI / 本地工具调用）。

POST /v1/internal/load      -> 加载指定 .gguf（多模型可同时驻留）
POST /v1/internal/unload    -> 卸载模型；body.model_name 不传则卸载全部
"""

import json
from http.server import BaseHTTPRequestHandler

from ...gguf import load as gguf_load, unload as gguf_unload, get_current_list
from ...config import load as cfg_load, update as cfg_update


def _read_request_body(handler: BaseHTTPRequestHandler) -> bytes:
    """读取 HTTP 请求体（兼容 Content-Length 与 Transfer-Encoding: chunked）。"""
    te = (handler.headers.get("Transfer-Encoding") or "").lower()
    if "chunked" in te:
        chunks = []
        while True:
            size_line = handler.rfile.readline().strip()
            if not size_line:
                break
            try:
                size = int(size_line.split(b";", 1)[0], 16)
            except ValueError:
                break
            if size == 0:
                handler.rfile.readline()
                break
            chunks.append(handler.rfile.read(size))
            handler.rfile.readline()
        return b"".join(chunks)

    length = int(handler.headers.get("Content-Length", "0") or "0")
    return handler.rfile.read(length) if length > 0 else b"{}"


def register(router):
    def handle_load(_handler: BaseHTTPRequestHandler):
        raw = _read_request_body(_handler)
        try:
            payload = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return 400, json.dumps({"error": "invalid json"}).encode("utf-8"), "application/json"

        model_name = payload.get("model_name") or payload.get("name")
        path = payload.get("path") or payload.get("model_path")
        n_ctx = int(payload.get("n_ctx", 0) or 0)

        if not model_name:
            return 400, json.dumps({"error": "缺少 model_name"}).encode("utf-8"), "application/json"
        if not path:
            return 400, json.dumps({"error": "缺少 path"}).encode("utf-8"), "application/json"

        cfg = cfg_load()
        # 兜底：若调用方未传 n_ctx，则依次回退到
        #   1) 该模型已注册配置里的 n_ctx
        #   2) 全局 llama_cpp.n_ctx
        #   3) 8192
        # 避免 GGUF 元数据缺失 n_ctx_train 时，llama-cpp-python 回退到 512 导致 decode 失败。
        if not n_ctx:
            n_ctx = int(
                (cfg.get("models", {}).get(model_name, {}) or {}).get("n_ctx")
                or cfg.get("llama_cpp", {}).get("n_ctx")
                or 8192
            )

        # 若模型未在配置中注册，则同步注册一份（GUI 通常先注册再加载；这里兜底）。
        if model_name not in cfg["models"] or cfg["models"].get(model_name, {}).get("path") != path:
            cfg["models"][model_name] = {"path": path, "n_ctx": n_ctx}
        else:
            cfg["models"][model_name]["path"] = path
            cfg["models"][model_name]["n_ctx"] = n_ctx

        cfg_update(models=cfg["models"])

        try:
            gguf_load(model_name, path, n_ctx)
        except FileNotFoundError as e:
            return 404, json.dumps({"error": str(e)}).encode("utf-8"), "application/json"
        except RuntimeError as e:
            return 500, json.dumps({"error": str(e)}).encode("utf-8"), "application/json"
        except Exception as e:
            # llama-cpp-python 抛的 TypeError/ValueError 等不在预知范围，统一兜底并返回详情
            return 500, json.dumps({"error": f"{type(e).__name__}: {e}"}).encode("utf-8"), "application/json"

        body = json.dumps({
            "status": "ok",
            "model": model_name,
            "path": path,
            "n_ctx": n_ctx,
            "loaded_models": get_current_list(),
        }, ensure_ascii=False).encode("utf-8")
        return 200, body, "application/json"

    def handle_unload(_handler: BaseHTTPRequestHandler):
        raw = _read_request_body(_handler)
        try:
            payload = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            payload = {}
        target = payload.get("model_name") or payload.get("name")
        if target:
            gguf_unload(target)
        else:
            gguf_unload()
        body = json.dumps({
            "status": "ok",
            "loaded_models": get_current_list(),
        }, ensure_ascii=False).encode("utf-8")
        return 200, body, "application/json"

    router.add("POST", "/v1/internal/load", handle_load)
    router.add("POST", "/v1/internal/unload", handle_unload)
