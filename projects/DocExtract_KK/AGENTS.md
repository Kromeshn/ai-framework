# DocExtract_КК

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

Агент редактирует или создаёт файлы в `docs/` только по явному разрешению пользователя. Без разрешения — даёт draft в чат.

Любая правка документации должна быть максимально плотной: полевая шпаргалка, только смысл, без воды.

Документы проекта — это не место для инициативной переработки.
При обновлении планов сохраняй исходный жанр, структуру и намерение.
Фактические отклонения добавляй отдельным минимальным блоком, не превращая план в отчёт.

---

## Предпочтения по объяснению

Учитывай профиль пользователя: технически сильный, но не Python-разработчик.

В **файлах документации** (`docs/`, `README.md`) для схем предпочитай Mermaid.
В **ответах в чате** Mermaid может не рендериться — использовать текстовое объяснение или ASCII-схему.

---

## Git

Перед любым коммитом следуй правилам из [.claude/skills/git-commit/SKILL.md](.claude/skills/git-commit/SKILL.md).

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

---

## Code Style

Для `.py` файлов перед написанием или редактированием прочитай [.claude/skills/dignified-python/SKILL.md](.claude/skills/dignified-python/SKILL.md) и следуй его правилам — это Python-специфичная реализация принципов выше (LBYL, Never Swallow Exceptions, type hints, PEP 8).

**Рекомендуемые инструменты** (если установлены): `ruff`, `mypy`, `pytest`.
