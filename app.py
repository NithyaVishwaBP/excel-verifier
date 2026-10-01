"""Excel BOM Verification Tool — Streamlit app.

Upload an .xlsx workbook, verify allergen propagation, BOM structure, costs,
yields, and formula correctness. Download a corrected workbook and audit report.
"""

import streamlit as st
import pandas as pd
from io import BytesIO

from utils import VerifyResult, find_sheet_by_keyword, find_column, safe_str, to_int, ALLERGENS
from rules import allergen_rules, bom_rules, cost_rules, formula_rules
from output import generate_corrected_excel, generate_audit_report


st.set_page_config(page_title="Excel BOM Verification Tool", page_icon=None, layout="wide")

st.title("EXCEL VERIFICATION & CALCULATOR")

uploaded = st.file_uploader("Upload .xlsx workbook", type=["xlsx"], accept_multiple_files=False)


def run_verification(file_bytes, sheet_names):
    result = VerifyResult()

    # Map sheets by keyword
    rm_sheet = None
    sfg_sheet = None
    sfg_bom_sheet = None
    sku_sheet = None
    sku_bom_sheet = None
    yield_sheet = None

    for name in sheet_names:
        ln = name.lower()
        if "bom" in ln:
            if "sfg" in ln and sfg_bom_sheet is None:
                sfg_bom_sheet = name
            elif "sku" in ln and sku_bom_sheet is None:
                sku_bom_sheet = name
        else:
            # Non-BOM sheets: master/overview sheets
            if "rm" in ln and rm_sheet is None:
                rm_sheet = name
            if "sfg" in ln and sfg_sheet is None:
                sfg_sheet = name
            if "sku" in ln and sku_sheet is None:
                sku_sheet = name
            if "yield" in ln and yield_sheet is None:
                yield_sheet = name

    # Fallbacks: if no dedicated BOM sheet found, use any SFG/SKU sheet
    if sfg_bom_sheet is None:
        sfg_bom_sheet = find_sheet_by_keyword(sheet_names, "SFG")
    if sku_bom_sheet is None:
        sku_bom_sheet = find_sheet_by_keyword(sheet_names, "SKU")
    if rm_sheet is None:
        rm_sheet = find_sheet_by_keyword(sheet_names, "RM")
    if sfg_sheet is None:
        # Use an SFG sheet that isn't the BOM sheet
        for name in sheet_names:
            if "sfg" in name.lower() and name != sfg_bom_sheet:
                sfg_sheet = name
                break
    if sku_sheet is None:
        for name in sheet_names:
            if "sku" in name.lower() and name != sku_bom_sheet:
                sku_sheet = name
                break
    if yield_sheet is None:
        yield_sheet = find_sheet_by_keyword(sheet_names, "Yield")

    # Read all sheets
    all_sheets = pd.read_excel(BytesIO(file_bytes), sheet_name=None, dtype=None)

    rm_df = all_sheets.get(rm_sheet) if rm_sheet else None
    sfg_df = all_sheets.get(sfg_sheet) if sfg_sheet else None
    sku_df = all_sheets.get(sku_sheet) if sku_sheet else None
    sfg_bom_df = all_sheets.get(sfg_bom_sheet) if sfg_bom_sheet else None
    sku_bom_df = all_sheets.get(sku_bom_sheet) if sku_bom_sheet else None
    yield_df = all_sheets.get(yield_sheet) if yield_sheet else None

    # --- Find columns ---
    rm_code = find_column(rm_df.columns, ["code"]) if rm_df is not None else None
    rm_name = find_column(rm_df.columns, ["name"]) if rm_df is not None else None
    rm_qty = find_column(rm_df.columns, ["qty", "quantity"]) if rm_df is not None else None
    rm_price = find_column(rm_df.columns, ["price", "cost"]) if rm_df is not None else None
    rm_allergen_cols = allergen_rules.get_allergen_cols(rm_df)

    sfg_code = find_column(sfg_df.columns, ["code"]) if sfg_df is not None else None
    sfg_allergen_cols = allergen_rules.get_allergen_cols(sfg_df)

    sku_code = find_column(sku_df.columns, ["code"]) if sku_df is not None else None
    sku_allergen_cols = allergen_rules.get_allergen_cols(sku_df)

    # BOM component/parent columns
    sfg_bom_comp = find_column(sfg_bom_df.columns, ["component", "code", "rm"]) if sfg_bom_df is not None else None
    sfg_bom_parent = find_column(sfg_bom_df.columns, ["parent", "sfg", "code"]) if sfg_bom_df is not None else None
    # Be smarter: if "parent" exists use it, else use the code-like col that isn't component
    if sfg_bom_df is not None:
        cols_l = [str(c).lower() for c in sfg_bom_df.columns]
        if "parent" in cols_l:
            sfg_bom_parent = list(sfg_bom_df.columns)[cols_l.index("parent")]
        if "component" in cols_l:
            sfg_bom_comp = list(sfg_bom_df.columns)[cols_l.index("component")]

    sku_bom_comp = None
    sku_bom_parent = None
    if sku_bom_df is not None:
        cols_l = [str(c).lower() for c in sku_bom_df.columns]
        if "component" in cols_l:
            sku_bom_comp = list(sku_bom_df.columns)[cols_l.index("component")]
        if "parent" in cols_l:
            sku_bom_parent = list(sku_bom_df.columns)[cols_l.index("parent")]
        # Fallbacks
        if sku_bom_comp is None:
            sku_bom_comp = find_column(sku_bom_df.columns, ["code", "component"])
        if sku_bom_parent is None:
            sku_bom_parent = find_column(sku_bom_df.columns, ["parent", "sku"])

    # --- Allergen verification ---
    rm_map = allergen_rules.build_rm_allergen_map(rm_df, rm_code, rm_allergen_cols)
    sfg_existing = allergen_rules.build_sfg_allergen_map(sfg_df, sfg_code, sfg_allergen_cols)
    sku_existing = allergen_rules.build_sfg_allergen_map(sku_df, sku_code, sku_allergen_cols)

    sfg_expected = allergen_rules.verify_sfg_allergens(
        sfg_bom_df, rm_map, sfg_existing, sfg_bom_comp, sfg_bom_parent,
        sfg_allergen_cols, result, sfg_bom_sheet or "SFG BOM",
    )
    # Merge computed SFG allergens into sfg_map for SKU propagation
    sfg_map_for_sku = dict(sfg_existing)
    for code, exp in sfg_expected.items():
        sfg_map_for_sku[code] = exp

    sku_expected = allergen_rules.verify_sku_allergens(
        sku_bom_df, rm_map, sfg_map_for_sku, sku_existing, sku_bom_comp,
        sku_bom_parent, sku_allergen_cols, result, sku_bom_sheet or "SKU BOM",
    )

    # --- BOM structure verification ---
    rm_codes = bom_rules.get_codes(rm_df, rm_code)
    sfg_codes = bom_rules.get_codes(sfg_df, sfg_code)

    bom_rules.verify_bom_structure(
        sfg_bom_df, rm_codes, set(), "RM Master",
        sfg_bom_comp, sfg_bom_parent, result, sfg_bom_sheet or "SFG BOM",
    )
    bom_rules.verify_circular_sfg(sfg_bom_df, sfg_bom_comp, sfg_bom_parent,
                                  result, sfg_bom_sheet or "SFG BOM")

    sku_codes = bom_rules.get_codes(sku_df, sku_code)
    bom_rules.verify_bom_structure(
        sku_bom_df, rm_codes, sfg_codes, "RM Master or SFG",
        sku_bom_comp, sku_bom_parent, result, sku_bom_sheet or "SKU BOM",
    )

    # --- Cost verification ---
    for sheet_label, df, code_col in [
        (rm_sheet, rm_df, rm_code),
        (sfg_sheet, sfg_df, sfg_code),
        (sku_sheet, sku_df, sku_code),
    ]:
        if df is None:
            continue
        qty_col = find_column(df.columns, ["qty", "quantity"])
        price_col = find_column(df.columns, ["price"])
        cost_col = find_column(df.columns, ["cost", "total"])
        cost_rules.verify_costs(df, code_col, qty_col, price_col, cost_col,
                                result, sheet_label)

    # --- Yield verification ---
    cost_rules.verify_yield(yield_df, yield_sheet or "Yield Report", result)

    # --- UOM check ---
    for sheet_label, df in [(rm_sheet, rm_df), (sfg_sheet, sfg_df), (sku_sheet, sku_df)]:
        if df is not None:
            cost_rules.verify_uom(df, sheet_label or "Sheet", result)

    # --- Formula verification ---
    formula_rules.verify_formulas(file_bytes, result)

    # --- Metrics ---
    result.rm_checked = len(rm_codes) if rm_codes else (len(rm_df) if rm_df is not None else 0)
    result.sku_checked = len(sku_codes) if sku_codes else (len(sku_df) if sku_df is not None else 0)

    # --- Generate outputs ---
    corrected = None
    audit = None
    try:
        corrected = generate_corrected_excel(
            file_bytes, rm_sheet, sfg_sheet, sku_sheet,
            rm_map, sfg_expected, sku_expected,
            rm_code, sfg_code, sku_code,
        )
    except Exception as e:
        result.add("Output", 0, "Error", "Corrected Excel", str(e),
                   f"Failed to generate corrected Excel: {e}")
    try:
        audit = generate_audit_report(result.errors, {
            "rm_checked": result.rm_checked,
            "sfg_mismatches": result.sfg_mismatches,
            "sku_checked": result.sku_checked,
            "formula_errors": result.formula_errors,
        })
    except Exception as e:
        result.add("Output", 0, "Error", "Audit Report", str(e),
                   f"Failed to generate audit report: {e}")

    result.corrected_bytes = corrected
    result.audit_bytes = audit
    return result


if uploaded is not None:
    file_bytes = uploaded.getvalue()
    try:
        sheet_names = pd.ExcelFile(BytesIO(file_bytes)).sheet_names
    except Exception as e:
        st.error(f"Could not read workbook: {e}")
        st.stop()

    st.subheader("Sheets detected")
    st.write(", ".join(sheet_names))

    if st.button("Verify Workbook"):
        with st.spinner("Verifying..."):
            result = run_verification(file_bytes, sheet_names)

        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("RM Checked", result.rm_checked)
        col2.metric("SFG Mismatches", result.sfg_mismatches)
        col3.metric("SKU Checked", result.sku_checked)
        col4.metric("Formula Errors", result.formula_errors)

        st.subheader("Detailed Errors")
        if result.errors:
            import pandas as _pd
            err_df = _pd.DataFrame([
                {"Sheet": e.Sheet, "Row": e.Row, "Type": e.Type,
                 "Expected": e.Expected, "Found": e.Found, "Message": e.Message}
                for e in result.errors
            ])
            st.dataframe(err_df, use_container_width=True)
        else:
            st.success("No errors found. Workbook verified successfully.")

        st.subheader("Downloads")
        dlcol1, dlcol2 = st.columns(2)
        with dlcol1:
            if result.corrected_bytes:
                st.download_button(
                    "Download Corrected Excel",
                    data=result.corrected_bytes,
                    file_name="corrected_bom.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            else:
                st.info("Corrected Excel not available.")
        with dlcol2:
            if result.audit_bytes:
                st.download_button(
                    "Download Audit Report",
                    data=result.audit_bytes,
                    file_name="audit_report.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            else:
                st.info("Audit report not available.")
else:
    st.info("Upload an .xlsx file to begin.")
