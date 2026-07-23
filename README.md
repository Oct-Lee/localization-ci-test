# Localization Quality Gate — PoC

GitHub CI gate：对 **PR / push 中变更或新建的文件** 抽取用户可见字符串，做拼写、语法与一致性检查。

**不做整仓扫描**；**不限定 `translations/` 目录**——仓库任意路径只要改到含文案常量的源文件都会检。

## 会检查什么

从变更文件中抽取模块级 `SCREAMING_SNAKE = "..."` 字符串（用户可见文案常量），然后：

| 检查 | 工具 | 严重度 |
|------|------|--------|
| 一致性（空串、占位符、英文中文标点等） | `check_consistency.py` | Error 阻断 |
| 拼写 | cspell | Error 阻断 |
| 语法 | LanguageTool | Error 阻断（`LQ_STRICT_GRAMMAR=1`） |

中文内容：一致性会检；拼写/语法跳过（按 locale 推断）。

**不会检查：** 变量名、函数名、类名、未改动的历史文件。

## 必须要 `scripts/` 吗？

**不必定叫 `scripts/`**，但需要有一段可执行的抽取 + 检查逻辑：

| 做法 | 说明 |
|------|------|
| 独立脚本（当前：`scripts/*.py`） | **推荐**：可本地复跑、易测、workflow 只负责编排 |
| 全部写进 workflow `run: \|` | 可以，但难维护、难本地调试 |
| 只用 Marketplace Action 扫整文件 | 会把标识符当单词，误报高，**不推荐**单独使用 |

目录可以改成 `tools/lq/` 等，本质是「抽取器 + 检查器」，不是文件夹名字本身。

## PR 如何触发

```text
pull_request / push
    → git diff base...HEAD（任意路径）
    → 从变更的 *.py 抽取文案常量
    → 并行：consistency / spelling / grammar
    → gate 汇总阻断
```

## 本地运行

```bash
# 模拟 PR：只抽相对 base 的变更文件
python3 scripts/extract_messages.py --changed-only --base origin/main -o out/texts.jsonl

# 指定文件（任意路径）
python3 scripts/extract_messages.py --files path/to/any.py -o out/texts.jsonl

python3 scripts/check_consistency.py -i out/texts.jsonl
npm install && python3 scripts/check_spelling.py -i out/texts.jsonl
# LanguageTool 就绪后：
python3 scripts/check_grammar.py -i out/texts.jsonl
```

## 误报控制

1. 先抽取字符串再检查（cspell 看不到常量名）  
2. [`dictionaries/unitx-terms.txt`](dictionaries/unitx-terms.txt) 术语表  
3. [`languagetool-ignore.txt`](languagetool-ignore.txt) 规则忽略  
4. 跳过 `scripts/`、`node_modules/`、`third_party/` 等目录  

## 当前限制（PoC）

- 仅支持 **Python** 模块级大写常量字符串  
- 尚未覆盖 JS/CSV/i18next 等格式（可后续加抽取器）  
- 散落的 `raise ValueError("...")` 默认不抽（避免噪声；若需要可另开规则）
