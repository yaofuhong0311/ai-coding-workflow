# 工具链架构详解

## 三个工具，三个角色

### Claude Code (CC) — 执行者
Claude Code 是实际写代码的 Agent。它能读写文件、执行命令、搜索代码库。

**但它有个致命缺陷：没有跨 session 记忆。** 每次新对话，之前学到的一切全部丢失。

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
superpowers 脑爆 → superpowers plan → CC 执行（ruflo 自动挂载）
```

**第一步：脑爆**
- 用脑爆模型讨论需求
- 发散思路，探索方案空间
- 产出：方向性结论 + 技术选型

**第二步：计划**
- 写结构化实施计划（存到 `~/coding/.plans/`）
- 用户确认后再动手
- 产出：plan.md

**第三步：执行**
- CC 按 plan 逐步实现
- ruflo 自动记录经验
- 学习记录自动写入 `.learnings/`
- 产出：代码 + 经验数据

## 为什么不直接起 CC 写代码？

因为 AI Agent 在没有明确目标的情况下容易"抢跑"——按自己理解的方向开始实现，做完才发现方向错了。

先对齐（脑爆 + plan），再执行。这和人类工程师的工作方式一样。
