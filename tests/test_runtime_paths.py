import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from models.config_manager import ConfigManager
from models.experience_memory import ExperienceMemoryManager
import models.experience_memory as experience_memory
from models.runtime_paths import resource_path, user_data_dir
from models.session_store import SessionStore
from models.tools.search_local_file import _everything_dll_path


class TestRuntimePaths(unittest.TestCase):
    def setUp(self) -> None:
        ConfigManager._instance = None
        ExperienceMemoryManager._instance = None
        experience_memory.chromadb = None

    def test_user_data_dir_windows(self) -> None:
        path = user_data_dir(
            platform="win32",
            environ={"APPDATA": "/tmp/ada/AppData/Roaming"},
            home="/tmp/ada",
            create=False,
        )
        self.assertEqual(path, Path("/tmp/ada/AppData/Roaming/AwiseOctopus").resolve())

    def test_user_data_dir_macos(self) -> None:
        path = user_data_dir(platform="darwin", environ={}, home="/Users/ada", create=False)
        self.assertEqual(path, Path("/Users/ada/Library/Application Support/AwiseOctopus"))

    def test_user_data_dir_linux(self) -> None:
        path = user_data_dir(platform="linux", environ={}, home="/home/ada", create=False)
        self.assertEqual(path, Path("/home/ada/.local/share/AwiseOctopus").resolve())

    def test_default_databases_use_user_data_dir(self) -> None:
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"AWISEOCTOPUS_DATA_DIR": td}, clear=False):
            config = ConfigManager()
            session_store = SessionStore()
            memory = ExperienceMemoryManager()
            try:
                self.assertEqual(config.db_path, str(Path(td).resolve() / "config.db"))
                self.assertEqual(session_store.db_path, str(Path(td).resolve() / "session.db"))
                self.assertEqual(memory.db_path, str(Path(td).resolve() / "experience.db"))
                self.assertEqual(memory.chroma_path, str(Path(td).resolve() / "experience_vector"))
            finally:
                session_store.close()
                memory.close()

    def test_resource_path_uses_override(self) -> None:
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"AWISEOCTOPUS_RESOURCE_DIR": td}, clear=False):
            self.assertEqual(resource_path("skills"), Path(td).resolve() / "skills")

    def test_everything_dll_path_uses_resource_dir(self) -> None:
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"AWISEOCTOPUS_RESOURCE_DIR": td}, clear=False):
            expected = Path(td).resolve() / "libs" / "Everything_SDK" / "dll" / "Everything64.dll"
            self.assertEqual(Path(_everything_dll_path()), expected)


if __name__ == "__main__":
    unittest.main()
