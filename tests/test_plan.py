from pathlib import Path

import pytest

from capitalplan.__main__ import main
from capitalplan.plan import Asset, build_plan, escalate, format_plan, read_assets, target_year

EX = Path(__file__).resolve().parent.parent / "examples" / "assets.csv"


def asset(asset_id="A-1", install=2010, life=20, condition="Good", cost=1000.0):
    return Asset(asset_id, "Unit", install, life, condition, cost)


def test_target_year_is_end_of_life():
    assert target_year(asset(install=2010, life=20), 2027) == 2030


def test_target_year_never_before_start():
    assert target_year(asset(install=1990, life=20), 2027) == 2027


def test_poor_condition_pulled_to_start():
    assert target_year(asset(install=2020, life=30, condition="Poor"), 2027) == 2027


def test_escalate_compounds():
    assert escalate(1000.0, 2027, 2027, 0.03) == 1000.0
    assert escalate(1000.0, 2027, 2029, 0.10) == pytest.approx(1210.0)


def test_no_cap_places_everything_at_target():
    plan = build_plan([asset(install=2010, life=20, cost=500.0)], 2027, 5, inflation=0.0)
    assert len(plan.lines) == 1
    assert plan.lines[0].year == 2030 and not plan.lines[0].deferred


def test_asset_after_plan_is_ignored():
    plan = build_plan([asset(install=2040, life=20)], 2027, 5)
    assert plan.lines == () and plan.unfunded == ()


def test_cap_defers_to_next_year():
    items = [asset("A", 2000, 20, "Poor", 600.0), asset("B", 2000, 20, "Fair", 600.0)]
    plan = build_plan(items, 2027, 3, inflation=0.0, annual_cap=1000.0)
    years = {line.asset.asset_id: line.year for line in plan.lines}
    assert years == {"A": 2027, "B": 2028}
    assert [line.deferred for line in plan.lines] == [False, True]


def test_item_larger_than_cap_is_unfunded():
    plan = build_plan([asset("BIG", 2000, 20, "Poor", 5000.0)], 2027, 3, annual_cap=1000.0)
    assert [a.asset_id for a in plan.unfunded] == ["BIG"]
    assert plan.lines == ()


def test_worst_condition_gets_money_first():
    items = [asset("G", 2000, 20, "Good", 800.0), asset("P", 2005, 30, "Poor", 800.0)]
    plan = build_plan(items, 2027, 2, inflation=0.0, annual_cap=1000.0)
    assert {line.asset.asset_id: line.year for line in plan.lines} == {"P": 2027, "G": 2028}


def test_totals_add_up_with_inflation():
    plan = build_plan(read_assets(EX), 2027, 5, inflation=0.03)
    assert plan.grand_total() == pytest.approx(sum(plan.year_total(y) for y in range(2027, 2032)))


def test_invalid_arguments():
    with pytest.raises(ValueError):
        build_plan([], 2027, 0)
    with pytest.raises(ValueError):
        build_plan([], 2027, 5, inflation=2.0)


def test_read_assets_rejects_bad_condition(tmp_path):
    path = tmp_path / "a.csv"
    path.write_text(
        "asset_id,name,install_year,expected_life_years,condition,replacement_cost\nX-1,n,2000,10,Great,5\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="condition"):
        read_assets(path)


def test_format_plan_mentions_unfunded_and_deferred():
    items = [asset("A", 2000, 20, "Poor", 600.0), asset("B", 2000, 20, "Fair", 600.0), asset("C", 2000, 20, "Good", 900.0)]
    text = format_plan(build_plan(items, 2027, 2, inflation=0.0, annual_cap=1000.0))
    assert "B*" in text
    assert "Unfunded: C" in text


def test_cli(capsys, tmp_path):
    assert main([str(EX), "--start", "2027", "--cap", "300000"]) == 0
    assert "Total" in capsys.readouterr().out
    assert main([str(tmp_path / "none.csv"), "--start", "2027"]) == 1
