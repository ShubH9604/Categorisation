import pandas as pd
import json, os
import re

# Load keywords
keywords_path = os.path.join(os.path.dirname(__file__), "keywords.json")
with open(keywords_path, "r") as f:
    data = json.load(f)
    bounce_keywords = data["bounce_keywords"]
    loan_keywords = data["loan_keywords"]

def preprocess(df):
    # Store original values to restore later
    df['Debits_original'] = df['Debits']
    df['Credits_original'] = df['Credits']
    df['Balance_original'] = df['Balance']
    df['Narration_original'] = df['Narration']
    df['Cheque_No_original'] = df['Cheque No']
    df['Xns_Date_str'] = df['Xns Date'].astype(str).str.replace(" 00:00:00", "")

    # Prepare working copies for logic
    df['Narration'] = df['Narration'].astype(str).str.lower()
    df['Narration_copy'] = df['Narration']
    df['Debits'] = pd.to_numeric(df['Debits'], errors='coerce')
    df['Debits_copy'] = df['Debits']
    df['Credits'] = pd.to_numeric(df['Credits'], errors='coerce')
    df['Credits_copy'] = df['Credits']
    df['Balance'] = pd.to_numeric(df['Balance'], errors='coerce')
    df['Balance_copy'] = df['Balance']
    df['Cheque_No_copy'] = df['Cheque No'].astype(str)
    df['Xns_Date_copy'] = pd.to_datetime(df['Xns Date'], errors='coerce')

    return df

def identify_bounce_type(narration):
    narration = narration.lower()

    # ✅ Handle "BOUNCE CHARGES - GST" first with specific rule
    gst_data = bounce_keywords.get("BOUNCE CHARGES", {})
    gst_type_keywords = list(map(str.lower, gst_data.get("type_keywords", [])))
    gst_keywords = list(map(str.lower, gst_data.get("keywords", [])))

    if "gst" in narration and \
       any(tk in narration for tk in gst_type_keywords) and \
       any(kw in narration for kw in gst_keywords):
        return "BOUNCE CHARGES - GST"

    # 🔁 Check all other bounce types except GST
    for bounce_type, data in bounce_keywords.items():
        if bounce_type == "BOUNCE CHARGES - GST":
            continue  # Already handled above

        type_keywords = list(map(str.lower, data.get("type_keywords", [])))
        keywords = list(map(str.lower, data.get("keywords", [])))

        if any(tk in narration for tk in type_keywords) and \
           any(kw in narration for kw in keywords):
            return bounce_type

    return None

def has_loan_keyword(narration):
    return any(kw.lower() in narration for kw in loan_keywords)

def tag_bounces(df):
    df['Bounce Type'] = None

    for i, row in df.iterrows():
        narration = str(row['Narration']).lower()
        cheque_no = str(row['Cheque_No_copy']).strip()
        date = row['Xns_Date_copy']
        debit_amt = row['Debits_copy']

        if pd.notna(debit_amt) and debit_amt > 0 and has_loan_keyword(narration):
            # Match by same Cheque No and near-same credit amount
            match = df[
                (df['Xns_Date_copy'] == date) &
                (df['Credits_copy'].fillna(0).between(debit_amt * 0.99, debit_amt * 1.01)) &
                (df['Cheque_No_copy'].astype(str).str.strip() == cheque_no) &
                (df.index != i)
            ]

            if not match.empty:
                j = match.index[0]
                df.at[i, 'Bounce Type'] = ""
                df.at[j, 'Bounce Type'] = "LOAN BOUNCE"
                continue

        bounce_type = identify_bounce_type(narration)
        if bounce_type == "NEFT":
            # NEFT bounce must have matching keywords AND amount only in Credits
            if any(kw.lower() in narration for kw in bounce_keywords["NEFT"]["keywords"]):
                if pd.isna(row['Credits_copy']) or row['Credits_copy'] < 0:
                    continue
                if not (pd.isna(row['Debits_copy']) or row['Debits_copy'] == 0):
                    continue
            else:
                continue
        if bounce_type:
            df.at[i, 'Bounce Type'] = bounce_type

    # ✅ Restore original values exactly as in input
    df['Narration'] = df['Narration_original']
    df['Debits'] = df['Debits_original']
    df['Credits'] = df['Credits_original']
    df['Balance'] = df['Balance_original']
    df['Cheque No'] = df['Cheque_No_original']
    df['Xns Date'] = df['Xns_Date_str']  # ✅ Preserved original string format

    # ✅ Drop all helper columns
    df.drop(columns=[
        'Narration_copy', 'Debits_copy', 'Credits_copy', 'Balance_copy',
        'Cheque_No_copy', 'Xns_Date_copy',
        'Narration_original', 'Debits_original', 'Credits_original',
        'Balance_original', 'Cheque_No_original', 'Xns_Date_str'
    ], inplace=True)

    return df

def main(input_path, output_path):
    # ✅ Force Excel to read Xns Date as raw string (visual format)
    df = pd.read_excel(input_path, converters={'Xns Date': str})
    df = preprocess(df)
    df = tag_bounces(df)
    df.to_excel(output_path, index=False)
    print(f"✅ Bounce tagging completed and saved as: {output_path}")

if __name__ == "__main__":
    input_file = "loan_bounce.xlsx"
    output_file = input_file.replace(".xlsx", "_output.xlsx")
    main(input_file, output_file)
