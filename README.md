# ai-framework

Персональный фреймворк Agentic Software Development: методология, скиллы и шаблоны проектных файлов.
Модель — «репа-мать»: источник правды здесь. `/skill-sync` по явной команде
приводит репозиторную версию скилла и глобальные копии Claude/Codex к
байт-в-байт одинаковому состоянию. Шаблонные `CLAUDE.md` и `AGENTS.md`
копируются в корень проекта, `project.gitignore` — туда же как `.gitignore`,
`_methodology.md` — в `docs/_methodology.md`.

## Layout

```
ai-framework/
├── skills/
│   └── <name>/SKILL.md      # Источник правды для скилла
├── templates/
│   ├── CLAUDE.md            # Рыба проектного CLAUDE.md
│   ├── AGENTS.md            # Рыба, копия CLAUDE.md
│   └── project.gitignore    # Рыба .gitignore нового проекта
├── _methodology.md          # Методология: жизненный цикл, цикл изменения, артефакты
├── CLAUDE.md                # Инструкции агентам, работающим в этой репе
├── AGENTS.md                # То же для Codex
└── README.md                # Этот файл
```
