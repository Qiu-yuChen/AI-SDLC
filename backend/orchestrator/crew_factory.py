"""CrewAI Crew Factory — Builds Agent Crews with ReAct tools"""

from typing import Callable, Optional

from crewai import Agent, Task, Crew, Process

from config import DOCS_INPUT, DOCS_OUTPUT, settings
from agents.design_agent import build_design_prompt
from agents.codegen_agent import build_codegen_prompt
from agents.test_agent import build_test_prompt
from tools.file_tools import read_file, write_file, list_directory
from tools.code_tools import syntax_check, format_code_file
from tools.quality_tools import validate_design_completeness
from .task_control import task_control

# ── LLM Config ──────────────────────────────────────────

def _get_llm():
    """Get LiteLLM-compatible LLM instance — uses primary_model as default,
    but each agent factory can override with _model().
    """
    return settings.primary_model


def _model(agent_model: str) -> str:
    """返回 Agent 的 LLM 模型字符串 + 自动配置环境
    - 用 .env 中 DESIGN_MODEL/CODEGEN_MODEL/TEST_MODEL 覆盖 primary_model
    - 自动检测 qwen/kimi/glm 并设置对应的 API base"""
    model = agent_model or settings.primary_model
    if "qwen" in model:
        _setup_local_qwen()
    if "kimi" in model:
        _setup_kimi()
    if "glm" in model.lower():
        _setup_glm()
    return model


def _setup_local_qwen():
    import os
    os.environ["OPENAI_API_BASE"] = settings.qwen_vllm_api_base
    if not os.environ.get("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = "not-needed"


def _setup_kimi():
    import os
    if settings.moonshot_api_base:
        os.environ["OPENAI_API_BASE"] = settings.moonshot_api_base
    if settings.moonshot_api_key:
        os.environ["OPENAI_API_KEY"] = settings.moonshot_api_key


def _setup_glm():
    import os
    if settings.zhipu_api_key:
        os.environ["ZHIPU_API_KEY"] = settings.zhipu_api_key
        os.environ["ZAI_API_KEY"] = settings.zhipu_api_key


# ── Agent Definitions ────────────────────────────────────

def create_design_agent() -> Agent:
    """概要设计 Agent — ReAct: 读规格书 → 分析 → 写设计文档"""
    return Agent(
        role="资深系统架构师",
        goal="根据产品规格说明书，生成结构完整、可直接指导开发的概要设计文档",
        backstory="""你是一名拥有15年经验的企业级系统架构师，精通Web应用架构设计。
你的工作流程（ReAct）：
1. 💭 思考：先完整阅读规格说明书，理解功能需求和非功能需求
2. 🎬 行动：分析业务领域，确定合适的架构模式（分层/MVC/微服务）
3. 👁️ 观察：检查设计是否覆盖了所有功能点
4. 💭 思考：如果不完善，补充遗漏的模块
5. 🎬 行动：输出完整的Markdown格式概要设计文档

设计文档必须包含：
- 系统概述与架构图（Mermaid）
- 模块划分（每个模块的功能描述）
- API接口定义（端点、方法、参数、返回值）
- 数据模型设计（表结构、字段、关系）
- 技术选型说明
- 非功能性需求（性能、安全等）

⚠️ 工具调用规范（非常重要）：
- write_file 调用时 path 和 content 参数都必须提供，缺一不可
- 示例：write_file(path="/path/to/file.md", content="完整的Markdown内容")
- 如果工具调用失败，仔细阅读错误信息，补全缺失参数后重试
- 不要传入空的路径或空的内容""",
        tools=[read_file, write_file, validate_design_completeness],
        llm=_model(settings.design_model),
        verbose=settings.react_verbose,
        allow_delegation=False,
        max_iter=settings.react_max_iter,
        max_rpm=10,  # rate limit safety
    )


def create_codegen_agent() -> Agent:
    """代码生成 Agent — ReAct: 读设计文档 → 写代码 → 语法检查 → 修复"""
    return Agent(
        role="资深全栈工程师",
        goal="根据概要设计文档，生成语法正确、结构清晰、可运行的源代码",
        backstory="""你是一名资深全栈Python工程师，代码风格干净、注释清晰。
你的工作流程（ReAct）：
1. 💭 思考：仔细阅读概要设计文档，理解每个模块的职责
2. 🎬 行动：逐个模块生成源代码文件
3. 👁️ 观察：运行语法检查，确认代码可编译
4. 💭 思考：如果有语法错误，分析原因
5. 🎬 行动：修复错误，重新检查
6. 输出所有源代码文件

代码规范：
- 使用类型注解（Type Hints）
- 每个函数有 docstring
- 错误处理完善（try/except）
- 命名遵循 PEP 8

⚠️ 端口规范（非常重要）：
- app.py 中禁止硬编码端口，必须随机选择空闲端口：
  import socket
  def find_free_port():
      s = socket.socket(); s.bind(("127.0.0.1", 0))
      port = s.getsockname()[1]; s.close()
      return port
  PORT = find_free_port()
  uvicorn.run(app, host="127.0.0.1", port=PORT)
- 禁止使用 8000 或任何固定端口号
                                                                                               
                                                                                                                                    
管理员系统要求：                                                                                                               
- 每个生成的项目必须包含后台管理员系统                                                                                     
- 管理员可查看/管理所有数据（用户、记录、配置等）                                                                           
- 管理员后台独立于普通用户界面，有权限校验                                                                                 
- 管理员默认账号: admin / admin123
- CSV 作为数据库（赛题要求）

⚠️ 工具调用规范（非常重要）：
- write_file 调用时 path 和 content 参数都必须提供，缺一不可
- 示例：write_file(path="/output/dir/app.py", content="完整的Python代码")
- content 参数必须包含完整的文件内容，不能为空字符串
- 确保 JSON 格式正确——字符串中的引号、换行符需要正确转义
- 如果工具调用失败，仔细阅读错误信息，补全缺失参数后重试""",
        tools=[read_file, write_file, list_directory, syntax_check, format_code_file],
        llm=_model(settings.codegen_model),
        verbose=settings.react_verbose,
        allow_delegation=False,
        max_iter=settings.react_max_iter,
        max_rpm=10,
    )


def create_test_agent() -> Agent:
    """单元测试 Agent — ReAct: 读代码 → 写测试 → 运行 → 提升覆盖率"""
    return Agent(
        role="资深测试工程师",
        goal="根据源代码和设计文档，生成覆盖率≥80%的高质量单元测试",
        backstory="""你是一名资深测试工程师，擅长发现边界条件和编写高质量测试。
你的工作流程（ReAct）：
1. 💭 思考：阅读设计文档和源代码，理解业务逻辑
2. 🎬 行动：为每个模块编写测试用例（正常/边界/异常）
3. 👁️ 观察：检查测试覆盖了哪些场景
4. 💭 思考：如果覆盖率不足，分析缺少哪些测试
5. 🎬 行动：补充缺失的测试用例

测试原则：
- 使用 pytest 框架
- 每个测试函数有清晰的断言
- 覆盖正常路径、边界值、异常处理
- 测试数据使用 fixture 管理
- Mock 外部依赖

⚠️ 工具调用规范（非常重要）：
- write_file 调用时 path 和 content 参数都必须提供，缺一不可
- 示例：write_file(path="/output/dir/test_x.py", content="完整的测试代码")
- content 参数必须包含完整的文件内容，不能为空字符串
- 如果工具调用失败，仔细阅读错误信息，补全缺失参数后重试""",
        tools=[read_file, write_file, list_directory, syntax_check],
        llm=_model(settings.test_model),
        verbose=settings.react_verbose,
        allow_delegation=False,
        max_iter=settings.react_max_iter,
        max_rpm=10,
    )


# ── Crew Builders ────────────────────────────────────────

def _stringify_step_value(value) -> str:
    if value is None:
        return ""
    text = str(value)
    return text if len(text) <= 1200 else text[:1200] + "..."


def _extract_react_step(step_output) -> dict:
    def pick(*names: str):
        if isinstance(step_output, dict):
            for name in names:
                if step_output.get(name):
                    return step_output.get(name)
        for name in names:
            value = getattr(step_output, name, None)
            if value:
                return value
        return None

    thought = pick("thought", "reasoning", "log", "llm_output")
    action = pick("tool", "action", "tool_name", "tool_name_used")
    action_input = pick("tool_input", "action_input", "args", "arguments")
    observation = pick("observation", "result", "output", "final_answer")

    step = {
        "thought": _stringify_step_value(thought),
        "action": _stringify_step_value(action),
        "action_input": _stringify_step_value(action_input),
        "observation": _stringify_step_value(observation),
    }
    cleaned = {key: value for key, value in step.items() if value}
    if cleaned:
        return cleaned

    fallback = _stringify_step_value(step_output)
    if fallback and " object at 0x" not in fallback:
        return {
            "observation": fallback,
            "source": type(step_output).__name__,
        }
    return {}


def build_single_agent_crew(
    agent: Agent,
    task_description: str,
    expected_output: str,
    output_dir: str,
    batch_id: str,
    node_id: str,
    emit_step: Optional[Callable[[str, str, dict], None]] = None,
) -> Crew:
    """Build a Crew with a single Agent+Task (per-node execution)"""

    def step_callback(step_output):
        """Intercept tool call errors and provide richer feedback"""
        task_control.ensure_running(batch_id)
        if hasattr(step_output, 'tool_errors') and step_output.tool_errors:
            for err in step_output.tool_errors:
                if hasattr(err, 'tool_name') and 'write_file' in str(err.tool_name):
                    print(f"[Tool Error Recovery] write_file failed: {err}")
        if emit_step:
            step = _extract_react_step(step_output)
            if step:
                emit_step(node_id, node_id, step)
        task_control.ensure_running(batch_id)
        return step_output

    # CrewAI can emit per-agent steps before the crew-level callback fires.
    # Keep both hooks wired so the UI gets live progress instead of only a final answer.
    agent.step_callback = step_callback

    task = Task(
        description=task_description,
        agent=agent,
        expected_output=expected_output,
        output_file="_result.txt",
    )
    return Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=settings.react_verbose,
        step_callback=step_callback,
    )


def build_design_crew(batch_id: str, spec_filename: str, emit_step=None) -> Crew:
    """Build the Design Agent crew"""
    spec_path = DOCS_INPUT / spec_filename
    output_dir = DOCS_OUTPUT / batch_id / "概要设计"

    agent = create_design_agent()
    task_desc = build_design_prompt(str(spec_path), str(output_dir))
    expected = "完整的概要设计文档（Markdown），包含架构设计、模块划分、API定义、数据模型"

    return build_single_agent_crew(agent, task_desc, expected, str(output_dir), batch_id, "概要设计", emit_step)


def build_codegen_crew(batch_id: str, emit_step=None) -> Crew:
    """Build the CodeGen Agent crew"""
    design_doc = DOCS_OUTPUT / batch_id / "概要设计" / "概要设计文档.md"
    output_dir = DOCS_OUTPUT / batch_id / "代码生成"

    agent = create_codegen_agent()
    task_desc = build_codegen_prompt(str(design_doc), str(output_dir))
    expected = "完整的项目源代码，语法正确可编译"

    return build_single_agent_crew(agent, task_desc, expected, str(output_dir), batch_id, "代码生成", emit_step)


def build_test_crew(batch_id: str, emit_step=None) -> Crew:
    """Build the Test Agent crew"""
    design_doc = DOCS_OUTPUT / batch_id / "概要设计" / "概要设计文档.md"
    code_dir = DOCS_OUTPUT / batch_id / "代码生成"
    output_dir = DOCS_OUTPUT / batch_id / "单元测试"

    agent = create_test_agent()
    task_desc = build_test_prompt(str(design_doc), str(code_dir), str(output_dir))
    expected = "完整的单元测试代码，覆盖率≥80%"

    return build_single_agent_crew(agent, task_desc, expected, str(output_dir), batch_id, "单元测试", emit_step)


CREW_BUILDERS = {
    "概要设计": build_design_crew,
    "代码生成": build_codegen_crew,
    "单元测试": build_test_crew,
    # 质量评分由 OrchestratorEngine._run_scoring() 直接执行，不走 CrewAI
    "质量评分": lambda batch_id: (_ for _ in ()).throw(
        RuntimeError("质量评分由 OrchestratorEngine 直接执行，不走 CrewAI")
    ),
}
