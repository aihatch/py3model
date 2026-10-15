#!/usr/bin/python3
# coding=utf-8

"""
配置管理：负责读写 ~/.py3model/config.json

配置文件采用 JSON 格式，首次运行时会自动创建并填充默认值。
任何需要持久化的参数（模型路径、推理参数、服务端口等）都集中在这里。
"""

import json
import os
import threading
from pathlib import Path

# 配置文件锁：读写并发时避免数据竞争
_lock = threading.RLock()

# 默认配置
_DEFAULTS = {
    "system": {
        "version": 1,  # 配置文件版本号，用于兼容性检查。
    },
    "models": {},  # 已注册的模型列表。key 为模型名，value 为 {"path": ..., "n_ctx": ...}
    "server": {
        "host": "127.0.0.1",
        "port": 11435,
    },
    "llama_cpp": {
        "n_ctx": 8192,  # 文本上下文窗口大小（token 数）。0 表示使用模型自带的 n_ctx_train。常见设置：2048 / 4096 / 8192 / 32768。越大占用内存越多。
        "n_batch": 512,  # 提示词处理（prompt eval）的逻辑最大批大小。不需要手动调整，除非 GPU 显存不足时可适当调小。
        "n_ubatch": 512,  # 物理 micro-batch 大小。通常与 n_batch 保持一致或更小。
        "split_mode": 1,  # 多 GPU 时的模型拆分模式。1 为 llama.cpp 默认的按层拆分。单 GPU 或 CPU 使用时通常无需修改。
        "main_gpu": 0,  # 主 GPU 编号。单 GPU 通常为 0；多 GPU 时可指定主要承载中间结果的设备。
        "n_threads": None,  # 文本生成（token 生成）阶段的 CPU 线程数。留空表示由 llama.cpp 自动选择；手动设置时建议接近物理 CPU 核心数。
        "n_threads_batch": None,  # 提示词处理（prompt eval）阶段的 CPU 线程数。留空表示由 llama.cpp 自动选择；可与 n_threads 不同。
        "n_gpu_layers": -1,  # 卸载到 GPU 的层数。0 = 纯 CPU，-1 = 全部层数都放到 GPU。显存不足时减小此值，剩余层会自动回落到 CPU。
        "use_mmap": True,  # 使用 mmap 加载模型文件（默认 True）。可以节省内存并加快加载速度，建议保持开启。
        "use_mlock": False,  # 强制系统把模型常驻内存，禁止 swap。可避免大模型被换出，但会占用更多物理内存。
        "vocab_only": False,  # 仅加载词汇表，不加载模型权重。仅用于特殊场景（如测试 tokenizer）。
        "logits_all": False,  # 返回所有 token 的 logits（而非仅最后一个）。需要 logprobs 时必须设为 True；日常对话保持 False 以节省内存。
        "embedding": False,  # 开启 embedding 模式（模型仅用于文本转向量）。日常对话保持 False。
        "offload_kqv": True,  # 把 K/Q/V 张量卸载到 GPU。建议保持 True，能显著提升生成速度。
        "flash_attn": False,  # 启用 Flash Attention。需要当前 llama.cpp 编译后端、硬件和模型共同支持。不确认硬件支持时保持 False。
        "op_offload": None,  # 是否把部分操作卸载到 GPU。留空表示使用 llama.cpp 默认策略。
        "swa_full": None,  # 是否为滑动窗口注意力分配完整 KV cache。留空表示使用 llama.cpp 默认策略。
        "rope_freq_base": 0.0,  # RoPE 基础频率。0 表示使用模型自带值。一般无需调整；扩展上下文时可能需要调高。
        "rope_scaling_type": -1,  # RoPE 缩放类型。-1 表示使用 llama.cpp 或模型元数据默认值。仅在明确知道模型需要特定缩放策略时修改。
        "rope_freq_scale": 0.0,  # RoPE 频率缩放因子。0 表示使用模型自带值。扩展上下文（如 NTK-aware）时常用 < 1 的值。
        "yarn_orig_ctx": 0,  # YaRN 扩展时使用的『原始训练上下文大小』。0 表示使用模型自带值。仅在使用 YaRN 扩展上下文时设置。
        "yarn_ext_factor": -1.0,  # YaRN 插值外推因子。负数表示使用模型自带值。仅在使用 YaRN 时设置。
        "yarn_attn_factor": 1.0,  # YaRN attention 缩放因子。通常保持默认 1.0。
        "yarn_beta_fast": 32.0,  # YaRN beta fast 参数。仅在手动调试 YaRN 上下文扩展时修改。
        "yarn_beta_slow": 1.0,  # YaRN beta slow 参数。仅在手动调试 YaRN 上下文扩展时修改。
        "type_k": None,  # KV cache 中 K 张量的 GGML 类型。留空表示使用 llama.cpp 默认值。常见值：1=f16，2=q4_0，8=q8_0；量化可省显存但可能影响质量。
        "type_v": None,  # KV cache 中 V 张量的 GGML 类型。留空表示使用 llama.cpp 默认值。常见值：1=f16，2=q4_0，8=q8_0；量化可省显存但可能影响质量。
        "last_n_tokens_size": 64,  # 用于 repeat_penalty 计算的最近 token 队列大小。日常对话保持默认 64 即可。
        "seed": 4294967295,  # 随机种子，4294967295 表示随机。想要可复现的输出时设为固定值（如 0）。
        "pooling_type": -1,  # 池化类型。-1 表示使用模型或 llama.cpp 默认值，主要用于 embedding 场景。
        "attention_type": -1,  # 注意力类型。-1 表示使用模型或 llama.cpp 默认值，通常无需修改。
        "lora_base": None,  # LoRA base 模型路径。留空表示不使用。
        "lora_scale": 1.0,  # LoRA 权重缩放系数。使用 LoRA 时通常保持 1.0。
        "lora_path": None,  # LoRA 适配器路径。留空表示不加载 LoRA。
        "numa": False,  # 启用 NUMA 相关优化。普通桌面环境保持 False。
        "chat_format": None,  # 指定聊天模板格式。留空表示由 llama-cpp-python 根据模型自动选择。
        "spm_infill": False,  # 启用 SentencePiece infill 模式。仅补全/填空类模型可能需要。
        "no_perf": False,  # 禁用性能计时信息。日常使用保持 False。
        "verbose": False,  # 是否输出 llama.cpp 内部的运行日志。日常使用保持 False；调试时设为 True。
    },
}


def config_dir() -> Path:
    """返回配置目录 ~/.py3model/，不存在则创建。"""
    home = Path.home()
    d = home / ".py3model"
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_path() -> Path:
    """返回配置文件全路径。"""
    return config_dir() / "config.json"


def load() -> dict:
    """
    读取配置。文件不存在则用默认值初始化并落盘。
    已存在但缺少某些字段时，会用默认值补齐（向前兼容）。
    """
    with _lock:
        path = config_path()
        if not path.exists():
            save(_DEFAULTS)
            return dict(_DEFAULTS)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            # 文件损坏或读取失败，回退到默认
            save(_DEFAULTS)
            return dict(_DEFAULTS)
        # 补齐缺失字段
        changed = False
        for key, val in _DEFAULTS.items():
            if key not in data:
                data[key] = val
                changed = True
        if changed:
            save(data)
        return data


def save(data: dict) -> None:
    """原子写入配置文件，避免半写状态。"""
    with _lock:
        path = config_path()
        tmp = path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)


def update(**kwargs) -> dict:
    """
    更新部分字段并落盘（merge 语义，不会删除已有 key）。
    支持以下用法：
      - update(server={"host": "0.0.0.0"})  # 合并到顶层 dict（dict-of-dict 语义）

    注意：对顶层 dict 是「逐 key 合并」语义，不会删除传入 dict 中不存在的 key。
    如需「整段替换」（例如删除/编辑模型），请使用 replace()。
    """
    with _lock:
        data = load()
        for key1, val1 in kwargs.items():
            if isinstance(val1, dict):
                for key2, val2 in val1.items():
                    data[key1][key2] = val2
            else:
                # 顶层标量直接覆盖
                data[key1] = val1
        save(data)
        return data


def replace(**kwargs) -> dict:
    """
    整体替换顶层字段（不是 merge）。适合「删除 / 编辑」需要把整个 dict
    替换掉的场景，例如：

      - replace(models={"qwen3.5": {...}})  # 整段替换 models
      - replace(server={"host": "0.0.0.0", "port": 11435})
    """
    with _lock:
        data = load()
        for key, val in kwargs.items():
            data[key] = val
        save(data)
        return data


def reset() -> dict:
    """重置为默认配置。"""
    with _lock:
        save(_DEFAULTS)
        return dict(_DEFAULTS)
