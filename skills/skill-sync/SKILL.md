---
name: skill-sync
description: Ручная синхронизация скилла во все места (репа-источник, Claude, Codex). Используй только при явном вызове `/skill-sync`; не активируй по смыслу или автоматически после правки скилла.
---

# Sync скилла во все места

## Запуск

Скилл запускается только по явной команде пользователя `/skill-sync`. Просьба создать, изменить или обновить скилл сама по себе не разрешает синхронизацию.

Скилл обязан быть БАЙТ-в-байт одинаков в трёх местах (Windows):

| Место | Путь к `SKILL.md` |
|---|---|
| Репа-источник (git) | `C:\Users\ikotlyarov\Documents\AI\ai-framework\skills\<name>\SKILL.md` |
| Claude global | `C:\Users\ikotlyarov\.claude\skills\<name>\SKILL.md` |
| Codex global | `C:\Users\ikotlyarov\.codex\skills\<name>\SKILL.md` |

`<name>` — слаг скилла (имя папки). Источник правды — репа.

## Процедура
1. Записать **одинаковый** текст SKILL.md во все три пути (новый скилл — сперва создать папку `<name>/` в каждом).
2. Сверить: `diff` репа↔Claude и репа↔Codex — должны совпасть.
3. В репе `Documents\AI\ai-framework` (ветка `main`, remote `origin` → github `Kromeshn/ai-framework`) закоммитить по правилам [[git-commit]] (тип-префикс: `chore:` для правки, `feat:` для нового скилла) и запушить в `origin`.
