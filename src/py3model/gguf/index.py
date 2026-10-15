#!/usr/bin/python3
# coding=utf-8

"""
GGUF 模型管理：多实例（按 model_name 维度）加载 / 卸载 / 查询。
"""

import os
import threading
from typing import Dict, List, Optional

_lock = threading.RLock()
# 多模型共存：key 为 config.models 中的模型名，value 为 Llama 实例。
_llms: Dict[str, "Llama"] = {}

# 默认 llama.cpp 推理参数（除 n_ctx 外与 config._DEFAULTS.llama_cpp 完全一致）。
# 实际传递给 Llama() 的参数在调用时由 config.load() 注入并合并默认值。
_BASE_PARAMS = {
    "n_batch": 512,
    "n_ubatch": 512,
    "split_mode": 1,
    "main_gpu": 0,
    "n_threads": None,
    "n_threads_batch": None,
    "n_gpu_layers": -1,
    "use_mmap": True,
    "use_mlock": False,
    "vocab_only": False,
    "logits_all": False,
    "embedding": False,
    "offload_kqv": True,
    "flash_attn": False,
    "op_offload": None,
    "swa_full": None,
    "rope_freq_base": 0.0,
    "rope_scaling_type": -1,
    "rope_freq_scale": 0.0,
    "yarn_orig_ctx": 0,
    "yarn_ext_factor": -1.0,
    "yarn_attn_factor": 1.0,
    "yarn_beta_fast": 32.0,
    "yarn_beta_slow": 1.0,
    "type_k": None,
    "type_v": None,
    "last_n_tokens_size": 64,
    "seed": 4294967295,
    "pooling_type": -1,
    "attention_type": -1,
    "lora_base": None,
    "lora_scale": 1.0,
    "lora_path": None,
    "numa": False,
    "chat_format": None,
    "spm_infill": False,
    "no_perf": False,
    "verbose": False,
}


def _build_llama_kwargs(model_path: str, n_ctx: int) -> dict:
    """构造传给 Llama() 的参数字典。"""
    kwargs = dict(_BASE_PARAMS)
    kwargs["model_path"] = model_path
    # n_ctx 为 0 表示由模型自带元数据决定。
    kwargs["n_ctx"] = int(n_ctx) if n_ctx else 0
    # 简化 None 值（llama-cpp-python 不接受 None 的某些字段，先做安全剔除）
    cleaned = {}
    for k, v in kwargs.items():
        if v is None and k not in ("n_threads", "n_threads_batch", "chat_format",
                                   "type_k", "type_v", "op_offload", "swa_full"):
            continue
        cleaned[k] = v
    return cleaned


def load(model_name: str, model_path: str, n_ctx: int = 0) -> None:
    """加载 GGUF 模型到内存中（同步，调用方应在子线程执行）。

    多模型共存：若 model_name 已有实例在内存，会先卸载旧实例再加载。
    不同 name 的实例互不影响，可同时驻留。

    Raises:
        FileNotFoundError: 模型文件不存在
        RuntimeError: 加载失败
    """
    from llama_cpp import Llama

    with _lock:
        # 同名已加载：先卸载旧的
        if model_name in _llms:
            _safe_unload_one_locked(model_name)

        if not os.path.isfile(model_path):
            raise FileNotFoundError(f"Model path does not exist: {model_path}")

        kwargs = _build_llama_kwargs(model_path, n_ctx)
        try:
            new_llm = Llama(**kwargs)
        except FileNotFoundError:
            # 极少数情况下 Llama 内部也会抛 FileNotFoundError，原样透传便于路由层判定 404
            raise
        except Exception as e:
            raise RuntimeError(f"加载模型失败: {e}") from e
        _llms[model_name] = new_llm


def unload(model_name: Optional[str] = None) -> None:
    """卸载模型。

    Args:
        model_name: 指定要卸载的模型名；不传或 None 表示卸载全部。
    """
    with _lock:
        if model_name is None:
            _safe_unload_all_locked()
        else:
            _safe_unload_one_locked(model_name)


def _safe_unload_all_locked() -> None:
    names = list(_llms.keys())
    for n in names:
        _safe_unload_one_locked(n)


def _safe_unload_one_locked(model_name: str) -> None:
    inst = _llms.pop(model_name, None)
    if inst is not None:
        try:
            del inst  # llama-cpp-python 当前版本未提供显式 close，置 None 触发 GC。
        except Exception:
            pass


def get_current() -> Optional[str]:
    """兼容旧接口：返回第一个已加载的模型名；未加载返回 None。"""
    with _lock:
        if not _llms:
            return None
        return next(iter(_llms))


def get_current_list() -> List[str]:
    """返回当前已加载的模型名列表。"""
    with _lock:
        return list(_llms.keys())


def is_loaded(model_name: Optional[str] = None) -> bool:
    """是否已加载模型。

    Args:
        model_name: 指定模型名时检查该模型是否已加载；不传时检查是否有任何已加载。
    """
    with _lock:
        if model_name is None:
            return bool(_llms)
        return model_name in _llms


def get_llm(model_name: Optional[str] = None):
    """返回指定 model_name 的 Llama 实例。

    Args:
        model_name: 模型名；不传时返回「当前活跃」即第一个已加载（兼容旧调用方）。
                    调用方应自行处理返回 None 的情况。
    """
    with _lock:
        if model_name is None:
            if not _llms:
                return None
            return next(iter(_llms.values()))
        return _llms.get(model_name)
