# Raw sources (immutable)

Сюда кладём оригиналы. **Не редактировать** после ingest — только добавлять новые файлы.

## Структура

```
raw/
  inbox/          # новые источники до классификации
  assets/         # картинки/вложения (Obsidian attachment folder)
  forehand/       # опционально по темам
  serve/
  ...
```

## Как добавить

1. Статья/PDF → сохранить md в `inbox/` (Obsidian Web Clipper ок).
2. Сказать агенту: «ingest `raw/inbox/<file>`».
3. После ingest файл можно перенести в `raw/<topic>/`.

PDF целиком можно хранить рядом; для wiki предпочтительнее текст/md excerpt.
