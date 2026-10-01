import pandas as pd
from io import BytesIO

def generate_corrected_excel(file_bytes, rm_sheet, sfg_sheet, sku_sheet,
                             rm_map, sfg_expected, sku_expected,
                             rm_code, sfg_code, sku_code):
    # Load all sheets
    xls = pd.read_excel(BytesIO(file_bytes), sheet_name=None)

    # FIX SFG SHEET
    if sfg_sheet in xls and sfg_code:
        df = xls[sfg_sheet]
        for idx, row in df.iterrows():
            code = str(row[sfg_code]).strip()
            if code in sfg_expected:
                for allergen, val in sfg_expected[code].items():
                    if allergen in df.columns:
                        df.at[idx, allergen] = val
        xls[sfg_sheet] = df

    # FIX SKU SHEET - THIS IS WHAT YOU WANT - RM -> SKU OVERVIEW
    if sku_sheet in xls and sku_code:
        df = xls[sku_sheet]
        for idx, row in df.iterrows():
            code = str(row[sku_code]).strip()
            if code in sku_expected:
                for allergen, val in sku_expected[code].items():
                    if allergen in df.columns:
                        df.at[idx, allergen] = val
        xls[sku_sheet] = df

    # Save same excel with fixed sheets
    out = BytesIO()
    with pd.ExcelWriter(out, engine='openpyxl') as writer:
        for name, df in xls.items():
            df.to_excel(writer, sheet_name=name, index=False)
    out.seek(0)
    return out.getvalue()

def generate_audit_report(errors, metrics):
    out = BytesIO()
    with pd.ExcelWriter(out, engine='openpyxl') as writer:
        pd.DataFrame([{"Sheet": e.Sheet, "Row": e.Row, "Type": e.Type, "Expected": e.Expected, "Found": e.Found, "Message": e.Message} for e in errors]).to_excel(writer, sheet_name="Errors", index=False)
        pd.DataFrame([metrics]).to_excel(writer, sheet_name="Summary", index=False)
    out.seek(0)
    return out.getvalue()
