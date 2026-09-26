from solution import two_sum

def check(nums, target, expected):
    result = two_sum(nums, target)
    assert sorted(result) == sorted(expected)
    assert len(result) == 2
    assert result[0] != result[1]
    assert nums[result[0]] + nums[result[1]] == target

def test_examples():
    check([2, 7, 11, 15], 9, [0, 1])
    check([3, 2, 4], 6, [1, 2])

def test_duplicates():
    check([3, 3], 6, [0, 1])

def test_negative_values():
    check([-1, -2, -3, -4, -5], -8, [2, 4])

def test_zero():
    check([0, 4, 3, 0], 0, [0, 3])
