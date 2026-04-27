import os
import json
import sqlite3
import uuid
import datetime
from pathlib import Path

try:
    import chromadb
except ImportError:
    chromadb = None

class ExperienceMemoryManager:
    _instance = None

    def __new__(cls, db_path="experience.db", chroma_path="experience_vector"):
        if cls._instance is None:
            cls._instance = super(ExperienceMemoryManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path="data/experience.db", chroma_path="data/experience_vector"):
        if self._initialized:
            return
            
        self._initialized = True
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        self.db_path = db_path
        self.chroma_path = chroma_path
        
        # Initialize SQLite
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._create_table()
        self._migrate_table()
        
        # Initialize ChromaDB
        if chromadb:
            self.chroma_client = chromadb.PersistentClient(path=self.chroma_path)
            self.collection = self.chroma_client.get_or_create_collection(name="agent_experiences")
        else:
            self.chroma_client = None
            self.collection = None

    def _create_table(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS experiences (
                id TEXT PRIMARY KEY,
                task_type TEXT,
                instruction TEXT,
                process_log TEXT,
                result TEXT,
                success_score REAL,
                weight REAL,
                created_at TIMESTAMP
            )
        ''')
        self.conn.commit()

    def _migrate_table(self):
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA table_info(experiences)")
        existing_cols = {row[1] for row in cursor.fetchall() if row and len(row) > 1}

        if "session_id" not in existing_cols:
            cursor.execute("ALTER TABLE experiences ADD COLUMN session_id TEXT")

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_experiences_task_session_time
            ON experiences(task_type, session_id, created_at)
            """
        )
        self.conn.commit()

    def add_experience(self, task_type, instruction, process_log, result, success_score, session_id=None):
        """记录任务经验，存储到 SQLite 和 ChromaDB"""
        exp_id = str(uuid.uuid4())
        created_at = datetime.datetime.now().isoformat()
        weight = float(success_score)
        
        # 1. 存入 SQLite
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO experiences (id, task_type, instruction, process_log, result, success_score, weight, created_at, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (exp_id, task_type, instruction, str(process_log), str(result), float(success_score), weight, created_at, session_id))
        self.conn.commit()
        
        # 2. 存入 ChromaDB
        if self.collection:
            metadata = {"task_type": task_type}
            if session_id is not None:
                metadata["session_id"] = session_id
            self.collection.add(
                documents=[instruction],
                metadatas=[metadata],
                ids=[exp_id]
            )

    def search_experience(self, task_type, instruction, top_k=3, session_id=None):
        """搜索历史经验，根据 weight 分为成功和失败两类"""
        if not self.collection:
            return ""
            
        # 1. 向量检索最相关的 instruction
        where_conditions = [{"task_type": task_type}]
        if session_id is not None:
            where_conditions.append({"session_id": session_id})
            
        if len(where_conditions) > 1:
            where = {"$and": where_conditions}
        else:
            where = where_conditions[0]

        results = self.collection.query(
            query_texts=[instruction],
            n_results=top_k * 2,
            where=where
        )
         
        if not results['ids'] or not results['ids'][0]:
            return ""
            
        # 过滤距离大于 0.3 的结果
        exp_ids = []
        if 'distances' in results and results['distances']:
            for i, distance in enumerate(results['distances'][0]):
                if distance <= 0.38:
                    exp_ids.append(results['ids'][0][i])
        else:
            exp_ids = results['ids'][0]
            
        if not exp_ids:
            return ""
        
        # 2. 从 SQLite 获取详细信息
        placeholders = ','.join('?' for _ in exp_ids)
        cursor = self.conn.cursor()
        cursor.execute(f'''
            SELECT id, instruction, process_log, result, weight 
            FROM experiences 
            WHERE id IN ({placeholders})
            ORDER BY weight DESC
        ''', exp_ids)
        
        rows = cursor.fetchall()
        
        successful_exps = []
        failed_exps = []
        
        for row in rows:
            exp = {
                "instruction": row[1],
                "process_log": row[2],
                "result": row[3],
                "weight": row[4]
            }
            if exp["weight"] >= 0.6:
                if len(successful_exps) < top_k:
                    successful_exps.append(exp)
            else:
                if len(failed_exps) < top_k:
                    failed_exps.append(exp)
                    
        if not successful_exps and not failed_exps:
            return ""
            
        # 3. 格式化输出
        hint = "【历史经验参考】\n针对类似的任务，系统有以下经验记录：\n"
        
        if successful_exps:
            hint += "\n✅ 成功的做法（高分经验）：\n"
            for i, exp in enumerate(successful_exps, 1):
                hint += f"  {i}. 任务: {exp['instruction']}\n     过程: {exp['process_log']}\n     结果: {exp['result']}\n"
                
        if failed_exps:
            hint += "\n❌ 失败的做法（请避免这些错误）：\n"
            for i, exp in enumerate(failed_exps, 1):
                hint += f"  {i}. 任务: {exp['instruction']}\n     过程: {exp['process_log']}\n     结果: {exp['result']}\n"
                
        return hint

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass
