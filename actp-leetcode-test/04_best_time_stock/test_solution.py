from solution import max_profit

def test_examples():
    assert max_profit([7, 1, 5, 3, 6, 4]) == 5
    assert max_profit([7, 6, 4, 3, 1]) == 0

def test_short_inputs():
    assert max_profit([]) == 0
    assert max_profit([5]) == 0
    assert max_profit([1, 2]) == 1

def test_best_trade_is_not_first_or_last():
    assert max_profit([3, 2, 6, 1, 5, 4]) == 4

def test_large_increase():
    assert max_profit([1, 2, 3, 4, 5]) == 4

def test_flat():
    assert max_profit([4, 4, 4, 4]) == 0
