# skills

Персональный mirror моих глобальных скиллов и проектных конфигов AI-агентов.
Обновляется **еженедельно по пятницам в 16:00** локальной Scheduled Task
`skills-sync` (хранится в `C:\Users\ikotlyarov\.claude\scheduled-tasks\skills-sync\`).

## Layout

```
skills/<name>/SKILL.md           — унифицированная версия скилла
skills/<name>/agents/openai.yaml — Codex-манифест, если есть
projects/DocExtract_KK/          — снимок CLAUDE.md / AGENTS.md / docs/_methodology.md
reports/DRIFT_REPORT.md          — последний отчёт о расхождениях
reports/history/                 — снимки по запускам
reports/backups/                 — версии, перезаписанные newer-wins
```

## Статус

**Baseline-снапшот, 2026-05-23.** Рутины ещё нет. Это первичный инвентарь
скиллов и проектных файлов для дальнейшего ревью. Целевая модель
синхронизации, exclude-листы и место хранения coding-discipline-правил
не финализированы — см. раздел «Open decisions» в `reports/DRIFT_REPORT.md`.

## Направление развития

Изначальная идея — репа как зеркало локальных папок. По итогу
обсуждения 2026-05-23 направление развернулось: **репа становится
источником истины** («матерью»), рабочие машины подтягивают её
содержимое в локальные `.claude\skills`, `.codex\skills`
и проектные `CLAUDE.md`/`AGENTS.md`. Финальный механизм синхронизации
определяется после ревью на домашней машине.

## Источники инвентаря (на момент baseline)

- Claude skills: `C:\Users\ikotlyarov\.claude\skills\`
- Codex  skills: `C:\Users\ikotlyarov\.codex\skills\`
- Project: `C:\Users\ikotlyarov\Documents\AI\DocExtract_КК\`

## Правила синхронизации

| Случай | Действие |
|---|---|
| Скилл идентичен в обоих окружениях | копируется в `skills/<name>/` |
| Скилл отличается в обоих           | **newer-wins по mtime**; loser → `reports/backups/`; winner → loser side и в репу |
| Скилл только в одном окружении     | копируется в репу, второе окружение **не трогается**; пишется в `DRIFT_REPORT.md` |
| `agents/openai.yaml`               | копируется рядом со SKILL.md, если есть хоть с одной стороны |

CLAUDE.md и AGENTS.md проекта сверяются по общим markdown-заголовкам, расхождения
пишутся в `DRIFT_REPORT.md`, **сами файлы не модифицируются**.
