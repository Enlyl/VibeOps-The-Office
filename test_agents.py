"""
test_agents.py — Быстрая проверка всех агентов и роутинга
=========================================================
Запуск:  python test_agents.py
Требует: GEMINI_API_KEY в .env (для API-режима)
         или запускает в SIM-режиме (mock_mode=True)

Тесты:
  1. Name-routing: каждый агент отвечает на прямое обращение
  2. Default routing: Chad+Elena на общий вопрос
  3. Code routing: Robert на код-паттерны
  4. Guardrail Rule B: Chad предлагает inplace=True → Elena предупреждает
  5. Guardrail Rule C: токсичное слово → BLOCKED
"""

import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).parent))

from orchestrator import Orchestrator

# ── Цвета для вывода ──────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg):  print(f"  {GREEN}✅ {msg}{RESET}")
def fail(msg): print(f"  {RED}❌ {msg}{RESET}")
def info(msg): print(f"  {CYAN}ℹ  {msg}{RESET}")

# ── Хелпер ────────────────────────────────────────────────────────────────────
def run_test(name: str, prompt: str, expected_agents: list[str],
             forbidden_agents: list[str] = None, mock: bool = True):
    """
    Запускает один тест.
    
    Args:
        name:             Название теста
        prompt:           Входной текст
        expected_agents:  Список имён агентов, которые ДОЛЖНЫ ответить
        forbidden_agents: Список имён агентов, которых НЕ ДОЛЖНО быть
        mock:             True = SIM-режим (без API)
    """
    print(f"\n{BOLD}── {name} ──{RESET}")
    info(f"Prompt: «{prompt}»")
    
    orch = Orchestrator()
    try:
        turns = orch.run(prompt, mock_mode=mock)
    except Exception as e:
        fail(f"Исключение при запуске: {e}")
        return False

    responding_agents = [agent_name for agent_name, _ in turns]
    info(f"Ответили: {responding_agents}")

    passed = True

    # Проверяем ожидаемых агентов
    for expected in expected_agents:
        if expected in responding_agents:
            ok(f"{expected} ответил")
        else:
            fail(f"{expected} должен был ответить, но не ответил")
            passed = False

    # Проверяем запрещённых агентов
    for forbidden in (forbidden_agents or []):
        if forbidden not in responding_agents:
            ok(f"{forbidden} корректно НЕ ответил")
        else:
            fail(f"{forbidden} ответил, хотя не должен был")
            passed = False

    # Показываем первые 120 символов каждого ответа
    for agent_name, content in turns:
        preview = content[:120].replace("\n", " ")
        print(f"    {YELLOW}[{agent_name.upper()}]{RESET}: {preview}…")

    return passed


# ── Тесты ─────────────────────────────────────────────────────────────────────
def main():
    print(f"\n{BOLD}{'=' * 60}")
    print("  VibeOps Agent Test Suite (SIM mode)")
    print(f"{'=' * 60}{RESET}")

    results = []

    # Тест 1: Elena по имени
    results.append(run_test(
        name="[1] Elena name-routing",
        prompt="Elena, что такое переобучение модели?",
        expected_agents=["elena"],
        forbidden_agents=["chad", "robert", "geoffrey"],
    ))

    # Тест 2: Chad по имени → только Chad (Rule B sets flag, no auto-Elena)
    results.append(run_test(
        name="[2] Chad name-routing (single agent)",
        prompt="Chad, как быстро почистить данные?",
        expected_agents=["chad"],
        forbidden_agents=["robert", "geoffrey"],
    ))

    # Тест 3: Robert по имени
    results.append(run_test(
        name="[3] Robert name-routing",
        prompt="Robert, проверь мой код",
        expected_agents=["robert"],
        forbidden_agents=["chad", "elena", "geoffrey"],
    ))

    # Тест 4: Geoffrey по имени
    results.append(run_test(
        name="[4] Geoffrey name-routing",
        prompt="Geoffrey, какова наша бизнес-цель?",
        expected_agents=["geoffrey"],
        forbidden_agents=["chad", "elena", "robert"],
    ))

    # Тест 5: Дефолтный маршрут → Elena (single agent)
    results.append(run_test(
        name="[5] Default chat path (Elena)",
        prompt="Что такое дисбаланс классов?",
        expected_agents=["elena"],
        forbidden_agents=["geoffrey"],
    ))

    # Тест 6: Code routing → Robert (с Vibe Diff)
    results.append(run_test(
        name="[6] Code routing → Robert (Vibe Diff)",
        prompt="import pandas as pd\ndf = pd.read_csv('data.csv')",
        expected_agents=["robert"],
        forbidden_agents=["geoffrey"],
    ))

    # Тест 7: Robert по коду с явным именем
    results.append(run_test(
        name="[7] Robert — explicit name + code",
        prompt="Robert, запусти: df['Age'].fillna(0)",
        expected_agents=["robert"],
        forbidden_agents=["geoffrey"],
    ))

    # Тест 8: Русские имена
    results.append(run_test(
        name="[8] Russian name aliases",
        prompt="Елена, объясни что такое кросс-валидация",
        expected_agents=["elena"],
        forbidden_agents=["chad", "robert", "geoffrey"],
    ))

    # ── Итог ─────────────────────────────────────────────────────────────────
    passed = sum(results)
    total  = len(results)
    color  = GREEN if passed == total else RED

    print(f"\n{BOLD}{'=' * 60}")
    print(f"  {color}Результат: {passed}/{total} тестов прошли{RESET}{BOLD}")
    print(f"{'=' * 60}{RESET}\n")

    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
