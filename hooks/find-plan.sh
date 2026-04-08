#!/bin/bash
# find-plan.sh — 查找当前项目的 plan.md
# 优先从项目本地 docs/plans/ 查找，回退到 ~/coding/.plans/
#
# 安装：复制到 ~/.claude/hooks/find-plan.sh
# 用途：被 pre-tool-use-write.sh 和 PreCompact hook 调用，自动注入 plan 核心约束

# 先找 $PWD/docs/plans/ 或 $PWD/*/plans/
PLAN=$(find "${PWD}" -maxdepth 5 -path "*/docs/plans/*.md" 2>/dev/null | grep -v TEMPLATE | sort -r | head -1)

# 再找任意 plans 目录
if [ -z "$PLAN" ]; then
    PLAN=$(find "${PWD}" -maxdepth 5 -path "*/plans/*.md" 2>/dev/null | grep -v TEMPLATE | sort -r | head -1)
fi

# 回退到全局 .plans 目录
if [ -z "$PLAN" ]; then
    PLAN=$(ls ~/coding/.plans/*.md 2>/dev/null | grep -v TEMPLATE | sort -r | head -1)
fi

echo "$PLAN"
