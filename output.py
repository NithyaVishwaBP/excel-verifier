import pandas as pd
from io import BytesIO

def create_output_files(original_file, fixed_sheets, errors):
    # Create fixed Excel in memory - SAME file structure but corrected
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for sheet_name, df in fixed_sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    output.seek(0)

    # Create Error CSV
    error_df = pd.DataFrame(errors)
    error_csv = error_df.to_csv(index=False).encode('utf-8')

    return output, error_csv, error_df
