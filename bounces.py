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
    df['Xns_Date_str'] = df['Xns Date'].astype(str).str.replace(" 00:00:00", "", regex=False)

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
    df['Xns_Date_copy'] = pd.to_datetime(df['Xns Date'], dayFirst=True)

    return df

def identify_bounce_type(narration):
    narration = narration.lower()
    bounce_indicators = ["rtn", "return", "ret", "rtnchg", "bounce"]

    gst_data = bounce_keywords.get("BOUNCE CHARGES - GST", {})
    normal_data = bounce_keywords.get("BOUNCE CHARGES", {})

    if any(tk in narration for tk in map(str.lower, gst_data.get("type_keywords", []))) and \
       any(re.search(r'\b{}\b'.format(re.escape(kw.lower())), narration) for kw in gst_data.get("keywords", [])) and \
       any(bk in narration for bk in bounce_indicators):
        return "BOUNCE CHARGES - GST"

    if any(tk in narration for tk in map(str.lower, normal_data.get("type_keywords", []))) and \
       any(re.search(r'\b{}\b'.format(re.escape(kw.lower())), narration) for kw in normal_data.get("keywords", [])) and \
       any(bk in narration for bk in bounce_indicators):
        return "BOUNCE CHARGES"

    for bounce_type, data in bounce_keywords.items():
        if bounce_type in ["BOUNCE CHARGES", "BOUNCE CHARGES - GST"]:
            continue

        type_keywords = list(map(str.lower, data.get("type_keywords", [])))

        if bounce_type == "CHEQUE":
            tech_keywords = list(map(str.lower, data.get("technical_keywords", [])))
            non_tech_keywords = list(map(str.lower, data.get("non_technical_keywords", [])))
            if any(tk in narration for tk in type_keywords) and (
                any(re.search(r'\b{}\b'.format(re.escape(kw)), narration) for kw in tech_keywords) or
                any(re.search(r'\b{}\b'.format(re.escape(kw)), narration) for kw in non_tech_keywords)
            ):
                return bounce_type
        else:
            if any(tk in narration for tk in type_keywords) and \
               any(re.search(r'\b{}\b'.format(re.escape(kw.lower())), narration) for kw in data.get("keywords", [])):
                return bounce_type

    return None

def has_loan_keyword(narration):
    return any(re.search(r'\b{}\b'.format(re.escape(kw.lower())), narration) for kw in loan_keywords)

def tag_bounces(df):
    df['Bounce Type'] = None

    for i, row in df.iterrows():
        narration = row['Narration_copy']
        cheque_no = row['Cheque_No_copy']
        date = row['Xns_Date_copy']
        debit_amt = row['Debits_copy']

        if has_loan_keyword(narration) and pd.notna(debit_amt) and debit_amt > 0:
            match = df[
                (df['Xns_Date_copy'] == date) &
                (df['Credits_copy'].fillna(0).between(debit_amt * 0.95, debit_amt * 1.05)) &
                (df['Cheque_No_copy'] == cheque_no) &
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
                if not any(re.search(r'\b{}\b'.format(re.escape(kw.lower())), narration) for kw in bounce_keywords["NEFT"]["keywords"]):
                    continue
                if row['Credits_copy'] <= 0 or row['Debits_copy'] > 0:
                    continue
            if bounce_type == "CHEQUE":
                tech_keywords = bounce_keywords["CHEQUE"].get("technical_keywords", [])
                non_technical_keywords = bounce_keywords["CHEQUE"].get("non_technical_keywords", [])
                if any(re.search(r'\b{}\b'.format(re.escape(tk)), narration) for tk in tech_keywords):
                    df.at[i, 'Bounce Type'] = "Cheque Bounce - Technical"
                elif any(re.search(r'\b{}\b'.format(re.escape(nk)), narration) for nk in non_technical_keywords):
                    df.at[i, 'Bounce Type'] = "Cheque Bounce - Non-Technical"
            else:
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
    input_file = "testfile6.xlsx"
    output_file = input_file.replace(".xlsx", "_output.xlsx")
    main(input_file, output_file)
