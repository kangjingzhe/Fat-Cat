# Fat-Cat: The LLM-Native Operating System

基于全局文档上下文与多阶段推理的下一代 Agent 框架

![Fat-Cat Framework](framework.png)

## 1. 背景与痛点：为什么我们需要 Fat-Cat？

在当前的 LLM Agent 开发范式中，工程师们正面临着"上下文管理的泥潭"与"脆弱的控制流"两大核心挑战。我将这些挑战总结为 Agent 设计的三大原罪：

### 痛点一：JSON 上下文的诅咒 (The JSON Trap)

传统的 Agent 框架（如 LangChain 早期模式或 Assistant API）倾向于通过复杂的 JSON 对象或 list 字典来传递状态。

**问题：** LLM 本质上是基于文本（Text-based）训练的。强制模型去解析深层嵌套的 JSON 状态会导致注意力分散（Attention Dilution），模型往往只见树木不见森林，容易遗漏关键约束。

**工程师的噩梦：** 调试时面对的是数千行的 JSON dump，难以直观理解 Agent 到底"想"什么。

### 痛点二：静态能力的局限 (The Static Toolset)

大多数 Agent 的能力是"硬编码"的。当面对未知问题时，Agent 只能在预设的 if-else 或固定 DAG 图中打转。它们缺乏**运行时学习（Runtime Learning）**的能力，无法像人类一样通过查阅资料获得新技能。

### 痛点三：元认知的缺失 (The Absence of Metacognition)

这是当前 Agent 最致命的弱点——"只有执行，没有反思"。

**现象：** 传统 Agent 接到任务就像一个莽撞的实习生，直接开始调用工具。一旦进入死胡同（如代码报错、搜索无果），它们往往会陷入死循环重试，或者产生幻觉（Hallucination）强行给出错误答案。

**缺失环节：** 缺乏一个高阶的"监视器"进程来评估："我现在做得对吗？"、"我现有的策略能解决这个问题吗？"、"我是不是需要停下来重新规划？"。

Fat-Cat 旨在解决上述问题，它不只是一个执行任务的 Bot，而是一个拥有"自我意识"和"进化能力"的操作系统雏形。

## 2. 核心设计哲学

### 2.1 LLM as Operating System (LLM 即操作系统)

在 Fat-Cat 中，我们将 LLM 视为 CPU，将Context（文档上下文）视为内存（RAM），将外部工具视为外设（I/O）。

Fat-Cat 框架本身充当 Kernel（内核），负责进程调度（Stage 切换）、内存管理（Memory Bridge）和异常处理（Watcher Agent）。

### 2.2 Document as Global Context (文档即全局总线)

我们摒弃了碎片化的 JSON，采用 Markdown 文档 作为全局状态的载体。每一个 Stage 的输出，都是对这份全局文档的一次"修订"或"增补"。

- Stage 1 生成 reasoner.md（问题分析书）
- Stage 2 生成 strategy.md（战术手册）
- Stage 3 生成 step.md（SOP 执行表）
- Stage 4 执行并回填结果。

这种设计让 Agent 的"思考过程"对人类完全可见、可调试。

## 3. 核心特性深度解析：Fat-Cat 的元认知体系

Fat-Cat 的核心突破在于构建了一个分层的元认知闭环。这不是简单的 Prompt Engineering，而是通过架构强制 Agent 进行"三思而后行"。

🧠 **Stage 1: Metacognitive Analysis (深度意图感知)**

"还没开始做，先想怎么做"

传统的 Agent 收到 "帮我写个爬虫" 可能直接就开始写代码。但在 Fat-Cat 中，Stage 1 Agent (Metacognitive_Analysis_agnet.py) 会强制通过 reasoner.md 进行元认知分析：

- **意图拆解：** 用户是真的只要代码，还是需要部署？
- **约束提取：** 隐含的语言、性能、依赖库要求是什么？
- **信息完备性检查：** 如果信息不足，它会拒绝执行并要求补充，而不是瞎猜。

🧭 **Stage 2: Dynamic Strategy & Metacognitive Search (元认知搜索与进化)**

"知道自己不知道，并主动学习"

这是 Fat-Cat 最具创新性的模块 (stage2_capability_upgrade_agent)。

- **策略检索：** Agent 首先会在本地 strategy_library 中检索是否有类似问题的解决经验。
- **元认知判断：** 如果检索到的策略匹配度低（例如遇到全新的框架或报错），Agent 会触发**"能力升级" (Capability Upgrade)** 信号。
- **元认知搜索 (Metacognitive Search)：**

此时，Agent 会挂起当前任务，启动一个子进程去互联网（通过 Firecrawl/Tavily）进行针对性学习。它不是在搜索"答案"，而是在搜索"解决此类问题的方法论"。

**例子：** 遇到一个新的 Python 库，Agent 会先去读官方文档，总结出用法，生成一个新的 Markdown 策略文件存入库中，然后再回头解决用户的问题。

📝 **Stage 3: Logical Step Decomposition (思维链固化)**

"将思考固化为指令"

在理解了问题（Stage 1）并学会了方法（Stage 2）后，Stage 3 (Step_agent.py) 将生成一份详尽的 SOP（标准作业程序）。这不是模糊的自然语言，而是类似于伪代码的严格步骤，确保 Stage 4 的执行器不会跑偏。

👁️ **Watcher Agent: Runtime Reflection (运行时反思)**

"站在系统之外的观察者"

Watcher_Agent 是一个独立运行的守护进程。它不参与具体任务，而是像看监控一样盯着全局文档的变化。

- **死循环检测：** 如果发现 Stage 4 连续三次输出同样的错误日志。
- **目标偏离：** 如果执行结果与 Stage 1 定义的元认知目标不符。
- **干预机制：** Watcher 有最高权限中断当前 Agent，强制回滚或请求人工介入。

## 4. 架构详解与目录结构

![Fat-Cat Architecture](framework.png)

```bash
Fat-Cat/
├── agents/                 # 基础 Agent 类定义
├── ability_library/        # 核心能力定义 (Markdown 描述)
├── strategy_library/       # [长期记忆] 策略库，存储已习得的解题思路
├── form_templates/         # 结构化输出模板
├── MCP/                    # [I/O 层] Model Context Protocol 工具实现
│   ├── code_interpreter.py # 沙箱代码解释器
│   ├── firecrawl.py        # 智能爬虫 (用于元认知搜索)
│   └── tavily.py           # 搜索引擎
├── Memory_system/          # [内存管理] 负责 Markdown 文档的读写流转
├── Document_Checking/      # [内存完整性] 防止上下文丢失
├── stage1_agent/           # [前额叶] 元认知分析：生成 reasoner.md
├── stage2_agent/           # [调度器] 策略选择：生成 strategy.md
├── stage2_capability_upgrade_agent/ # [进化模块] 负责元认知搜索与策略生成
├── stage3_agent/           # [指挥官] 步骤拆解：生成 step.md
├── stage4_agent/           # [执行器] 任务执行与工具调用
├── Watcher_Agent/          # [看门狗] 运行时监控与异常熔断
├── workflow/               # 流水线编排
├── config/                 # 配置
└── main.py                 # 入口
```

## 5. 快速开始 (Getting Started)

### 环境要求

- Python 3.10+
- 依赖包见 requirements-full.txt

### 安装

```bash
# 1. 克隆项目
git clone https://github.com/your-repo/fat-cat.git
cd fat-cat

# 2. 安装依赖 (提供了一键脚本)
python scripts/install_full_pipeline_deps.py
```

### 配置

在 config/model_config.py 中配置 LLM API Key。Fat-Cat 针对长上下文模型（如 Gemini 1.5 Pro, DeepSeek V3）进行了优化，建议使用支持 32k+ Context 的模型以获得最佳体验。

### 运行

```bash
# 启动全流程流水线
python workflow/full_pipeline_runner.py
```

## 6. 开发者指南：扩展与进化

Fat-Cat 是一个有生命的系统，你可以通过以下方式让它变强：

### 添加新工具 (MCP)

在 MCP/ 目录下继承 _mcp_function.py。Fat-Cat 会自动识别并将其注册到 Stage 4 的工具箱中。

### 手动注入知识 (Strategy Injection)

除了让 Agent 自己上网学，你也可以直接在 strategy_library/ 中添加 Markdown 格式的技术文档。Stage 2 Agent 会立即通过 RAG 索引到这些新知识。

### 调整元认知阈值

在 stage2_agent 中可以调整策略匹配的置信度阈值。阈值越高，Agent 越倾向于触发"能力升级"去搜索新知识，而不是依赖旧经验。

## 7. 许可证

[License 信息]
