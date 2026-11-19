"""Five-year capital plan from an asset list."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

CONDITION_RANK = {"Poor": 0, "Fair": 1, "Good": 2}


@dataclass(frozen=True)
class Asset:
    """An asset with the fields the plan needs."""

    asset_id: str
    name: str
    install_year: int
    expected_life_years: int
    condition: str
    replacement_cost: float


@dataclass(frozen=True)
class PlanLine:
    """One funded replacement."""

    asset: Asset
    year: int
    target_year: int
    cost: float

    @property
    def deferred(self) -> bool:
        """True when the cap pushed this item later than its target year."""
        return self.year > self.target_year


@dataclass(frozen=True)
class Plan:
    """The finished plan: funded lines by year and assets the cap left out."""

    start_year: int
    years: int
    lines: tuple[PlanLine, ...]
    unfunded: tuple[Asset, ...]

    def year_total(self, year: int) -> float:
        return sum(line.cost for line in self.lines if line.year == year)

    def grand_total(self) -> float:
        return sum(line.cost for line in self.lines)


def read_assets(path: str | Path) -> list[Asset]:
    """Read assets from CSV. Raises ValueError with the row number for bad values."""
    assets = []
    with open(path, newline="", encoding="utf-8") as handle:
        for number, row in enumerate(csv.DictReader(handle), start=1):
            try:
                asset = Asset(
                    row["asset_id"].strip(), row["name"].strip(), int(row["install_year"]),
                    int(row["expected_life_years"]), row["condition"].strip(), float(row["replacement_cost"]),
                )
            except (KeyError, ValueError, AttributeError) as error:
                raise ValueError(f"row {number}: {error!r}") from error
            if asset.condition not in CONDITION_RANK:
                raise ValueError(f"row {number}: condition must be Good, Fair or Poor")
            if asset.expected_life_years <= 0 or asset.replacement_cost < 0:
                raise ValueError(f"row {number}: life must be positive and cost cannot be negative")
            assets.append(asset)
    return assets


def target_year(asset: Asset, start_year: int) -> int:
    """Year the asset should be replaced if money were unlimited.

    End of life year, but never earlier than the plan start. Poor condition
    assets are pulled to the first year of the plan.
    """
    if asset.condition == "Poor":
        return start_year
    return max(asset.install_year + asset.expected_life_years, start_year)


def escalate(cost: float, start_year: int, year: int, inflation: float) -> float:
    """Cost in the year of spending, grown by compound inflation."""
    return cost * (1 + inflation) ** (year - start_year)


def build_plan(
    assets: list[Asset],
    start_year: int,
    years: int = 5,
    inflation: float = 0.03,
    annual_cap: float | None = None,
) -> Plan:
    """Place each asset in a year of the plan.

    Assets are handled worst condition first, then earliest target year, then
    highest cost. With an annual cap, an asset that does not fit moves to the
    next year; one that fits nowhere is listed as unfunded. Assets whose target
    year falls after the plan are not part of this plan.
    """
    if years < 1:
        raise ValueError("years must be at least 1")
    if inflation < -0.5 or inflation > 1:
        raise ValueError("inflation must be between -0.5 and 1")
    last_year = start_year + years - 1
    spent = {year: 0.0 for year in range(start_year, last_year + 1)}
    lines: list[PlanLine] = []
    unfunded: list[Asset] = []
    ranked = sorted(
        assets,
        key=lambda a: (CONDITION_RANK[a.condition], target_year(a, start_year), -a.replacement_cost, a.asset_id),
    )
    for asset in ranked:
        target = target_year(asset, start_year)
        if target > last_year:
            continue
        for year in range(target, last_year + 1):
            cost = escalate(asset.replacement_cost, start_year, year, inflation)
            if annual_cap is None or spent[year] + cost <= annual_cap:
                spent[year] += cost
                lines.append(PlanLine(asset, year, target, round(cost, 2)))
                break
        else:
            unfunded.append(asset)
    lines.sort(key=lambda line: (line.year, line.asset.asset_id))
    return Plan(start_year, years, tuple(lines), tuple(unfunded))


def format_plan(plan: Plan) -> str:
    """Render the plan as text: one line per year, then deferred and unfunded items."""
    out = [f"{'Year':<6}{'Items':>6}{'Total':>14}  Assets"]
    for year in range(plan.start_year, plan.start_year + plan.years):
        year_lines = [line for line in plan.lines if line.year == year]
        ids = ", ".join(line.asset.asset_id + ("*" if line.deferred else "") for line in year_lines)
        out.append(f"{year:<6}{len(year_lines):>6}{plan.year_total(year):>14,.0f}  {ids}")
    out.append(f"{'Total':<6}{len(plan.lines):>6}{plan.grand_total():>14,.0f}")
    if any(line.deferred for line in plan.lines):
        out.append("* moved later than its target year by the annual cap")
    if plan.unfunded:
        out.append("Unfunded: " + ", ".join(a.asset_id for a in plan.unfunded))
    return "\n".join(out)
