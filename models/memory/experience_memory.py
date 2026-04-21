import hashlib
import json
import os
import sqlite3
import threading
import time
import uuid


def _utc_ts() -> int:
    return int(time.time())


def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()


def _truncate(text: str, limit: int) -> str:
    if text is None:
        return ""
    text = str(text)
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


def _parse_bool_success(success) -> int:
    return 1 if bool(success) else 0


class ExperienceMemoryManager:
    _singleton_lock = threading.Lock()
    _singleton_instance = None

    @classmethod
    def get_singleton(cls, client=None, model=None):
        with cls._singleton_lock:
            if cls._singleton_instance is None:
                cls._singleton_instance = cls.from_env(client=client, model=model)
            else:
                if client is not None:
                    cls._singleton_instance.client = client
                if model is not None:
                    cls._singleton_instance.chat_model = model
            return cls._singleton_instance

    @classmethod
    def from_env(cls, client=None, model=None):
        db_path = os.getenv("EXPERIENCE_DB_PATH", os.path.join(".", "data", "experience.db"))
        chroma_path = os.getenv("CHROMA_PATH", os.path.join(".", "data", "chroma"))
        chroma_collection = os.getenv("CHROMA_COLLECTION", "awise_experiences")
        embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        alpha = float(os.getenv("EXPERIENCE_ALPHA", "1"))
        beta = float(os.getenv("EXPERIENCE_BETA", "1"))
        top_k = int(os.getenv("EXPERIENCE_TOP_K", "5"))
        raw_k = int(os.getenv("EXPERIENCE_RAW_K", "20"))
        enabled = os.getenv("EXPERIENCE_ENABLED", "1").strip().lower() not in {"0", "false", "off"}
        return cls(
            client=client,
            chat_model=model,
            db_path=db_path,
            chroma_path=chroma_path,
            chroma_collection=chroma_collection,
            embedding_model=embedding_model,
            alpha=alpha,
            beta=beta,
            top_k=top_k,
            raw_k=raw_k,
            enabled=enabled,
        )

    def __init__(
        self,
        client,
        chat_model,
        db_path: str,
        chroma_path: str,
        chroma_collection: str,
        embedding_model: str,
        alpha: float,
        beta: float,
        top_k: int,
        raw_k: int,
        enabled: bool = True,
    ):
        self.client = client
        self.chat_model = chat_model
        self.db_path = db_path
        self.chroma_path = chroma_path
        self.chroma_collection = chroma_collection
        self.embedding_model = embedding_model
        self.alpha = alpha
        self.beta = beta
        self.top_k = top_k
        self.raw_k = raw_k
        self.enabled = enabled

        self._db_lock = threading.Lock()
        self._chroma_lock = threading.Lock()
        self._collection = None

        if self.enabled:
            self._ensure_dirs()
            self._ensure_db_schema()

    def _ensure_dirs(self):
        db_dir = os.path.dirname(os.path.abspath(self.db_path))
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        chroma_dir = os.path.abspath(self.chroma_path)
        if chroma_dir and not os.path.exists(chroma_dir):
            os.makedirs(chroma_dir, exist_ok=True)

    def _connect(self):
        con = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        con.execute("PRAGMA journal_mode=WAL;")
        con.execute("PRAGMA synchronous=NORMAL;")
        return con

    def _ensure_db_schema(self):
        with self._db_lock:
            con = self._connect()
            try:
                con.execute(
                    """
                    CREATE TABLE IF NOT EXISTS experiences (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_type TEXT NOT NULL,
                        event_key TEXT NOT NULL,
                        summary TEXT NOT NULL,
                        success INTEGER NOT NULL,
                        created_at INTEGER NOT NULL,
                        metadata_json TEXT,
                        chroma_id TEXT
                    )
                    """
                )
                con.execute(
                    """
                    CREATE TABLE IF NOT EXISTS event_stats (
                        event_type TEXT NOT NULL,
                        event_key TEXT NOT NULL,
                        success_count INTEGER NOT NULL,
                        failure_count INTEGER NOT NULL,
                        weight REAL NOT NULL,
                        updated_at INTEGER NOT NULL,
                        PRIMARY KEY (event_type, event_key)
                    )
                    """
                )
                con.commit()
            finally:
                con.close()

    def _get_collection(self):
        if self._collection is not None:
            return self._collection
        with self._chroma_lock:
            if self._collection is not None:
                return self._collection
            import chromadb

            client = chromadb.PersistentClient(path=self.chroma_path)
            self._collection = client.get_or_create_collection(self.chroma_collection)
            return self._collection

    def _embed_texts(self, texts):
        if not texts:
            return []
        if self.client:
            resp = self.client.embeddings.create(model=self.embedding_model, input=texts)
            return [item.embedding for item in resp.data]

        dim = 256
        out = []
        for t in texts:
            t = str(t or "")
            vec = [0.0] * dim
            for raw in t.split():
                tok = raw.strip()
                if not tok:
                    continue
                h = hashlib.sha1(tok.encode("utf-8", errors="ignore")).digest()
                idx = int.from_bytes(h[:2], "big") % dim
                sign = 1.0 if (h[2] % 2 == 0) else -1.0
                vec[idx] += sign
            norm = sum(v * v for v in vec) ** 0.5
            if norm > 0:
                vec = [v / norm for v in vec]
            out.append(vec)
        return out

    def _update_event_stats(self, con, event_type: str, event_key: str, success_int: int):
        cur = con.execute(
            "SELECT success_count, failure_count FROM event_stats WHERE event_type=? AND event_key=?",
            (event_type, event_key),
        )
        row = cur.fetchone()
        if row is None:
            success_count = 1 if success_int else 0
            failure_count = 0 if success_int else 1
        else:
            success_count, failure_count = int(row[0]), int(row[1])
            if success_int:
                success_count += 1
            else:
                failure_count += 1

        denom = success_count + failure_count + self.alpha + self.beta
        weight = (success_count + self.alpha) / denom if denom > 0 else 0.5
        now = _utc_ts()
        con.execute(
            """
            INSERT INTO event_stats(event_type, event_key, success_count, failure_count, weight, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_type, event_key) DO UPDATE SET
                success_count=excluded.success_count,
                failure_count=excluded.failure_count,
                weight=excluded.weight,
                updated_at=excluded.updated_at
            """,
            (event_type, event_key, success_count, failure_count, float(weight), now),
        )
        return success_count, failure_count, float(weight)

    def _get_weight_map(self, pairs):
        if not pairs:
            return {}
        uniq = list({(et, ek) for et, ek in pairs})
        with self._db_lock:
            con = self._connect()
            try:
                out = {}
                for et, ek in uniq:
                    cur = con.execute(
                        "SELECT weight, success_count, failure_count FROM event_stats WHERE event_type=? AND event_key=?",
                        (et, ek),
                    )
                    row = cur.fetchone()
                    if row:
                        out[(et, ek)] = {
                            "weight": float(row[0]),
                            "success_count": int(row[1]),
                            "failure_count": int(row[2]),
                        }
                    else:
                        out[(et, ek)] = {"weight": float((self.alpha) / (self.alpha + self.beta)), "success_count": 0, "failure_count": 0}
                return out
            finally:
                con.close()

    def _summarize_dag_task(self, task_info, result_text: str, success: bool):
        if not self.client or not self.chat_model:
            title = task_info.get("title") or task_info.get("id") or "task"
            base = f"适用场景: {title}\n要点: {title}\n注意事项: \n原因: {'成功' if success else '失败'}"
            return base

        task_type = task_info.get("type", "agent")
        tool_name = task_info.get("tool")
        tool_input = task_info.get("input", {})
        instruction = task_info.get("instruction", "")
        title = task_info.get("title", "")

        payload = {
            "task_id": task_info.get("id", ""),
            "title": title,
            "task_type": task_type,
            "tool_name": tool_name,
            "tool_input": tool_input,
            "instruction": _truncate(instruction, 1200),
            "result": _truncate(result_text, 2000),
            "success": bool(success),
        }
        prompt = (
            "你是一个经验沉淀助手。给定一次子任务执行的输入与结果，请总结“完成该事件的方案与思路”。\n"
            "要求：\n"
            "1) 只输出纯文本；\n"
            "2) 用固定结构：适用场景/操作步骤要点/注意事项坑/成功或失败原因；\n"
            "3) 语句简洁，可复用；\n"
            "4) 不要泄露密钥、路径中的隐私信息；\n"
            "输入如下（JSON）：\n"
            f"{json.dumps(payload, ensure_ascii=False)}"
        )
        resp = self.client.chat.completions.create(
            model=self.chat_model,
            messages=[
                {"role": "system", "content": "你是一个严谨的经验总结助手。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        return (resp.choices[0].message.content or "").strip()

    def _summarize_user_request(self, user_request: str, final_output_text: str, success: bool):
        if not self.client or not self.chat_model:
            event_key = "user_request:" + _sha1(_truncate(user_request, 400))
            summary = f"适用场景: { _truncate(user_request, 80) }\n操作步骤要点: \n注意事项坑: \n原因: {'成功' if success else '失败'}"
            return event_key, summary

        payload = {
            "user_request": _truncate(user_request, 2000),
            "final_output": _truncate(final_output_text, 2500),
            "success": bool(success),
        }
        prompt = (
            "你是一个经验沉淀助手。给定一次用户请求及最终输出，请生成：\n"
            "A) event_key：一个短的意图标签（10~30字，中文优先，不含标点，尽量可复用）；\n"
            "B) summary：总结“完成该事件的方案与思路”，用固定结构：适用场景/操作步骤要点/注意事项坑/成功或失败原因。\n"
            "要求：\n"
            "- 只输出 JSON（不要 Markdown，不要解释），字段为 event_key、summary。\n"
            "- 不要包含密钥、token、具体本地绝对路径等隐私。\n"
            f"输入如下（JSON）：{json.dumps(payload, ensure_ascii=False)}"
        )
        resp = self.client.chat.completions.create(
            model=self.chat_model,
            messages=[
                {"role": "system", "content": "你是一个严谨的经验总结助手，只输出 JSON。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        content = (resp.choices[0].message.content or "").strip()
        try:
            obj = json.loads(content)
            event_key = str(obj.get("event_key", "")).strip()
            summary = str(obj.get("summary", "")).strip()
        except Exception:
            event_key = "user_request:" + _sha1(_truncate(user_request, 400))
            summary = content
        if not event_key:
            event_key = "user_request:" + _sha1(_truncate(user_request, 400))
        return event_key, summary

    def record_dag_task(self, task_info, result_text: str, success: bool, metadata=None):
        if not self.enabled:
            return
        task_type = task_info.get("type", "agent")
        if task_type == "tool":
            tool_name = task_info.get("tool") or ""
            event_key = "tool:" + tool_name
        else:
            title = (task_info.get("title") or "").strip()
            if title:
                event_key = "agent_title:" + title
            else:
                instr = task_info.get("instruction") or ""
                event_key = "agent_instr_hash:" + _sha1(_truncate(instr, 2000))
        summary = self._summarize_dag_task(task_info, result_text, success)
        self._record_event(
            event_type="dag_task",
            event_key=event_key,
            summary=summary,
            success=success,
            metadata=metadata or {},
        )

    def record_user_request(self, user_request: str, final_output_text: str, success: bool, metadata=None):
        if not self.enabled:
            return
        event_key, summary = self._summarize_user_request(user_request, final_output_text, success)
        self._record_event(
            event_type="user_request",
            event_key=event_key,
            summary=summary,
            success=success,
            metadata=metadata or {},
        )

    def _record_event(self, event_type: str, event_key: str, summary: str, success: bool, metadata):
        success_int = _parse_bool_success(success)
        now = _utc_ts()
        chroma_id = str(uuid.uuid4())
        meta = dict(metadata or {})
        meta.update({"event_type": event_type, "event_key": event_key, "success": bool(success), "created_at": now})
        metadata_json = json.dumps(meta, ensure_ascii=False)

        with self._db_lock:
            con = self._connect()
            try:
                con.execute(
                    """
                    INSERT INTO experiences(event_type, event_key, summary, success, created_at, metadata_json, chroma_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (event_type, event_key, summary or "", success_int, now, metadata_json, chroma_id),
                )
                _, _, weight = self._update_event_stats(con, event_type, event_key, success_int)
                con.commit()
            finally:
                con.close()

        try:
            emb = self._embed_texts([summary or ""])[0]
            collection = self._get_collection()
            with self._chroma_lock:
                collection.add(
                    ids=[chroma_id],
                    documents=[summary or ""],
                    embeddings=[emb],
                    metadatas=[{**meta, "weight": float(weight)}],
                )
        except Exception:
            return

    def search(self, query_text: str, top_k: int = None):
        if not self.enabled:
            return []
        if not query_text or not str(query_text).strip():
            return []
        k = int(top_k or self.top_k or 5)
        raw_k = max(int(self.raw_k or 20), k)

        try:
            q_emb = self._embed_texts([_truncate(str(query_text), 2000)])[0]
        except Exception:
            return []

        try:
            collection = self._get_collection()
            with self._chroma_lock:
                res = collection.query(
                    query_embeddings=[q_emb],
                    n_results=raw_k,
                    include=["documents", "metadatas", "distances"],
                )
        except Exception:
            return []

        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]

        pairs = []
        for m in metas:
            if not m:
                continue
            pairs.append((m.get("event_type", ""), m.get("event_key", "")))
        weight_map = self._get_weight_map(pairs)

        items = []
        for doc, meta, dist in zip(docs, metas, dists):
            if not meta:
                continue
            event_type = meta.get("event_type", "")
            event_key = meta.get("event_key", "")
            stat = weight_map.get((event_type, event_key), {"weight": float((self.alpha) / (self.alpha + self.beta)), "success_count": 0, "failure_count": 0})
            weight = float(stat["weight"])
            try:
                dist_f = float(dist)
            except Exception:
                dist_f = 1.0
            sim = max(0.0, min(1.0, 1.0 - dist_f))
            score = sim * 0.7 + weight * 0.3
            items.append(
                {
                    "event_type": event_type,
                    "event_key": event_key,
                    "weight": weight,
                    "success_count": int(stat.get("success_count", 0)),
                    "failure_count": int(stat.get("failure_count", 0)),
                    "similarity": sim,
                    "score": score,
                    "summary": str(doc or "").strip(),
                }
            )

        items.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        return items[:k]

    def format_injected_context(self, query_text: str, top_k: int = None):
        items = self.search(query_text=query_text, top_k=top_k)
        if not items:
            return ""
        lines = ["历史经验（向量检索召回，已按权重重排）："]
        for i, it in enumerate(items, 1):
            header = f"{i}. [{it.get('event_type')} | {it.get('event_key')}] weight={it.get('weight'):.3f} (S={it.get('success_count')},F={it.get('failure_count')})"
            lines.append(header)
            lines.append(_truncate(it.get("summary", ""), 900))
        return "\n".join(lines).strip()
