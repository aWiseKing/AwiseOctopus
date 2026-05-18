import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from models.config_manager import ConfigManager
from models.personas import DEFAULT_PERSONA_NAME, list_personas, load_persona_prompt


class TestPersonaLoader(unittest.TestCase):
    def setUp(self) -> None:
        self._reset_config_manager()

    def tearDown(self) -> None:
        self._reset_config_manager()

    def _reset_config_manager(self) -> None:
        instance = ConfigManager._instance
        if instance is not None and getattr(instance, "conn", None) is not None:
            instance.conn.close()
        ConfigManager._instance = None

    def _write_prompt(self, root: str, persona_name: str, prompt_name: str, content: str) -> None:
        prompt_path = (
            Path(root)
            / "models"
            / "personas"
            / persona_name
            / f"{prompt_name}.md"
        )
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(content, encoding="utf-8")

    def test_load_persona_prompt_defaults_to_gongnenglove(self) -> None:
        with tempfile.TemporaryDirectory() as resource_dir, tempfile.TemporaryDirectory() as data_dir:
            self._write_prompt(resource_dir, DEFAULT_PERSONA_NAME, "demo", "default prompt")

            with patch.dict(
                os.environ,
                {
                    "AWISEOCTOPUS_RESOURCE_DIR": resource_dir,
                    "AWISEOCTOPUS_DATA_DIR": data_dir,
                },
                clear=False,
            ):
                self._reset_config_manager()
                try:
                    self.assertEqual(load_persona_prompt("demo"), "default prompt")
                finally:
                    self._reset_config_manager()

    def test_load_persona_prompt_uses_configured_persona(self) -> None:
        with tempfile.TemporaryDirectory() as resource_dir, tempfile.TemporaryDirectory() as data_dir:
            self._write_prompt(resource_dir, DEFAULT_PERSONA_NAME, "demo", "default prompt")
            self._write_prompt(resource_dir, "OtherPersona", "demo", "other prompt")

            with patch.dict(
                os.environ,
                {
                    "AWISEOCTOPUS_RESOURCE_DIR": resource_dir,
                    "AWISEOCTOPUS_DATA_DIR": data_dir,
                },
                clear=False,
            ):
                self._reset_config_manager()
                try:
                    ConfigManager().set("persona_name", "OtherPersona")
                    self.assertEqual(load_persona_prompt("demo"), "other prompt")
                finally:
                    self._reset_config_manager()

    def test_load_persona_prompt_renders_template_vars(self) -> None:
        with tempfile.TemporaryDirectory() as resource_dir, tempfile.TemporaryDirectory() as data_dir:
            self._write_prompt(
                resource_dir,
                DEFAULT_PERSONA_NAME,
                "demo",
                "hello {name}",
            )

            with patch.dict(
                os.environ,
                {
                    "AWISEOCTOPUS_RESOURCE_DIR": resource_dir,
                    "AWISEOCTOPUS_DATA_DIR": data_dir,
                },
                clear=False,
            ):
                self._reset_config_manager()
                try:
                    self.assertEqual(
                        load_persona_prompt("demo", name="world"), "hello world"
                    )
                finally:
                    self._reset_config_manager()

    def test_list_personas_returns_directories(self) -> None:
        with tempfile.TemporaryDirectory() as resource_dir, tempfile.TemporaryDirectory() as data_dir:
            self._write_prompt(resource_dir, DEFAULT_PERSONA_NAME, "demo", "default prompt")
            self._write_prompt(resource_dir, "OtherPersona", "demo", "other prompt")

            with patch.dict(
                os.environ,
                {
                    "AWISEOCTOPUS_RESOURCE_DIR": resource_dir,
                    "AWISEOCTOPUS_DATA_DIR": data_dir,
                },
                clear=False,
            ):
                self._reset_config_manager()
                try:
                    self.assertEqual(
                        list_personas(), [DEFAULT_PERSONA_NAME, "OtherPersona"]
                    )
                finally:
                    self._reset_config_manager()

    def test_load_persona_prompt_raises_for_missing_persona(self) -> None:
        with tempfile.TemporaryDirectory() as resource_dir, tempfile.TemporaryDirectory() as data_dir:
            self._write_prompt(resource_dir, DEFAULT_PERSONA_NAME, "demo", "default prompt")

            with patch.dict(
                os.environ,
                {
                    "AWISEOCTOPUS_RESOURCE_DIR": resource_dir,
                    "AWISEOCTOPUS_DATA_DIR": data_dir,
                },
                clear=False,
            ):
                self._reset_config_manager()
                try:
                    with self.assertRaises(FileNotFoundError):
                        load_persona_prompt("demo", persona_name="MissingPersona")
                finally:
                    self._reset_config_manager()

    def test_load_persona_prompt_raises_for_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as resource_dir, tempfile.TemporaryDirectory() as data_dir:
            with patch.dict(
                os.environ,
                {
                    "AWISEOCTOPUS_RESOURCE_DIR": resource_dir,
                    "AWISEOCTOPUS_DATA_DIR": data_dir,
                },
                clear=False,
            ):
                self._reset_config_manager()
                try:
                    persona_dir = (
                        Path(resource_dir) / "models" / "personas" / DEFAULT_PERSONA_NAME
                    )
                    persona_dir.mkdir(parents=True, exist_ok=True)
                    with self.assertRaises(FileNotFoundError):
                        load_persona_prompt("demo")
                finally:
                    self._reset_config_manager()


if __name__ == "__main__":
    unittest.main()
