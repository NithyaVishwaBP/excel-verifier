import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Excel BOM Verification Tool", layout="wide")
st.title("EXCEL VERIFICATION & CALCULATOR - Auto Fix RM->SKU")

uploaded = st.file_uploader("Upload.xlsx workbook", type=["xlsx"])

if uploaded:
    file_bytes = uploaded.getvalue()
    xls = pd.read_excel(BytesIO(file_bytes), sheet_name=None, dtype=None)
    st.write("Sheets detected:", ", ".join(xls.keys()))

    # Find sheets
    rm_sheet = [k for k in xls if 'rm' in k.lower()][0] if any('rm' in k.lower() for k in xls) else list(xls.keys())[0]
    sfg_bom_sheet = [k for k in xls if 'sfg' in k.lower() and 'bom' in k.lower()][0] if any('sfg' in k.lower() and 'bom' in k.lower() for k in xls) else None
    sku_bom_sheet = [k for k in xls if 'sku' in k.lower() and 'bom' in k.lower()][0] if any('sku' in k.lower() and 'bom' in k.lower() for k in xls) else None
    sku_sheet = [k for k in xls if 'sku' in k.lower() and 'bom' not in k.lower() and 'overview' in k.lower() or 'sku' in k.lower() and 'bom' not in k.lower()][0] if True else None
    # Better find sku overview
    for k in xls:
        if 'sku' in k.lower() and 'bom' not in k.lower():
            sku_sheet = k
            break

    rm_df = xls[rm_sheet]
    # Detect allergen cols (0/1 cols)
    allergen_cols = []
    for c in rm_df.columns:
        try:
            vals = set(rm_df[c].dropna().unique())
            if vals.issubset({0,1,0.0,1.0,'0','1',1,0}):
                if c.lower() not in ['code','name','qty','quantity','price','cost','uom']:
                    allergen_cols.append(c)
        except:
            pass

    st.write(f"Allergen columns found: {allergen_cols}")

    if st.button("Verify Workbook & Auto-Fix from RM Master"):
        rm_code_col = rm_df.columns[0]
        rm_map = {}
        for _, r in rm_df.iterrows():
            code = str(r[rm_code_col]).strip()
            rm_map[code] = {a: int(r[a]) if pd.notna(r[a]) else 0 for a in allergen_cols if a in r}

        errors = []
        fixed_xls = xls.copy()

        # Fix SFG BOM if exists
        if sfg_bom_sheet and sfg_bom_sheet in xls:
            sfg_df = xls[sfg_bom_sheet].copy()
            sfg_code_col = sfg_df.columns[0]
            # Find RM columns in SFG BOM (look for RM code cols)
            for idx, row in sfg_df.iterrows():
                sfg_code = str(row[sfg_code_col]).strip()
                # collect all RM codes in this row
                rms_in_row = [str(v).strip() for v in row.values if str(v).strip() in rm_map]
                computed = {a:0 for a in allergen_cols}
                for rm_c in rms_in_row:
                    for a in allergen_cols:
                        computed[a] = max(computed[a], rm_map[rm_c].get(a,0))
                # check and fix
                for a in allergen_cols:
                    if a in sfg_df.columns:
                        existing = int(row[a]) if pd.notna(row[a]) else 0
                        if existing!= computed[a]:
                            errors.append({"Sheet":"SFG BOM","Code":sfg_code,"Type":a,"Expected":computed[a],"Found":existing,"Message":f"SFG {sfg_code} {a} should be {computed[a]} but is {existing} from RM"})
                        sfg_df.at[idx, a] = computed[a]
            fixed_xls[sfg_bom_sheet] = sfg_df

        # Fix SKU Overview - RM -> SKU directly (what you asked)
        # For simplicity, SKU Overview is fixed from SKU BOM -> SFG -> RM
        # If SKU BOM exists, use it
        sku_fixed_map = {}
        if sku_bom_sheet and sku_bom_sheet in xls:
            sku_bom_df = xls[sku_bom_sheet]
            sku_bom_parent = sku_bom_df.columns[0]
            # For each SKU, find its RMs/SFGs
            for sku_code in sku_bom_df[sku_bom_parent].unique():
                rows = sku_bom_df[sku_bom_df[sku_bom_parent]==sku_code]
                all_rms = []
                for v in rows.values.flatten():
                    vs = str(v).strip()
                    if vs in rm_map:
                        all_rms.append(vs)
                comp = {a:0 for a in allergen_cols}
                for rm_c in all_rms:
                    for a in allergen_cols:
                        comp[a] = max(comp[a], rm_map[rm_c].get(a,0))
                # Also check SFGs that were fixed
                sku_fixed_map[str(sku_code).strip()] = comp

        # Apply to SKU Overview sheet
        if sku_sheet and sku_sheet in xls:
            sku_df = xls[sku_sheet].copy()
            sku_code_col = sku_df.columns[0]
            for idx, row in sku_df.iterrows():
                sku_c = str(row[sku_code_col]).strip()
                # Try to get from sku_fixed_map, if not found compute from row RMs directly
                if sku_c in sku_fixed_map:
                    computed = sku_fixed_map[sku_c]
                else:
                    rms_in_row = [str(v).strip() for v in row.values if str(v).strip() in rm_map]
                    computed = {a:0 for a in allergen_cols}
                    for rm_c in rms_in_row:
                        for a in allergen_cols:
                            computed[a] = max(computed[a], rm_map[rm_c].get(a,0))
                for a in allergen_cols:
                    if a in sku_df.columns:
                        existing = int(row[a]) if pd.notna(row[a]) else 0
                        if existing!= computed.get(a,0):
                            errors.append({"Sheet":"SKU Overview","Code":sku_c,"Type":a,"Expected":computed.get(a,0),"Found":existing,"Message":f"SKU {sku_c} {a} should be {computed.get(a,0)} but is {existing} (from RM Master)"})
                        sku_df.at[idx, a] = computed.get(a,0)
            fixed_xls[sku_sheet] = sku_df

        # Metrics
        col1, col2 = st.columns(2)
        col1.metric("Errors Found & Fixed", len(errors))
        col2.metric("Allergen Cols", len(allergen_cols))

        if errors:
            st.dataframe(pd.DataFrame(errors), use_container_width=True)
        else:
            st.success("No errors - RM = SKU already correct!")

        # Download fixed excel - SAME FILE but CORRECTED SKU OVERVIEW FROM RM MASTER
        out = BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer:
            for name, df in fixed_xls.items():
                df.to_excel(writer, sheet_name=name, index=False)
        out.seek(0)

        st.download_button("Download Corrected Excel (RM->SKU Auto-Fixed)", data=out.getvalue(), file_name="corrected_RM_to_SKU_Fixed.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        # Error CSV
        if errors:
            csv = pd.DataFrame(errors).to_csv(index=False).encode('utf-8')
            st.download_button("Download Error Report CSV", data=csv, file_name="errors.csv", mime="text/csv")
