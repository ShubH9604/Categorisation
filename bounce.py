import pandas as pd
from keywords import bounce_keywords, loan_keywords

def main():
    # Step 1: Load Excel
    input_file = "bounce.xlsx"
    df = pd.read_excel(input_file)

    # Step 2: Column name mapping dictionary
    column_map = {
        'Narration': ['narration', 'Description', 'narrations',"Translation"],
        'Debits': ['Debit', 'debit', 'dr amount'],
        'Credits': ['credits', 'Credit', 'cr amount'],
        'Balance': ['balance', 'available balance'],
        'Cheque No': ['cheque no', 'cheque number', 'cheque'],
        'XN Date': ['Date', 'date', 'txn date', 'transaction date']
    }

    # Step 3: Resolve actual column names in file
    def resolve_column(possible_names, df_columns):
        for name in possible_names:
            for col in df_columns:
                if name.strip().lower() == col.strip().lower():
                    return col
        return None

    resolved_map = {}
    for standard_col, variants in column_map.items():
        resolved_col = resolve_column(variants, df.columns)
        if resolved_col:
            resolved_map[resolved_col] = standard_col

    # Step 4: Rename columns to standardized ones
    df = df.rename(columns=resolved_map)

    # Step 5: Preprocessing
    original_narration = df['Narration'].copy()
    df['Narration'] = df['Narration'].astype(str).str.lower()
    df['Debits'] = pd.to_numeric(df.get('Debits', 0), errors='coerce')
    df['Credits'] = pd.to_numeric(df.get('Credits', 0), errors='coerce')
    df['Balance'] = pd.to_numeric(df.get('Balance', 0), errors='coerce')
    df['Cheque No'] = df.get('Cheque No', '').astype(str).str.strip()
    df['XN Date'] = pd.to_datetime(df.get('XN Date', ''), errors='coerce')

    # Step 8: Helper functions
    def identify_bounce_type(narration):
        bounce_indicators = ["rtn", "return", "ret", "rtnchg", "bounce"]

        # First check for GST-specific bounce charges, but only if bounce-related terms exist
        gst_data = bounce_keywords["BOUNCE CHARGES - GST"]
        if any(tk in narration for tk in gst_data["type_keywords"]) and \
           any(kw in narration for kw in gst_data["keywords"]) and \
           any(bounce_kw in narration for bounce_kw in bounce_indicators):
            return "BOUNCE CHARGES - GST"

        # Then check for normal bounce charges, only if bounce-related terms exist
        normal_data = bounce_keywords["BOUNCE CHARGES"]
        if any(tk in narration for tk in normal_data["type_keywords"]) and \
           any(kw in narration for kw in normal_data["keywords"]) and \
           any(bounce_kw in narration for bounce_kw in bounce_indicators):
            return "BOUNCE CHARGES"

        # Then check for other bounce types
        for bounce_type, data in bounce_keywords.items():
            if bounce_type in ["BOUNCE CHARGES", "BOUNCE CHARGES - GST"]:
                continue
            if any(tk in narration for tk in data["type_keywords"]):
                if any(kw in narration for kw in data["keywords"]):
                    return bounce_type

        return None

    def has_loan_keyword(narration):
        return any(kw in narration for kw in loan_keywords)

    # Step 9: Main bounce tagging logic
    df['Bounce Type'] = None

    for i, row in df.iterrows():
        narration = str(row['Narration']).lower()
        cheque_no = str(row['Cheque No']).strip()
        date = row['XN Date']
        debit_amt = row['Debits']

        if has_loan_keyword(narration) and pd.notna(debit_amt) and debit_amt > 0:
            # Match by same Cheque No and near-same credit amount
            match = df[
                (df['XN Date'] == date) &
                (df['Credits'].fillna(0).between(debit_amt * 0.95, debit_amt * 1.05)) &
                (df['Cheque No'].astype(str).str.strip() == cheque_no) &
                (df.index != i)
            ]

            if not match.empty:
                j = match.index[0]
                df.at[i, 'Bounce Type'] = ""
                df.at[j, 'Bounce Type'] = "Loan Bounce"
                continue

        bounce_type = identify_bounce_type(narration)
        if bounce_type:
            if bounce_type == "NEFT":
                if not any(kw in narration for kw in bounce_keywords["NEFT"]["keywords"]):
                    continue
                if row.get('Credits', 0) <= 0 or row.get('Debits', 0) > 0:
                    continue
            df.at[i, 'Bounce Type'] = bounce_type

    df['Narration'] = original_narration

    # Step 10: Save the output
    output_file = input_file.replace(".xlsx", "_output.xlsx")
    df.to_excel(output_file, index=False)

    print("✅ Bounce type tagging completed. File saved as:", output_file)

if __name__ == "__main__":
    main()