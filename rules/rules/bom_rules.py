"""BOM structure rules: existence, duplicates, circular references."""

from utils import safe_str


def verify_bom_structure(bom_df, rm_codes, sfg_codes, valid_label, component_col,
                         parent_col, result, sheet_name):
    """Verify a BOM sheet's components and parents.

    - component codes must exist in the valid set (rm_codes and/or sfg_codes)
    - no duplicate component codes within the same parent
    - no circular reference (a parent containing itself as a component)
    """
    if bom_df is None or component_col is None:
        return

    rm_set = set(rm_codes or [])
    sfg_set = set(sfg_codes or [])
    valid_set = rm_set | sfg_set

    seen_components_per_parent = {}
    for idx, row in bom_df.iterrows():
        parent = safe_str(row.get(parent_col)) if parent_col else ""
        comp = safe_str(row.get(component_col))
        excel_row = idx + 2  # header is row 1

        # Existence check
        if comp and comp not in valid_set:
            result.add(
                sheet_name, excel_row, "Missing Component",
                f"Exists in {valid_label}", "Not found",
                f"Component '{comp}' in parent '{parent}' not found in {valid_label}",
            )

        # Self-reference (circular)
        if parent and comp and parent == comp:
            result.add(
                sheet_name, excel_row, "Circular Reference",
                "Parent != Component", f"{parent} == {comp}",
                f"'{parent}' references itself",
            )

        # Duplicate component within same parent
        if parent and comp:
            key = (parent, comp)
            if key in seen_components_per_parent:
                result.add(
                    sheet_name, excel_row, "Duplicate Code",
                    "Unique component per parent", f"Duplicate '{comp}'",
                    f"Component '{comp}' duplicated in parent '{parent}'",
                )
            else:
                seen_components_per_parent[key] = True


def verify_circular_sfg(sfg_bom_df, component_col, parent_col, result, sheet_name):
    """Detect circular references among SFGs (SFG A uses SFG B which uses SFG A)."""
    if sfg_bom_df is None or component_col is None or parent_col is None:
        return

    # Build adjacency: parent -> [components that are also SFGs]
    sfg_parents = set()
    adj = {}
    for _, row in sfg_bom_df.iterrows():
        parent = safe_str(row.get(parent_col))
        comp = safe_str(row.get(component_col))
        if parent and comp:
            sfg_parents.add(parent)
            sfg_parents.add(comp)
            adj.setdefault(parent, []).append(comp)

    def dfs(node, visited, stack):
        if node in stack:
            return list(stack[stack.index(node):]) + [node]
        if node in visited:
            return None
        visited.add(node)
        stack.append(node)
        for nbr in adj.get(node, []):
            cycle = dfs(nbr, visited, stack)
            if cycle:
                return cycle
        stack.pop()
        return None

    visited_all = set()
    for node in sfg_parents:
        if node not in visited_all:
            cycle = dfs(node, visited_all, [])
            if cycle:
                result.add(
                    sheet_name, 0, "Circular Reference",
                    "No cycle", " -> ".join(cycle),
                    f"Circular SFG reference: {' -> '.join(cycle)}",
                )


def get_codes(df, code_col):
    """Return a set of non-empty code strings from a dataframe column."""
    if df is None or code_col is None:
        return set()
    codes = set()
    for _, row in df.iterrows():
        c = safe_str(row.get(code_col))
        if c:
            codes.add(c)
    return codes
