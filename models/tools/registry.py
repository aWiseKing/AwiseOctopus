class SkillRegistry:
    def __init__(self):
        self.skills = {}
        self.schemas = []

    def register(
        self,
        name,
        description,
        parameters,
        requires_confirmation=False,
        action_kind=None,
    ):
        """
        注册技能的装饰器
        """
        def decorator(func):
            self.skills[name] = {
                "func": func,
                "requires_confirmation": requires_confirmation,
                "action_kind": action_kind,
            }
            self.schemas.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters
                }
            })
            return func
        return decorator

    def get_skill_info(self, name):
        """
        获取技能信息（包括是否需要用户确认）
        """
        return self.skills.get(name)

    def execute(self, name, args):
        """
        执行技能
        """
        if name in self.skills:
            try:
                return self.skills[name]["func"](**args)
            except Exception as e:
                return f"执行技能 {name} 发生异常: {e}"
        else:
            return f"技能 {name} 不存在"

# 全局的技能注册表实例
registry = SkillRegistry()
