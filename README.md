# Localization Quality Gate — PoC

对 **PR/push 变更文件** 抽取**用户可见字符串**，做**通用**拼写、语法与一致性检查（不写死具体错词）。

## 检查什么 / 不检查什么

| 检查 | 不检查 |
|------|--------|
| 文案目录（`translations*` / `english.py`…）中的 `SCREAMING_SNAKE = "..."` | 普通变量、函数名、类名 |
| 其它 `.py` 中的 `*_ERROR` / `*_MSG` / `*_MODE` / `*_DIALOG` 等文案常量 | `tests/`、`test_*.py`、`*_test.py` |
| `logger.info` / `logger.warning` / `logger.error`（及 `logging.*`）字符串参数 | `scripts/`、第三方目录 |
| Shell（`.sh` 或 `#!/bin/bash` 等，含误命名为 `.py`）里的 `echo`/`printf` 用户文案 | |
| 任意拼写错误（cspell 词典） | **无法解析的杂 Python 文件**（仅 notice，不阻断） |
| 任意语法/语言问题（LanguageTool 规则） | |

## 行为摘要

- 只检 PR/push **实际变更的文件**（不自动加载同目录其它文件）
- 拼写/语法为通用引擎，不维护「错词黑名单」
- 语法错误的 `.py`：**跳过并提示**，不会再用 `Syntax error` 误报成合入失败原因
- 一致性：空串、英文中文标点；本次变更里多语言共有 key 的占位符对齐

## 报错格式（示例）

```text
[ERROR] test.py:1: Spelling: Unknown word (wuord) | key=DEVELOPER_MODE | text='Developer Mode wuord summer'
```

## 本地运行

```bash
python3 scripts/extract_messages.py --changed-only --base origin/main -o out/texts.jsonl
# 或：
python3 scripts/extract_messages.py --files test.py -o out/texts.jsonl

python3 scripts/check_consistency.py -i out/texts.jsonl
npm install && python3 scripts/check_spelling.py -i out/texts.jsonl
LQ_STRICT_GRAMMAR=1 python3 scripts/check_grammar.py -i out/texts.jsonl
```

## 已知坑

| 问题 | 原因 | 处理 |
|------|------|------|
| `oef` 等短词不报 | cspell 默认 `minWordLength=4` | 已设为 `2` |
| 合入时只看到 Syntax error | 杂文件无法 parse 曾直接失败 | 已改为 skip + notice |
| `test.py` 里 `Evrror` 不报 | 文件是 bash（`#!/bin/bash`），按 Python 解析会跳过 | 已支持 shell shebang / `.sh` 的 echo 文案 |
