import pandas as pd

# Step 1: Load Excel
input_file = "testfile6.xlsx"
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
df['Narration'] = df['Narration'].astype(str).str.lower()
df['Debits'] = pd.to_numeric(df.get('Debits', 0), errors='coerce')
df['Credits'] = pd.to_numeric(df.get('Credits', 0), errors='coerce')
df['Balance'] = pd.to_numeric(df.get('Balance', 0), errors='coerce')
df['Cheque No'] = df.get('Cheque No', '').astype(str).str.strip()
df['XN Date'] = pd.to_datetime(df.get('XN Date', ''), errors='coerce')

# Step 6: Bounce keyword dictionary
bounce_keywords = {
    "BOUNCE CHARGES": {
    "type_keywords": ["bounce charges", "achdebitreturncharges", ".achdebitreturncharges", "cheque", "chq", "imps", "rtgs", "nach", "ach", "ecs"],
    "keywords": [
        "rtn chgs", "return chgs", "ret chgs", "rtn chrgs", "return chrgs", "ret chrgs",
        "rtn charges", "return charges", "ret charges", "bounce charges", "debit return", "credit return", "rtnchg", "bounced charges", "rtn chrg", "rtn_chrg", "achdebitreturncharges"
    ]
    },
    "BOUNCE CHARGES - GST": {
        "type_keywords": ["bounce charges-gst", "achdebitreturnchargesgst", "chg", "chgs", "charges", "chrgs", "chrg"],
        "keywords": [
            "rtn chgs gst", "return chgs gst", "ret chgs gst", "rtn chrgs gst",
            "return chrgs gst", "ret chrgs gst", "rtnchgsgst", "rtnchg gst", "gst"
        ]
    },
    "ACH": {
        "type_keywords": ["ach", "nach"],
        "keywords": ["nach return", "nach rtn", "rev:nach", "achdebit rtn"]
    },
    "CHEQUE": {
        "type_keywords": ["chq", "cheque", "returned", "inward return", "reject"],
        "keywords": [
            "reject", "returned", "chq ret", "chq return", "funds insufficient", "i/w chq ret",
            "i/w chq rtn", "i/w chq return", "o/w rtn chq", "rtn(chq no.)", "chq issued bounce",
            "reject:(chq no.)", "ow chq rej", "brn-ow rtn", "brn-ow rtn clg", "reject:funds insufficient",
            "returned:funds insufficient", "payment stopped by drawer", "returned:", "reject:",
            "reject:.*", "funds insufficient", "instrument undated", "signature differs",
            "payment stopped", "exceeds arrangement"
        ]
    },
    "NEFT": {
        "type_keywords": ["neft", "returned"],
        "keywords": [
            "account does not exist", "rej", "rtn", "ret", "return", "return(account closed)",
            "return(not a valid cpin)", "returned", "returnfor", "reversal",
            "rtn(blocked account)", "rtn(invalid account)"
        ]
    },
    "IMPS": {
        "type_keywords": ["imps"],
        "keywords": ["imps return", "rev:imps", "reversal", "ret", "rtn", "failed", "rev-imps", "return-imps"]
    },
    "UPI": {
        "type_keywords": ["upi"],
        "keywords": ["return", "ret", "rtn", "returned", "failed", "rev", "reversal", "fail", "failur", "faild"]
    },
    "RTGS": {
        "type_keywords": ["rtgs"],
        "keywords": ["rtgs return", "rtgs failed", "rtn:rtgs", "rev"]
    },
    "ECS": {
        "type_keywords": ["ecs"],
        "keywords": ["ecs return", "return ach", "nach fail", "inward return"]
    },
}

# Step 7: Loan keywords
loan_keywords = [
    "emi", "achd", "repay", "instalment", "installment", "finance", "nbfc"
]

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
    narration = row['Narration']
    
    if has_loan_keyword(narration) and row['Debits'] > 0 and row['Balance'] < 0:
        cheque_no = row['Cheque No']
        amount = row['Debits']
        date = row['XN Date']

        match = df[
            (df['XN Date'] == date) &
            (df['Credits'] >= amount * 0.9) &
            (df['Cheque No'] == cheque_no) &
            (df.index != i)
        ]

        if not match.empty:
            j = match.index[0]
            df.at[i, 'Bounce Type'] = "Loan Bounce"
            df.at[j, 'Bounce Type'] = "Reversed/Disbursed"
            continue

    bounce_type = identify_bounce_type(narration)
    if bounce_type:
        if bounce_type == "NEFT":
            if not any(kw in narration for kw in bounce_keywords["NEFT"]["keywords"]):
                continue
            if row.get('Credits', 0) <= 0 or row.get('Debits', 0) > 0:
                continue
        df.at[i, 'Bounce Type'] = bounce_type

# Step 10: Save the output
output_file = input_file.replace(".xlsx", "_output.xlsx")
df.to_excel(output_file, index=False)

print("✅ Bounce type tagging completed. File saved as:", output_file)
