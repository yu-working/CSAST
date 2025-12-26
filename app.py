import streamlit as st
import pandas as pd
import akasha
import os
import akasha.helper as ah
import shutil
import json
import docx2txt
from pptx import Presentation
from pypdf import PdfReader


st.set_page_config(page_title="CSW")
# --- 1. 環境設定 ---
DATA_FOLDER = os.getenv("DATA_FOLDER", "data")
DEFAULT_DATA_FILE = os.getenv("DEFAULT_DATA_FILE", "default_data/FAQ_Default.xlsx")
os.makedirs(DATA_FOLDER, exist_ok=True)
DEFAULT_FILE = os.path.join(DATA_FOLDER, "FAQ_Default.xlsx")
DATA_STATE_PATH = "data_state.json"
ALLOWED_EXTS = {".xlsx", ".docx", ".txt", ".pdf", ".pptx"}
if not os.path.exists(DEFAULT_FILE):
    if not os.path.exists(DEFAULT_DATA_FILE):
        st.write(f"缺少預設文件{DEFAULT_DATA_FILE}，請建立資料夾 default_data 並將 FAQ_Default.xlsx 存入後重新整理頁面。")
        st.stop()
    else:
        shutil.copy(DEFAULT_DATA_FILE, DEFAULT_FILE)
ACTIVE_FILE = os.path.join(DATA_FOLDER, "FAQ_Active.xlsx")

MODEL_CONFIG = {
    "Google Gemini(2.5-flash)": {
        "env_var": "GEMINI_API_KEY",
        "model_name": "gemini:gemini-2.5-flash"
    },
    "OpenAI (GPT-4o)": {
        "env_var": "OPENAI_API_KEY",
        "model_name": "openai:gpt-4o"
    },
    "OpenAI (GPT-5)": {
        "env_var": "OPENAI_API_KEY",
        "model_name": "openai:gpt-5"
    },
    "Anthropic Claude": {
        "env_var": "ANTHROPIC_API_KEY",
        "model_name": "claude:claude-3-opus-20240229"
    }
}

# 初始化 Session State
if "history_list" not in st.session_state:
    st.session_state.history_list = []
if "messages" not in st.session_state:
    st.session_state.messages = []
# 透過 data_state.json 管理目前是否使用預設檔與檔名
def load_data_state():
    try:
        if os.path.exists(DATA_STATE_PATH):
            with open(DATA_STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {"mode": "default", "file_name": ["FAQ_Default.xlsx"]}

def save_data_state(mode: str, file_names):
    try:
        # file_names should be a list
        files = file_names if isinstance(file_names, list) else [file_names]
        with open(DATA_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump({"mode": mode, "file_name": files}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

state_json = load_data_state()
if "include_default" not in st.session_state:
    st.session_state.include_default = (state_json.get("mode") == "default")
if "use_data_name" not in st.session_state:
    files = state_json.get("file_name") or state_json.get("file") or []
    st.session_state.use_data_name = files if files else []
if "current_data" not in st.session_state:
    st.session_state.current_data = None
if "file_processed" not in st.session_state:
    st.session_state.file_processed = False

# 假設圖片路徑
# USER_AVATAR = "static/user_icon.png"
# BOT_AVATAR = "https://your-domain.com/bot-logo.png"
# 用法
# with st.chat_message("user", avatar=USER_AVATAR):

# --- 2. 工具函數 ---
@st.cache_data    
def read_excel_sheets(file_path):
    if not os.path.exists(file_path):
        return None
    target_sheets = ["E管家", "智慧插座", "安裝前中後問題"]
    try:
        return pd.read_excel(file_path, sheet_name=target_sheets)
    except Exception as e:
        st.error(f"讀取 Excel 失敗: {e}")
        return None

@st.cache_data
def extract_text_from_docx(path: str) -> str:
    try:
        return docx2txt.process(path) or ""
    except Exception as e:
        st.error(f"讀取 DOCX 失敗: {e}")
        return ""

@st.cache_data
def extract_text_from_txt(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        st.error(f"讀取 TXT 失敗: {e}")
        return ""

@st.cache_data
def extract_text_from_pdf(path: str) -> str:
    try:
        reader = PdfReader(path)
        pages_text = []
        for p in reader.pages:
            try:
                pages_text.append(p.extract_text() or "")
            except Exception:
                pages_text.append("")
        return "\n".join(pages_text)
    except Exception as e:
        st.error(f"讀取 PDF 失敗: {e}")
        return ""

@st.cache_data
def extract_text_from_pptx(path: str) -> str:
    try:
        prs = Presentation(path)
        texts = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "has_text_frame") and shape.has_text_frame:
                    texts.append("\n".join([p.text for p in shape.text_frame.paragraphs]))
        return "\n".join(texts)
    except Exception as e:
        st.error(f"讀取 PPTX 失敗: {e}")
        return ""

def df_from_text(text: str, source_label: str) -> pd.DataFrame:
    return pd.DataFrame({"來源": [source_label], "內容": [text]})

# 支援多檔案合併：
# - xlsx：依既有三個工作表名稱合併
# - 其他(docx/txt/pdf/pptx)：以檔名為鍵，內容形成單列 DataFrame
def read_excel_list(file_paths):
    if not file_paths:
        return None
    combined = {}
    for p in file_paths:
        ext = os.path.splitext(p)[1].lower()
        base = os.path.basename(p)
        if ext == ".xlsx":
            data = read_excel_sheets(p)
            if not data:
                continue
            for sheet_name, df in data.items():
                if sheet_name in combined:
                    try:
                        combined[sheet_name] = pd.concat([combined[sheet_name], df], ignore_index=True)
                    except Exception as e:
                        st.error(f"合併工作表 {sheet_name} 失敗: {e}")
                else:
                    combined[sheet_name] = df
        elif ext == ".docx":
            text = extract_text_from_docx(p)
            df = df_from_text(text, base)
            key = base
            combined[key] = pd.concat([combined[key], df], ignore_index=True) if key in combined else df
        elif ext == ".txt":
            text = extract_text_from_txt(p)
            df = df_from_text(text, base)
            key = base
            combined[key] = pd.concat([combined[key], df], ignore_index=True) if key in combined else df
        elif ext == ".pdf":
            text = extract_text_from_pdf(p)
            df = df_from_text(text, base)
            key = base
            combined[key] = pd.concat([combined[key], df], ignore_index=True) if key in combined else df
        elif ext == ".pptx":
            text = extract_text_from_pptx(p)
            df = df_from_text(text, base)
            key = base
            combined[key] = pd.concat([combined[key], df], ignore_index=True) if key in combined else df
        else:
            st.warning(f"不支援的檔案類型: {base}")
    return combined if combined else None

def format_data_for_ai(data_dict):
    """將 DataFrame 字典轉為 AI 易讀的字串"""
    if not data_dict: return "目前無參考資料。"
    full_text = ""
    for name, df in data_dict.items():
        full_text += f"\n--- {name} 知識庫 ---\n"
        full_text += df.to_csv(index=False)
    return full_text

# 定義一個內部函數來把 list 轉回字串，方便計算 Token
def get_history_string(h_list):
    return "".join([f"\n提問: {item['q']}\n回覆: {item['a']}" for item in h_list])

# --- 3. 初始資料載入邏輯 ---
# 只有在 current_data 是 None 的時候才去執行讀取，並依照 toggle 狀態決定來源
if st.session_state.current_data is None:
    # 依照 checkbox 選擇決定載入資料
    files = st.session_state.use_data_name if isinstance(st.session_state.use_data_name, list) else []
    paths = [os.path.join(DATA_FOLDER, f) for f in files if os.path.exists(os.path.join(DATA_FOLDER, f))]
    if st.session_state.include_default:
        paths = [DEFAULT_FILE] + paths
    if paths:
        st.session_state.current_data = read_excel_list(paths)
        save_data_state("default" if (st.session_state.include_default and not files) else "active", files)
    else:
        # 無選擇時使用預設
        st.session_state.include_default = True
        st.session_state.current_data = read_excel_sheets(DEFAULT_FILE)
        save_data_state("default", ["FAQ_Default.xlsx"])

# --- 4. Streamlit 側邊欄介面設定 ---
with st.sidebar:
    # 1.下拉式選單選擇模型
    selected_model_display = st.selectbox("選擇模型來源",options=list(MODEL_CONFIG.keys()))
    # 取得對應的配置
    config = MODEL_CONFIG[selected_model_display]

    # 2.加入API_KEY輸入框
    user_api_key = st.text_input(
        "輸入您的 API KEY", 
        type="password",
        help="輸入有效API_KEY後即可進行對話"
    )
    api_valid = False
    if user_api_key:
        os.environ[config["env_var"]] = user_api_key
        # 發送一次測試請求以確認 Key 有效性
        try:
            test_ak = akasha.ask(
                model=config["model_name"],
                temperature=0.1,
            )
            test = test_ak(prompt="return hi")
            st.success("API Key 已就緒！")
            api_valid = True 
        except Exception as e:
            st.error(f"API Key 無效，請檢查後重新輸入。")
            api_valid = False
    else:
        st.warning("請先輸入 API Key")
    st.divider()

    # 3.資料上傳
    uploaded_files = st.file_uploader(
        "上傳更新資料 (xlsx/docx/txt/pdf/pptx)", 
        type=["xlsx", "docx", "txt", "pdf", "pptx"],
        accept_multiple_files=True,
        )
    if uploaded_files and not st.session_state.get("file_processed", False):
        saved_names = []
        for uf in uploaded_files:
            target_path = os.path.join(DATA_FOLDER, uf.name)
            with open(target_path, "wb") as f:
                f.write(uf.getbuffer())
            saved_names.append(uf.name)
        # 更新目前的使用清單：保留原有，再加入新檔（去重）
        existing = st.session_state.use_data_name if isinstance(st.session_state.use_data_name, list) else []
        new_list = list(dict.fromkeys(existing + saved_names))
        st.cache_data.clear()
        paths = ([DEFAULT_FILE] if st.session_state.include_default else []) + [os.path.join(DATA_FOLDER, f) for f in new_list if os.path.exists(os.path.join(DATA_FOLDER, f))]
        st.session_state.current_data = read_excel_list(paths)
        st.session_state.file_processed = True
        st.session_state.use_data_name = new_list if new_list else ["DEFAULT"]
        st.session_state.include_default = st.session_state.include_default if new_list else True
        save_data_state("active" if new_list else "default", new_list if new_list else ["FAQ_Default.xlsx"])
        st.success(f"✅ 已加入 {len(saved_names)} 個檔案")
        st.rerun()

    # 使用預設資料庫選項（checkbox）
    st.session_state.include_default = st.checkbox("使用預設資料庫", value=st.session_state.include_default, help="是否包含預設資料庫")

    # 列出可用檔案並提供勾選
    def list_available_files():
        try:
            files = []
            for fn in os.listdir(DATA_FOLDER):
                path = os.path.join(DATA_FOLDER, fn)
                if os.path.isfile(path) and os.path.splitext(fn)[1].lower() in ALLOWED_EXTS and fn != os.path.basename(DEFAULT_FILE):
                    files.append(fn)
            return sorted(files)
        except Exception:
            return []

    available_files = list_available_files()
    selected = []
    for fn in available_files:
        checked = st.checkbox(fn, value=(fn in (st.session_state.use_data_name or [])), key=f"chk_{fn}")
        if checked:
            selected.append(fn)

    # 若選擇與現狀不同，更新資料與狀態檔
    if set(selected) != set(st.session_state.use_data_name or [] ) or st.session_state.current_data is None:
        st.session_state.use_data_name = selected
        st.cache_data.clear()
        load_paths = ([DEFAULT_FILE] if st.session_state.include_default else []) + [os.path.join(DATA_FOLDER, f) for f in selected]
        if load_paths:
            st.session_state.current_data = read_excel_list(load_paths)
            save_data_state("default" if (st.session_state.include_default and not selected) else "active", selected)
        else:
            # 無選擇時載入預設
            st.session_state.include_default = True
            st.session_state.current_data = read_excel_sheets(DEFAULT_FILE)
            save_data_state("default", ["FAQ_Default.xlsx"])

    # 顯示目前檔案資訊
    try:
        names_list = (st.session_state.use_data_name or [])
        if st.session_state.include_default:
            names_list = ["DEFAULT"] + names_list
        names_str = ", ".join(names_list)
    except Exception:
        names_str = "DEFAULT" if st.session_state.include_default else ""
    st.caption(f"目前生效檔案：{names_str}")

    # 使用者手動點擊「X」移除檔案時的重置
    if not uploaded_files and st.session_state.file_processed:
        # 清空當次選取的上傳狀態
        st.session_state.file_processed = False
    st.divider()
    
    if st.button("清除對話歷史"):
        st.session_state.messages = []
        st.session_state.history_list = []
        st.rerun()

# --- 5. 生成 System Prompt ---
# 確保 context_data 永遠對應到目前選用的資料 (current_data)
context_text = format_data_for_ai(st.session_state.current_data)
system_prompt = f"""
<角色>你是一名客服人員的專屬助理</角色>
<任務>
    1. 請先分析提問，是需要一般的問題還是想要從歷史紀錄找出相關資料，如果是一般的問題正常回答即可，如果是想從歷史紀錄找出相關資料，則查找資料中有無類似或相關之資訊。
    2. 若資料中有相關資訊，請依據歷史回答生成建議的回覆，並在下面條列式整理參考來源。如有多個相關資訊，則依照相關度高到低條列並區隔開來。
    3. 若資料中無相關資訊，請分析客戶提問，並給予類型、流程階段(僅包含APP、安裝前、安裝中、安裝後)、關鍵字。
</任務>
<限制>
    1. 生成建議的回覆時，需使用``` ```的程式碼區塊包裹
    2. 生成建議的回覆時，需盡可能簡單易懂
    3. 生成建議的回覆時，請只使用中文文字及數字，不得使用粗體、斜體、底線等格式
    4. 列出參考的歷史來源時，格式應符合:
        ```
        ### 參考資料1
        ...
        ---
        ### 參考資料2
        ...
        ```
</限制>
<資料>{context_text}</資料>
"""

# --- 6. 主介面顯示 ---
st.title("Customer Service Wingman")
st.caption("Version: v1.1.0")

# 顯示現有的對話紀錄
for message in st.session_state.messages:
    avatar_icon = "🦥" if message["role"] == "user" else "🐑"
    with st.chat_message(message["role"], avatar=avatar_icon):
        st.markdown(message["content"])

# --- 7. 對話邏輯 ---
if prompt := st.chat_input("請問我有什麼可以協助的嗎?"):

    # 檢查驗證
    if not api_valid:
        st.error("驗證失敗：請檢查後在左側選單重新輸入 API Key")
        st.stop()
    if not st.session_state.current_data:
        st.error("缺少資料庫資料")
        st.stop()

    # 顯示使用者訊息
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🦥"):
        st.markdown(prompt)

    # 呼叫 Akasha 回覆
    with st.chat_message("assistant", avatar="🐑"):
        with st.spinner("思考中..."):
            try:
                ak = akasha.ask(
                    model=config["model_name"],
                    temperature=0.1,
                    max_input_tokens=20000,
                    max_output_tokens=20000
                )
                history_text = get_history_string(st.session_state.history_list)
                final_prompt = (
                    system_prompt + 
                    f"\n# 提問: {prompt}" + 
                    f"\n# 對話歷史: {history_text}"
                )
                response = ak(prompt=final_prompt)
                st.markdown(response)

                # --- Token 管理與修剪 --- 
                st.session_state.history_list.append({"q": prompt, "a": response})
                
                # 更新並計算 Token
                current_h_text = get_history_string(st.session_state.history_list)
                total_content = system_prompt + prompt + current_h_text
                
                # 迴圈修剪
                while ah.myTokenizer.compute_tokens(total_content, config["model_name"]) > 8000 and len(st.session_state.history_list) > 1:
                    st.session_state.history_list.pop(0)
                    current_h_text = get_history_string(st.session_state.history_list)
                    total_content = system_prompt + prompt + current_h_text

                # 存回 messages 用於顯示
                st.session_state.messages.append({"role": "assistant", "content": response})
            except Exception as e:
                st.error(f"模型呼叫失敗: {str(e)}")