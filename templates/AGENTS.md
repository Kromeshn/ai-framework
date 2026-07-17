<!-- Рыба CLAUDE.md для нового проекта: заполнить плейсхолдеры <...>, пустые разделы удалить.
     AGENTS.md — идентичная копия этого файла (правятся парой). -->

# <Имя проекта>

## Project Overview

**Описание:** <что за система: что принимает, что отдаёт, для кого — 2–3 строки>

**Архитектура:** <форма и стек: single-file скрипт / HTTP-сервис / пайплайн; ключевые технологии>

---

## Project Structure

```
├── <код проекта>
├── README.md                    # Входная дверь проекта
├── INSTALLATION.md              # Установка и деплой
├── docs/
│   ├── B0-context.md            # Бизнес-контекст
│   ├── target-architecture.md   # Целевая картина, временный
│   ├── L1-architecture.md       # Архитектура системы
│   ├── L2-functions.md          # Описание функций
│   ├── ROADMAP.md               # Шаги проекта
│   ├── _backlog.md              # Парковка отложенного
│   ├── _methodology.md          # Методология, gitignored
│   ├── Business artifacts/      # Сырьё дискавери, gitignored
│   ├── Meeting Transcripts/     # Транскрипты, gitignored
│   ├── Meeting Protocols/       # Протоколы встреч
│   └── Archive/                 # Закрытое и отжившее
└── ...
```

---

## Методология

Процесс разработки — [docs/_methodology.md](docs/_methodology.md): жизненный цикл проекта, цикл изменения, артефакты документации. Источник правды фрейма — репа `ai-framework`.

Если мы в рамках цикла изменения, выполняй только явно запрошенный этап и не переходи к другому автоматически, если не сказано обратного: Sensemaking, Human Plan, Human Plan Review, Agent Plan, Implementation, Implementation Review, Live Validation, Doc Sync, Commit + Push.

---

## Проектные правила

<грабли и исключения, которых нет в скиллах и методологии: особые пути,
тестовые окружения, ограничения инструментов. Пример: «docs/Meeting Transcripts/
в gitignore — Grep-тул их не видит, искать bash-grep'ом». Нет таких — раздел удалить.>
