import pandas as pd
import requests
import json
import time
from typing import Dict, List, Optional
from tqdm import tqdm

class OpenRouterBounceDetector:
    def __init__(self, api_key: str):
        self.api_endpoint = "https://openrouter.ai/api/v1/chat/completions"
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def get_system_prompt(self) -> str:
        return """You are an expert financial analyst specialized in bank statement bounce detection. 
        You must analyze transaction data and identify bounce types based on specific patterns and keywords.
        Always return your response in JSON format with the exact structure requested."""
    
    def get_analysis_prompt(self) -> str:
        return """
        BOUNCE DETECTION RULES:

        BOUNCE TYPE KEYWORDS:
        1. ACH: type_keywords=["ach","nach"], bounce_keywords=["ach debit return","nach return","nach rtn","rev:nach","achdebit rtn"], but if narration contains any of ["ret", "return", "rtn", "rt"] AND any of ["chg", "chrgs", "charges", "chgs", "chrg"], then classify as "BOUNCE CHARGES" or "BOUNCE CHARGES - GST" (if "gst" is present), not ACH. Also in bounce keyword if only ach debit if found and not return or any bounce related complete keyword id not found then it is not ach bounce. if exclude keywords are present in narration for ach then dont consider it as ACH bounce.
        2. IMPS: type_keywords=["imps"] AND bounce_keywords=["imps return","rev:imps","reversal","ret","rtn","failed","rev-imps"] then only it is imps bounce but make sure it does not consider parts of the meaningful words (for eg: ret from retail or rt from transport or ret from creta, etc) and retur should not be considered as return.
        3. UPI: A transaction should be classified as a UPI bounce only if the narration contains “upi”, includes at least one valid bounce keyword (e.g., “return”, “ret”, “rtn”, “rev”, etc.), and the transaction is a credit (not a debit). Optionally, a matching debit of the same amount within ±2 days may support the classification. If either the bounce keyword is missing or the transaction is not a credit, it must not be classified as a UPI bounce under any circumstance.
        4. RTGS: type_keywords=["rtgs"], bounce_keywords=["rtgs return","rtgs failed","rtn:rtgs","rev"]
        5. CHEQUE: type_keywords=["chq","cheque","returned","inward return","reject"], bounce_keywords=["reject","returned","chq ret","chq return","funds insufficient","i/w chq ret","i/w chq rtn","i/w chq return","o/w rtn chq","rtn(chq no.)","chq issued bounce","reject:(chq no.)","ow chq rej","brn-ow rtn","brn-ow rtn clg","reject:funds insufficient","returned:funds insufficient","payment stopped by drawer","returned:","reject:","reject:.*","funds insufficient","instrument undated","signature differs","payment stopped","exceeds arrangement","chq return","inward return","chq ret","returned","reject"] and if only chq/cheque or any of it is present then it is not a cheque bounce.
        6. ECS: type_keywords=["ecs"], bounce_keywords=["ecs return","return ach","nach fail","inward return"] but if narration contains any of ["ret", "return", "rtn", "rt"] AND any of ["chg", "chrgs", "charges", "chgs", "chrg"], then classify as "BOUNCE CHARGES" or "BOUNCE CHARGES - GST" (if "gst" is present), not ECS
        7. NEFT: Identify NEFT bounce transactions only when the narration contains both a NEFT-specific keyword such as “neft” and at least one bounce-related keyword from the list: “account does not exist”, “rej”, “rtn”, “ret”, “return”, “return(account closed)”, “return(not a valid cpin)”, “returned”, “returnfor”, “rev”, “reversal”, “rtn(blocked account)”, “rtn(invalid account)”, or “rem”. Both conditions must be met simultaneously—if either the NEFT keyword or the bounce keyword is missing, the transaction must not be classified as a NEFT bounce. Additionally, do not classify based on partial or misleading matches, such as matching “rt” from unrelated words like “export”. All keyword matching should be based on full words or valid bounce indicators only.In NEFT if neft and any other bounce keywords for that is not there then consider it as None and not a bounce.
        8. BOUNCE CHARGES: If narration contains imps/rtgs/ach/neft/upi/chq/cheque AND any of ["ret", "return", "rtn", "rt"] AND any of ["chg", "chrgs", "charges", "chgs", "chrg"] then classify as "BOUNCE CHARGES", even if the narration also contains "ecs". This explicitly handles cases like "ecsrtnchg210619_sr618430837".
        9. BOUNCE CHARGES - GST: If narration contains any of ["ret", "return", "rtn", "rt"] AND any of ["chg", "chrgs", "charges", "chgs", "chrg"] AND "gst", then classify as "BOUNCE CHARGES - GST", even if the narration also contains "ecs". This explicitly handles cases like "ecsrtnchgs150921_sr776206431gst".
        Do not classify based on partial matches like 'rt' from words such as 'export' in any of the bounce types.
        Note: BOUNCE CHARGES and BOUNCE CHARGES - GST logic should take precedence over ECS if both patterns are matched.
        Note: For rtgs/imps/neft/upi keep ensure that it does have respective type name inside the narration along with the ret/return/rtn/rt or any other keywords to find bounce but make sure it does not consider parts of the meaningful words (for eg: ret from retail or rt from transport or ret from creta, etc)
        Note: If any of imps/neft/upi/ach/rtgs/cheque/ecs is only in the narration then it should not be considered respective bounces.
        LOAN KEYWORDS: ["emi","achd","repay","achd","instalment","installment","finance","nbfc"]
        Ensure bounce keywords like "ret", "rtn", "rev", etc., are not matched if they appear inside other words (e.g., "retail", "transport", "creta", "returnable", "trucks", etc.). Only consider them if they are standalone words or clearly separate tokens (e.g., separated by space, colon, dash).

        DETECTION LOGIC:
        1. PRIORITY 1 - LOAN BOUNCE: If narration contains loan keyword AND Debits > 0 AND Balance < 0, then look for credit reversal on same date with same cheque number where credit >= 90% of debit amount. If found, mark debit as "Loan Bounce".
        For Loan Bounce if achd is present in narration then consider it Loan Bounce.
        2. PRIORITY 2 - STANDARD BOUNCE: If loan logic doesn't apply, check if narration contains both type_keyword and bounce_keyword from same category.

        IMPORTANT: All narration matching must be done in lowercase. Return ONLY JSON format.
        """
    
    def call_llm(self, prompt: str, max_retries: int = 3) -> Optional[str]:
        for attempt in range(max_retries):
            try:
                payload = {
                    "model": "google/gemma-3-27b-it",
                    "messages": [
                        {"role": "system", "content": self.get_system_prompt()},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 2000
                }
                
                response = requests.post(
                    self.api_endpoint,
                    headers=self.headers,
                    json=payload,
                    timeout=60
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result.get("choices", [{}])[0].get("message", {}).get("content", "")
                else:
                    print(f"API Error {response.status_code}: {response.text}")
                    
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    
        return None
    
    def analyze_transaction_batch(self, transactions: List[Dict]) -> List[Dict]:
        transaction_data = []
        for i, txn in enumerate(transactions):
            transaction_data.append({
                "index": i,
                "narration": str(txn.get("Narration", "")).lower(),
                "debits": float(txn.get("Debits", 0)),
                "credits": float(txn.get("Credits", 0)),
                "balance": float(txn.get("Balance", 0)),
                "cheque_no": str(txn.get("Cheque No", "")),
                "date": str(txn.get("XN Date", ""))
            })
        
        prompt = f"""the logic i want in 
        {self.get_analysis_prompt()}
        
        TRANSACTION DATA:
        {json.dumps(transaction_data, indent=2)}
        
        TASK: Analyze each transaction and identify bounce types. For each transaction, return JSON with:
        {{
            "results": [
                {{
                    "index": 0,
                    "bounce_type": "ACH" or "IMPS" or "UPI" or "RTGS" or "CHEQUE" or "ECS" or "NEFT" or "BOUNCE CHARGES" or "BOUNCE CHARGES - GST" or "Loan Bounce" or null,
                    "reasoning": "explanation of why this bounce type was assigned"
                }}
            ]
        }}
        
        Apply loan bounce logic first (higher priority), then standard bounce detection.
        """
        
        response = self.call_llm(prompt)
        if not response:
            return [{"index": i, "bounce_type": None, "reasoning": "API call failed"} for i in range(len(transactions))]
        
        try:
            # Remove markdown-style code block markers if present
            if response.startswith("```json") or response.startswith("```"):
                response = response.strip("`").strip()
                if response.startswith("json"):
                    response = response[4:].strip()
            result = json.loads(response)
            return result.get("results", [])
        except json.JSONDecodeError:
            print(f"Failed to parse LLM response: {response}")
            return [{"index": i, "bounce_type": None, "reasoning": "JSON parse error"} for i in range(len(transactions))]
    
    def process_dataframe(self, df: pd.DataFrame, batch_size: int = 5) -> pd.DataFrame:
        print("Starting LLM-based bounce detection...")
        
        df['Bounce Type'] = None
        df['LLM Reasoning'] = None
        
        total_rows = len(df)
        processed = 0
        
        for start_idx in tqdm(range(0, total_rows, batch_size), desc="Processing transaction", unit="row"):
            end_idx = min(start_idx + batch_size, total_rows)
            batch_df = df.iloc[start_idx:end_idx]
            
            transactions = []
            for _, row in batch_df.iterrows():
                transactions.append({
                    "Narration": row.get("Narration", ""),
                    "Debits": row.get("Debits", 0),
                    "Credits": row.get("Credits", 0),
                    "Balance": row.get("Balance", 0),
                    "Cheque No": row.get("Cheque No", ""),
                    "XN Date": row.get("XN Date", "")
                })
            
            results = self.analyze_transaction_batch(transactions)
            
            for i, result in enumerate(results):
                actual_idx = start_idx + i
                if actual_idx < total_rows:
                    df.at[actual_idx, 'Bounce Type'] = result.get('bounce_type')
                    print(f"Row {actual_idx} classified as: {result.get('bounce_type')}")
                    df.at[actual_idx, 'LLM Reasoning'] = result.get('reasoning', '')
            
            processed += len(transactions)
            
            time.sleep(1)
        
        return df

def main():
    API_KEY = "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"
    
    detector = OpenRouterBounceDetector(API_KEY)
    
    input_file = "predicted_hdfc1yr.xlsx"
    print(f"Loading {input_file}...")
    
    try:
        df = pd.read_excel(input_file)
        print(f"Loaded {len(df)} transactions")
        
        df['Narration'] = df['Narration'].astype(str).str.lower()
        # df['Cheque No'] = df.get('Cheque No', '').astype(str).str.strip()
        df['XN Date'] = pd.to_datetime(df.get('XN Date', ''), errors='coerce')
        
        df_processed = detector.process_dataframe(df, batch_size=1)
        
        output_file = "predicted_hdfc1yr_output.xlsx"
        df_processed.to_excel(output_file, index=False)
        
        bounce_counts = df_processed['Bounce Type'].value_counts()
        print("\n✅ LLM Bounce Detection Complete!")
        print(f"📁 Output saved to: {output_file}")
        print(f"\n📊 Bounce Type Summary:")
        print(bounce_counts)
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    main()
