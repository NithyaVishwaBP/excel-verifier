import pandas as pd
from io import BytesIO
from openpyxl import load_workbook

def generate_corrected_excel(file_bytes, rm_sheet, sfg_sheet, sku_sheet,
                             rm_map, sfg_expected, sku_expected,
                             rm_code, sfg_code, sku_code):
    """
    RM Master is Source of Truth.
    Auto-fixes SFG and SKU Overview allergen columns in SAME Excel and returns it.
    """
    wb = load_workbook(BytesIO(file_bytes))

    # Helper to update sheet
    def update_sheet(sheet_name, expected_map, code_col_name):
        if not sheet_name or sheet_name not in wb.sheetnames:
            return
        ws = wb[sheet_name]
        # Read header row
        headers = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column+1)]
        # Find code column index
        code_idx = None
        for i, h in enumerate(headers):
            if h and str(h).strip().lower() == str(code_col_name).strip().lower():
                code_idx = i+1
                break
        if not code_idx:
            code_idx = 1 # assume first col is code

        # Find allergen column indexes
        allergen_col_idx = {}
        for i, h in enumerate(headers):
            if h and str(h).lower() in ['gluten','soy','milk','egg','peanut','nut','fish','shellfish','sesame','mustard','celery','lupin','sulphite','contains milk','contains soy']:
                allergen_col_idx[str(h).lower()] = i+1
            # Also detect 0/1 columns - assume allergen
            # We'll use headers as keys

        # Update rows
        for r in range(2, ws.max_row+1):
            code_val = ws.cell(row=r, column=code_idx).value
            if not code_val:
                continue
            code_str = str(code_val).strip()
            if code_str in expected_map:
                for allergen_name, expected_val in expected_map[code_str].items():
                    # Find column for this allergen
                    for hdr, col_idx in enumerate(headers, start=1):
                        if hdr and str(hdr).strip().lower() == str(allergen_name).strip().lower():
                            ws.cell(row=r, column=col_idx, value=expected_val)

    # Fix SFG sheet
    update_sheet(sfg_sheet, sfg_expected, sfg_code)
    # Fix SKU sheet - THIS IS WHAT YOU WANTED - SKU Overview from RM Master
    update_sheet(sku_sheet, sku_expected, sku_code)

    # Save to bytes
    out = BytesIO()
    wb.save(out)
    out.seek(0)
    return out.getvalue()

def generate_audit_report(errors, metrics):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if errors:
            err_df = pd.DataFrame([{
                "Sheet": e.Sheet, "Row": e.Row, "Type": e.Type,
                "Expected": e.Expected, "Found": e.Found, "Message": e.Message
            } for e in errors])
        else:
            err_df = pd.DataFrame([{"Message": "No errors"}])
        err_df.to_excel(writer, sheet_name="Errors", index=False)

        metrics_df = pd.DataFrame([metrics])
        metrics_df.to_excel(writer, sheet_name="Summary", index=False)
    output.seek(0)
    return output.getvalue()
