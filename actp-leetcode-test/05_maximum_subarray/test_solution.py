from solution import max_sub_array

def test_examples():
    assert max_sub_array([-2, 1, -3, 4, -1, 2, 1, -5, 4]) == 6
    assert max_sub_array([1]) == 1
    assert max_sub_array([5, 4, -1, 7, 8]) == 23

def test_all_negative():
    assert max_sub_array([-5, -2, -8]) == -2

def test_two_elements():
    assert max_sub_array([1, -1]) == 1
    assert max_sub_array([-1, 1]) == 1

def test_all_positive():
    assert max_sub_array([1, 2, 3, 4]) == 10

def test_mixed():
    assert max_sub_array([-2, 5, -1, 2, -3, 4]) == 7
