<img src="./logo.jpeg" />

# [py3model](https://github.com/aihatch/py3model)

一行命令在本地启动一个 OpenAI 兼容的 LLM 服务，配套一个极简的可视化管理窗口。

<p>
    <a href="https://github.com/aihatch/py3model" target='_blank'>
        <img alt="GitHub repo stars" src="https://img.shields.io/github/stars/aihatch/py3model?style=social">
    </a>
</p>

## 特性

- 基于 [llama-cpp-python](https://github.com/abetlen/llama-cpp-python) 加载本地 `.gguf` 模型，零额外依赖
- 启动一个 Tkinter 可视化窗口，用来注册 / 加载 / 卸载 / 删除模型
- 同时启动一个 OpenAI 兼容的 HTTP 服务（`/v1/chat/completions`、`/v1/completions`、`/v1/models`、`/health`），可直接对接 OpenAI Python SDK、LangChain、Cursor、Open WebUI 等客户端
- 支持**多模型同时驻留**内存，按请求里的 `model` 字段路由到对应实例
- 配置统一落在 `~/.py3model/config.json`，可视化窗口是配置的可视化编辑界面

## 快速开始

```bash
pip3 install py3model
py3model
```

启动后：

1. 在「模型列表」点「新增模型」选择本地 `.gguf` 文件并命名
2. 选「加载」，把模型加载到内存（首次加载需要几秒到几十秒，取决于模型大小和磁盘）
3. 在「HTTP 服务」卡片里点「启动服务」（默认 `127.0.0.1:11435`）
4. 用任何 OpenAI 兼容的客户端，把 `base_url` 指向 `http://127.0.0.1:11435/v1` 即可

> 想同时用多个模型？只要每个都在 GUI 里点过「加载」，它们就同时驻留在内存里；客户端在请求里把 `model` 字段设成对应名字即可路由到正确的实例。

## 文档

- [安装与启动](./docs/install.md)
- [配置文件](./docs/config.md)
- [HTTP API（OpenAI 兼容）](./docs/api.md)

## 关闭

直接关掉可视化窗口即可，应用退出时会自动停止 HTTP 服务并卸载所有已加载的模型。

## 版权

MIT License

Copyright (c) [zxl20070701](https://zxl20070701.github.io/notebook/home.html) 走一步，再走一步
