from solution import is_valid

def test_examples():
    assert is_valid("()") is True
    assert is_valid("()[]{}") is True
    assert is_valid("(]") is False
    assert is_valid("([)]") is False
    assert is_valid("{[]}") is True

def test_empty():
    assert is_valid("") is True

def test_nested():
    assert is_valid("(([]){})") is True
    assert is_valid("(([])") is False

def test_single_bracket():
    assert is_valid("(") is False
    assert is_valid("]") is False

def test_long_sequence():
    assert is_valid("[" * 100 + "]" * 100) is True
