import pandas as pd

def check_and_fix_allergens(wb_sheets):
    """
    RM Master is Source of Truth
    RM -> SFG BOM -> SKU BOM -> SKU Overview auto-propagation
    """
    rm_df = wb_sheets['RM Master']
    sfg_df = wb_sheets['SFG BOM']
    sku_bom_df = wb_sheets['SKU BOM']
    sku_overview_df = wb_sheets['SKU Overview']

    errors = []

    # Find allergen columns (common allergens)
    allergen_cols = [c for c in rm_df.columns if c.lower() in ['gluten','soy','milk','egg','peanut','nut','fish','shellfish','sesame','mustard','celery','lupin','sulphite','milk product','soy lecithin']]
    # If not found by name, take columns after RM code/name that have 0/1 values
    if not allergen_cols:
        # assume allergen columns are those with only 0/1 values in RM Master
        for col in rm_df.columns:
            try:
                vals = set(rm_df[col].dropna().unique())
                if vals.issubset({0,1,0.0,1.0,'0','1'}):
                    allergen_cols.append(col)
            except:
                pass
        # Remove first few non-allergen columns
        allergen_cols = [c for c in allergen_cols if c not in rm_df.columns[:4]]

    print(f"Allergen columns detected: {allergen_cols}")

    # Step 1: Build RM allergen map
    rm_allergen_map = {}
    rm_code_col = rm_df.columns[0] # first col is RM code
    for _, row in rm_df.iterrows():
        rm_code = str(row[rm_code_col]).strip()
        rm_allergen_map[rm_code] = {a: int(row[a]) if pd.notna(row[a]) else 0 for a in allergen_cols}

    # Step 2: Fix SFG BOM - based on its RMs
    # SFG BOM structure: SFG code + RM codes + allergen cols
    sfg_code_col = sfg_df.columns[0]
    sfg_rm_cols = sfg_df.columns[1:5] # adjust based on your sheet - RMs are listed

    # For each SFG, collect its RMs and compute allergen
    sfg_fixed = {}
    for sfg_code in sfg_df[sfg_code_col].unique():
        sfg_rows = sfg_df[sfg_df[sfg_code_col] == sfg_code]
        # Get all RM codes used in this SFG
        rm_list = []
        for col in sfg_df.columns:
            if 'RM' in str(col) or 'rm' in str(col).lower():
                rm_list.extend(sfg_rows[col].dropna().astype(str).tolist())

        # Calculate allergen as MAX of its RMs
        computed = {a: 0 for a in allergen_cols}
        for rm_code in rm_list:
            rm_code = rm_code.strip()
            if rm_code in rm_allergen_map:
                for a in allergen_cols:
                    computed[a] = max(computed[a], rm_allergen_map[rm_code].get(a,0))

        sfg_fixed[sfg_code] = computed

        # Check mismatches
        for _, row in sfg_rows.iterrows():
            for a in allergen_cols:
                if a in row:
                    existing = int(row[a]) if pd.notna(row[a]) else 0
                    if existing!= computed[a]:
                        errors.append({
                            'Sheet': 'SFG BOM',
                            'Code': sfg_code,
                            'Type': a,
                            'Expected': computed[a],
                            'Found': existing,
                            'Message': f"SFG '{sfg_code}' {a} should be {computed[a]} but is {existing} (from RM)"
                        })

    # Apply fix to SFG BOM dataframe
    for idx, row in sfg_df.iterrows():
        sfg_code = str(row[sfg_code_col]).strip()
        if sfg_code in sfg_fixed:
            for a in allergen_cols:
                if a in sfg_df.columns:
                    sfg_df.at[idx, a] = sfg_fixed[sfg_code][a]

    # Step 3: Fix SKU Overview - based on SFGs
    sku_code_col_bom = sku_bom_df.columns[0]
    sku_code_col_overview = sku_overview_df.columns[0]

    # Build SFG allergen map (now fixed)
    # Build SKU allergen from its SFGs
    sku_fixed = {}
    for sku_code in sku_bom_df[sku_code_col_bom].unique():
        sku_rows = sku_bom_df[sku_bom_df[sku_code_col_bom] == sku_code]
        sfg_list = []
        for col in sku_bom_df.columns:
            if 'SFG' in str(col) or 'sfg' in str(col).lower():
                sfg_list.extend(sku_rows[col].dropna().astype(str).tolist())

        computed = {a: 0 for a in allergen_cols}
        for sfg_code in sfg_list:
            sfg_code = sfg_code.strip()
            if sfg_code in sfg_fixed:
                for a in allergen_cols:
                    computed[a] = max(computed[a], sfg_fixed[sfg_code][a])

        sku_fixed[sku_code] = computed

    # Apply fix to SKU Overview
    for idx, row in sku_overview_df.iterrows():
        sku_code = str(row[sku_code_col_overview]).strip()
        if sku_code in sku_fixed:
            for a in allergen_cols:
                if a in sku_overview_df.columns:
                    # check error before fixing
                    existing = int(row[a]) if pd.notna(row[a]) and a in row else 0
                    expected = sku_fixed[sku_code][a]
                    if existing!= expected:
                        errors.append({
                            'Sheet': 'SKU Overview',
                            'Code': sku_code,
                            'Type': a,
                            'Expected': expected,
                            'Found': existing,
                            'Message': f"SKU '{sku_code}' {a} should be {expected} but is {existing} (from RM->SFG)"
                        })
                    sku_overview_df.at[idx, a] = expected

    # Update sheets dict
    wb_sheets['SFG BOM'] = sfg_df
    wb_sheets['SKU Overview'] = sku_overview_df

    return errors, wb_sheets
