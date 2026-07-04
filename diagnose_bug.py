"""
Диагностика: почему текст идёт к Robert
"""
import sys, os, re
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(__file__))

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

test_inputs = [
    "Привет! Я хочу изучить Pandas, с чего начать?",
    "Как удалить пропуски в данных?",
    "импортировать pandas",
    "import pandas as pd",
    "df = pd.read_csv('data.csv')",
    "обучение модели с помощью sklearn",
    "Что такое overfitting?",
    "Елена, расскажи про bias",
    "Chad, почини данные",
    "напиши код для загрузки csv",
    "print('hello world')",
    "Я хочу импортировать данные",
]

# The INLINE regex currently used in _analysis_stage
INLINE_RE = re.compile(r"df\[|pd\.|import |=|```(?:python)?")

# The _contains_code patterns (with word boundaries)
_CODE_PATTERNS = [
    re.compile(r"\bimport\b"),
    re.compile(r"\bdf\s*\["),
    re.compile(r"\bpd\."),
    re.compile(r"\bnp\."),
    re.compile(r"```python", re.IGNORECASE),
    re.compile(r"\bdef\s+\w+\s*\("),
    re.compile(r"\w+\s*=\s*.+"),
]

# Name routing patterns
_NAME_PATTERNS = [
    (re.compile(r"\b(elena|елена|ментор|mentor|senior)\b", re.IGNORECASE), "AGENT_ELENA"),
    (re.compile(r"\b(chad|чад|джуниор|junior|vibe.?coder)\b", re.IGNORECASE), "AGENT_CHAD"),
    (re.compile(r"\b(robert|роберт|mlops|mlоps|validator)\b", re.IGNORECASE), "AGENT_ROBERT"),
    (re.compile(r"\b(geoffrey|джеффри|boss|cto)\b", re.IGNORECASE), "AGENT_GEOFFREY"),
]

print(f"{BOLD}ДИАГНОСТИКА МАРШРУТИЗАЦИИ{RESET}")
print(f"{'='*70}")

for text in test_inputs:
    inline_match = bool(INLINE_RE.search(text))
    code_match = any(p.search(text) for p in _CODE_PATTERNS)
    name_match = None
    for pat, stage in _NAME_PATTERNS:
        if pat.search(text):
            name_match = stage
            break
    
    inline_route = "ROBERT" if inline_match else "CHAD"
    code_route = "ROBERT" if code_match else "CHAD"
    name_route = name_match or "—"
    
    # Determine what ACTUALLY happens in _analysis_stage
    if name_match:
        actual_route = name_match
    elif inline_match:
        actual_route = "ROBERT (inline)"
    elif code_match:
        actual_route = "ROBERT (_contains_code)"
    else:
        actual_route = "CHAD → ELENA"
    
    color = RED if inline_match != code_match or (inline_match and name_match) else GREEN
    
    print(f"\n{color}[{actual_route}]{RESET}")
    print(f"  Ввод: {text}")
    print(f"  inline regex → {'⚠ РОБЕРТ' if inline_match else 'ЧАД'}")
    print(f"  _contains_code → {'⚠ РОБЕРТ' if code_match else 'ЧАД'}")
    print(f"  name-routing → {name_route}")
    
    # Show WHAT matched
    if inline_match:
        match_obj = INLINE_RE.search(text)
        print(f"  {YELLOW}inline match: '{match_obj.group()}' at pos {match_obj.start()}{RESET}")
    if code_match:
        for p in _CODE_PATTERNS:
            m = p.search(text)
            if m:
                print(f"  {YELLOW}code match: /{p.pattern}/ → '{m.group()}' at pos {m.start()}{RESET}")

print(f"\n{'='*70}")
print(f"{BOLD}ВЫВОД:{RESET}")
print(f"  inline regex НЕ имеет word boundaries: `import` матчит 'импорт...'")
print(f"  _contains_code() имеет \\b границы — точнее")
print(f"  Проблема: в _analysis_stage используется inline, а не _contains_code()")
print(f"{'='*70}")
