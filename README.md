# Localization Quality Gate — PoC

对 **PR/push 变更文件** 抽取用户可见字符串，做**通用**拼写、语法与一致性检查（不写死具体错词）。

## 原则

| 项 | 行为 |
|----|------|
| 范围 | git diff 变更的 `*.py`（任意目录），不做整仓扫描 |
| 抽取 | 模块级 `SCREAMING_SNAKE = "..."` 字符串常量 |
| 拼写 | **cspell 全词典**（任意生僻/错误单词），术语白名单见 `dictionaries/` |
| 语法 | **LanguageTool 全规则**（任意语法/拼写命中），仅忽略 `languagetool-ignore.txt` |
| 一致性 | 空串、英文中文标点；多语言**共有 key** 的占位符对齐（默认不强制缺 key） |

## 一致性说明

默认 **incremental**（适合 PR）：

- 只对「本次目录里出现在 ≥2 种语言」的 key 比对占位符  
- **不会**因为只改了英文文件就要求中文补齐所有 key  

全量对齐（可选）：

```bash
python3 scripts/check_consistency.py -i out/texts.jsonl --strict-locale-alignment
```

## 本地运行

```bash
python3 scripts/extract_messages.py --changed-only --base origin/main -o out/texts.jsonl
# 或指定文件：
python3 scripts/extract_messages.py --files src/translations/888.py src/translations/666.py -o out/texts.jsonl

python3 scripts/check_consistency.py -i out/texts.jsonl
npm install && python3 scripts/check_spelling.py -i out/texts.jsonl
LQ_STRICT_GRAMMAR=1 python3 scripts/check_grammar.py -i out/texts.jsonl
```

## 关于 scripts/

不必定叫 `scripts/`，但需要独立抽取/检查逻辑（比全部写进 workflow 更好维护）。

## 已知坑（已修）

| 问题 | 原因 | 修复 |
|------|------|------|
| `oef` 等 3 字母错词不报 | cspell 默认 `minWordLength=4` | 设为 `2` |

**范围：** 只检查 PR/push **实际变更的文件**，不自动加载同目录其它文件。  
跨语言占位符一致性：仅当本次 PR **同时改到** 多种语言文件且含同一 key 时才会比对。

- 目前主要支持 Python 大写常量字符串  
- 中文不做 LT 拼写/语法（工具能力不足）；仍做一致性  
- LanguageTool 免费规则无法覆盖所有语法问题（如部分主谓不一致）
