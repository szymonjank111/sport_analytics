import pytest

from drop_ci_datasets import main, run_datasets


def test_takes_the_run_and_its_layers_only() -> None:
    datasets = ["raw", "ci_12", "ci_12_staging", "ci_12_marts_public", "ci_123_staging", "marts"]

    assert run_datasets(datasets, "ci_12") == ["ci_12", "ci_12_staging", "ci_12_marts_public"]


def test_refuses_datasets_of_anything_but_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["drop_ci_datasets.py", "raw"])

    with pytest.raises(SystemExit) as exit_info:
        main()

    assert exit_info.value.code == 2
