"""Cost and yield rules."""

from utils import safe_str


def verify_costs(df, code_col, qty_col, price_col, cost_col, result, sheet_name):
    """Verify Cost = Quantity * Price for each row."""
    if df is None or qty_col is None or price_col is None or cost_col is None:
        return

    for idx, row in df.iterrows():
        code = safe_str(row.get(code_col)) if code_col else f"Row {idx+2}"
        try:
            qty = float(row.get(qty_col))
        except (ValueError, TypeError):
            qty = None
        try:
            price = float(row.get(price_col))
        except (ValueError, TypeError):
            price = None
        try:
            cost = float(row.get(cost_col))
        except (ValueError, TypeError):
            cost = None

        if qty is None or price is None or cost is None:
            continue

        expected_cost = round(qty * price, 4)
        if abs(expected_cost - cost) > 0.01:
            result.add(
                sheet_name, idx + 2, "Cost",
                expected_cost, cost,
                f"'{code}' cost should be {qty} * {price} = {expected_cost} but is {cost}",
            )


def verify_yield(yield_df, sheet_name, result):
    """Check Yield Report: Yield % = Output / Input * 100."""
    if yield_df is None or yield_df.empty:
        return

    # Find relevant columns
    cols = [str(c).lower() for c in yield_df.columns]
    input_col = None
    output_col = None
    yield_col = None
    for i, c in enumerate(cols):
        if "input" in c and input_col is None:
            input_col = list(yield_df.columns)[i]
        if "output" in c and output_col is None:
            output_col = list(yield_df.columns)[i]
        if "yield" in c and yield_col is None:
            yield_col = list(yield_df.columns)[i]

    if input_col is None or output_col is None or yield_col is None:
        return

    for idx, row in yield_df.iterrows():
        try:
            inp = float(row.get(input_col))
            out = float(row.get(output_col))
            yld = float(row.get(yield_col))
        except (ValueError, TypeError):
            continue
        if inp == 0:
            continue
        expected = round((out / inp) * 100, 2)
        if abs(expected - yld) > 0.5:
            result.add(
                sheet_name, idx + 2, "Yield",
                f"{expected}%", f"{yld}%",
                f"Yield should be {out}/{inp}*100 = {expected}% but is {yld}%",
            )


def verify_uom(df, sheet_name, result, uom_col=None):
    """Flag rows with missing or blank UOM."""
    if df is None:
        return
    if uom_col is None:
        for c in df.columns:
            if "uom" in str(c).lower() or "unit" in str(c).lower():
                uom_col = c
                break
    if uom_col is None:
        return
    for idx, row in df.iterrows():
        uom = safe_str(row.get(uom_col))
        if not uom:
            result.add(
                sheet_name, idx + 2, "UOM",
                "Non-empty UOM", "Empty",
                f"Row {idx+2} has missing UOM",
            )
