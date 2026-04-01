# 工具链架构详解

## 四个工具，四个角色

### Claude Code (CC) — 执行者
Claude Code 是实际写代码的 Agent。它能读写文件、执行命令、搜索代码库。

**但它有个致命缺陷：没有跨 session 记忆。** 每次新对话，之前学到的一切全部丢失。

### python-quality-gate.sh — 执法者

`~/.claude/hooks/python-quality-gate.sh` 通过 PostToolUse hook 挂载在 CC 上：

- CC 每次写/编辑 `.py` 文件后，hook **同步**触发脚本
- 违规信息注入 CC 上下文，CC 被迫看到并修复
- 当前检查：ruff lint + hardcode 端口 + 文件超 500 行
- 脚本可持续扩展，加新检查段即永久生效

**机制**：输出驱动。脚本有 stdout 输出 → AI 自动修复；无输出 = 通过。CC 无法绕过。

### ruflo (claude-flow) — 记录者
ruflo 是一个 MCP（Model Context Protocol）工具，以 hooks 形式挂载在 CC 上：

- 所有 coding 操作自动触发 ruflo hooks
- 经验存储在 SQLite 数据库（`.swarm/memory.db`）
- 支持 `memory_search` 查询历史经验
- 支持 `memory_store` 存储新经验

ruflo 解决了"采集"问题——每次编码的经验都不丢失。

### OpenClaw — 编排者
OpenClaw 是 AI Agent 运行时，在本工作流中承担：

- **定时任务**：每天 19:00 触发蒸馏脚本
- **通知渠道**：通过飞书推送蒸馏预览
- **审核流程**：接收用户确认，触发写入
- **日常助理**：面试准备、信息推送等

## 三步工作流

```
superpowers 脑爆 → superpowers plan → CC 执行（ruflo + ast-grep 自动挂载）
```

**第一步：脑爆**
- 用脑爆模型讨论需求
- 发散思路，探索方案空间
- 产出：方向性结论 + 技术选型

**第二步：计划**
- 写结构化实施计划，保存到当前项目 `docs/plans/`
- `find-plan.sh` 优先从 `$PWD/docs/plans/` 查找，回退到 `~/coding/.plans/`
- plan.md 建议包含 `## 核心约束` 章节，PreToolUse hook 自动提取注入上下文
- 用户确认后再动手
- 产出：plan.md

**第三步：执行**
- CC 按 plan 逐步实现
- python-quality-gate.sh hook 实时拦截 Python 问题代码（同步，不可绕过）
- ruflo 自动记录经验
- 学习记录自动写入 `.learnings/`
- 产出：代码 + 经验数据

**代码审查（可选）**
- 日常：superpowers code-reviewer（快速单 Agent 审查）
- 合并前：`/fagan-review`（双 Agent 并行审查——结构检查 + 语义检查，合并去重出报告）

## 为什么不直接起 CC 写代码？

因为 AI Agent 在没有明确目标的情况下容易"抢跑"——按自己理解的方向开始实现，做完才发现方向错了。

先对齐（脑爆 + plan），再执行。这和人类工程师的工作方式一样。
