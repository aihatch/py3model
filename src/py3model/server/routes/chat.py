#!/usr/bin/python3
# coding=utf-8

"""
POST /v1/chat/completions
OpenAI 兼容的聊天补全接口，支持流式与非流式。
"""

import json
import re
import time
import uuid
from http.server import BaseHTTPRequestHandler

from ...gguf import get_llm, get_current_list as gguf_get_current_list


# 匹配模型在文本中输出的工具调用（兼容 Qwen / Llama3 等常见的类 XML / Hermes 风格）
# 形如：
#   <tool_call>
#   <function=readPlain>
#   <parameter=filepath>./.mailmap</parameter>
#   </function>
#   </tool_call>
_TOOL_CALL_RE = re.compile(
    r"<\s*tool_call\s*>(.*?)<\s*/\s*tool_call\s*>",
    re.DOTALL | re.IGNORECASE,
)
_FN_NAME_RE = re.compile(r"<\s*function\s*=\s*([^\s>]+)\s*>", re.IGNORECASE)
_PARAM_RE = re.compile(
    r"<\s*parameter\s*=\s*([^\s>]+)\s*>(.*?)<\s*/\s*parameter\s*>",
    re.DOTALL | re.IGNORECASE,
)


def _parse_text_tool_calls(content: str):
    """从模型输出的文本中解析出 OpenAI 标准的 tool_calls 列表。

    返回 ([tool_calls], cleaned_content)：
      - tool_calls: 与 OpenAI 兼容的字典列表（id/type/function.name/function.arguments）
      - cleaned_content: 已剥离 tool_call 文本后的剩余内容（若无则原样返回）
    """
    if not content:
        return [], content

    tool_calls = []
    cleaned = content
    for match in _TOOL_CALL_RE.finditer(content):
        block = match.group(1)
        name_m = _FN_NAME_RE.search(block)
        if not name_m:
            continue
        fname = name_m.group(1).strip()

        # 收集参数（多个 <parameter=name>value</parameter>）
        args_dict = {}
        for p in _PARAM_RE.finditer(block):
            pname = p.group(1).strip()
            pvalue = p.group(2).strip()
            # 尝试按 JSON 解析 value（带引号/对象/数组），否则作为字符串
            try:
                args_dict[pname] = json.loads(pvalue)
            except Exception:
                args_dict[pname] = pvalue

        tool_calls.append({
            "id": f"call_{uuid.uuid4().hex[:24]}",
            "type": "function",
            "function": {
                "name": fname,
                "arguments": json.dumps(args_dict, ensure_ascii=False),
            },
        })

    if not tool_calls:
        return [], content

    # 剥离 tool_call 文本，避免 content 中残留脏数据
    cleaned = _TOOL_CALL_RE.sub("", content).strip()
    return tool_calls, cleaned


def _normalize_tool_calls_in_message(message: dict) -> dict:
    """把 message 中的文本式工具调用转换为 OpenAI 标准的 tool_calls。

    - 若已有 tool_calls（来自原生支持的 chat_format），原样保留。
    - 否则尝试从 content 文本中解析。
    """
    if not isinstance(message, dict):
        return message

    tool_calls = message.get("tool_calls")
    content = message.get("content") or ""
    if tool_calls:
        # 已有结构化 tool_calls：content 应为 null（OpenAI 规范）
        message["content"] = None
        return message

    parsed, cleaned = _parse_text_tool_calls(content)
    if parsed:
        message["tool_calls"] = parsed
        # 当整段都是 tool_call 文本时，content 置 null（OpenAI 规范）
        message["content"] = cleaned if cleaned else None
    return message


def _read_request_body(handler: BaseHTTPRequestHandler) -> bytes:
    """读取 HTTP 请求体。

    同时兼容：
      - Content-Length 头（普通 POST）
      - Transfer-Encoding: chunked（Node.js 默认不显式设 Content-Length 时使用）
    """
    te = (handler.headers.get("Transfer-Encoding") or "").lower()
    if "chunked" in te:
        # 手解 chunked：每个 chunk = "<size in hex>\\r\\n<data>\\r\\n"，以 "0\\r\\n\\r\\n" 结束
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
                # 读掉结尾的空 CRLF
                handler.rfile.readline()
                break
            chunks.append(handler.rfile.read(size))
            handler.rfile.readline()  # 段尾的 CRLF
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
        messages = params.get("messages") or []
        if not isinstance(messages, list) or not messages:
            return 400, json.dumps({"error": "messages 必填且为非空数组"}).encode("utf-8"), "application/json"

        stream = bool(params.get("stream", False))
        temperature = params.get("temperature", 0.7)
        max_tokens = params.get("max_tokens") or params.get("n_predict")
        created = int(time.time())

        chat_kwargs = {
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        if max_tokens:
            chat_kwargs["max_tokens"] = int(max_tokens)

        # OpenAI tool calling 规范字段：tools / tool_choice
        # 透传给 llama-cpp-python，由其 chat_format 处理 tool prompt 注入
        tools = params.get("tools")
        if tools:
            if not isinstance(tools, list):
                return 400, json.dumps({"error": "tools 必须为数组"}).encode("utf-8"), "application/json"
            chat_kwargs["tools"] = tools
            tool_choice = params.get("tool_choice")
            if tool_choice is not None:
                chat_kwargs["tool_choice"] = tool_choice

        if stream:
            return _stream_chat(handler, llm, chat_kwargs, model_id, created)
        return _non_stream_chat(handler, llm, chat_kwargs, model_id, created)

    router.add("POST", "/v1/chat/completions", handle)


def _non_stream_chat(handler, llm, chat_kwargs, model_id, created):
    try:
        result = llm.create_chat_completion(**chat_kwargs)
    except Exception as e:
        return 500, json.dumps({"error": f"推理失败: {e}"}).encode("utf-8"), "application/json"

    # 把文本式工具调用转换为 OpenAI 标准 tool_calls
    for choice in (result.get("choices") or []):
        if isinstance(choice, dict):
            message = choice.get("message")
            if isinstance(message, dict):
                _normalize_tool_calls_in_message(message)
                # 若模型产生工具调用，finish_reason 应为 tool_calls
                if message.get("tool_calls") and choice.get("finish_reason") in (None, "", "stop"):
                    choice["finish_reason"] = "tool_calls"

    # 补齐 OpenAI 必需字段
    result.setdefault("id", f"chatcmpl-{created}")
    result.setdefault("object", "chat.completion")
    result.setdefault("created", created)
    result.setdefault("model", model_id)

    body = json.dumps(result, ensure_ascii=False).encode("utf-8")
    return 200, body, "application/json; charset=utf-8"


def _find_tool_call_start(text: str) -> int:
    """返回 <tool_call> 起始位置；找不到返回 -1。"""
    m = re.search(r"<\s*tool_call\s*>", text, re.IGNORECASE)
    return m.start() if m else -1


def _find_tool_call_end(text: str, start: int) -> int:
    """从 start 起，匹配首个 </tool_call> 的结束位置；找不到返回 -1。"""
    m = re.search(r"<\s*/\s*tool_call\s*>", text[start:], re.IGNORECASE)
    return (start + m.end()) if m else -1


def _match_partial_tool_call_prefix(text: str) -> int:
    """从 text 末尾往前匹配 `tool_call` 的最长可能前缀（不区分大小写）。

    返回匹配到的字符数：
      - 0 表示 text 末尾没有 `<tool_call>` 前缀的迹象，可全部 emit；
      - N (1 ≤ N ≤ 10) 表示末尾 N 个字符是 `<tool_call>` 起始前缀的一部分，
        应该保留不 emit，等待下一 chunk 补全。

    例：输入 "正文<" 返回 1；输入 "正文<t" 返回 2；输入 "正文<tool_call" 返回 10。
    """
    target = "<tool_call"
    target_len = len(target)  # 10
    max_check = min(len(text), target_len)
    # 从最长可能前缀往下试
    for n in range(max_check, 0, -1):
        suffix = text[-n:]
        if target[:n].lower() == suffix.lower():
            return n
    return 0


def _match_partial_tool_call_close_prefix(text: str) -> int:
    """从 text 末尾往前匹配 `</tool_call>` 的最长可能前缀（不区分大小写）。

    返回匹配到的字符数；0 表示没有前缀迹象。
    注意：闭合标签允许起始有空白字符 (`</tool_call>` 中 `/` 前可有空白)，
    以及闭合标签内可选空白 (`</ tool_call >`)，所以判断时使用宽松匹配。
    """
    # 把 </tool_call> 拆成字符序列：< / t o o l _ c a l l >，允许插入 0+ 个空白
    target = "</tool_call"
    target_len = len(target)  # 11
    if len(text) == 0:
        return 0
    max_check = min(len(text), target_len)
    for n in range(max_check, 0, -1):
        suffix = text[-n:]
        if target[:n].lower() == suffix.lower():
            return n
    return 0


def _stream_chat(handler, llm, chat_kwargs, model_id, created):
    """流式响应：SSE 格式（data: {...}\n\n）。

    同时把模型输出的「文本式」工具调用（Qwen/Hermes 风格的 XML 片段）
    转换为 OpenAI 标准的结构化 delta.tool_calls，并从 delta.content 中
    剥离对应的 XML 文本，避免客户端噪音。

    实现策略（按 choice 维护状态）：
      - `buffer[idx]`: 累积的 delta.content（包含未消费的）
      - `consumed[idx]`: buffer 中已 emit 为干净 content 的位置
      - `waiting_close[idx]`: bool，是否处于「已看到 <tool_call> 起始但还没
        看到 </tool_call> 闭合」的等待状态。此状态下所有后续 content 不 emit。

      每个新 chunk 到达时：
      1. 把 incoming 追加到 buffer。
      2. 若 waiting_close：在 incoming 里找 </tool_call>，找到则切换状态、
         切走闭合段、转 emit tool_calls。
      3. 否则：扫描 buffer 是否出现 <tool_call>：
         - 未出现 → 把 buffer[consumed:] 全部 emit 为 content（流式 think/正文）。
         - 已出现 → emit buffer[consumed:start] 为 content，consumed = start，
                    切走起始标记，等待下一 chunk 补齐闭合。
    """
    try:
        chunks = llm.create_chat_completion(**chat_kwargs)
    except Exception as e:
        handler.send_response(500)
        handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
        handler.end_headers()
        err = json.dumps({"error": f"推理失败: {e}"}, ensure_ascii=False)
        handler.wfile.write(f"data: {err}\n\n".encode("utf-8"))
        handler.wfile.write(b"data: [DONE]\n\n")
        return

    completion_id = f"chatcmpl-{created}"
    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("Connection", "close")
    handler.end_headers()

    buffers = {}        # idx -> 累积的全部 content
    consumed = {}       # idx -> buffer 中已 emit 干净 content 的位置
    waiting_close = {}  # idx -> bool 是否处于等待 </tool_call> 闭合状态

    _TC_OPEN = re.compile(r"<\s*tool_call\s*>", re.IGNORECASE)
    _TC_CLOSE = re.compile(r"<\s*/\s*tool_call\s*>", re.IGNORECASE)

    def _emit(chunk):
        chunk.setdefault("id", completion_id)
        chunk.setdefault("object", "chat.completion.chunk")
        chunk.setdefault("created", created)
        chunk.setdefault("model", model_id)
        line = "data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n"
        try:
            handler.wfile.write(line.encode("utf-8"))
            handler.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            raise

    def _emit_content(idx, text):
        """emit 干净 delta.content。"""
        if not text:
            return
        _emit({
            "choices": [{
                "index": idx,
                "delta": {"content": text},
            }]
        })

    try:
        for chunk in chunks:
            choices = chunk.get("choices") or []

            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                delta = choice.get("delta") or {}
                idx = choice.get("index", 0)
                incoming = delta.get("content") or ""
                if not incoming:
                    continue

                if idx not in buffers:
                    buffers[idx] = ""
                    consumed[idx] = 0
                    waiting_close[idx] = False

                buffers[idx] += incoming
                buf = buffers[idx]
                con = consumed[idx]

                if waiting_close[idx]:
                    # 状态：在等待 </tool_call> 闭合。
                    # consumed[idx] 必须保持指向 <tool_call> 起始位置（open_start），
                    # 不能被推进——否则解析时拿不到完整 tool_call 文本。
                    m_close = _TC_CLOSE.search(buf, con)
                    if m_close is None:
                        # 还没闭合：保留 con 不变，buffer 继续累积
                        continue
                    # 找到闭合：解析 [con, m_close.end()) 之间的整段 tool_call
                    block_end = m_close.end()
                    block_text = buf[con:block_end]
                    parsed, _ = _parse_text_tool_calls(block_text)
                    if parsed:
                        _emit({
                            "choices": [{
                                "index": idx,
                                "delta": {"tool_calls": parsed},
                            }]
                        })
                        # 切掉整段（从 open_start 到 block_end），重置状态
                        buffers[idx] = buf[:con] + buf[block_end:]
                        consumed[idx] = con
                        waiting_close[idx] = False
                        buf = buffers[idx]
                        # fall through 到下面的常规扫描（可能还有下一个 tool_call）
                    else:
                        # 解析失败：放弃该段，当作普通文本 emit
                        _emit_content(idx, buf[con:block_end])
                        buffers[idx] = buf[:con] + buf[block_end:]
                        consumed[idx] = con
                        waiting_close[idx] = False
                        buf = buffers[idx]

                # 常规扫描：buf 中是否有 <tool_call> 起始
                m_open = _TC_OPEN.search(buf, con)
                if m_open is None:
                    # 没有 tool_call 起始。
                    # 但若 buffer 末尾是 `<` / `<t` / `<tool_cal` 这种可能是
                    # `<tool_call>` 前缀的不完整片段，暂不 emit，避免跨 chunk
                    # 切断了 tool_call 标记。
                    tail_len = _match_partial_tool_call_prefix(buf[con:])
                    safe_end = len(buf) - tail_len
                    tail = buf[con:safe_end]
                    if tail:
                        _emit_content(idx, tail)
                    consumed[idx] = safe_end
                    buffers[idx] = buf
                else:
                    open_start = m_open.start()
                    # 起始前的干净 content emit
                    pre = buf[con:open_start]
                    if pre:
                        _emit_content(idx, pre)
                    # 进入等待闭合状态
                    buffers[idx] = buf
                    consumed[idx] = open_start
                    waiting_close[idx] = True
                    # 立即尝试在同一 buf 内找闭合（可能 tool_call 完整闭合）
                    m_close2 = _TC_CLOSE.search(buf, open_start)
                    if m_close2 is not None:
                        block_end2 = m_close2.end()
                        block_text2 = buf[open_start:block_end2]
                        parsed2, _ = _parse_text_tool_calls(block_text2)
                        if parsed2:
                            _emit({
                                "choices": [{
                                    "index": idx,
                                    "delta": {"tool_calls": parsed2},
                                }]
                            })
                            buffers[idx] = buf[:open_start] + buf[block_end2:]
                            consumed[idx] = open_start
                            waiting_close[idx] = False
                            buf = buffers[idx]
                            # 切完后可能还有下一个 tool_call，再扫一次
                            m_open2 = _TC_OPEN.search(buf, consumed[idx])
                            if m_open2 is not None:
                                pre2 = buf[consumed[idx]:m_open2.start()]
                                if pre2:
                                    _emit_content(idx, pre2)
                                buffers[idx] = buf
                                consumed[idx] = m_open2.start()
                                waiting_close[idx] = True
                        else:
                            _emit_content(idx, buf[open_start:block_end2])
                            buffers[idx] = buf[:open_start] + buf[block_end2:]
                            consumed[idx] = open_start
                            waiting_close[idx] = False
                            buf = buffers[idx]

            # 转发原 chunk 中除 delta.content 外的字段（reasoning_content / reasoning / role 等）
            # 注意：只保留「真非空」的字段，避免向客户端发空 reasoning_content 噪音。
            cleaned_choices = []
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                new_delta = dict(choice.get("delta") or {})
                new_delta.pop("content", None)
                # 过滤掉空字符串/空列表字段（保留非空的有意义字段）
                new_delta = {
                    k: v for k, v in new_delta.items()
                    if v not in (None, "", [], {})
                }
                if new_delta or "finish_reason" in choice:
                    item = {"index": choice.get("index", 0), "delta": new_delta}
                    if "finish_reason" in choice:
                        item["finish_reason"] = choice["finish_reason"]
                    cleaned_choices.append(item)
            if cleaned_choices:
                try:
                    _emit({"choices": cleaned_choices})
                except (BrokenPipeError, ConnectionResetError):
                    return

        # 流结束后：把每个 buffer 中剩余的干净 content flush 出去
        for idx in buffers:
            tail = buffers[idx][consumed.get(idx, 0):]
            if tail:
                _emit_content(idx, tail)

        handler.wfile.write(b"data: [DONE]\n\n")
        handler.wfile.flush()

    except (BrokenPipeError, ConnectionResetError):
        return
    except Exception as e:
        err = json.dumps({"error": f"生成中断: {e}"}, ensure_ascii=False)
        try:
            handler.wfile.write(f"data: {err}\n\n".encode("utf-8"))
            handler.wfile.write(b"data: [DONE]\n\n")
        except Exception:
            pass
