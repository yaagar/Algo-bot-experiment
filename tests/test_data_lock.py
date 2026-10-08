"""Hard lock on the reserved period (before 2022-01-01), spec v1.4.

Fails if any module other than src/data_access.py reads price files, if MT5 history is
pulled without the reserved-period check, or if any results file (outside the Phase 4c
folder) contains a pre-2022 date. Functional tests use a tiny synthetic Parquet file,
so the tests themselves never touch real reserved data.
"""
import datetime as dt
import re
from pathlib import Path

import pandas as pd
import pytest

from src.config import PROJECT_ROOT
from src.data_access import CONFIRM_TEMPLATE, ReservedDataLocked, check_window, read_prices

SRC = PROJECT_ROOT / "src"
RESULTS = PROJECT_ROOT / "results"


def src_lines():
    for f in SRC.rglob("*.py"):
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if not line.lstrip().startswith("#"):
                yield f.name, n, line


# --- nobody else reads price data -----------------------------------------------------

def test_price_files_are_read_only_through_data_access():
    offenders = [f"{f}:{n}" for f, n, line in src_lines()
                 if "read_parquet(" in line and f != "data_access.py" and "CALENDAR_PATH" not in line]
    assert offenders == [], f"price files read outside src/data_access.py: {offenders}"


def test_forex_factory_csv_read_only_through_data_access():
    offenders = [f"{f}:{n}" for f, n, line in src_lines()
                 if "read_csv(" in line and f != "data_access.py" and "results" not in line
                 and "PHASE4" not in line]
    assert offenders == [], f"CSV data read outside src/data_access.py: {offenders}"


def test_mt5_history_only_pulled_behind_the_lock():
    copy = [f"{f}:{n}" for f, n, line in src_lines() if "copy_rates" in line and f != "data_mt5.py"]
    pulls = [f for f, n, line in src_lines() if re.search(r"\bpull_rates\(", line) and "def pull_rates" not in line]
    assert copy == [] and set(pulls) <= {"pull_prices.py", "pull_data.py"}
    assert "check_window(SEARCH_FROM" in (SRC / "pull_prices.py").read_text(encoding="utf-8")
    exp3 = (SRC / "exp3" / "pull_data.py").read_text(encoding="utf-8")
    assert "check_window(START" in exp3 and 'START = datetime(2022, 1, 1' in exp3


def test_pull_prices_refuses_without_confirmation():
    from src import pull_prices
    with pytest.raises(ReservedDataLocked):
        pull_prices.main()            # refused before any MT5 connection is made


# --- the lock itself (synthetic data) --------------------------------------------------------

@pytest.fixture
def fake(tmp_path):
    path = tmp_path / "fake_M1.parquet"
    pd.DataFrame({"time_utc": pd.to_datetime(["2021-12-31 10:00", "2022-01-03 10:00"], utc=True),
                  "close": [1.0, 2.0]}).to_parquet(path, index=False)
    return path, tmp_path / "access_log.md"


def test_reserved_window_refused_without_confirmation(fake):
    path, log = fake
    with pytest.raises(ReservedDataLocked):
        read_prices("X", "M1", pd.Timestamp("2021-12-01", tz="UTC"), None, path=path, log_path=log)
    assert not log.exists()


def test_confirmation_from_another_day_is_refused(fake):
    path, log = fake
    stale = CONFIRM_TEMPLATE.format(date="2026-01-01", purpose="test")
    with pytest.raises(ReservedDataLocked):
        read_prices("X", "M1", None, None, purpose="test", confirm=stale, path=path, log_path=log)


def test_todays_confirmation_works_and_is_logged(fake):
    path, log = fake
    ok = CONFIRM_TEMPLATE.format(date=dt.date.today().isoformat(), purpose="unit test")
    bars = read_prices("X", "M1", None, None, purpose="unit test", confirm=ok, path=path, log_path=log)
    assert len(bars) == 2 and "unit test" in log.read_text(encoding="utf-8")


def test_post_2022_window_needs_no_confirmation_and_never_returns_reserved_rows(fake):
    path, log = fake
    bars = read_prices("X", "M1", pd.Timestamp("2022-01-01", tz="UTC"), None, path=path, log_path=log)
    assert bars.time_utc.min() >= pd.Timestamp("2022-01-01", tz="UTC") and not log.exists()


def test_check_window_accepts_naive_and_aware_starts():
    check_window(pd.Timestamp("2022-01-01"))          # naive = UTC, not reserved
    with pytest.raises(ReservedDataLocked):
        check_window(dt.datetime(2010, 1, 1, tzinfo=dt.timezone.utc))


# --- no reserved-period dates in results ---------------------------------------------------

def test_no_results_file_contains_pre_2022_dates():
    bad = []
    for f in RESULTS.rglob("*.csv"):
        if "phase4c" in f.parts:
            continue
        d = pd.read_csv(f, dtype=str)
        for col in [c for c in d.columns if "date" in c or c.endswith("_utc")]:
            years = d[col].dropna().str.extract(r"^(\d{4})-")[0].dropna().astype(int)
            if len(years) and years.min() < 2022:
                bad.append(f"{f.relative_to(PROJECT_ROOT)}:{col}")
    assert bad == [], f"pre-2022 dates in results: {bad}"
