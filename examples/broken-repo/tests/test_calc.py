import pytest

# BUG: missing import of add, divide from the calc module


def test_add():
    assert add(2, 3) == 5


def test_divide_by_zero():
    with pytest.raises(ZeroDivisionError):
        divide(1, 0)
