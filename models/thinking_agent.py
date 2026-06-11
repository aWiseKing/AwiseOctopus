import json
import os
from .agent_errors import create_chat_completion, iter_chat_completion_stream, raise_if_agent_abort_error
from .execution_agent import ExecutionAgent
from .personas import load_persona_prompt, resolve_persona_name
from .tools import registry
from .experience_memory import ExperienceMemoryManager
from .experience_agent import ExperienceAgent
from .interaction import resolve_interaction_handler
from .message_utils import messages_for_model, normalize_assistant_message
from .runtime_paths import resource_path

def _search_skill(keyword):
    """根据关键字搜索 skills 目录，返回匹配的 skill.md 内容"""
    skills_dir = str(resource_path("skills"))
    if not os.path.exists(skills_dir):
        return "未找到 skills 目录。"
    
    keyword = keyword.lower().strip() if keyword else ""
    available_skills = []
    matched_skills = []
    
    for skill_name in os.listdir(skills_dir):
        skill_path = os.path.join(skills_dir, skill_name)
        if not os.path.isdir(skill_path):
            continue
            
        available_skills.append(skill_name)
        
        # 如果没有关键字，直接继续收集所有可用技能
        if not keyword:
            continue
            
        is_match = False
        
        # 1. 匹配文件夹名
        if keyword in skill_name.lower():
            is_match = True
            
        # 2. 匹配 description.txt
        if not is_match:
            desc_file = os.path.join(skill_path, "description.txt")
            if os.path.exists(desc_file):
                with open(desc_file, "r", encoding="utf-8") as f:
                    desc_content = f.read()
                    if keyword in desc_content.lower():
                        is_match = True
                        
        # 3. 匹配 md 文件内容
        if not is_match:
            for filename in os.listdir(skill_path):
                if filename.lower().endswith(".md"):
                    md_file = os.path.join(skill_path, filename)
                    try:
                        with open(md_file, "r", encoding="utf-8") as f:
                            md_content = f.read()
                            if keyword in md_content.lower():
                                is_match = True
                                break
                    except Exception:
                        pass
                        
        if is_match:
            matched_skills.append(_read_skill_md(skill_path))
            
    if not keyword:
        return f"当前可用的技能有: {', '.join(available_skills)}"
        
    if not matched_skills:
        return f"未找到与 '{keyword}' 相关的技能。当前可用的技能有: {', '.join(available_skills)}"
        
    return "\n\n".join(matched_skills)

def _read_skill_md(skill_path):
    # 优先查找 skill.md 或 SKILL.md
    for filename in ["skill.md", "SKILL.md"]:
        skill_md_file = os.path.join(skill_path, filename)
        if os.path.exists(skill_md_file):
            with open(skill_md_file, "r", encoding="utf-8") as f:
                return f"成功加载技能 [{os.path.basename(skill_path)}] ({filename})：\n" + f.read()
    
    # 否则查找任意 .md 文件
    for filename in os.listdir(skill_path):
        if filename.lower().endswith(".md"):
            skill_md_file = os.path.join(skill_path, filename)
            try:
                with open(skill_md_file, "r", encoding="utf-8") as f:
                    return f"成功加载技能 [{os.path.basename(skill_path)}] ({filename})：\n" + f.read()
            except Exception:
                pass
                
    return f"技能 [{os.path.basename(skill_path)}] 缺少 .md 文件。"

class ThinkingAgent:
    def __init__(
        self,
        client,
        model,
        session_id=None,
        session_store=None,
        interaction_handler=None,
        persona_name=None,
    ):
        self.client = client
        self.model = model
        self.session_id = session_id
        self.session_store = session_store
        self.persona_name = resolve_persona_name(persona_name)
        self.interaction_handler = resolve_interaction_handler(
            interaction_handler, session_id=session_id
        )
        self.memory_manager = ExperienceMemoryManager()
        self.experience_agent = ExperienceAgent(client, model)
        
        execution_tools_info = json.dumps(registry.schemas, ensure_ascii=False)
        self.system_prompt = load_persona_prompt(
            "thinking_agent",
            persona_name=self.persona_name,
            execution_tools_info=execution_tools_info,
        )
        self.thinking_tools_schema = [
            {
                "type": "function",
                "function": {
                    "name": "search_skill",
                    "description": "搜索并加载相关的专家技能（纯文本Prompt/SOP）。如果不知道具体技能名，可以先传入空字符串获取所有可用技能列表。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "keyword": {"type": "string", "description": "技能的关键字。传入空字符串可以列出所有可用技能。"}
                        },
                        "required": ["keyword"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "execute_subtask",
                    "description": "将一个子任务委派给执行Agent并获取执行结果。你需要给出详细的任务描述。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "instruction": {"type": "string", "description": "子任务的详细指令"}
                        },
                        "required": ["instruction"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "submit_plan",
                    "description": "当你完成思考和信息收集，准备好完整的任务执行计划时调用此工具。将计划以文本形式提交给DAG Agent进行后续的DAG转换。调用此工具代表你的思考阶段结束。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "plan": {
                                "type": "string",
                                "description": "详细的任务执行计划描述，包括每个步骤需要调用的工具或委派的指令，以及步骤间的依赖关系。"
                            }
                        },
                        "required": ["plan"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "continue_task",
                    "description": "在复盘（review）阶段使用。如果评估完某个局部任务的结果后，认为不需要修改剩余的DAG计划，直接调用此工具让引擎继续执行原计划。",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "ask_user_for_help",
                    "description": "当你遇到模糊不清的需求目标、多次尝试失败、或者无法确定下一步如何执行时调用。你必须向用户描述当前困境，整理出可能的方向供用户选择，或者让用户直接给出思路。在没有明确目标前，不要随意操作。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string", "description": "向用户提出的问题，包括当前的困境和可能的新思考方向供用户选择。"}
                        },
                        "required": ["question"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "finish_task",
                    "description": "当整个用户任务完成时调用，返回最终的综合答案。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "final_answer": {"type": "string", "description": "最终回复用户的答案"}
                        },
                        "required": ["final_answer"]
                    }
                }
            }
        ]

        self.messages = [{"role": "system", "content": self.system_prompt}]
        if self.session_store and self.session_id:
            for msg in self.session_store.load_messages(self.session_id):
                if isinstance(msg, dict) and msg.get("role") != "system":
                    self.messages.append(msg)

    def _append_message(self, msg: dict, persist: bool = True) -> None:
        if not isinstance(msg, dict):
            return
        self.messages.append(msg)
        if (
            persist
            and self.session_store
            and self.session_id
            and msg.get("role") != "system"
        ):
            self.session_store.append_message(self.session_id, msg)

    def _append_tool_message(self, tool_call_id, name, content) -> None:
        self._append_message(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": name,
                "content": str(content),
            }
        )

    def _append_tool_error(self, tool_call, exc: Exception) -> None:
        name = (tool_call.get("function") or {}).get("name") or "unknown_tool"
        self._append_tool_message(
            tool_call.get("id"),
            name,
            f"Tool call failed: {type(exc).__name__}: {exc}",
        )

    def _refresh_short_term_session_summary(self) -> None:
        if not self.session_id:
            return
        conversational = [
            msg
            for msg in self.messages
            if isinstance(msg, dict)
            and msg.get("role") in {"user", "assistant"}
            and not msg.get("tool_calls")
            and str(msg.get("content") or "").strip()
        ]
        if len(conversational) < 8:
            return
        recent = conversational[-12:]
        lines = []
        for msg in recent:
            role = "用户" if msg.get("role") == "user" else "助手"
            content = str(msg.get("content") or "").replace("\n", " ").strip()
            if len(content) > 280:
                content = content[:280].rstrip() + "..."
            lines.append(f"{role}: {content}")
        summary = "当前会话近期摘要：\n" + "\n".join(lines)
        try:
            self.memory_manager.upsert_session_summary(
                session_id=self.session_id,
                content=summary,
                message_count=len(conversational),
            )
        except Exception:
            pass

    def _normalize_assistant_message(self, msg):
        return normalize_assistant_message(msg)

    def _messages_for_llm(self, injected_system_message: str | None):
        if not injected_system_message:
            return messages_for_model(self.messages, self.model)

        base = list(self.messages)
        if base and isinstance(base[0], dict) and base[0].get("role") == "system":
            merged_first = dict(base[0])
            merged_first["content"] = (
                f"{base[0].get('content', '')}\n\n{injected_system_message}"
            ).strip()
            return messages_for_model([merged_first, *base[1:]], self.model)

        return messages_for_model(
            [{"role": "system", "content": injected_system_message}, *base],
            self.model,
        )
        
    def run_stream(self, user_request):
        yield ("RUNNING", "\n=== [思考Agent 启动] 开始分析任务 ===")

        self._refresh_short_term_session_summary()
        try:
            self.memory_manager.upsert_task_working_set(
                session_id=self.session_id,
                task_type="thinking",
                content=f"思考任务进行中：{user_request}",
                status="active",
            )
        except Exception:
            pass

        hint = self.memory_manager.build_memory_context(
            "thinking", user_request, session_id=self.session_id
        )
        if not hint:
            hint = self.memory_manager.search_experience(
                "thinking", user_request, session_id=self.session_id
            )
        injected_system_message = None
        if hint:
            yield ("RUNNING", "\n[思考Agent 多模式记忆] 检索到相关记忆，已注入上下文。")
            injected_system_message = (
                "〖系统注入的多模式记忆（仅供参考，如与用户最新指令冲突，以用户指令为准）〗\n"
                f"{hint}\n"
                "〖记忆参考结束〗"
            )


        self._append_message({"role": "user", "content": user_request})
        
        while True:
            response = create_chat_completion(
                self.client,
                stage="思考阶段",
                model=self.model,
                messages=self._messages_for_llm(injected_system_message),
                tools=self.thinking_tools_schema,
                tool_choice="auto",
            )
            msg = self._normalize_assistant_message(response.choices[0].message)
            self._append_message(msg)
            
            if msg.get("tool_calls"):
                final_return_payload = None
                final_return_status = None
                
                for tool_call in msg.get("tool_calls", []):
                    try:
                        name = (tool_call.get("function") or {}).get("name")
                        args = json.loads((tool_call.get("function") or {}).get("arguments") or "{}")
                        
                        if name == "search_skill":
                            keyword = args.get("keyword", "")
                            yield ("RUNNING", f"\n[思考Agent 检索技能] 关键词: {keyword}")
                            skill_content = _search_skill(keyword)
                            self._append_tool_message(tool_call.get("id"), name, skill_content)
                        elif name == "execute_subtask":
                            instruction = args.get("instruction", "")
                            yield ("RUNNING", f"\n[思考Agent 决策] 委派子任务 -> {instruction}")
                            worker = ExecutionAgent(
                                self.client,
                                self.model,
                                session_id=self.session_id,
                                interaction_handler=self.interaction_handler,
                                persona_name=self.persona_name,
                            )
                            
                            # 消费 ExecutionAgent 的流式输出
                            worker_gen = worker.run_stream(instruction)
                            try:
                                while True:
                                    log_msg = next(worker_gen)
                                    yield ("RUNNING", log_msg)
                            except StopIteration as e:
                                result = e.value
                            
                            self._append_tool_message(tool_call.get("id"), name, result)
                        elif name == "ask_user_for_help":
                            question = args.get("question", "")
                            yield ("RUNNING", f"\n[思考Agent 遇到困难求助] {question}")
                            
                            user_reply = yield ("ASK_USER", question)
                            self._append_tool_message(
                                tool_call.get("id"),
                                name,
                                f"用户提供的思路/回答: {user_reply}",
                            )
                        elif name == "submit_plan":
                            plan = args.get("plan", "")
                            yield ("RUNNING", f"\n=== [思考Agent 规划完成] 提交计划给 DAG Agent ===\n{plan}")
                            try:
                                self.memory_manager.upsert_task_working_set(
                                    session_id=self.session_id,
                                    task_type="thinking",
                                    content=f"当前任务已规划，等待 DAG 执行。\n用户请求：{user_request}\n计划：{plan}",
                                    status="planned",
                                )
                            except Exception:
                                pass
                            
                            from .dag_agent import DAGAgent
                            dag_agent = DAGAgent(
                                self.client,
                                self.model,
                                persona_name=self.persona_name,
                            )
                            dag_gen = dag_agent.generate_dag_stream(plan)
                            
                            tasks = []
                            try:
                                while True:
                                    status, payload = next(dag_gen)
                                    if status == "RUNNING":
                                        yield ("RUNNING", payload)
                                    elif status == "FINISHED":
                                        tasks = payload
                                        break
                            except StopIteration as e:
                                if e.value is not None:
                                    tasks = e.value
                            
                            self._append_tool_message(
                                tool_call.get("id"),
                                name,
                                "计划已由 DAG Agent 成功转化为 DAG 图并提交执行。",
                            )
                            
                            final_return_status = "FINISHED"
                            final_return_payload = tasks
                        elif name == "continue_task":
                            yield ("RUNNING", "\n=== [思考Agent 复盘完成] 维持原DAG计划，继续执行 ===")
                            self._append_tool_message(tool_call.get("id"), name, "维持原计划继续执行")
                            
                            final_return_status = "FINISHED"
                            final_return_payload = "CONTINUE"
                        elif name == "finish_task":
                            final_answer = args.get("final_answer", "")
                            yield ("RUNNING", "\n=== [思考Agent 完成] 所有任务已完成 ===")
                            self._append_tool_message(
                                tool_call.get("id"),
                                name,
                                f"任务已完成，最终回复: {final_answer}",
                            )
                            
                            # 记录经验 (直接完成类型任务)
                            yield ("RUNNING", "\n[思考Agent] 开始请求经验总结 Agent 处理执行结果...")
                            process_log_str = "Direct finish without DAG."
                            for log_msg in self.experience_agent.process_experience_stream(
                                "thinking",
                                user_request,
                                process_log_str,
                                final_answer,
                                session_id=self.session_id,
                            ):
                                yield ("RUNNING", f"  -> {log_msg}")

                            try:
                                self.memory_manager.upsert_task_working_set(
                                    session_id=self.session_id,
                                    task_type="thinking",
                                    content=f"思考任务已完成：{user_request}\n最终回答：{final_answer}",
                                    status="completed",
                                )
                            except Exception:
                                pass
                            
                            final_return_status = "FINISHED"
                            final_return_payload = final_answer
                        else:
                            yield ("RUNNING", f"\n[思考Agent 错误] 调用了未知工具: {name}")
                            self._append_tool_message(
                                tool_call.get("id"),
                                name or "unknown_tool",
                                f"Error: Unknown tool '{name}'.",
                            )
                    except Exception as e:
                        raise_if_agent_abort_error(e)
                        name = (tool_call.get("function") or {}).get("name") or "unknown_tool"
                        yield ("RUNNING", f"\n[思考Agent 工具调用失败] {name}: {type(e).__name__}: {e}")
                        self._append_tool_error(tool_call, e)
                        
                if final_return_status:
                    yield (final_return_status, final_return_payload)
                    return final_return_payload
            else:
                content = msg.get("content")
                if content:
                    yield ("RUNNING", f"\n[思考Agent 自言自语] {content}")
                    self._append_message(
                        {
                            "role": "user",
                            "content": "请使用工具 execute_subtask 委派任务，或使用 finish_task 结束。",
                        }
                    )

    def run(self, user_request):
        gen = self.run_stream(user_request)
        user_input_to_send = None
        
        try:
            while True:
                if user_input_to_send is not None:
                    status, payload = gen.send(user_input_to_send)
                    user_input_to_send = None
                else:
                    status, payload = next(gen)
                    
                if status == "RUNNING":
                    print(payload)
                elif status == "ASK_USER":
                    user_reply = input(f"[提示] 请给Agent提供思路或选择方案: ")
                    user_input_to_send = user_reply
                elif status == "FINISHED":
                    return payload
        except StopIteration as e:
            return e.value

    def review_dag(self, completed_task_id, result, pending_tasks):
        """用于在 DAG 执行过程中复盘某个任务结果，并决定是否调整后续任务"""
        review_instruction = (
            f"任务 `{completed_task_id}` 已执行完成，标记了 requires_review。\n"
            f"执行结果如下：\n{result}\n\n"
            f"当前尚未执行的 DAG 任务列表为：\n{json.dumps(pending_tasks, ensure_ascii=False, indent=2)}\n\n"
            "请判断是否需要调整后续计划：\n"
            "1. 如果需要调整，请调用 `submit_plan` 输出全新的待执行任务计划（新计划将完全覆盖上述尚未执行的任务列表）。\n"
            "2. 如果不需要调整，请直接调用 `continue_task` 工具。"
        )
        print(f"\n[DAG 执行器] 请求思考Agent复盘任务 {completed_task_id}...")
        return self.run(review_instruction)

    def summarize_dag_results_stream(self, user_request, dag_results):
        """流式生成最终的 DAG 执行结果总结"""
        system_prompt = load_persona_prompt(
            "summary",
            persona_name=self.persona_name,
        )
        content = f"用户的原始请求：\n{user_request}\n\n各个子任务的执行结果（JSON格式）：\n{json.dumps(dag_results, ensure_ascii=False, indent=2)}\n\n请提供最终的总结报告："
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content}
        ]
        
        response = create_chat_completion(
            self.client,
            stage="结果总结阶段",
            model=self.model,
            messages=messages,
            stream=True,
        )
        
        summary_text = ""
        for chunk in iter_chat_completion_stream(response, stage="结果总结阶段"):
            if chunk.choices and chunk.choices[0].delta.content is not None:
                content = chunk.choices[0].delta.content
                summary_text += content
                yield content
        
        # 当流式输出结束后，记录完整的 DAG 经验
        yield "\n\n[思考Agent] 开始请求经验总结 Agent 处理执行结果...\n"
        process_log_str = json.dumps(dag_results, ensure_ascii=False)
        for log_msg in self.experience_agent.process_experience_stream(
            "thinking",
            user_request,
            process_log_str,
            summary_text,
            session_id=self.session_id,
        ):
            yield f"  -> {log_msg}\n"
                
        # 注入总结结果到思考 Agent 的上下文中
        self._append_message({
            "role": "user",
            "content": f"系统通知：上一个任务的DAG执行结果总结如下：\n{summary_text}\n请在后续对话中记住这些信息。"
        })
        try:
            self.memory_manager.upsert_task_working_set(
                session_id=self.session_id,
                task_type="thinking",
                content=f"DAG 任务已完成。\n用户请求：{user_request}\n总结：{summary_text}",
                status="completed",
            )
        except Exception:
            pass
