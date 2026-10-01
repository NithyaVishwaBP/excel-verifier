import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Excel BOM Verification", layout="wide")
st.title("EXCEL VERIFICATION & CALCULATOR - RM Master Truth")

uploaded = st.file_uploader("Upload.xlsx workbook", type=["xlsx"])

if uploaded:
    file_bytes = uploaded.getvalue()
    xls = pd.read_excel(BytesIO(file_bytes), sheet_name=None, dtype=None)
    st.write("Sheets detected:", ", ".join(xls.keys()))

    # Find sheets - DO NOT TOUCH Recipe Viewer
    rm_sheet = next((k for k in xls if 'rm' in k.lower() and 'master' in k.lower()), None)
    if not rm_sheet:
        rm_sheet = next((k for k in xls if 'rm' in k.lower()), list(xls.keys())[0])

    sfg_bom_sheet = next((k for k in xls if 'sfg' in k.lower() and 'bom' in k.lower()), None)
    sku_bom_sheet = next((k for k in xls if 'sku' in k.lower() and 'bom' in k.lower()), None)
    sku_sheet = next((k for k in xls if 'sku' in k.lower() and 'overview' in k.lower()), None)
    if not sku_sheet:
        sku_sheet = next((k for k in xls if 'sku' in k.lower() and 'bom' not in k.lower()), None)

    rm_df = xls[rm_sheet]

    # ONLY real allergen columns
    real_allergens = ['gluten','crustaceans','molluscs','milk','egg','fish','peanut','tree nut','soy','sulphite','sesame','mustard','celery','lupin']
    allergen_cols = []
    for c in rm_df.columns:
        cl = str(c).lower()
        for real in real_allergens:
            if real in cl:
                allergen_cols.append(c)
                break

    st.success(f"RM Master Sheet: {rm_sheet} | SKU Overview: {sku_sheet}")
    st.write(f"Allergen columns from RM Master: {allergen_cols}")

    if st.button("Verify & Create NEW Verified Columns in SKU Overview"):
        rm_code_col = rm_df.columns[0]
        rm_map = {}
        for _, r in rm_df.iterrows():
            code = str(r[rm_code_col]).strip()
            if code and code!= 'nan':
                rm_map[code] = {a: int(r[a]) if pd.notna(r[a]) else 0 for a in allergen_cols if a in r}

        # Build SFG allergen map from SFG BOM
        sfg_map = {}
        if sfg_bom_sheet and sfg_bom_sheet in xls:
            sfg_bom_df = xls[sfg_bom_sheet]
            sfg_parent_col = sfg_bom_df.columns[0]
            # Group by SFG
            for sfg_code in sfg_bom_df[sfg_parent_col].dropna().unique():
                sfg_code_str = str(sfg_code).strip()
                rows = sfg_bom_df[sfg_bom_df[sfg_parent_col]==sfg_code]
                # Find all RM codes in these rows
                rms = []
                for val in rows.values.flatten():
                    v = str(val).strip()
                    if v in rm_map:
                        rms.append(v)
                computed = {a:0 for a in allergen_cols}
                for rm_c in rms:
                    for a in allergen_cols:
                        computed[a] = max(computed[a], rm_map[rm_c].get(a,0))
                sfg_map[sfg_code_str] = computed

        # Build SKU allergen from SKU BOM (RM + SFG)
        sku_computed = {}
        if sku_bom_sheet and sku_bom_sheet in xls:
            sku_bom_df = xls[sku_bom_sheet]
            sku_parent_col = sku_bom_df.columns[0]
            for sku_code in sku_bom_df[sku_parent_col].dropna().unique():
                sku_str = str(sku_code).strip()
                rows = sku_bom_df[sku_bom_df[sku_parent_col]==sku_code]
                all_rms_from_sku = []
                all_sfgs_from_sku = []
                for val in rows.values.flatten():
                    v = str(val).strip()
                    if v in rm_map:
                        all_rms_from_sku.append(v)
                    if v in sfg_map:
                        all_sfgs_from_sku.append(v)
                computed = {a:0 for a in allergen_cols}
                # From direct RMs
                for rm_c in all_rms_from_sku:
                    for a in allergen_cols:
                        computed[a] = max(computed[a], rm_map[rm_c].get(a,0))
                # From SFGs (which already have RM allergens)
                for sfg_c in all_sfgs_from_sku:
                    for a in allergen_cols:
                        computed[a] = max(computed[a], sfg_map[sfg_c].get(a,0))
                sku_computed[sku_str] = computed

        # NOW CREATE NEW COLUMNS IN SKU OVERVIEW - DO NOT CHANGE OLD COLUMNS
        fixed_xls = xls.copy() # Keep Recipe Viewer and all sheets untouched
        if sku_sheet and sku_sheet in xls:
            sku_df = xls[sku_sheet].copy()
            sku_code_col = sku_df.columns[0]
            # Add NEW columns at end with prefix Verified_
            for allergen in allergen_cols:
                new_col_name = f"Verified_{allergen}_From_RM"
                # Initialize new column
                sku_df[new_col_name] = 0
                for idx, row in sku_df.iterrows():
                    sku_c = str(row[sku_code_col]).strip()
                    if sku_c in sku_computed:
                        sku_df.at[idx, new_col_name] = sku_computed[sku_c].get(allergen, 0)
                    else:
                        # Fallback: try to find RM directly in SKU Overview row
                        rms_in_row = [str(v).strip() for v in row.values if str(v).strip() in rm_map]
                        comp = 0
                        for rm_c in rms_in_row:
                            comp = max(comp, rm_map[rm_c].get(allergen,0))
                        sku_df.at[idx, new_col_name] = comp
            fixed_xls[sku_sheet] = sku_df

            

        # Show results
        st.success(f"Created {len(allergen_cols)} NEW Verified columns in SKU Overview without changing original columns!")
        st.write(f"SKU Codes traced: {len(sku_computed)}")

        if sku_sheet:
            st.subheader(f"Preview of {sku_sheet} - NEW columns at end")
            st.dataframe(fixed_xls[sku_sheet].head(), use_container_width=True)

        # Download - SAME Excel structure, Recipe Viewer untouched, SKU Overview has NEW columns
        out = BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer:
            for name, df in fixed_xls.items():
                df.to_excel(writer, sheet_name=name, index=False)
        out.seek(0)

        st.download_button(
            "Download Excel - SKU Overview with NEW Verified Columns (Original columns unchanged)",
            data=out.getvalue(),
            file_name="Verified_RM_to_SKU_NEW_Columns.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
