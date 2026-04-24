import json
import re
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
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            return response.choices[0].message.content.strip()
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
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=10
            )
            raw = response.choices[0].message.content or ""
            score = self._extract_score(raw)
            cleaned_preview = self._strip_think(raw).replace("\n", " ").strip()[:200]
            print(f"[经验总结 Agent] 评估回复(清洗后): {cleaned_preview}")

            if score is None:
                return 0.5

            return max(0.0, min(1.0, float(score)))
        except Exception as e:
            print(f"\n[经验总结 Agent] 评估失败，默认给予 0.5 分: {e}")
            return 0.5

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
        self.memory_manager.add_experience(
            task_type, instruction, distilled_log, result, score, session_id=session_id
        )
        
        yield f"[经验总结 Agent] 经验已记录 (得分: {score})"
