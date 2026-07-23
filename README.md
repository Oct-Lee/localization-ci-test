# Localization Quality Gate — PoC

GitHub CI gate that checks **user-facing translation strings** (not identifiers)
for spelling, grammar, and cross-locale consistency.

Designed to mirror [unitx-monorepo](https://github.com/) Pattern A:

```text
translations*/english.py
translations*/chinese.py
translations*/portuguese.py
```

## What it checks

| Check | Tool | Locales | Severity |
|-------|------|---------|----------|
| Key alignment / placeholders / empty strings / CN punct in EN | `scripts/check_consistency.py` | en/zh/pt | **Error** |
| Spelling | cspell + `dictionaries/unitx-terms.txt` | en, **pt-BR** (+ pt-PT dict) | **Error（阻断）** |
| Grammar | LanguageTool (Docker) | en-US, pt-PT | **Error（阻断）** |

CI 中拼写与语法为**并行 job**（互不等待、互不阻断对方执行）；`LQ_STRICT_GRAMMAR=1`，最终 Gate 汇总任一失败则整体红灯。

> Spelling uses **pt-BR** dictionaries because product copy (e.g. `câmera`) matches Brazilian Portuguese; LanguageTool still runs `pt-PT` for grammar to align with X-platform `pt-PT` locale labels. Orthography-reform nags from LT are filtered.

Chinese (`chinese.py`) is included in consistency checks only (no spell/grammar).

## Layout

```text
src/translations/
  english.py | chinese.py | portuguese.py   # 标准语言文件名
  *.py                                      # 其它文案模块也会被扫描（按内容推断 locale）
scripts/
  extract_messages.py   # 支持全量 / --changed-only PR 增量
```

### 为什么以前新增 `666.py` / `888.py` 不会被检查？

旧逻辑**只认**文件名 `english.py` / `chinese.py` / `portuguese.py`。  
现已改为扫描 `translations*/**/*.py`，并用文件名或文案内容推断 `en` / `zh` / `pt`。

### PR 增量

`pull_request` 事件下使用：

```bash
python3 scripts/extract_messages.py --changed-only --base <PR_BASE_SHA>
```

只抽取相对 base **变更过的** translations 下 `.py`，不做整仓检测。

## Local run

### Extract only

```bash
python3 scripts/extract_messages.py --root . -o out/texts.jsonl
```

### Consistency

```bash
python3 scripts/check_consistency.py -i out/texts.jsonl
```

### Spelling

```bash
npm install
python3 scripts/check_spelling.py -i out/texts.jsonl
```

### Grammar (needs LanguageTool)

```bash
docker run -d --name languagetool -p 8010:8010 silviof/docker-languagetool
# wait until ready, then:
python3 scripts/check_grammar.py -i out/texts.jsonl
```

### Full gate

```bash
# Skip grammar if Docker is unavailable:
python3 scripts/run_lq_gate.py --skip-grammar

# Full (LanguageTool must be on :8010):
python3 scripts/run_lq_gate.py
```

## Intentional bad examples (this PoC)

[`src/translations/english.py`](src/translations/english.py) includes known issues so CI can prove the gate works:

- Spelling: `Founded`, `configration`
- Grammar: `Camera have started` (warning)
- Chinese punctuation in English: `，`
- Empty string: `EMPTY_PLACEHOLDER`
- Placeholder mismatch vs Chinese: `PLACEHOLDER_MISMATCH_DEMO`

Expect **failing** CI until those samples are fixed — that is intentional.

## False-positive controls

1. **Extract-then-check** — cspell only sees string values under `out/spell/`, never constant names like `CAMERA_NOT_FOUND_ERROR`.
2. **Project dictionary** — add product terms to [`dictionaries/unitx-terms.txt`](dictionaries/unitx-terms.txt).
3. **LanguageTool ignores** — add rule IDs to [`languagetool-ignore.txt`](languagetool-ignore.txt); style categories are already filtered.
4. **Tiered gate** — grammar does not block by default.

## Porting to unitx-monorepo

1. Copy `scripts/`, `cspell.json`, `dictionaries/`, `languagetool-ignore.txt`.
2. Point extract globs at P0 roots, for example:

```bash
python3 scripts/extract_messages.py --root . \
  --glob 'apps/production/production_src/translations_prod/*.py' \
  --glob 'shared/config/config/translations/*.py' \
  --glob 'apps/optix/optix_src/server/translations_optix/*.py' \
  --glob 'apps/digix_client/digix_client_src/translations/*.py' \
  --glob 'apps/cortex/backend/translations_backend/*.py' \
  --glob 'platform/boot_check/translations/*.py' \
  -o out/texts.jsonl
```

3. Add a workflow job similar to [`.github/workflows/localization-check.yml`](.github/workflows/localization-check.yml).
4. For first rollout on a large catalog, introduce an allowlist/baseline of known findings so only **new** issues fail the PR (not included in this PoC).

## Out of scope (Phase 1)

- JS `TranslationsCnst`, X-platform `i18n.csv`, i18next / vue-i18n
- Scattered `raise ValueError("...")` / log strings
- README / docs prose
