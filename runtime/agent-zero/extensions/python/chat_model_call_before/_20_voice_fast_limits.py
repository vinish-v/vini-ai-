from __future__ import annotations

import json
from typing import Any

import models
from helpers import files
from helpers.extension import Extension
from plugins._model_config.helpers import model_config


VOICE_CONFIG_PATH = "usr/plugins/_vini_voice/config.json"
DEFAULT_VOICE_MODEL = {
    "enabled": True,
    "provider": "cerebras",
    "name": "gpt-oss-120b",
    "api_base": "https://api.cerebras.ai/v1",
    "ctx_length": 8192,
    "vision": False,
    "kwargs": {
        "max_tokens": 128,
        "temperature": 0.35,
    },
}


def _read_voice_model_config() -> dict[str, Any]:
    cfg = dict(DEFAULT_VOICE_MODEL)
    path = files.get_abs_path(VOICE_CONFIG_PATH)
    if not files.exists(path):
        return cfg

    try:
        saved = json.loads(files.read_file(path))
    except Exception:
        return cfg

    voice_model = saved.get("voice_model", saved) if isinstance(saved, dict) else {}
    if not isinstance(voice_model, dict):
        return cfg

    merged = {**cfg, **voice_model}
    merged_kwargs = dict(cfg.get("kwargs") or {})
    if isinstance(voice_model.get("kwargs"), dict):
        merged_kwargs.update(voice_model["kwargs"])
    merged["kwargs"] = merged_kwargs
    return merged


def _build_voice_model(cfg: dict[str, Any]):
    mc = model_config.build_model_config(cfg, models.ModelType.CHAT)
    return models.get_chat_model(
        mc.provider,
        mc.name,
        model_config=mc,
        **mc.build_kwargs(),
    )


class VoiceFastLimits(Extension):
    async def execute(self, call_data: dict | None = None, **kwargs):
        if not self.agent or not call_data:
            return

        if not self.agent.get_data("vini_voice_fast_once"):
            return

        self.agent.set_data("vini_voice_fast_once", False)
        call_kwargs = call_data.setdefault("call_kwargs", {})
        voice_cfg = _read_voice_model_config()

        if voice_cfg.get("enabled", False):
            call_data["model"] = _build_voice_model(voice_cfg)

        existing_max_tokens = call_kwargs.get("max_tokens")
        if isinstance(existing_max_tokens, int) and existing_max_tokens > 0:
            call_kwargs["max_tokens"] = min(existing_max_tokens, 128)
        else:
            call_kwargs["max_tokens"] = 128

        call_kwargs.setdefault("temperature", 0.35)
        call_kwargs.setdefault("a0_retry_attempts", 1)
        call_kwargs.setdefault("a0_retry_delay_seconds", 0.15)
        if (
            str(voice_cfg.get("provider", "")).lower() == "cerebras"
            and str(voice_cfg.get("name", "")) != "llama3.1-8b"
        ):
            call_kwargs.setdefault("a0_fallback_models", ["cerebras/llama3.1-8b"])
