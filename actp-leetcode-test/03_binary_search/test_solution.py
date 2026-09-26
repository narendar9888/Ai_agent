from solution import search

def test_examples():
    assert search([-1, 0, 3, 5, 9, 12], 9) == 4
    assert search([-1, 0, 3, 5, 9, 12], 2) == -1

def test_single_element():
    assert search([5], 5) == 0
    assert search([5], 2) == -1

def test_boundaries():
    nums = [1, 2, 3, 4, 5]
    assert search(nums, 1) == 0
    assert search(nums, 5) == 4

def test_empty():
    assert search([], 1) == -1

def test_negative():
    assert search([-10, -5, -2, 0, 4], -5) == 1
