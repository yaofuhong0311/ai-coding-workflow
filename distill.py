#!/usr/bin/env python3
"""
蒸馏脚本：汇总所有项目的 ruflo DB + .learnings/ 文件，提炼写入 ~/.claude/CLAUDE.md
用法：
  python3 distill.py            # 生成预览，写 pending 文件，等领导确认
  python3 distill.py --dry-run  # 只预览，不写文件
  python3 distill.py --commit   # 领导确认后直接写入 CLAUDE.md
"""

import sqlite3
import os
import sys
import json
import re
from datetime import datetime
from pathlib import Path

CODING_ROOT = Path.home() / "coding"
CLAUDE_MD = Path.home() / ".claude" / "CLAUDE.md"
PENDING_FILE = Path.home() / ".openclaw/workspace/memory/distill-pending.json"

# 项目级 CLAUDE.md 映射：project名 → 文件路径
PROJECT_CLAUDE_MD = {
    "agent2agent": CODING_ROOT / "agent2agent" / "CLAUDE.md",
    "cip_backend": CODING_ROOT / "cip_backend" / "CLAUDE.md",
    "frontisAI-backend": CODING_ROOT / "frontisAI-backend" / "CLAUDE.md",
}
DRY_RUN = "--dry-run" in sys.argv
COMMIT = "--commit" in sys.argv

EXPERIENCE_START = "<!-- DISTILLED_EXPERIENCE_START -->"
EXPERIENCE_END = "<!-- DISTILLED_EXPERIENCE_END -->"


# ─── 来源1：ruflo SQLite DB ────────────────────────────────────────────────────

def find_all_dbs():
    dbs = []
    for db_path in CODING_ROOT.rglob(".swarm/memory.db"):
        project = db_path.parent.parent.name
        dbs.append((project, db_path))
    return dbs


def parse_ruflo_content(content):
    """把 ruflo 原始内容（可能是 JSON）解析成可读文本"""
    if not content:
        return content
    content = content.strip()
    # 尝试 JSON 解析
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            # 优先取 pattern/summary/description/message 字段
            for field in ("pattern", "summary", "description", "message", "insight", "text"):
                if field in data and isinstance(data[field], str) and data[field].strip():
                    return data[field].strip()
            # fallback：拼接所有字符串值
            parts = [str(v) for v in data.values() if isinstance(v, (str, int, float)) and str(v).strip()]
            return " | ".join(parts[:3]) if parts else content
        elif isinstance(data, str):
            return data.strip()
    except (json.JSONDecodeError, ValueError):
        pass
    return content


def read_ruflo_memories(project, db_path):
    memories = []
    try:
        conn = sqlite3.connect(str(db_path))
        rows = conn.execute(
            "SELECT key, content FROM memory_entries ORDER BY rowid DESC"
        ).fetchall()
        for key, content in rows:
            readable = parse_ruflo_content(content)
            memories.append({
                "source": "ruflo",
                "project": project,
                "key": key,
                "content": readable,
            })
        conn.close()
    except Exception as e:
        print(f"  ⚠️  读取 ruflo DB {project} 失败: {e}")
    return memories


# ─── 来源2：.learnings/ markdown 文件 ─────────────────────────────────────────

def read_learnings_files(project, project_path):
    memories = []
    learnings_dir = project_path / ".learnings"
    if not learnings_dir.exists():
        return memories

    for md_file in learnings_dir.glob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")
            # 按 ## [LRN-/ERR-/FEAT- 分割条目
            entries = re.split(r'\n(?=## \[(?:LRN|ERR|FEAT)-)', content)
            for entry in entries:
                entry = entry.strip()
                if not entry or not entry.startswith("## ["):
                    continue
                # 提取 Summary
                summary_match = re.search(r'### Summary\n(.+?)(?:\n###|\Z)', entry, re.DOTALL)
                summary = summary_match.group(1).strip() if summary_match else entry[:100]
                # 提取 category（LRN-20260304-001 后面的词）
                cat_match = re.match(r'## \[(?:LRN|ERR|FEAT)-\d+-\w+\] (\w+)', entry)
                category = cat_match.group(1) if cat_match else "general"

                memories.append({
                    "source": "learnings",
                    "project": project,
                    "file": md_file.name,
                    "category": category,
                    "key": f"{project}_{md_file.stem}_{hash(summary) % 10000}",
                    "content": summary,
                    "full_entry": entry,
                })
        except Exception as e:
            print(f"  ⚠️  读取 .learnings {project}/{md_file.name} 失败: {e}")
    return memories


# ─── 合并 & 去重 ───────────────────────────────────────────────────────────────

def collect_all():
    all_memories = []

    # ruflo DB
    dbs = find_all_dbs()
    for project, db_path in dbs:
        ms = read_ruflo_memories(project, db_path)
        if ms:
            print(f"  [ruflo] {project}: {len(ms)} 条")
        all_memories.extend(ms)

    # .learnings/ 文件
    for project_path in CODING_ROOT.iterdir():
        if not project_path.is_dir():
            continue
        ms = read_learnings_files(project_path.name, project_path)
        if ms:
            print(f"  [.learnings] {project_path.name}: {len(ms)} 条")
        all_memories.extend(ms)

    return all_memories


def deduplicate(all_memories):
    seen = {}
    for m in all_memories:
        key = m["key"]
        if key not in seen or len(m["content"]) > len(seen[key]["content"]):
            seen[key] = m
    return list(seen.values())


# ─── 分类 ──────────────────────────────────────────────────────────────────────

def categorize(memories):
    categories = {
        "架构设计": [],
        "算法与数据结构": [],
        "Bug 与踩坑": [],
        "性能优化": [],
        "纠正记录": [],
        "其他经验": [],
    }
    kw_map = {
        "架构设计": ["架构", "设计", "模式", "异步", "接口", "api", "幂等"],
        "算法与数据结构": ["算法", "dp", "贪心", "排序", "搜索", "二分", "动态规划", "关键词", "匹配"],
        "Bug 与踩坑": ["坑", "错误", "bug", "error", "不能", "失败", "exception"],
        "性能优化": ["性能", "优化", "缓存", "复杂度", "瓶颈"],
        "纠正记录": ["correction", "纠正", "不对", "应该是"],
    }
    for m in memories:
        text = (m.get("content", "") + " " + m.get("category", "")).lower()
        placed = False
        for cat, kws in kw_map.items():
            if any(k in text for k in kws):
                categories[cat].append(m)
                placed = True
                break
        if not placed:
            categories["其他经验"].append(m)
    return categories


# ─── 原子化拆分 ─────────────────────────────────────────────────────────────────

def atomize_content(content):
    """
    把一条蒸馏内容拆成原子化知识条目。
    每条只含一个知识点，标记类型：FACT / RULE / GOTCHA。

    拆分规则：
    1. 按序号分割（"1) ... 2) ..." 或 "1. ... 2. ..."）
    2. 按分号分割
    3. 如果都没有，整条保留

    打标签规则：
    - 含"必须/应该/需要/不要/禁止/先...再/fallback/注意" → RULE
    - 含"坑/bug/错误/失败/null/常为/陷阱/踩" → GOTCHA
    - 其余 → FACT
    """
    content = content.strip()
    if not content:
        return []

    # 尝试按编号拆分：1) ... 2) ... 或 1. ... 2. ...
    numbered = re.split(r'(?:^|\s)(?:\d+[\)\.]\s)', content)
    numbered = [s.strip() for s in numbered if s.strip()]

    if len(numbered) >= 2:
        atoms = numbered
    else:
        # 尝试按分号拆分
        by_semi = [s.strip() for s in content.split("；") if s.strip()]
        if len(by_semi) < 2:
            by_semi = [s.strip() for s in content.split(";") if s.strip()]
        if len(by_semi) >= 2:
            atoms = by_semi
        else:
            atoms = [content]

    # 给每个原子打标签
    tagged = []
    for atom in atoms:
        atom = atom.strip().rstrip("。；;")
        if not atom or len(atom) < 5:
            continue
        tag = _classify_atom(atom)
        tagged.append((tag, atom))
    return tagged


def _classify_atom(text):
    """根据内容关键词判断知识类型"""
    text_lower = text.lower()
    gotcha_kw = ["坑", "bug", "错误", "失败", "null", "常为", "陷阱", "踩", "注意不能",
                 "不生效", "实际上", "但其实", "容易忽略", "常见错误"]
    rule_kw = ["必须", "应该", "需要", "不要", "禁止", "先.*再", "fallback", "注意",
               "建议", "规范", "要求", "确保", "务必", "优先"]

    if any(k in text_lower for k in gotcha_kw):
        return "GOTCHA"
    if any(re.search(k, text_lower) for k in rule_kw):
        return "RULE"
    return "FACT"


TAG_EMOJI = {"FACT": "📌", "RULE": "⚙️", "GOTCHA": "⚠️"}


# ─── 格式化 ────────────────────────────────────────────────────────────────────

def format_block(categories):
    """按项目分组格式化，返回 {target_file: block_content} 字典"""
    today = datetime.now().strftime("%Y-%m-%d")

    # 先按目标文件分桶
    buckets = {}  # target_path -> {cat -> [items]}
    for cat, items in categories.items():
        for m in items:
            proj = m["project"]
            target = PROJECT_CLAUDE_MD.get(proj, CLAUDE_MD)
            if target not in buckets:
                buckets[target] = {}
            if cat not in buckets[target]:
                buckets[target][cat] = []
            buckets[target][cat].append(m)

    # 格式化每个目标文件的内容
    result = {}
    for target, cats in buckets.items():
        lines = [f"\n> 最近蒸馏时间：{today}\n"]
        for cat, items in cats.items():
            if not items:
                continue
            lines.append(f"\n### {cat}\n")
            for m in items:
                proj = m["project"]
                content = m["content"].strip()
                atoms = atomize_content(content)
                if not atoms:
                    text = content.split("\n")[0][:120]
                    lines.append(f"- 📌[{proj}][FACT] {text}")
                else:
                    for tag, atom in atoms:
                        emoji = TAG_EMOJI.get(tag, "📌")
                        lines.append(f"- {emoji}[{proj}][{tag}] {atom}")
        result[target] = "\n".join(lines)
    return result


def format_preview(categories):
    """给飞书通知用的简短预览"""
    lines = []
    total_atoms = 0
    for cat, items in categories.items():
        if not items:
            continue
        # 统计该分类下原子化后的总条数
        cat_atoms = sum(max(len(atomize_content(m["content"])), 1) for m in items)
        total_atoms += cat_atoms
        lines.append(f"**{cat}**（{cat_atoms}条）")
        # 预览前2条的第一个原子
        for m in items[:2]:
            atoms = atomize_content(m["content"])
            if atoms:
                tag, atom = atoms[0]
                emoji = TAG_EMOJI.get(tag, "📌")
                lines.append(f"  {emoji}[{m['project']}][{tag}] {atom[:60]}")
            else:
                lines.append(f"  📌[{m['project']}] {m['content'].strip()[:60]}")
        if len(items) > 2:
            lines.append(f"  ...还有更多")
    return "\n".join(lines)


# ─── 写入 CLAUDE.md ────────────────────────────────────────────────────────────

def write_to_claude_md(experience_blocks):
    """experience_blocks: {target_path: block_content} 字典"""
    for target, block in experience_blocks.items():
        if not target.exists():
            print(f"⚠️  目标文件不存在，跳过: {target}")
            continue
        content = target.read_text(encoding="utf-8")
        pattern = f"{re.escape(EXPERIENCE_START)}.*?{re.escape(EXPERIENCE_END)}"
        def _repl(m):
            return f"{EXPERIENCE_START}\n{block}\n{EXPERIENCE_END}"
        new_content = re.sub(pattern, _repl, content, flags=re.DOTALL)
        target.write_text(new_content, encoding="utf-8")
        print(f"✅ 已写入 {target}")


def write_pending(experience_blocks, total_count, preview):
    today = datetime.now().strftime("%Y-%m-%d")
    # 把 Path key 转成字符串存 JSON
    blocks_serializable = {str(k): v for k, v in experience_blocks.items()}
    pending = {
        "date": today,
        "total_count": total_count,
        "preview": preview,
        "experience_blocks": blocks_serializable,
        "timestamp": int(datetime.now().timestamp()),
        "status": "pending"
    }
    PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    PENDING_FILE.write_text(json.dumps(pending, ensure_ascii=False, indent=2))
    print(f"📝 pending 文件已写入，等待飞书确认")


# ─── 入口 ──────────────────────────────────────────────────────────────────────

def main():
    if COMMIT:
        if PENDING_FILE.exists():
            pending = json.loads(PENDING_FILE.read_text())
            # 兼容旧格式（experience_block 单字符串）和新格式（experience_blocks 字典）
            if "experience_blocks" in pending:
                blocks = {Path(k): v for k, v in pending["experience_blocks"].items()}
            else:
                blocks = {CLAUDE_MD: pending["experience_block"]}
            write_to_claude_md(blocks)
            pending["status"] = "committed"
            PENDING_FILE.write_text(json.dumps(pending, ensure_ascii=False, indent=2))
            print(f"✅ 蒸馏完成，共 {pending['total_count']} 条经验写入")
        else:
            print("⚠️  没有 pending 文件")
        return

    print(f"🔍 扫描 {CODING_ROOT} ...")
    all_memories = collect_all()

    if not all_memories:
        print("⚠️  没有找到任何经验，退出")
        return

    print(f"\n📊 合并前：{len(all_memories)} 条")
    deduped = deduplicate(all_memories)
    print(f"📊 去重后：{len(deduped)} 条")

    categories = categorize(deduped)
    experience_blocks = format_block(categories)
    preview = format_preview(categories)

    if DRY_RUN:
        print("\n=== [DRY RUN] 蒸馏预览 ===")
        for target, block in experience_blocks.items():
            print(f"\n--- 写入: {target} ---")
            print(block)
        print("=== 未写入 ===")
        return

    write_pending(experience_blocks, len(deduped), preview)


if __name__ == "__main__":
    main()
