# .learnings/ 记录格式规范

## 文件结构

每个项目根目录下创建 `.learnings/` 目录：

```
project/
├── .learnings/
│   ├── LEARNINGS.md    # 学习记录
│   └── ERRORS.md       # 错误记录
├── src/
└── ...
```

## 记录格式

```markdown
## [LRN-YYYYMMDD-XXX] category
**Logged**: 2026-03-04 14:30
**Priority**: high
**Area**: backend

### Summary
一句话说明学到了什么

### Details
完整上下文：
- 发生了什么
- 错在哪
- 正确做法是什么

### Suggested Action
具体的改进建议（可选）
---
```

## Category 类型

| Category | 触发条件 | 示例 |
|----------|---------|------|
| `correction` | 用户纠正了 AI（"不对"、"应该是"） | "应该用 flush 不是 commit" |
| `best_practice` | 发现更好的做法 | "lazy import 避免循环依赖" |
| `knowledge_gap` | 知识过时或不准确 | "这个 API 已经 deprecated 了" |
| `error` | 命令执行失败 | "import path 不存在" |

## 自动触发规则

AI Agent 在以下情况**立即**创建记录，无需用户指示：

1. **命令非零退出** → 写 ERRORS.md
2. **用户说"不对/应该是/你搞错了"** → 写 LEARNINGS.md，category: correction
3. **发现更优方案** → category: best_practice
4. **知识被证实过时** → category: knowledge_gap

## 示例

```markdown
## [LRN-20260304-001] correction
**Logged**: 2026-03-04 14:30
**Priority**: high
**Area**: backend

### Summary
FastAPI 服务层应该用 session.flush() 不是 session.commit()

### Details
在 service 层直接调用 commit() 会导致事务边界不清晰。
正确做法是 service 层只做 flush()（写入但不提交），
由 dependency injection 的 get_db_session 统一管理 commit/rollback。

### Suggested Action
检查所有 service 文件，将 commit() 替换为 flush() + refresh()
---
```
