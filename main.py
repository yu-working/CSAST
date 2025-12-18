import pandas as pd
import akasha  # noqa: E402
import dotenv
import os
import sys
import akasha.helper as ah

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

dotenv_path = os.path.join(BASE_DIR, ".env")
dotenv.load_dotenv(dotenv_path)

MODEL = os.getenv("MODEL")
data_dir = os.getenv("DATA_DIR", "data.xlsx")
def read_excel_sheets():
    dfs = pd.read_excel(data_dir, sheet_name=["E管家", "智慧插座", "安裝前中後問題"])

    return dfs

data = read_excel_sheets()

def format_data_for_ai(data_dict):
    full_text = ""
    for name, df in data_dict.items():
        full_text += f"\n--- {name} 知識庫 ---\n"
        full_text += df.to_csv(index=False) # CSV 格式通常對 AI 來說比 to_string 更省 token 且結構清晰
    return full_text

context_data = format_data_for_ai(data)

system_prompt = f"""
你是一名客服人員的助理，請注意以下事項：
1. 請先分析提問，是需要一般的問題還是想要從歷史紀錄找出相關資料，如果是一般的問題正常回答即可，如果是想從歷史紀錄找出相關資料，則查找資料{context_data}中有無類似或相關之資訊。
2. 若資料中有相關資訊，請整理並條列式顯示:歷史提問、歷史回答、裝置世代(如有)、類型、流程階段、關鍵字。如有多個相關資訊，請全部條列出來並區隔開來。
3. 若資料中無相關資訊，請分析客戶提問，並給予類型、流程階段(僅包含APP、安裝前、安裝中、安裝後)、關鍵字。
        """

ak = akasha.ask(
    model=MODEL,
    temperature=0.1,
    max_input_tokens=20000,
    max_output_tokens=20000
)
history = ""
while True:
    question = input("請問我有什麼可以協助的嗎: ")
    
    if question.lower() in ["exit", "quit","e","q"]:
        break
    if question.lower() in ["clear"]:
        history = ""
        print("對話歷史已清除。")
        continue
    final_prompt = system_prompt + f"\n# 客戶提問: {question}" + f"\n# 對話歷史: {history}"
    res = ak(
        prompt=final_prompt,
    )
    print("Final response:")
    print(res)
    history = history + f"\n提問: {question}\n回覆: {res}"
    ### compute the tokens of the text by the model ###
    tokens = ah.myTokenizer.compute_tokens(final_prompt, MODEL)
    print(tokens)


