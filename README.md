# Localization Quality Gate — PoC

对 **PR/push 变更文件** 中的**用户可见文案**做拼写、语法与一致性检查。

## 检查什么 / 不检查什么

| 检查 | 不检查 |
|------|--------|
| 错误提示 `*_ERROR` / `*_MSG` / `*_TITLE` … | 普通变量、函数名、类名 |
| `translations*` / `english.py` 等文案目录中的大写常量 | `test.py`、`tests/`、`*_test.py` |
| Log / UI / CLI / Exception 类文案常量 | 非文案业务代码、语法都坏掉的杂文件 |
| | `scripts/` 门禁工具自身 |

任意路径都可以，但必须是**用户可见文案**形态，不是「改了任意 .py 就扫全部字符串」。

## 行为摘要

- 只检 PR/push **实际变更的文件**（不加载同目录 sibling）
- 文案目录：抽取全部 `SCREAMING_SNAKE = "..."`  
- 其它文件：仅 `*_ERROR` / `*_MSG` / `*_DIALOG` 等后缀  
- 测试文件直接跳过；语法错误文件警告跳过，**不阻断合入**

## 本地运行

```bash
python3 scripts/extract_messages.py --changed-only --base origin/main -o out/texts.jsonl
python3 scripts/check_consistency.py -i out/texts.jsonl
npm install && python3 scripts/check_spelling.py -i out/texts.jsonl
LQ_STRICT_GRAMMAR=1 python3 scripts/check_grammar.py -i out/texts.jsonl
```
