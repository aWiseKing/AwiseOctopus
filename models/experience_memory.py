from __future__ import annotations

from . import memory as memory_module
from .memory import MemoryManager

try:
    import chromadb
except ImportError:
    chromadb = None


class ExperienceMemoryManager:
    _instance = None

    @staticmethod
    def _resolve_paths(
        db_path: str | None = None,
        chroma_path: str | None = None,
    ) -> tuple[str, str]:
        return MemoryManager._resolve_paths(db_path, chroma_path)

    def __new__(cls, db_path: str | None = None, chroma_path: str | None = None):
        resolved_db_path, resolved_chroma_path = cls._resolve_paths(db_path, chroma_path)
        current_key = getattr(cls._instance, "_path_key", None) if cls._instance is not None else None
        if cls._instance is None or current_key != (resolved_db_path, resolved_chroma_path):
            cls._instance = super(ExperienceMemoryManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: str | None = None, chroma_path: str | None = None):
        resolved_db_path, resolved_chroma_path = self._resolve_paths(db_path, chroma_path)
        if self._initialized:
            return

        self._initialized = True
        self._path_key = (resolved_db_path, resolved_chroma_path)
        memory_module.chromadb = chromadb
        self._manager = MemoryManager(db_path=resolved_db_path, chroma_path=resolved_chroma_path)
        self.db_path = self._manager.db_path
        self.chroma_path = self._manager.chroma_path
        self.conn = self._manager.conn
        self.chroma_client = self._manager.chroma_client
        self.collection = self._manager.collection

    def add_experience(
        self,
        task_type,
        instruction,
        process_log,
        result,
        success_score,
        session_id=None,
    ):
        """记录任务经验，保持旧接口兼容。"""
        return self._manager.add_experience(
            task_type,
            instruction,
            process_log,
            result,
            success_score,
            session_id=session_id,
        )

    def search_experience(self, task_type, instruction, top_k=3, session_id=None):
        """搜索历史经验，保持旧接口兼容。"""
        return self._manager.search_experience(
            task_type,
            instruction,
            top_k=top_k,
            session_id=session_id,
        )

    def build_memory_context(self, agent_role, user_request, session_id=None, **kwargs):
        return self._manager.build_memory_context(
            agent_role,
            user_request,
            session_id=session_id,
            **kwargs,
        )

    def upsert_session_summary(self, **kwargs):
        return self._manager.upsert_session_summary(**kwargs)

    def upsert_task_working_set(self, **kwargs):
        return self._manager.upsert_task_working_set(**kwargs)

    def add_memory(self, **kwargs):
        return self._manager.add_memory(**kwargs)

    def search_memories(self, **kwargs):
        return self._manager.search_memories(**kwargs)

    def update_memory(self, memory_id, **kwargs):
        return self._manager.update_memory(memory_id, **kwargs)

    def close(self):
        self._manager.close()
        self._initialized = False
        type(self)._instance = None
