# HTTP API

base_url：`http://127.0.0.1:11435`（具体值取决于「HTTP 服务」卡片里设置的 host/port）

兼容 OpenAI 接口协议，可直接用 OpenAI Python SDK、LangChain、Cursor、Open WebUI 等工具接入。

> 注意：以下接口都要求 HTTP 服务已启动，并且请求体里 `model` 字段对应的模型已经在 GUI 中「加载」成功（GUI 的「模型列表」里该模型的状态为「已加载」）。

## 标准 OpenAI 兼容接口

### `POST /v1/chat/completions`

聊天补全接口，支持流式与非流式。

请求体示例：

```json
{
  "model": "qwen3.5",
  "messages": [
    { "role": "system", "content": "你是一个助手" },
    { "role": "user", "content": "你好" }
  ],
  "stream": true,
  "temperature": 0.7
}
```

- `model`：**必填**，要使用的模型名。需要与 GUI 中「已加载」的某个模型名一致
- `stream`：`true` 时返回 SSE（`data: {json}\n\n`，结束标志 `data: [DONE]`）
- `temperature`、`max_tokens`、`tools`、`tool_choice` 等字段含义与 OpenAI 相同

错误码：

| 状态码 | 含义 |
| --- | --- |
| `400` | 缺 `model` 字段，或 `model` 为空 |
| `404` | `model` 不在已加载集合中（响应里会附带当前已加载列表） |
| `500` | 推理失败（GGUF 损坏、显存不足等） |

### `POST /v1/completions`

文本补全接口（无 chat template 包装），用法与 OpenAI 一致，错误码同上。

### `GET /v1/models`

返回当前已加载的模型列表，OpenAI 格式：

```json
{
  "object": "list",
  "data": [
    { "id": "qwen3.5", "object": "model", "created": 1690000000, "owned_by": "py3model" },
    { "id": "qwen3.6", "object": "model", "created": 1690000000, "owned_by": "py3model" }
  ]
}
```

### `GET /health`

健康检查。返回服务运行状态与当前已加载的模型：

```json
{
  "status": "ok",
  "model_loaded": true,
  "model": "qwen3.5",
  "models": ["qwen3.5", "qwen3.6"]
}
```

- `model`：兼容旧字段，返回第一个已加载的模型名
- `models`：当前所有已加载的模型名列表

## 内部接口（非 OpenAI 兼容，仅供 GUI 使用）

### `POST /v1/internal/load`

把一个 `.gguf` 加载到内存。**多模型可同时驻留**：不同 `model_name` 的实例互不影响；同名重复加载会替换旧的实例。

请求体：

```json
{
  "model_name": "qwen3.5",
  "path": "/Users/.../Qwen3.5-9B-Q5_K_M.gguf",
  "n_ctx": 8192
}
```

- `model_name`：模型名（会写入 `~/.py3model/config.json` 的 `models`）
- `path`：本地 `.gguf` 文件绝对路径
- `n_ctx`：上下文窗口大小，0 表示由模型自带元数据决定；若未传，会依次回退到该模型已注册配置里的 `n_ctx` → 全局 `llama_cpp.n_ctx` → `8192`

成功返回 `{"status":"ok", "model":"qwen3.5", "path":"...", "n_ctx":8192, "loaded_models":["..."]}`；失败时返回 4xx/5xx + `{"error":"..."}`。

### `POST /v1/internal/unload`

卸载模型。请求体可带 `model_name`：

- 带 `model_name`：按名称卸载指定模型
- 不带或为空：卸载全部已加载模型

请求示例（按名卸载）：

```json
{ "model_name": "qwen3.5" }
```

成功返回 `{"status":"ok", "loaded_models":["..."]}`。
