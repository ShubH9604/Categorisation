import pandas as pd

# Step 1: Load Excel
input_file = "testfile1.xlsx"
df = pd.read_excel(input_file)
df['Narration'] = df.get('Narration') if 'Narration' in df.columns else df.get('Description')
df['Narration'] = df['Narration'].astype(str).str.lower()
df['Debits'] = pd.to_numeric(df.get('Debits') if 'Debits' in df.columns else df.get('Debit', 0), errors='coerce')
df['Credits'] = pd.to_numeric(df.get('Credits') if 'Credits' in df.columns else df.get('Credit', 0), errors='coerce')
df['Balance'] = pd.to_numeric(df.get('Balance', 0), errors='coerce') if 'Balance' in df.columns else 0
df['Cheque No'] = df.get('Cheque No', '').astype(str).str.strip()
df['XN Date'] = pd.to_datetime(df.get('XN Date') if 'XN Date' in df.columns else df.get('Date', ''), errors='coerce')

# Step 2: Bounce keyword dictionary
bounce_keywords = {
    "ACH": {
        "type_keywords": ["ach", "nach"],
        "keywords": ["ach debit return", "nach return", "nach rtn", "rev:nach", "achdebit rtn"]
    },
    "NEFT": {
        "type_keywords": ["neft","returned"],
        "keywords": [
            "account does not exist", "rej", "rtn", "ret", "return", "return(account closed)",
            "return(not a valid cpin)", "returned", "returnfor", "reversal",
            "rtn(blocked account)", "rtn(invalid account)"
        ]
    },
    "IMPS": {
        "type_keywords": ["imps"],
        "keywords": ["imps return", "rev:imps", "reversal", "ret", "rtn", "failed", "rev-imps"]
    },
    "UPI": {
        "type_keywords": ["upi"],
        "keywords": ["return", "ret", "rtn", "returned", "failed", "rev", "reversal", "fail", "failur", "faild"]
    },
    "RTGS": {
        "type_keywords": ["rtgs"],
        "keywords": ["rtgs return", "rtgs failed", "rtn:rtgs", "rev"]
    },
    "CHEQUE": {
        "type_keywords": ["chq", "cheque", "returned", "inward return", "reject"],
        "keywords": [
            "reject", "returned", "chq ret", "chq return", "funds insufficient", "i/w chq ret",
            "i/w chq rtn", "i/w chq return", "o/w rtn chq", "rtn(chq no.)", "chq issued bounce",
            "reject:(chq no.)", "ow chq rej", "brn-ow rtn", "brn-ow rtn clg", "reject:funds insufficient",
            "returned:funds insufficient", "payment stopped by drawer", "returned:", "reject:",
            "reject:.*", "funds insufficient", "instrument undated", "signature differs",
            "payment stopped", "exceeds arrangement", "chq return", "inward return", "chq ret", "returned", "reject"
        ]
    },
    "ECS": {
        "type_keywords": ["ecs"],
        "keywords": ["ecs return", "return ach", "nach fail", "inward return"]
    },
    "BOUNCE CHARGES": {
        "type_keywords": ["bounce charges", "achdebitreturncharges"],
        "keywords": [
            "rtn chgs", "return chgs", "ret chgs", "rtn chrgs", "return chrgs", "ret chrgs", "charges"
        ]
    },
    "BOUNCE CHARGES - GST": {
        "type_keywords": ["bounce charges-gst", "achdebitreturnchargesgst"],
        "keywords": [
            "rtn chgs gst", "return chgs gst", "ret chgs gst", "rtn chrgs gst",
            "return chrgs gst", "ret chrgs gst"
        ]
    },
}

# Step 3: Loan keywords
loan_keywords = [
    "emi", "achd", "repay", "achd","instalment", "installment", "finance", "nbfc"
]

# Step 4: Bounce type identifier
def identify_bounce_type(narration):
    for bounce_type, data in bounce_keywords.items():
        if any(tk in narration for tk in data["type_keywords"]):
            if any(kw in narration for kw in data["keywords"]):
                return bounce_type
    return None

# Step 5: Loan keyword check
def has_loan_keyword(narration):
    return any(kw in narration for kw in loan_keywords)

# Step 6: Main bounce tagging logic
df['Bounce Type'] = None

for i, row in df.iterrows():
    narration = row['Narration']
    
    # Check if loan keyword exists and use logic to confirm
    if has_loan_keyword(narration) and row['Debits'] > 0 and row['Balance'] < 0:
        cheque_no = row['Cheque No']
        amount = row['Debits']
        date = row['XN Date']

        # Look for a credit reversal on same date with same cheque no
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
            continue  # Skip standard bounce tagging if loan logic applied

    # Otherwise, apply normal bounce keyword logic
    bounce_type = identify_bounce_type(narration)
    if bounce_type:
        # For NEFT, enforce both type and bounce keyword match, and ensure it's a credit without debit
        if bounce_type == "NEFT":
            if not any(kw in narration for kw in bounce_keywords["NEFT"]["keywords"]):
                continue
            if (row.get('Credits', 0) <= 0 and row.get('Credit', 0) <= 0) or (row.get('Debits', 0) > 0 or row.get('Debit', 0) > 0):
                continue
        df.at[i, 'Bounce Type'] = bounce_type

# Step 7: Save to file
df_output = df

output_file = input_file.replace(".xlsx", "_output.xlsx")
df_output.to_excel(output_file, index=False)

print("✅ Bounce type tagging completed. File saved as:", output_file)