import pandas as pd
import json, os
keywords_path = os.path.join(os.path.dirname(__file__), "keywords.json")
with open(keywords_path, "r") as f:
    data = json.load(f)
    bounce_keywords = data["bounce_keywords"]
    loan_keywords = data["loan_keywords"]

def preprocess(df):
    # Clean and convert column data
    df['Narration'] = df['Narration'].astype(str).str.lower()
    df['Debits'] = pd.to_numeric(df['Debits'], errors='coerce')
    df['Credits'] = pd.to_numeric(df['Credits'], errors='coerce')
    df['Balance'] = pd.to_numeric(df['Balance'], errors='coerce')
    df['Cheque No'] = df['Cheque No'].astype(str).str.strip()
    df['Xns Date'] = pd.to_datetime(df['Xns Date'], errors='coerce')
    return df

def identify_bounce_type(narration):
    narration = narration.lower()
    bounce_indicators = ["rtn", "return", "ret", "rtnchg", "bounce"]

    gst_data = bounce_keywords.get("BOUNCE CHARGES - GST", {})
    normal_data = bounce_keywords.get("BOUNCE CHARGES", {})

    if any(tk in narration for tk in map(str.lower, gst_data.get("type_keywords", []))) and \
       any(kw in narration for kw in map(str.lower, gst_data.get("keywords", []))) and \
       any(bounce_kw in narration for bounce_kw in bounce_indicators):
        return "BOUNCE CHARGES - GST"

    if any(tk in narration for tk in map(str.lower, normal_data.get("type_keywords", []))) and \
       any(kw in narration for kw in map(str.lower, normal_data.get("keywords", []))) and \
       any(bounce_kw in narration for bounce_kw in bounce_indicators):
        return "BOUNCE CHARGES"

    for bounce_type, data in bounce_keywords.items():
        if bounce_type in ["BOUNCE CHARGES", "BOUNCE CHARGES - GST"]:
            continue

        type_keywords = list(map(str.lower, data.get("type_keywords", [])))

        if bounce_type == "CHEQUE":
            tech_keywords = list(map(str.lower, data.get("technical_keywords", [])))
            non_tech_keywords = list(map(str.lower, data.get("non_technical_keywords", [])))
            if any(tk in narration for tk in type_keywords) and (
                any(kw in narration for kw in tech_keywords) or
                any(kw in narration for kw in non_tech_keywords)
            ):
                return bounce_type
        else:
            if any(tk in narration for tk in type_keywords) and \
               any(kw in narration for kw in map(str.lower, data.get("keywords", []))):
                return bounce_type

    return None

def has_loan_keyword(narration):
    return any(kw in narration for kw in loan_keywords)

def tag_bounces(df):
    df['Bounce Type'] = None
    original_narration = df['Narration'].copy()

    for i, row in df.iterrows():
        narration = row['Narration']
        cheque_no = row['Cheque No']
        date = row['Xns Date']
        debit_amt = row['Debits']

        if has_loan_keyword(narration) and pd.notna(debit_amt) and debit_amt > 0:
            match = df[
                (df['Xns Date'] == date) &
                (df['Credits'].fillna(0).between(debit_amt * 0.95, debit_amt * 1.05)) &
                (df['Cheque No'] == cheque_no) &
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
                if row['Credits'] <= 0 or row['Debits'] > 0:
                    continue
            if bounce_type == "CHEQUE":
                technical_keywords = bounce_keywords["CHEQUE"].get("technical_keywords", [])
                non_technical_keywords = bounce_keywords["CHEQUE"].get("non_technical_keywords", [])
                if any(tk in narration for tk in technical_keywords):
                    df.at[i, 'Bounce Type'] = "Cheque Bounce - Technical"
                elif any(nk in narration for nk in non_technical_keywords):
                    df.at[i, 'Bounce Type'] = "Cheque Bounce - Non-Technical"
            else:
                df.at[i, 'Bounce Type'] = bounce_type

    df['Narration'] = original_narration
    return df

def main(input_path, output_path):
    df = pd.read_excel(input_path)
    df = preprocess(df)
    df = tag_bounces(df)
    df.to_excel(output_path, index=False)
    print(f"✅ Bounce tagging completed and saved as: {output_path}")

if __name__ == "__main__":
    input_file = "hdfc14.xlsx"
    output_file = input_file.replace(".xlsx", "_output.xlsx")
    main(input_file, output_file)
