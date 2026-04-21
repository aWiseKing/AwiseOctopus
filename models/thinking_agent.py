import json
import os
import jsonschema
from .execution_agent import ExecutionAgent
from .tools import registry

def _validate_dag_tasks(tasks, schema):
    """
    校验 DAG 任务列表的 Schema 结构以及逻辑（存在性和无环检测）
    返回 (is_valid, error_message)
    """
    # 1. 基础 Schema 校验
    try:
        # tasks 在外部是 list，但 schema 是为包裹 tasks 的 object 设计的
        # 所以我们包装一下进行校验
        jsonschema.validate(instance={"tasks": tasks}, schema=schema)
    except jsonschema.exceptions.ValidationError as e:
        return False, f"Schema validation error: {e.message}"

    # 2. 逻辑校验：提取所有的 task_id
    task_ids = set()
    for t in tasks:
        if t['id'] in task_ids:
            return False, f"Logical error: Duplicate task id '{t['id']}' found."
        task_ids.add(t['id'])

    # 3. 逻辑校验：依赖是否存在
    for t in tasks:
        for dep in t.get('dependencies', []):
            if dep not in task_ids:
                return False, f"Logical error: Task '{t['id']}' depends on non-existent task '{dep}'."

    # 4. 逻辑校验：循环依赖检测 (DFS 拓扑排序)
    # 状态: 0=未访问, 1=访问中, 2=已访问
    visited = {tid: 0 for tid in task_ids}
    adj_list = {t['id']: t.get('dependencies', []) for t in tasks}

    def has_cycle(tid):
        if visited[tid] == 1:
            return True
        if visited[tid] == 2:
            return False
        
        visited[tid] = 1
        for dep in adj_list[tid]:
            if has_cycle(dep):
                return True
        visited[tid] = 2
        return False

    for tid in task_ids:
        if visited[tid] == 0:
            if has_cycle(tid):
                return False, f"Logical error: Circular dependency detected involving task '{tid}'."

    # 5. 逻辑校验：类型校验
    for t in tasks:
        t_type = t.get('type', 'agent')
        if t_type == 'tool':
            if 'tool' not in t or 'input' not in t:
                return False, f"Logical error: Task '{t['id']}' with type 'tool' must have 'tool' and 'input' fields."
        else:
            if 'instruction' not in t:
                return False, f"Logical error: Task '{t['id']}' with type 'agent' must have 'instruction' field."

    return True, None

def _search_skill(keyword):
    """根据关键字搜索 skills 目录，返回匹配的 skill.md 内容"""
    skills_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")
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
    def __init__(self, client, model):
        self.client = client
        self.model = model
        
        execution_tools_info = json.dumps(registry.schemas, ensure_ascii=False)
        self.system_prompt = (
            "你是一个思考Agent（Manager）。你的任务是拆解用户的复杂请求，进行必要的信息收集，并最终规划出一个基于DAG（有向无环图）的任务执行计划。\n"
            "【阶段一：信息收集与探索】\n"
            "你可以使用工具 `execute_subtask` 将探索性的子任务（如读取代码、搜索网络等）委派给执行Agent。\n"
            "执行Agent会返回结果。你需要根据结果判断是否已经收集到足够的信息来制定完整的计划。如果信息不足，继续委派探索任务；如果信息足够，进入阶段二。\n"
            "\n【专家技能加载】\n"
            "如果你遇到了特定领域的任务（例如数据分析、前端开发等），请先使用 `search_skill` 工具查找并加载相关的专家技能指导（skill.md）。\n"
            "将加载出来的指导原则和SOP作为你后续思考、规划任务的重要参考依据！\n"
            "\n【重要容错与修正策略】\n"
            "当某一个探索任务或方法多次失败、无法获得预期结果（例如网络搜索失败、计算出错等）时，你必须**主动修正思考方向**。\n"
            "一种非常有效的替代方案是：**让执行Agent通过编写并运行Python代码（使用其内置的 python_eval 工具）来完成任务**。例如通过Python去请求API、爬取网页、处理复杂逻辑等。\n"
            "如果各种方法都尝试失败，或者你对如何规划有严重疑虑时，请**使用 `ask_user_for_help` 工具向用户提问**。特别地，对于**模糊不清的需求目标等信息**，你必须**整理出可能的方向后由用户选择**，切勿自行猜测。\n"
            "\n【阶段二：输出DAG任务执行图】\n"
            "当你的思考和信息收集完成，并明确了所有需要执行的步骤后，必须使用 `create_task` 工具输出整个DAG任务执行图。\n"
            "在DAG图中，你需要将任务进行**细致的拆分**，支持两种任务节点类型：\n"
            "  1. `type='tool'`：直接调用特定的执行工具。必须指定 `tool`（工具名称）和 `input`（工具参数）。\n"
            "  2. `type='agent'`：将复杂的模糊指令委派给执行Agent处理。必须指定 `instruction`。\n"
            "请优先将明确的操作拆分为 `type='tool'` 节点。当前可直接调用的执行工具（用于 type='tool'）如下：\n"
            f"{execution_tools_info}\n"
            "\n**【动态DAG调整（复盘机制）】**\n"
            "如果你觉得某个任务执行后可能需要根据它的结果来决定后续任务如何进行，请将该任务的 `requires_review` 设为 true。DAG 引擎在执行完该任务后会暂停，并将结果返回给你重新规划。\n"
            "调用 `create_task` 意味着你的思考阶段结束，DAG任务图将交给执行引擎去并行或顺序执行。\n"
            "如果你认为用户的请求只是一个简单的问题解答，不需要规划DAG任务图，你可以直接使用 `finish_task` 工具返回最终答案。\n"
            "千万不要自己去猜事实或做计算，必须依靠执行引擎去完成实际操作！"
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
                    "name": "create_task",
                    "description": "当你完成思考和信息收集，准备好完整的任务执行图时调用此工具。输出一个基于DAG（有向无环图）的任务计划。调用此工具代表你的思考阶段结束。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tasks": {
                                "type": "array",
                                "description": "DAG任务列表，每个任务包含id、指令和依赖项。",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "id": {
                                            "type": "string",
                                            "description": "任务的唯一标识符，例如 'task_1'"
                                        },
                                        "type": {
                                            "type": "string",
                                            "enum": ["tool", "agent"],
                                            "description": "任务类型。'tool'表示直接调用具体的工具，'agent'表示委派给执行Agent处理复杂逻辑"
                                        },
                                        "tool": {
                                            "type": "string",
                                            "description": "如果type为'tool'，指定要调用的工具名称"
                                        },
                                        "input": {
                                            "type": "object",
                                            "description": "如果type为'tool'，指定工具的输入参数"
                                        },
                                        "instruction": {
                                            "type": "string",
                                            "description": "如果type为'agent'，给出执行指令，给执行Agent看"
                                        },
                                        "dependencies": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                            "description": "该任务依赖的其他任务id列表。如果是独立任务，传空数组 []"
                                        },
                                        "requires_review": {
                                            "type": "boolean",
                                            "description": "是否需要在该任务完成后暂停执行，并将结果交由你进行复盘以决定是否调整后续DAG任务。如果其结果可能改变后续走向，设为true。"
                                        }
                                    },
                                    "required": ["id", "type", "dependencies"]
                                }
                            }
                        },
                        "required": ["tasks"]
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
        
    def run_stream(self, user_request):
        yield ("RUNNING", "\n=== [思考Agent 启动] 开始分析任务 ===")
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_request}
        ]
        
        while True:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.thinking_tools_schema
            )
            msg = response.choices[0].message
            messages.append(msg)
            
            if msg.tool_calls:
                for tool_call in msg.tool_calls:
                    name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)
                    
                    if name == "search_skill":
                        keyword = args.get("keyword", "")
                        yield ("RUNNING", f"\n[思考Agent 检索技能] 关键词: {keyword}")
                        skill_content = _search_skill(keyword)
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": name,
                            "content": str(skill_content)
                        })
                    elif name == "execute_subtask":
                        instruction = args.get("instruction", "")
                        yield ("RUNNING", f"\n[思考Agent 决策] 委派子任务 -> {instruction}")
                        worker = ExecutionAgent(self.client, self.model)
                        
                        # 消费 ExecutionAgent 的流式输出
                        worker_gen = worker.run_stream(instruction)
                        try:
                            while True:
                                log_msg = next(worker_gen)
                                yield ("RUNNING", log_msg)
                        except StopIteration as e:
                            result = e.value
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": name,
                            "content": result
                        })
                    elif name == "ask_user_for_help":
                        question = args.get("question", "")
                        yield ("RUNNING", f"\n[思考Agent 遇到困难求助] {question}")
                        
                        user_reply = yield ("ASK_USER", question)
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": name,
                            "content": f"用户提供的思路/回答: {user_reply}"
                        })
                    elif name == "create_task":
                        tasks = args.get("tasks", [])
                        
                        # 获取 create_task 的 schema
                        create_task_schema = next((t["function"]["parameters"] for t in self.thinking_tools_schema if t["function"]["name"] == "create_task"), None)
                        
                        # 进行校验
                        is_valid, error_msg = _validate_dag_tasks(tasks, create_task_schema)
                        
                        if not is_valid:
                            yield ("RUNNING", f"\n[校验失败] DAG图存在错误: {error_msg}")
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": name,
                                "content": f"Failed to create task due to validation error: {error_msg}. Please fix the error and try again."
                            })
                            continue
                            
                        yield ("RUNNING", f"\n=== [思考Agent 规划完成] 输出DAG任务图: 共 {len(tasks)} 个任务 ===")
                        dag_json = json.dumps(tasks, ensure_ascii=False, indent=2)
                        yield ("RUNNING", f"\n[DAG 任务图详情]:\n{dag_json}")
                        yield ("FINISHED", tasks)
                        return tasks
                    elif name == "continue_task":
                        yield ("RUNNING", "\n=== [思考Agent 复盘完成] 维持原DAG计划，继续执行 ===")
                        yield ("FINISHED", "CONTINUE")
                        return "CONTINUE"
                    elif name == "finish_task":
                        final_answer = args.get("final_answer", "")
                        yield ("RUNNING", "\n=== [思考Agent 完成] 所有任务已完成 ===")
                        yield ("FINISHED", final_answer)
                        return final_answer
            else:
                if msg.content:
                    yield ("RUNNING", f"\n[思考Agent 自言自语] {msg.content}")
                    messages.append({"role": "user", "content": "请使用工具 execute_subtask 委派任务，或使用 finish_task 结束。"})

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
            "1. 如果需要调整，请调用 `create_task` 输出全新的待执行任务图（新任务图将完全覆盖上述尚未执行的任务列表）。\n"
            "2. 如果不需要调整，请直接调用 `continue_task` 工具。"
        )
        print(f"\n[DAG 执行器] 请求思考Agent复盘任务 {completed_task_id}...")
        return self.run(review_instruction)

    def summarize_dag_results_stream(self, user_request, dag_results):
        """流式生成最终的 DAG 执行结果总结"""
        system_prompt = "你是一个智能总结助手。请根据用户的原始请求和各个子任务的执行结果，撰写一份连贯、排版良好且易读的最终总结报告。"
        content = f"用户的原始请求：\n{user_request}\n\n各个子任务的执行结果（JSON格式）：\n{json.dumps(dag_results, ensure_ascii=False, indent=2)}\n\n请提供最终的总结报告："
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content}
        ]
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True
        )
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content
