import unittest
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from rich.console import Console

from acli.commands.chat import (
    _has_model_setup,
    _parse_model_command,
    _run_first_use_model_setup,
)
from acli.model_registry import find_provider, infer_provider


class _FakeConfigManager:
    def __init__(self, data: dict[str, str] | None = None) -> None:
        self.data = dict(data or {})

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value: str) -> None:
        self.data[key] = value


class TestModelRegistry(unittest.TestCase):
    def test_find_provider_by_id(self) -> None:
        provider = find_provider("deepseek")
        self.assertIsNotNone(provider)
        self.assertEqual(provider.base_url, "https://api.deepseek.com/v1")
        self.assertEqual(provider.api_key_config_key, "api_key.deepseek")

    def test_find_provider_sensenova_by_id(self) -> None:
        provider = find_provider("sensenova")
        self.assertIsNotNone(provider)
        self.assertEqual(provider.base_url, "https://token.sensenova.cn/v1")
        self.assertEqual(provider.default_model, "sensenova-6.7-flash-lite")
        self.assertIn("sensenova-u1-fast", provider.model_examples)

    def test_infer_provider_by_base_url(self) -> None:
        provider = infer_provider(base_url="https://api.openai.com/v1/", model=None)
        self.assertIsNotNone(provider)
        self.assertEqual(provider.id, "openai")

    def test_infer_provider_by_sensenova_model(self) -> None:
        provider = infer_provider(model="sensenova-u1-fast")
        self.assertIsNotNone(provider)
        self.assertEqual(provider.id, "sensenova")

    def test_parse_model_command_keeps_quoted_model(self) -> None:
        parts = _parse_model_command('/model switch openrouter "openai/gpt-5.1"')
        self.assertEqual(parts, ["/model", "switch", "openrouter", "openai/gpt-5.1"])

    def test_has_model_setup_requires_base_url_model_and_key(self) -> None:
        ctx = SimpleNamespace(
            api_key=None,
            base_url="https://api.deepseek.com/v1",
            model="deepseek-v4-flash",
        )
        self.assertFalse(_has_model_setup(_FakeConfigManager(), ctx))
        self.assertTrue(
            _has_model_setup(
                _FakeConfigManager(
                    {
                        "base_url": "https://api.deepseek.com/v1",
                        "MODEL": "deepseek-v4-flash",
                        "api_key.deepseek": "secret",
                    }
                ),
                ctx,
            )
        )

    def test_first_use_model_setup_saves_provider_defaults(self) -> None:
        ctx = SimpleNamespace(api_key=None, base_url="", model="")
        config_mgr = _FakeConfigManager()
        console = Console(file=StringIO(), force_terminal=False, no_color=True)
        with patch(
            "acli.commands.chat.Prompt.ask",
            side_effect=["deepseek", "", "deepseek-v4-pro", "secret"],
        ):
            _run_first_use_model_setup(ctx, console, config_mgr)

        self.assertEqual(ctx.base_url, "https://api.deepseek.com/v1")
        self.assertEqual(ctx.model, "deepseek-v4-pro")
        self.assertEqual(ctx.api_key, "secret")
        self.assertEqual(config_mgr.get("base_url"), "https://api.deepseek.com/v1")
        self.assertEqual(config_mgr.get("MODEL"), "deepseek-v4-pro")
        self.assertEqual(config_mgr.get("api_key.deepseek"), "secret")


if __name__ == "__main__":
    unittest.main()
