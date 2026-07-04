"""
Тест текстового приветствия — воспроизводим баг
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(__file__))

from orchestrator import Orchestrator

orch = Orchestrator()
prompt = "Привет! Я хочу изучить Pandas, с чего начать?"
print(f"=== ТЕСТ: «{prompt}» ===\n")

# Запускаем 10 раз, чтобы поймать Rule A (20% вероятности)
for i in range(10):
    o = Orchestrator()
    turns = o.run(prompt, mock_mode=True)
    agents = [a for a, _ in turns]
    has_code = False
    for name, content in turns:
        if "```python" in content or "```" in content:
            has_code = True
            print(f"[{i+1}] ⚠ Rule A FAIL! {name.upper()} содержит код!")
            print(content[:200])
            break
    if not has_code:
        print(f"[{i+1}] ✅ Нормально. Агенты: {agents}")
        for name, content in turns:
            preview = content[:80].replace("\n", " ").strip()
            print(f"     {name}: {preview}...")
