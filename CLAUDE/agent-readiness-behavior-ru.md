# Поведенческие правила для AI-агента (Karpathy-inspired)

Reference extract публичных правил, снижающих типичные ошибки LLM в кодинге. Wording близок к оригиналу.

**Источник:** [github.com/forrestchang/andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills) (MIT License). На основе [публичных наблюдений Andrej Karpathy](https://x.com/karpathy/status/2015883857489522876) о типичных промахах LLM в кодинге.

**Trade-off (из источника):** правила склоняют в сторону осторожности, а не скорости. Для тривиальных задач (typo, очевидный one-liner) используй здравый смысл. Цель: снизить дорогие ошибки на нетривиальной работе, не тормозить простую.

---

## Проблемы (по Karpathy)

> The models make wrong assumptions on your behalf and just run along with them without checking. They don't manage their confusion, don't seek clarifications, don't surface inconsistencies, don't present tradeoffs, don't push back when they should.

> They really like to overcomplicate code and APIs, bloat abstractions, don't clean up dead code... implement a bloated construction over 1000 lines when 100 would do.

> They still sometimes change/remove comments and code they don't sufficiently understand as side effects, even if orthogonal to the task.

Краткий перевод: модели молча принимают неверные допущения, не управляют своей confusion, не задают уточняющие вопросы, не показывают trade-offs, не возражают когда стоило бы. Любят переусложнять код и API, раздувать абстракции, не убирают dead code. Иногда меняют/удаляют комментарии и код которые не понимают, в качестве side effect, даже если это ортогонально задаче.

---

## Решение: четыре принципа

| Принцип                    | Что решает                                                     |
| -------------------------- | -------------------------------------------------------------- |
| **Think Before Coding**    | Неверные допущения, скрытая confusion, не озвученные trade-offs |
| **Simplicity First**       | Переусложнение, раздутые абстракции                            |
| **Surgical Changes**       | Posторонние правки, изменения не относящегося к задаче кода    |
| **Goal-Driven Execution**  | Leverage через tests-first и проверяемые success criteria      |

---

## Принцип 1. Think Before Coding

**Не предполагай. Не скрывай confusion. Озвучивай trade-offs.**

LLM часто молча выбирает одну интерпретацию и идёт делать. Этот принцип форсирует явное рассуждение.

До начала имплементации:

* **Озвучивай свои допущения явно.** Если не уверен, спроси.
* **Если есть несколько интерпретаций, покажи их.** Не выбирай молча.
* **Возражай когда есть основания.** Если есть более простой подход, скажи это.
* **Останавливайся когда confused.** Назови что неясно. Спроси.

---

## Принцип 2. Simplicity First

**Минимум кода, который решает задачу. Никакой спекулятивности.**

Бороться с тенденцией к over-engineering:

* Никаких фич сверх того, что попросили.
* Никаких абстракций для одноразового кода.
* Никакой "гибкости" или "конфигурируемости", которую не просили.
* Никакого error handling для невозможных сценариев.
* Если написал 200 строк, а можно 50, перепиши.

**Проверка:** скажет ли senior engineer "это переусложнено"? Если да, упрости.

---

## Принцип 3. Surgical Changes

**Трогай только то, что обязан. Убирай только свой мусор.**

При редактировании существующего кода:

* Не "улучшай" соседний код, комментарии или форматирование.
* Не рефактори то, что не сломано.
* Соблюдай существующий стиль, даже если ты бы сделал иначе.
* Если заметил не связанный dead code, упомяни. Не удаляй его.

Когда твои изменения создают orphans:

* Удали imports/variables/functions, которые ИМЕННО ТВОИ изменения сделали unused.
* Не удаляй ранее существовавший dead code, если об этом не просили.

**Проверка:** каждая изменённая строка должна напрямую трассироваться к запросу пользователя.

---

## Принцип 4. Goal-Driven Execution

**Определи success criteria. Закольцовывайся до проверки.**

Преобразовывай императивные задачи в верифицируемые цели:

| Вместо...           | Преобразовать в...                                              |
| ------------------- | --------------------------------------------------------------- |
| "Добавь валидацию"  | "Напиши тесты для невалидных входов, потом сделай чтобы прошли" |
| "Исправь баг"       | "Напиши тест, который воспроизводит баг, потом сделай чтобы прошёл" |
| "Отрефактори X"     | "Убедись что тесты проходят до и после"                         |

Для multi-step задач сформулируй короткий план:

```text
1. [Шаг] -> verify: [проверка]
2. [Шаг] -> verify: [проверка]
3. [Шаг] -> verify: [проверка]
```

Сильные success criteria позволяют агенту loop'аться независимо. Слабые ("make it work") требуют постоянных уточнений.

### Ключевой insight (Karpathy)

> LLMs are exceptionally good at looping until they meet specific goals... Don't tell it what to do, give it success criteria and watch it go.

Перевод: LLM исключительно хороши в закольцовывании до достижения конкретных целей. Не говори ей что делать, дай success criteria и смотри как она работает.

---

## Прикладные примеры

Конкретные сценарии из источника (EXAMPLES.md).

### Пример 1: Think Before Coding

Пользователь просит "export user data". Наивный агент молча предполагает: всех пользователей, конкретный формат файла, конкретные поля, конкретное место. Правильное поведение: перечислить неопределённости.

* "Export all users, or a filtered subset?"
* "Which format: file download, email attachment, or API endpoint?"
* "Which fields: full profile, or a sanitized subset?"

### Пример 2: Simplicity First

Пользователь просит посчитать скидку. Наивный агент строит Strategy pattern с configuration class и pluggable discount types. Простая версия, которая решает задачу:

```python
def apply_discount(amount, percent):
    return amount * (percent / 100)
```

Сложность вводи только когда её реально требуют requirements.

### Пример 3: Surgical Changes

Баг: пустая строка проходит email validation. Фикс: обработать empty-string. Наивный агент также добавляет username validation, улучшает email regex попутно, переформатирует файл. Surgical-версия: меняет только empty-string check.

### Пример 4: Goal-Driven Execution

Вместо "I will review and improve":

1. Написать failing test, воспроизводящий issue.
2. Имплементировать fix.
3. Проверить что тест прошёл.
4. Прогнать полный suite на регрессии.

Принцип общий:

> Хороший код это код, который просто решает сегодняшнюю задачу. Не код, который преждевременно решает завтрашнюю.

---

## Как применять

Три варианта, от наиболее интегрированного к наиболее портативному.

### Вариант A. Plugin (Claude Code)

В Claude Code:

```text
/plugin marketplace add forrestchang/andrej-karpathy-skills
/plugin install andrej-karpathy-skills@karpathy-skills
```

Установит правила как Claude Code skill, доступный на всех проектах.

### Вариант B. CLAUDE.md per-project

Новый проект:

```bash
curl -o CLAUDE.md https://raw.githubusercontent.com/forrestchang/andrej-karpathy-skills/main/CLAUDE.md
```

Существующий проект (append):

```bash
echo "" >> CLAUDE.md
curl https://raw.githubusercontent.com/forrestchang/andrej-karpathy-skills/main/CLAUDE.md >> CLAUDE.md
```

### Вариант C. Вручную перенести в AGENTS.md / CLAUDE.md

Скопировать четыре принципа в agent context файл в корне репо. Дополнить project-specific guidance:

```markdown
## Behavioral Guidelines (Karpathy-inspired)

1. Think before coding: озвучивай допущения, спрашивай при ambiguity, показывай trade-offs.
2. Simplicity first: минимум кода, решающего задачу, никаких спекулятивных абстракций.
3. Surgical changes: трогай только то, что требует задача, соблюдай существующий стиль.
4. Goal-driven execution: определи success criteria, loop'айся до проверки.

## Project-Specific Guidelines

- Use TypeScript strict mode
- All API endpoints must have tests
- Follow the existing error handling patterns in `src/utils/errors.ts`
```

Источник явно проектирует правила для merge с project-specific rules; они не заменяют их.

---

## Working test (по источнику)

Правила работают если ты видишь:

* **Меньше лишних изменений в diff'ах.** В диффе только запрошенные изменения.
* **Меньше rewrite'ов из-за переусложнения.** Код простой с первого раза.
* **Уточняющие вопросы до имплементации,** не после ошибок.
* **Чистые, минимальные PR.** Никакого drive-by рефакторинга или "улучшений".

---

## Связь с `agent-readiness-ru.md`

Эти правила дополняют readiness model, не пересекаются с ней. Readiness model оценивает **environment** (делает ли репа агентов эффективными?). Эти правила настраивают **поведение агента** (действует ли агент разумно?). Репа может быть Level 5 по readiness, но агенты всё равно будут вести себя плохо, если behavioral guidelines не загружены.

Естественная интеграция:

* **Pillar 4 (Documentation & Agent Context).** Cheatsheet файла agent context рекомендует раздел `Behavioral Guidelines`. Эти четыре принципа default off-the-shelf для него.
* **Pillar 10 (Agent Tooling & Interfaces).** На L3 чек-лист требует чтобы `AGENTS.md` / `CLAUDE.md` был tuned. Включение этих четырёх принципов это минимальный бар для behavioral tuning.

---

## License

Source repository: MIT License. Перевод и summary воспроизводятся под этой лицензией. Attribution: оригинальные guidelines от Forrest Chang (`forrestchang/andrej-karpathy-skills`), на основе публичных наблюдений Andrej Karpathy.
