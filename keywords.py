{
    "bounce_keywords": {
      "BOUNCE CHARGES": {
        "type_keywords": ["bounce charges", "cheque", "chq", "imps", "rtgs", "nach", "ach", "ecs"],
        "keywords": [
          "achdebitreturncharges", "ACH RTN CHRG", "rtn chgs", "return chgs", "ret chgs", "rtn chrgs",
          "return chrgs", "ret chrgs", "rtn charges", "return charges", "retcharges", "ret charges",
          "bounce charges", "debit return", "credit return", "rtnchg", "bounced charges", "rtn chrg", "rtn_chrg"
        ]
      },
      "BOUNCE CHARGES - GST": {
        "type_keywords": ["bounce charges-gst", "achdebitreturnchargesgst"],
        "keywords": [
          "rtn chgs gst", "return chgs gst", "ret chgs gst", "rtn chrgs gst",
          "return chrgs gst", "ret chrgs gst"
        ]
      },
      "CHEQUE": {
        "type_keywords": ["chq", "cheque", "returned", "inward return", "reject"],
        "technical_keywords": [
          "instrument undated", "signature differs", "payment stopped",
          "payment stopped by drawer", "exceeds arrangement"
        ],
        "non_technical_keywords": [
          "chq ret", "chq return", "funds insufficient", "i/w chq ret",
          "i/w chq rtn", "i/w chq return", "o/w rtn chq", "rtn(chq no.)", "chq issued bounce",
          "reject:(chq no.)", "ow chq rej", "brn-ow rtn", "brn-ow rtn clg",
          "reject:funds insufficient", "returned:funds insufficient"
        ]
      },
      "ACH": {
        "type_keywords": ["ach", "nach"],
        "keywords": ["nach return", "nach rtn", "rev:nach", "achdebit rtn"]
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
      }
    },
    "loan_keywords": [
      "emi", "achd", "repay", "instalment", "installment", "finance", "nbfc"
    ]
  }
