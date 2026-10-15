#!/usr/bin/python3
# coding=utf-8

"""
POST /v1/completions
OpenAI 兼容的文本补全接口。
"""

import json
import time
from http.server import BaseHTTPRequestHandler

from ...gguf import get_llm, get_current_list as gguf_get_current_list


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
    def handle(handler: BaseHTTPRequestHandler):
        raw = _read_request_body(handler)
        try:
            params = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return 400, json.dumps({"error": "invalid json"}).encode("utf-8"), "application/json"

        # 校验 model 字段：客户端必须显式传 model，按 model 路由到对应 Llama 实例。
        requested_model = params.get("model")
        if requested_model is None or str(requested_model).strip() == "":
            loaded = gguf_get_current_list()
            hint = f"loaded: {loaded}" if loaded else "no model loaded"
            return 400, json.dumps({
                "error": f"缺少 model 字段；{hint}"
            }).encode("utf-8"), "application/json"

        llm = get_llm(str(requested_model))
        if llm is None:
            return 404, json.dumps({
                "error": f"model '{requested_model}' not found or not loaded; currently loaded: {gguf_get_current_list()}"
            }).encode("utf-8"), "application/json"

        model_id = str(requested_model)
        prompt = params.get("prompt")
        if not prompt:
            return 400, json.dumps({"error": "prompt 必填"}).encode("utf-8"), "application/json"

        stream = bool(params.get("stream", False))
        temperature = params.get("temperature", 0.7)
        max_tokens = params.get("max_tokens")
        created = int(time.time())

        complete_kwargs = {
            "prompt": prompt,
            "temperature": temperature,
            "stream": stream,
        }
        if max_tokens:
            complete_kwargs["max_tokens"] = int(max_tokens)

        if stream:
            return _stream(handler, llm, complete_kwargs, model_id, created)
        return _non_stream(handler, llm, complete_kwargs, model_id, created)

    router.add("POST", "/v1/completions", handle)


def _non_stream(handler, llm, kwargs, model_id, created):
    try:
        result = llm.create_completion(**kwargs)
    except Exception as e:
        return 500, json.dumps({"error": f"推理失败: {e}"}).encode("utf-8"), "application/json"
    result.setdefault("id", f"cmpl-{created}")
    result.setdefault("object", "text_completion")
    result.setdefault("created", created)
    result.setdefault("model", model_id)
    body = json.dumps(result, ensure_ascii=False).encode("utf-8")
    return 200, body, "application/json; charset=utf-8"


def _stream(handler, llm, kwargs, model_id, created):
    try:
        chunks = llm.create_completion(**kwargs)
    except Exception as e:
        handler.send_response(500)
        handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
        handler.end_headers()
        handler.wfile.write(f"data: {json.dumps({'error': str(e)})}\n\n".encode("utf-8"))
        handler.wfile.write(b"data: [DONE]\n\n")
        return
    completion_id = f"cmpl-{created}"
    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
    handler.send_header("Cache-Control", "no-cache")
    handler.end_headers()
    try:
        for chunk in chunks:
            chunk.setdefault("id", completion_id)
            chunk.setdefault("object", "text_completion")
            chunk.setdefault("created", created)
            chunk.setdefault("model", model_id)
            handler.wfile.write(("data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n").encode("utf-8"))
            handler.wfile.flush()
        handler.wfile.write(b"data: [DONE]\n\n")
    except Exception:
        pass
