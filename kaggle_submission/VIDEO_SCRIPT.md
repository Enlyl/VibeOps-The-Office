# VibeOps — Video Script (≤ 4 min)

**Режим**: LIVE API (mock_mode=False) — Gemini 2.5 Flash
**Тема**: Dark Tech
**Разрешение**: 1920×1080, 30fps
**Запись**: OBS Studio, без музыки, голос за кадром

> **Важно**: Ответы генеративные — текст на экране будет отличаться от примеров. Следуй логике сцены, а не точным формулировкам.

---

## Концепции для демонстрации

| # | Концепция | День | Время |
|---|---|---|---|
| 1 | Multi-Agent Routing + Socratic Method | День 1 | 0:00–1:15 |
| 2 | Guardrail Rule B — Destructive Code Warning | День 4 | 1:15–2:30 |
| 3 | Vibe Diff + Sandbox Execution | День 5 | 2:30–3:45 |

---

## Сцена 1 — Multi-Agent Routing + Socratic Method (0:00–1:15)

### Что показать
Система маршрутизирует сообщение: вопрос идёт к Elena, которая учит через вопросы.

### Ввод пользователя (скопировать и вставить):
```
How do I handle missing values in dirty_data.csv?
```

### Что происходит на экране:
1. **0:00–0:10** — Дашборд загружается. Показать сайдбар: агенты, guardrails, workspace
2. **0:10–0:20** — Напечатать сообщение, нажать Enter
3. **0:20–0:50** — Появляется ответ **Elena** (через Gemini API) — задаёт направляющие вопросы о данных, не даёт код
4. **0:50–1:15** — Показать сайдбар: Agent Log показывает роутинг

### Голос за кадром:
> "I ask a simple question about missing values. The orchestrator detects it's a question — not code — and routes it to Elena, the Socratic mentor. Notice: she never gives code. She asks what percentage of rows are affected, whether the missingness is random. This is the Socratic method enforced at the system level — the mentor literally cannot break her contract."

### Если что-то пошло не так:
- Если ответ слишком долгий (>15 сек) — покажи загрузочный индикатор, не вырезай
- Если Elena выдала код — Rule A сработает и перезапустит (это даже лучше для демо)

---

## Сцена 2 — Guardrail Rule B: Destructive Code Warning (1:15–2:30)

### Что показать
Chad предлагает опасное решение → Rule B срабатывает → Elena предупреждает.

### Ввод пользователя (скопировать и вставить):
```
Write me code to remove all nulls from the dataset
```

### Что происходит на экране:
1. **1:15–1:25** — Обновить страницу для нового чата
2. **1:25–1:35** — Ввести сообщение, Enter
3. **1:35–2:00** — Появляется ответ **Chad** с `inplace=True` или `drop()` в тексте
4. **2:00–2:20** — Появляется ответ **Elena** с предупреждением о state mutation
5. **2:20–2:30** — Показать лог в сайдбаре: "RULE B triggered"

### Голос за кадром:
> "Now watch: I ask for code to remove nulls. Chad recommends inplace=True — the classic mistake. The guardrail engine catches it instantly. Rule B fires. It doesn't block Chad, but forces Elena to speak next with a warning about state mutation. His bad suggestion becomes a teachable moment."

### Если что-то пошло не так:
- Если Chad НЕ предложил `inplace=True` — ответ Gemini непредсказуем. Повтори попытку или перезапиши сцену
- Если Rule B не сработала — покажи лог в сайдбаре, где видно что guardrails активны

---

## Сцена 3 — Vibe Diff + Sandbox Execution (2:30–3:45)

### Что показать
Robert генерирует код → Vibe Diff блокирует ввод → Approve → Sandbox выполняет.

### Ввод пользователя (скопировать и вставить):
```
import pandas as pd
df = pd.read_csv('workspace/dirty_data.csv')
print(df.shape)
print(df.describe())
```

### Что происходит на экране:
1. **2:30–2:40** — Обновить страницу для нового чата
2. **2:40–2:50** — Ввести код, Enter
3. **2:50–3:10** — Появляется **Robert** с планом и кодом. Чат-ввод **заблокирован**. Кнопки "Approve & Run" / "Reject"
4. **3:10–3:20** — Нажать "Approve & Run"
5. **3:20–3:40** — Результат sandbox: execution time, stdout (shape и describe)
6. **3:40–3:45** — Показать сайдбар: Sandbox output

### Голос за кадром:
> "The most critical feature: Vibe Diff. I paste Python code. Robert generates a plan, but the chat is locked — I cannot continue until I decide. I click Approve. Only then does Robert execute in an isolated sandbox with a ten-second timeout. He reports execution time, output, and errors. The agent proposes, the human disposes."

### Если что-то пошло не так:
- Если Robert не сгенерировал код-блок — Vibe Diff не покажется. Повтори сцену
- Если sandbox упал — покажи ошибку, это тоже демонстрация безопасности

---

## Сцена 4 — Финал (3:45–4:00)

### На экране
Полный дашборд со всей историей чата → сайдбар с Agent Log → fade out

### Голос за кадром:
> "VibeOps demonstrates three core pillars of the Kaggle Intensive: multi-agent routing, output guardrails that catch LLM failures in real time, and sandboxed execution with human approval. The code is open source. Try it — and never vibe code without a safety net."

---

## Чеклист перед записью

- [ ] Приложение запущено в **API-режиме** (mock_mode=False в сайдбаре)
- [ ] `.env` содержит рабочий `GEMINI_API_KEY`
- [ ] Тема: Dark Tech
- [ ] Чат пустой перед каждой сценой (обнови страницу)
- [ ] Три сообщения 준비лены для копипаста
- [ ] Sidebar раскрыт (Agent Log, Guardrails, Sandbox)
- [ ] Протестируй каждую сцену перед записью — Gemini отвечает по-разному
- [ ] Запаси время на повторные дубли (LAPI может отвечать медленно)

## Тайминг

| Сцена | Концепция | Время |
|---|---|---|
| 1 | Multi-Agent Routing + Socratic | 0:00–1:15 |
| 2 | Guardrail Rule B | 1:15–2:30 |
| 3 | Vibe Diff + Sandbox | 2:30–3:45 |
| 4 | Финал | 3:45–4:00 |
| **Итого** | | **4:00** |
