from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from models.config_manager import ConfigManager


@dataclass(frozen=True)
class ModelProvider:
    id: str
    name: str
    base_url: str
    api_key_config_key: str
    api_key_env_var: str
    default_model: str
    model_examples: tuple[str, ...]
    note: str = ""


MODEL_PROVIDERS: tuple[ModelProvider, ...] = (
    ModelProvider(
        id="dashscope",
        name="阿里云百炼 DashScope",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key_config_key="api_key.dashscope",
        api_key_env_var="DASHSCOPE_API_KEY",
        default_model="qwen-plus",
        model_examples=("qwen-plus", "qwen-max", "qwen-turbo", "qwq-plus"),
        note="兼容 OpenAI Chat Completions。",
    ),
    ModelProvider(
        id="openai",
        name="OpenAI",
        base_url="https://api.openai.com/v1",
        api_key_config_key="api_key.openai",
        api_key_env_var="OPENAI_API_KEY",
        default_model="gpt-5.1",
        model_examples=("gpt-5.1", "gpt-5.1-mini", "gpt-4.1", "gpt-4.1-mini"),
        note="官方 OpenAI API。",
    ),
    ModelProvider(
        id="deepseek",
        name="DeepSeek",
        base_url="https://api.deepseek.com/v1",
        api_key_config_key="api_key.deepseek",
        api_key_env_var="DEEPSEEK_API_KEY",
        default_model="deepseek-v4-flash",
        model_examples=("deepseek-v4-flash", "deepseek-v4-pro"),
        note="兼容 OpenAI API。",
    ),
    ModelProvider(
        id="zhipu",
        name="智谱 BigModel",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        api_key_config_key="api_key.zhipu",
        api_key_env_var="ZHIPU_API_KEY",
        default_model="glm-5",
        model_examples=("glm-5", "glm-4.5", "glm-4-flash"),
        note="兼容 OpenAI API。",
    ),
    ModelProvider(
        id="moonshot",
        name="Moonshot AI",
        base_url="https://api.moonshot.cn/v1",
        api_key_config_key="api_key.moonshot",
        api_key_env_var="MOONSHOT_API_KEY",
        default_model="kimi-k2-0711-preview",
        model_examples=("kimi-k2-0711-preview", "moonshot-v1-8k", "moonshot-v1-32k"),
        note="兼容 OpenAI API。",
    ),
    ModelProvider(
        id="siliconflow",
        name="SiliconFlow",
        base_url="https://api.siliconflow.cn/v1",
        api_key_config_key="api_key.siliconflow",
        api_key_env_var="SILICONFLOW_API_KEY",
        default_model="Qwen/Qwen3-32B",
        model_examples=("Qwen/Qwen3-32B", "deepseek-ai/DeepSeek-V3", "moonshotai/Kimi-K2-Instruct"),
        note="聚合多家开源/商业模型。",
    ),
    ModelProvider(
        id="openrouter",
        name="OpenRouter",
        base_url="https://openrouter.ai/api/v1",
        api_key_config_key="api_key.openrouter",
        api_key_env_var="OPENROUTER_API_KEY",
        default_model="openai/gpt-5.1",
        model_examples=("openai/gpt-5.1", "anthropic/claude-sonnet-4.5", "google/gemini-2.5-pro"),
        note="模型聚合网关，模型 ID 通常带厂商前缀。",
    ),
    ModelProvider(
        id="gemini",
        name="Google Gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key_config_key="api_key.gemini",
        api_key_env_var="GEMINI_API_KEY",
        default_model="gemini-2.5-pro",
        model_examples=("gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash"),
        note="Google Gemini 的 OpenAI 兼容接口。",
    ),
    ModelProvider(
        id="groq",
        name="Groq",
        base_url="https://api.groq.com/openai/v1",
        api_key_config_key="api_key.groq",
        api_key_env_var="GROQ_API_KEY",
        default_model="llama-3.3-70b-versatile",
        model_examples=("llama-3.3-70b-versatile", "openai/gpt-oss-120b", "moonshotai/kimi-k2-instruct"),
        note="高速推理服务，兼容 OpenAI API。",
    ),
    ModelProvider(
        id="hunyuan",
        name="腾讯混元 Hunyuan",
        base_url="https://api.hunyuan.cloud.tencent.com/v1",
        api_key_config_key="api_key.hunyuan",
        api_key_env_var="HUNYUAN_API_KEY",
        default_model="hunyuan-turbos-latest",
        model_examples=("hunyuan-turbos-latest", "hunyuan-lite"),
        note="兼容 OpenAI API。",
    ),
    ModelProvider(
        id="sensenova",
        name="商汤科技 SenseNova AI",
        base_url="https://token.sensenova.cn/v1",
        api_key_config_key="api_key.sensenova",
        api_key_env_var="SENSENOVA_API_KEY",
        default_model="sensenova-6.7-flash-lite",
        model_examples=(
            "sensenova-6.7-flash-lite",
            "sensenova-u1-fast",
            "deepseek-v4-flash",
        ),
        note="兼容 OpenAI API。",
    ),
)


def get_model_providers() -> tuple[ModelProvider, ...]:
    return MODEL_PROVIDERS


def find_provider(ref: str) -> ModelProvider | None:
    normalized = ref.strip().lower()
    for provider in MODEL_PROVIDERS:
        if normalized in {provider.id.lower(), provider.name.lower()}:
            return provider
    return None


def infer_provider(*, base_url: str | None = None, model: str | None = None) -> ModelProvider | None:
    if base_url:
        normalized_base_url = base_url.rstrip("/")
        for provider in MODEL_PROVIDERS:
            if provider.base_url.rstrip("/") == normalized_base_url:
                return provider

    if model:
        normalized_model = model.lower()
        for provider in MODEL_PROVIDERS:
            if normalized_model in {m.lower() for m in provider.model_examples}:
                return provider
            if normalized_model == provider.default_model.lower():
                return provider
    return None


def get_provider_api_key(provider: ModelProvider, config_mgr: ConfigManager) -> str | None:
    return (
        config_mgr.get(provider.api_key_config_key)
        or os.getenv(provider.api_key_env_var)
    )


def get_active_api_key(
    provider: ModelProvider | None,
    config_mgr: ConfigManager,
    *,
    fallback_api_key: str | None = None,
) -> str | None:
    if provider:
        provider_api_key = get_provider_api_key(provider, config_mgr)
        if provider_api_key:
            return provider_api_key
    return fallback_api_key or config_mgr.get("api_key") or os.getenv("api_key")


def save_provider_api_key(provider: ModelProvider, config_mgr: ConfigManager, api_key: str) -> None:
    config_mgr.set(provider.api_key_config_key, api_key)


def fetch_provider_models(provider: ModelProvider, api_key: str, *, timeout: float = 20.0) -> list[str]:
    client = OpenAI(api_key=api_key, base_url=provider.base_url, timeout=timeout)
    response = client.models.list()
    data: Any = getattr(response, "data", response)
    models: list[str] = []
    for item in data:
        model_id = getattr(item, "id", None)
        if model_id is None and isinstance(item, dict):
            model_id = item.get("id")
        if model_id:
            models.append(str(model_id))
    return sorted(set(models), key=str.lower)
