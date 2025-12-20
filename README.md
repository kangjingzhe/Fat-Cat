<p align="center">
  <img src="Image 2025年11月16日 16_14_49.png" alt="neosgenesis logo" width="220">
</p>

## 项目简介

`neogenesis` 是一个以 Markdown 文档为核心的多阶段多 Agent 工作流。所有任务都通过 `workflow/full_pipeline_runner.py` 串联模板生成、Stage1～4 代理、策略/能力自我升级以及 Watcher 审计，实现“看得见、可复用、可调试”的上下文工程。

## 阶段 Agent 角色速览

| 阶段 | 入口文件 | 核心职责 |
| ---- | -------- | -------- |
| Stage 1：元能力分析 | `stage1_agent/Metacognitive_Analysis_agnet.py` | 读取协作表 `## 索引` 与用户上下文，识别任务类型、关键风险、所需能力，并把分析写回 `finish_form`。 |
| Stage 2-A：候选策略 | `stage2_candidate_agent/Candidate_Selection_agent.py` | 在 `strategy_library/strategy.md` 中检索/拼接 2-3 条策略候选，输出动因、覆盖范围与适用能力。 |
| Stage 2-B：策略遴选 | `stage2_agent/Strategy_Selection_agent.py` | 对候选策略进行批判、融合和加固，产生唯一的 `refined_strategy` 以及交接说明 `handover_notes`。 |
| Stage 2-C：策略库升级 | `stage2_capability_upgrade_agent/stage2_capability_upgrade_agent.py` | 结合 Stage1 & Stage2-B 输出判断是否需要向策略库写入补丁（可配置自动写入）。 |
| Stage 3：执行规划 | `stage3_agent/Step_agent.py` | 将最终策略分解为可执行计划（步骤、质量校验、可用工具、风险映射），供 Stage4 执行。 |
| Stage 4：执行与复盘 | `stage4_agent/Executor_agent.py` | 在工具桥 (`stage4_agent/tools_bridge.py`) 支持下执行计划，记录工具调用、结果、偏差与“Final Answer”。 |
| Watcher 审计 | `Watcher_Agent/Watcher_agent.py` | 贯穿 Stage4 工具循环，针对偏差、空结果或多次失败提供实时纠偏建议。 |
| 能力升级 Agent | `capability_upgrade_agent/capability_upgrade_agent.py` | 针对 `ability_library/core_capabilities.md` 生成/调整能力条目，使系统长期演化。 |

所有代理共享统一模型配置（`OPENAI_API_KEY` / `KIMI_API_KEY` / `DEEPSEEK_API_KEY`）。若开启 Watcher，可单独在 `.env` 中提供 `WATCHER_*` 参数。

## 测试数据集与脚本

| 数据集 / 任务 | 入口脚本 | 完整结果路径 | 日志路径 | 描述 |
| ------------- | -------- | ------------ | -------- | ---- |
| AIME 2025 | `AIME_2025/run_aime_benchmark.py` | `AIME_2025/full_pipeline_results.jsonl`（汇总：`full_pipeline_results_summary.json`） | — | 对 AIME 数据进行全流程基准评估，并在脚本内自动提取、归一化数值答案。 |
| Bamboogle | `bamboogle_benchmark/run_bamboogle_benchmark.py`（以及 `test_bamboogle_pipeline.py`） | `bamboogle_benchmark/results.jsonl`（重判：`results_rejudged.jsonl` / `rejudged_results.jsonl`） | `bamboogle_benchmark/benchmark.log` | 针对 Bamboogle 问答的流水线，支持 `rejudge_result.py` 等脚本从日志中提纯 Final Answer 重新判定。 |
| GAIA | `GAIA/run_gaia_validation_tests.py` | `GAIA/logs/*.log`（验证任务以日志为主） | `GAIA/logs/*.log` | 运行 GAIA Validations，日志位于 `GAIA/logs/`。 |
| GPQA | `GPQA/run_gpqa_eval.py` | `GPQA/gpqa_results.jsonl`（汇总：`gpqa_results.summary.json`） | `GPQA/logs/*.log` | 针对 GPQA 数据集的评估脚本，包含多种 Final Answer 抽取与清洗逻辑。 |
| HotpotQA | `hotpot_QA/test_revalidation_report.py` 等 | `hotpot_QA/hotpotqa_eval_results.jsonl`（重判：`revalidated_robust.jsonl`） | `hotpot_QA/logs/hotpotqa_eval.log` | 提供多轮验证脚本，可对 Stage4 输出进行候选提纯、别名/数字等价判断后重判。 |
| MedQA | `Med_QA/run_medqa_full_pipeline_eval.py` | `Med_QA/medqa_eval_results.jsonl`（英文版：`medqa_eval_results_en.jsonl`） | `hotpot_QA/logs/medqa_eval.log`（英文版：`hotpot_QA/logs/medqa_eval_en.log`） | 运行医疗问答全流程评测，内置数据清洗与离线检索 fallback。 |
| MBPP | `MBPP/run_baseline.py`、`MBPP/run_full_pipeline_benchmark.py` | `MBPP/pipeline_results.jsonl`（补充：`MBPP/results.jsonl`） | `MBPP/pipeline_benchmark.log` | 针对代码生成基准，可同样搭配日志解析做结果复核。 |
| 其他工具 / 样例 | `test_tavily_hardcoded.py`、`Document_Checking/template_generation.py` | — | — | 供单功能调试使用。 |

<p style="color:#ffffff;"><strong>提纯 / 再判定补充：</strong><br/>
HotpotQA：`hotpot_QA/test_revalidation_report.py` 读取 `incorrect_with_answers.jsonl`，通过候选提取、别名与数字等价匹配输出 `revalidated_robust.jsonl`。<br/>
Bamboogle：`bamboogle_benchmark/rejudge_result.py` 解析 `benchmark.log`，清洗 Final Answer 段落后生成 `rejudged_results.jsonl`。<br/>
MedQA：数据来自 `Med_QA/data_clean/*`，脚本若无法访问 Elasticsearch 会回退到本地分句后的教材语料，确保上下文噪声可控。<br/>
所有重判结论最终由 `Gemini-3.0-pro` 统一审核，确保跨数据集的一致性标准。</p>

每个目录下均附带对应 `logs/` 或 `*.jsonl` 结果文件，可直接定位评估输出。

## 依赖安装与环境准备

1. **推荐方式：** 使用安装脚本 `scripts/install_full_pipeline_deps.py`  
   ```bash
   python scripts/install_full_pipeline_deps.py --upgrade
   ```
   - 该脚本按“core / stage4”分组安装依赖，并自动下载 `en_core_web_sm` 模型。  
   - 可通过 `--groups core` / `--no-stage4-extras` 控制安装范围，使用 `--dry-run` 查看命令。

2. **脚本异常时的备用方案：** 使用 `requirements-full.txt`  
   ```bash
   pip install -r requirements-full.txt
   python -m spacy download en_core_web_sm
   ```

3. **环境变量：** 在项目根目录创建 `.env`，至少包含：
   ```env
   OPENAI_API_KEY=xxx   # 或 KIMI_API_KEY / DEEPSEEK_API_KEY
   TAVILY_API_KEY=xxx
   FIRECRAWL_API_KEY=可选
   ```

4. **运行全流程：**  
   ```bash
   python -m workflow.full_pipeline_runner --objective "用一句话描述任务"
   ```
   输出将包含最新 `finish_form/*.md` 路径与策略/能力升级提示。

如有新的依赖或数据集，可在 `scripts/install_full_pipeline_deps.py` 中扩展示例组，同时更新 README 对应段落。祝使用顺利！ 🎯
