import sys
from pathlib import Path

repo_root = Path(__file__).parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import pytest

from src.bench.reducers import bootstrap_stderr, mean, std, stderr


def test_reducer_basic_math():
    values = [1.0, 2.0, 4.0]

    assert mean(values) == pytest.approx(7 / 3)
    assert std(values) == pytest.approx(1.5275252316519465)
    assert stderr(values) == pytest.approx(0.8819171036881969)


def test_bootstrap_stderr_is_deterministic_and_matches_reference_value():
    values = [1.0, 2.0, 4.0]

    assert bootstrap_stderr(values, num_samples=10, seed=123) == pytest.approx(
        0.5962847939999438
    )
    assert bootstrap_stderr(values, num_samples=10, seed=123) == bootstrap_stderr(
        values, num_samples=10, seed=123
    )


def test_variance_reducers_return_zero_for_singletons():
    assert std([1.0]) == 0.0
    assert stderr([1.0]) == 0.0
    assert bootstrap_stderr([1.0]) == 0.0


def test_bootstrap_stderr_decreases_with_more_samples_from_same_distribution():
    few_epochs = [1.0, 2.0, 3.0, 4.0, 5.0]
    more_epochs = few_epochs * 4

    assert bootstrap_stderr(more_epochs, num_samples=2000, seed=1) < bootstrap_stderr(
        few_epochs, num_samples=2000, seed=1
    )
