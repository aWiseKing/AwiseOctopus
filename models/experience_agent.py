import json
import re
from .agent_errors import AgentOperationAbortedError, create_chat_completion
from .experience_memory import ExperienceMemoryManager

class ExperienceAgent:
    """专门负责经验总结和记录的 Agent"""
    
    def __init__(self, client, model):
        self.client = client
        self.model = model
        self.memory_manager = ExperienceMemoryManager()

    def _strip_think(self, text: str) -> str:
        if not text:
            return ""
        return re.sub(r"<think>[\s\S]*?</think>", "", str(text), flags=re.IGNORECASE).strip()

    def _extract_score(self, text: str):
        cleaned = self._strip_think(text)
        s = cleaned.strip()

        if s.startswith("{") and s.endswith("}"):
            try:
                obj = json.loads(s)
            except Exception:
                obj = None
            if isinstance(obj, dict):
                for key in ("score", "rating", "value"):
                    if key in obj:
                        try:
                            return float(obj[key])
                        except Exception:
                            return None

        m = re.search(r"(?<![\d.])(?:0(?:\.\d+)?|1(?:\.0+)?)(?![\d.])", s)
        if not m:
            return None
        try:
            return float(m.group(0))
        except Exception:
            return None
        
    def _distill_process_log(self, process_log):
        """使用 LLM 提炼 process_log 内容，避免上下文过重"""
        prompt = (
            "你是一个经验提炼专家。请提炼以下任务的执行过程日志，保留关键步骤、核心决策和错误原因，"
            "去除冗余的上下文、代码细节或过长的原始输出。提炼后的内容需要尽可能简练，字数不要过多。\n\n"
            f"原始过程日志：\n{process_log}"
        )
        try:
            response = create_chat_completion(
                self.client,
                stage="经验提炼阶段",
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except AgentOperationAbortedError as e:
            print(f"[经验总结 Agent] 提炼过程已跳过: {e}")
            return str(process_log)[:500] + "...(模型服务异常，已跳过提炼)"
        except Exception as e:
            print(f"[经验总结 Agent] 提炼过程日志失败: {e}")
            # 如果提炼失败，则截断返回
            return str(process_log)[:500] + "...(提炼失败，已截断)"
            
    def _evaluate_experience(self, instruction, distilled_log, result):
        """使用 LLM 评估任务得分"""
        prompt = (
            "你是一个任务评估专家。请根据以下信息，评估任务的执行是否成功。\n\n"
            f"原始任务指令：\n{instruction}\n\n"
            f"提炼后的执行过程：\n{distilled_log}\n\n"
            f"最终结果：\n{result}\n\n"
            "请给出一个 0.0 到 1.0 之间的浮点数作为评分（1.0 表示完美完成，0.0 表示完全失败）。\n"
            "评分标准：\n"
            "- 1.0: 完美解决，没有任何错误\n"
            "- 0.8: 基本解决，但有些许瑕疵\n"
            "- 0.5: 部分解决，存在明显问题\n"
            "- 0.2: 严重错误，偏离目标\n"
            "- 0.0: 完全失败或崩溃\n"
            "请直接回复这个浮点数，不要输出任何其他内容，也不要包含 <think> 标签或其他标签。"
        )
        try:
            response = create_chat_completion(
                self.client,
                stage="经验评估阶段",
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=10,
            )
            raw = response.choices[0].message.content or ""
            score = self._extract_score(raw)
            cleaned_preview = self._strip_think(raw).replace("\n", " ").strip()[:200]
            print(f"[经验总结 Agent] 评估回复(清洗后): {cleaned_preview}")

            if score is None:
                return 0.5

            return max(0.0, min(1.0, float(score)))
        except AgentOperationAbortedError as e:
            print(f"\n[经验总结 Agent] 评估已跳过，默认给予 0.5 分: {e}")
            return 0.5
        except Exception as e:
            print(f"\n[经验总结 Agent] 评估失败，默认给予 0.5 分: {e}")
            return 0.5

    def _parse_long_term_memories(self, text: str) -> list[dict]:
        cleaned = self._strip_think(text)
        try:
            data = json.loads(cleaned)
        except Exception:
            start = cleaned.find("[")
            end = cleaned.rfind("]")
            if start < 0 or end < start:
                return []
            try:
                data = json.loads(cleaned[start : end + 1])
            except Exception:
                return []
        if isinstance(data, dict):
            data = data.get("memories") or data.get("items") or []
        if not isinstance(data, list):
            return []
        items = []
        for item in data:
            if not isinstance(item, dict):
                continue
            content = str(item.get("content") or item.get("memory") or "").strip()
            if not content:
                continue
            try:
                confidence = float(item.get("confidence", 0.0))
                importance = float(item.get("importance", 0.0))
            except Exception:
                continue
            if confidence < 0.7 or importance < 0.6:
                continue
            items.append(
                {
                    "content": content,
                    "scope": str(item.get("scope") or "user_fact").strip() or "user_fact",
                    "summary": str(item.get("summary") or content[:160]).strip(),
                    "confidence": max(0.0, min(1.0, confidence)),
                    "importance": max(0.0, min(1.0, importance)),
                }
            )
        return items[:5]

    def _extract_long_term_memories(self, instruction, distilled_log, result) -> list[dict]:
        prompt = (
            "你是长期记忆抽取器。请从这次任务中抽取可跨会话复用的稳定信息，"
            "只保留用户偏好、稳定事实、项目背景、长期约束。不要记录临时闲聊、一次性任务细节、隐私敏感内容或低置信内容。\n\n"
            f"用户指令：\n{instruction}\n\n"
            f"执行过程摘要：\n{distilled_log}\n\n"
            f"最终结果：\n{result}\n\n"
            "请只输出 JSON 数组。每项格式："
            '{"content":"...","scope":"user_preference|stable_fact|project_context","summary":"...","confidence":0.0到1.0,"importance":0.0到1.0}'
        )
        try:
            response = create_chat_completion(
                self.client,
                stage="长期记忆抽取阶段",
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            return self._parse_long_term_memories(response.choices[0].message.content or "")
        except AgentOperationAbortedError as e:
            print(f"[经验总结 Agent] 长期记忆抽取已跳过: {e}")
            return []
        except Exception as e:
            print(f"[经验总结 Agent] 长期记忆抽取失败: {e}")
            return []

    def _save_long_term_memories(self, memories, session_id=None):
        saved = 0
        for item in memories:
            try:
                similar = self.memory_manager.search_memories(
                    mode="long_term",
                    query=item["content"],
                    top_k=1,
                )
                if similar:
                    existing = similar[0]
                    existing_text = str(existing.get("content") or "").strip()
                    if existing_text == item["content"]:
                        self.memory_manager.update_memory(
                            existing["id"],
                            summary=item["summary"],
                            confidence=max(float(existing.get("confidence") or 0), item["confidence"]),
                            importance=max(float(existing.get("importance") or 0), item["importance"]),
                        )
                        saved += 1
                        continue
                self.memory_manager.add_memory(
                    mode="long_term",
                    scope=item["scope"],
                    session_id=session_id,
                    content=item["content"],
                    summary=item["summary"],
                    confidence=item["confidence"],
                    importance=item["importance"],
                )
                saved += 1
            except Exception as e:
                print(f"[经验总结 Agent] 保存长期记忆失败: {e}")
        return saved

    def process_experience_stream(self, task_type, instruction, process_log, result, session_id=None):
        """流式处理并记录经验，返回日志状态"""
        yield f"[经验总结 Agent] 正在提炼执行过程..."
        
        # 1. 提炼 process_log
        distilled_log = self._distill_process_log(process_log)
        
        yield f"[经验总结 Agent] 正在评估执行结果..."
        # 2. 评估分数
        score = self._evaluate_experience(instruction, distilled_log, result)
        
        yield f"[经验总结 Agent] 正在保存经验数据..."
        # 3. 保存经验
        try:
            self.memory_manager.add_experience(
                task_type, instruction, distilled_log, result, score, session_id=session_id
            )
        except Exception as e:
            yield f"[经验总结 Agent] 保存经验失败，已跳过: {e}"
        else:
            yield f"[经验总结 Agent] 经验已记录 (得分: {score})"

        yield f"[经验总结 Agent] 正在抽取长期记忆..."
        long_term_items = self._extract_long_term_memories(instruction, distilled_log, result)
        saved_count = self._save_long_term_memories(long_term_items, session_id=session_id)
        yield f"[经验总结 Agent] 长期记忆已更新 ({saved_count} 条)"
