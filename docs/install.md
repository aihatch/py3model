# 安装与启动

## 安装

```bash
pip3 install py3model
```

依赖 `llama-cpp-python==0.3.23`，首次安装会从 PyPI 自动拉取。如果你需要 GPU 加速（Metal / CUDA），请参考 llama-cpp-python 官方文档的「预编译 wheel」指引，pip 默认装的是 CPU 版本。

## 启动

最简单的启动方式：

```bash
py3model
```

启动后会弹出一个可视化窗口，界面只有「管理」一个标签页，分为两张卡片：

- **HTTP 服务**：填写监听地址和端口（默认 `127.0.0.1:11435`），点「启动服务」即可开启 OpenAI 兼容的 HTTP 接口。
- **模型列表**：点「新增模型」选择本地 `.gguf` 文件并命名；点「加载」会调用 llama.cpp 把模型加载到内存；点「编辑 / 删除」可维护模型条目。

服务启动后，所有 OpenAI 兼容的客户端（OpenAI Python SDK、LangChain、Cursor、Open WebUI 等）都可以通过 `base_url` 接入。请求时把 `model` 字段填成「模型列表」里已加载的那个模型名即可。

> 多模型共存：可以在「模型列表」里同时对多个模型点「加载」，它们会同时驻留在内存里。客户端按 `model` 字段路由，互不影响。

## 关闭

直接关闭可视化窗口即可，应用退出时会自动停止 HTTP 服务并卸载所有已加载的模型。
