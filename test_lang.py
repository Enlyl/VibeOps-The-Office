"""Tests for language adaptation (detect_language_directive) — always English."""
from guardrails import detect_language_directive


def test_always_english():
    d = detect_language_directive("hi")
    assert "English" in d
    assert "Never use Russian" in d


def test_always_english_russian_input():
    d = detect_language_directive("привет")
    assert "EXCLUSIVELY" in d or "exclusively" in d
    assert "English" in d


def test_always_english_mixed():
    d = detect_language_directive("привет hi")
    assert "English" in d


def test_always_english_code():
    d = detect_language_directive("import pandas as pd")
    assert "English" in d


def test_always_english_numbers():
    d = detect_language_directive("123")
    assert "English" in d


def test_always_english_empty():
    d = detect_language_directive("")
    assert "English" in d


def test_directive_contains_exclusively():
    d = detect_language_directive("hello")
    assert "exclusively" in d or "EXCLUSIVELY" in d


def test_directive_contains_never_use_russian():
    d = detect_language_directive("как дела?")
    assert "Never use Russian" in d


def test_directive_contains_critical():
    d = detect_language_directive("show me table")
    assert "CRITICAL" in d


if __name__ == "__main__":
    import sys
    tests = [v for k, v in locals().items() if k.startswith("test_")]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  OK: {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed}/{passed+failed} passed")
    sys.exit(1 if failed else 0)
