# 配置文件

配置文件位置：`~/.py3model/config.json`

首次启动会自动创建并填充默认值。也可以手动编辑；任何字段的修改都会在下次启动时被加载进来。

## 文件结构

```json
{
  "system": {
    "version": 1
  },
  "server": {
    "host": "127.0.0.1",
    "port": 11435
  },
  "models": {
    "qwen3.5": {
      "path": "/Users/.../Qwen3.5-9B-Q5_K_M.gguf",
      "n_ctx": 8192
    },
    "qwen3.6": {
      "path": "/Users/.../Qwen3.6-9B-Q5_K_M.gguf",
      "n_ctx": 16384
    }
  },
  "llama_cpp": {
    "n_ctx": 8192,
    "n_batch": 512,
    "n_ubatch": 512,
    "n_gpu_layers": -1,
    "use_mmap": true,
    "offload_kqv": true,
    "seed": 4294967295
  }
}
```

> `llama_cpp` 的完整字段非常长（几十项），上例只列了常用的几个；完整默认值见 `src/py3model/config/index.py` 的 `_DEFAULTS["llama_cpp"]`。

## 字段说明

### `system.version`
配置文件版本号，用于兼容性检查，**不要手动修改**。

### `server.host` / `server.port`
HTTP 服务的监听地址与端口，默认 `127.0.0.1:11435`。在可视化界面「HTTP 服务」卡片里可以直接修改并保存。

### `models`
模型注册表。`key` 是模型名（自定义，仅在 GUI 中显示），`value` 是：

- `path`：本地 `.gguf` 文件绝对路径
- `n_ctx`：上下文窗口大小（token 数）。仅在「加载」时生效

可视化界面「模型列表」卡片的新增 / 编辑 / 删除会同步修改这里。**注册到这里的模型不一定会被加载到内存**；是否驻留由「加载 / 卸载」按钮控制。

客户端请求时用哪个模型，取决于请求体里 `model` 字段是否对应了一个已加载的模型。

### `llama_cpp`
llama.cpp 推理参数。除 `n_ctx` 外，**用户不需要也不应该修改这里**——可视化界面已经按推荐值填好默认值。`n_ctx` 也建议优先用界面里的「新增模型」弹窗（提供 `4k / 8k / 16k / 32k / 64k / 128k / 256k` 离散档位）来设置。

各字段含义请参考 `src/py3model/config/index.py` 的 `_DEFAULTS["llama_cpp"]` 注释。
