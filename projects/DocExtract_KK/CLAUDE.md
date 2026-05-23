# DocExtract_КК

## Plane

- **Project:** DocExtract_КК (`OCRKK`)
- **project_id:** `0cbbf9ac-41dc-4f85-992c-950007f0c25f`
- **workspace_id:** `9d8ca3cd-8461-498e-8634-27e955016ba4`

Использовать эти ID напрямую в MCP-вызовах Plane, чтобы не делать `list_projects`.

---

## Project Overview

**Описание:** FastAPI HTTP-сервис для распознавания счёта на оплату: извлечение банковских реквизитов из первой страницы PDF через OCR.

**Архитектура:** Single-file Python script ([main.py](main.py))

---

## Project Structure

```
├── main.py
├── docs/
│   ├── _methodology.md          # Методология документирования
│   ├── B0-context.md            # Бизнес-контекст
│   ├── L1-architecture.md       # Архитектура системы
│   └── L2-functions.md          # Описание функций
├── sgr/                         # Промпты и JSON-схемы для vLLM
└── .claude/skills/              # git-commit, dignified-python, sgr-debug
```

---

## Синхронизация документации

После каждого изменения [main.py](main.py) ОБЯЗАТЕЛЬНО актуализируй диаграммы в `docs/` в соответствии с изменениями в коде. Диаграмма должна всегда отражать текущее состояние скрипта.

---

## Структура планового файла

Когда в plan mode согласован и принят план реализации фичи — первым делом перенеси его целиком в `docs/<feature>.md`. Файл = полная копия согласованного в чате плана, не его пересборка. Обязательные секции:

- **Контекст** — что и зачем, связь с Plane-тикетом.
- **Валидация** — чек-лист приёмки, `✅` по мере прохождения.

По необходимости — **Этапы** (что меняется функционально, пронумерованно) и другие разделы. Эталон по плотности и стилю: [docs/Archive/docker-deploy.md](docs/Archive/docker-deploy.md).

---

## Предпочтения по объяснению

Учитывай профиль пользователя: технически сильный, но не Python-разработчик.

В **ответах в чате** Mermaid не рендерится — использовать текстовое объяснение или ASCII-диаграммы.
Mermaid уместен только в **файлах документации** (`docs/`, `README.md`, `CLAUDE.md`).

---

## Coding Approach (karpathy-guidelines)

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.