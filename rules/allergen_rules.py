"""Allergen propagation rules.

RM Master is the source of truth for allergens. Allergens propagate:
  RM -> SFG  (any RM with allergen=1 in the SFG BOM sets that SFG allergen=1)
  RM/SFG -> SKU  (any RM or SFG with allergen=1 in the SKU BOM sets that SKU allergen=1)

We recompute the 14 standard allergens for every SFG and SKU and compare with the
existing values, recording mismatches and producing corrected values.
"""

from utils import ALLERGENS, to_int, safe_str


def _allergen_col_name(allergen, columns):
    """Find the column name corresponding to a given allergen."""
    for col in columns:
        if allergen.lower() in str(col).lower():
            return col
    return None


def build_rm_allergen_map(rm_df, code_col, allergen_cols):
    """Return {rm_code: {allergen_name: 0|1}} for all RM rows."""
    rm_map = {}
    if rm_df is None or code_col is None:
        return rm_map
    for _, row in rm_df.iterrows():
        code = safe_str(row.get(code_col))
        if not code:
            continue
        rm_map[code] = {}
        for allergen, col in allergen_cols.items():
            if col is not None:
                rm_map[code][allergen] = to_int(row.get(col))
            else:
                rm_map[code][allergen] = 0
    return rm_map


def build_sfg_allergen_map(sfg_df, code_col, allergen_cols):
    """Return {sfg_code: {allergen_name: 0|1}} for all SFG rows (from SFG sheet, not BOM)."""
    sfg_map = {}
    if sfg_df is None or code_col is None:
        return sfg_map
    for _, row in sfg_df.iterrows():
        code = safe_str(row.get(code_col))
        if not code:
            continue
        sfg_map[code] = {}
        for allergen, col in allergen_cols.items():
            if col is not None:
                sfg_map[code][allergen] = to_int(row.get(col))
            else:
                sfg_map[code][allergen] = 0
    return sfg_map


def _resolve_allergen_cols(df, allergen_cols):
    """Given a partial allergen_cols dict, fill missing column names by scanning df."""
    if df is None:
        return allergen_cols
    cols = list(df.columns)
    for allergen in ALLERGENS:
        if allergen_cols.get(allergen) is None:
            allergen_cols[allergen] = _allergen_col_name(allergen, cols)
    return allergen_cols


def compute_component_allergens(code, rm_map, sfg_map, _depth=0):
    """Return {allergen: 0|1} for a component code, looking up RM then SFG."""
    if _depth > 10:
        return {a: 0 for a in ALLERGENS}
    if code in rm_map:
        return dict(rm_map[code])
    if code in sfg_map:
        return dict(sfg_map[code])
    return {a: 0 for a in ALLERGENS}


def verify_sfg_allergens(sfg_bom_df, rm_map, sfg_allergen_existing,
                         component_col, parent_col, allergen_cols, result, sheet_name):
    """For each SFG parent, aggregate allergens from its RM components and compare."""
    if sfg_bom_df is None or parent_col is None or component_col is None:
        return {}

    # Group components by parent SFG code
    sfg_components = {}
    for _, row in sfg_bom_df.iterrows():
        parent = safe_str(row.get(parent_col))
        comp = safe_str(row.get(component_col))
        if not parent or not comp:
            continue
        sfg_components.setdefault(parent, []).append(comp)

    # Compute expected allergens per SFG
    sfg_expected = {}
    for parent, comps in sfg_components.items():
        expected = {a: 0 for a in ALLERGENS}
        for comp in comps:
            comp_allergens = compute_component_allergens(comp, rm_map, {}, 0)
            for a in ALLERGENS:
                if comp_allergens.get(a, 0) == 1:
                    expected[a] = 1
        sfg_expected[parent] = expected

        # Compare with existing values (from SFG sheet allergen map)
        existing = sfg_allergen_existing.get(parent, {})
        for allergen in ALLERGENS:
            exp_val = expected[allergen]
            got_val = to_int(existing.get(allergen, 0))
            if exp_val != got_val:
                col = allergen_cols.get(allergen)
                result.add(
                    sheet_name, 0, "Allergen",
                    exp_val, got_val,
                    f"SFG '{parent}' {allergen} should be {exp_val} but is {got_val}",
                )
                result.sfg_mismatches += 1
    return sfg_expected


def verify_sku_allergens(sku_bom_df, rm_map, sfg_map, sku_allergen_existing,
                         component_col, parent_col, allergen_cols, result, sheet_name):
    """For each SKU parent, aggregate allergens from its RM/SFG components and compare."""
    if sku_bom_df is None or parent_col is None or component_col is None:
        return {}

    sku_components = {}
    for _, row in sku_bom_df.iterrows():
        parent = safe_str(row.get(parent_col))
        comp = safe_str(row.get(component_col))
        if not parent or not comp:
            continue
        sku_components.setdefault(parent, []).append(comp)

    sku_expected = {}
    for parent, comps in sku_components.items():
        expected = {a: 0 for a in ALLERGENS}
        for comp in comps:
            comp_allergens = compute_component_allergens(comp, rm_map, sfg_map, 0)
            for a in ALLERGENS:
                if comp_allergens.get(a, 0) == 1:
                    expected[a] = 1
        sku_expected[parent] = expected

        existing = sku_allergen_existing.get(parent, {})
        for allergen in ALLERGENS:
            exp_val = expected[allergen]
            got_val = to_int(existing.get(allergen, 0))
            if exp_val != got_val:
                result.add(
                    sheet_name, 0, "Allergen",
                    exp_val, got_val,
                    f"SKU '{parent}' {allergen} should be {exp_val} but is {got_val}",
                )
                result.sfg_mismatches += 1
    return sku_expected


def get_allergen_cols(df):
    """Return {allergen_name: column_name_or_None} for a dataframe."""
    allergen_cols = {}
    if df is None:
        return {a: None for a in ALLERGENS}
    for allergen in ALLERGENS:
        allergen_cols[allergen] = _allergen_col_name(allergen, list(df.columns))
    return allergen_cols
