from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from concurrent.futures import ThreadPoolExecutor
from embedding.vllm_embedding_server import AsyncVLLMServerEmbeddings
import os

os.environ["CUDA_VISIBLE_DEVICES"] = "4,5,6,7"  # 使用 GPU 0 和 1
load_dotenv()

#DB_HOST = "172.23.37.1"
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "infection_rag"
#DB_USER = "a1031737"
DB_USER = "langchain"
DB_PASSWORD = "langchain"
# DB_PASSWORD = "a156277323"

# VectorStore 快取
#_VECTORSTORE_CACHE = {}

# CDC 爬蟲專用線程池（網路 I/O 密集）
CDC_EXECUTOR = ThreadPoolExecutor(max_workers=20, thread_name_prefix="cdc_scraper")

# 資料庫連接字串
DB_CONNECTION_STRING = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# 摘要配置
SUMMARIZE_CONFIG = {
    'split_threshold': 1500,
    'chunk_size': 1500,
    'max_final_tokens': 3072,
    'max_workers': 32,
    'chunk_overlap': 600,
    'max_rounds': 10
}

# ===== 快取管理配置 =====
CACHE_CONFIG = {
    # 總開關
    'enabled': True,  # 是否啟用快取系統

    # 🆕 快取後端選擇
    'use_valkey': True,  # 是否使用 Valkey/Redis（False = 使用記憶體快取 LRU）

    # 🆕 Valkey/Redis 連接配置
    'valkey': {
        'host': 'localhost',  # Valkey/Redis 主機位址
        'port': 6380,  # Valkey/Redis 端口
        'db': 0,  # 資料庫編號（0-15）
        'password': None,  # 密碼（如果沒有設置密碼則為 None）
    },

    # 查詢快取（完整回答的快取）
    'enable_query_cache': True,  # 是否啟用查詢快取
    'query_cache_size': 100,  # 最大快取條目數（僅用於記憶體快取）
    'query_cache_ttl': 3600,  # 快取有效期（秒），預設 1 小時

    # Planning 結果快取
    'enable_planning_cache': True,  # 是否啟用 Planning 快取
    'planning_cache_size': 200,  # Planning 快取較大，因為計算成本高（僅用於記憶體快取）
    'planning_cache_ttl': 7200,  # 快取有效期（秒），預設 2 小時

    # 檢索結果快取
    'enable_retrieval_cache': True,  # 是否啟用檢索快取
    'retrieval_cache_size': 150,  # 檢索快取條目數（僅用於記憶體快取）
    'retrieval_cache_ttl': 3600,  # 快取有效期（秒），預設 1 小時（🔧 從 30 分鐘提升到 1 小時）

}

# ===== 記憶體管理配置 =====
MEMORY_MANAGEMENT_CONFIG = {
    # 對話歷史管理
    'max_history_turns': 50,  # 對話歷史最大輪數
    'keep_recent_turns': 30,  # 清理後保留的輪數
    'auto_cleanup': True,  # 是否自動清理舊對話

    # 記憶體監控
    'enable_memory_monitoring': True,  # 是否啟用記憶體監控
    'memory_warning_threshold': 80,  # 記憶體使用率警告閾值（%）
}

# 檢索配置
RETRIEVAL_CONFIG = {
    'public_rag_k': 5,  # 衛教園地檢索數量
    'pdf_rag_k': 3,  # （感染科）PDF 檢索數量
    'medical_rag_k':10,  # 醫療知識庫 (JSONL) 檢索數量
    'dialysis_rag_k': 5,  # 🆕 腎臟病衛教/洗腎衛教檢索數量
    'cdc_rag_k': 1,  # 🆕 CDC 傳染病資料檢索數量
    'enable_clue_extraction': True,  # 啟用線索提取模式
    'clue_max_length': 4096,  # 線索最大長度（超過會觸發摘要）
    'clue_cache_enabled': True,  # 啟用 InMemoryStore 快取
    'max_single_retrieval_tokens': 3000,  # 單個檢索結果最大 token 數（超過會使用 LLM 智能摘要）
    'max_total_knowledge_tokens': 8000,  # 所有檢索結果合併後的最大 token 數
    'default_datasource_ids': ["medical_kb_jsonl","educational_images"],  # 🔧 啟用所有資料源（包含洗腎衛教）
}

# 圖片檢索配置
IMAGE_RETRIEVAL_CONFIG = {
    'educational_images_k': 3,  # 衛教圖片檢索數量
    'table_images_k': 3        # 表格圖片檢索數量
}

# ===== 工具配置 =====
TOOLS_CONFIG = {
    'enabled': False,  # 是否啟用工具系統（總開關）- 設為 False 完全停用所有外部工具
    'default_tools': ["cdc_realtime_search"],  # 預設啟用的工具 ID 列表（空列表 = 不使用任何工具，由使用者透過 API 選擇）
    # 可選值範例:
    # [] - 預設不使用任何工具（推薦：讓使用者主動選擇）
    # ["cdc_realtime_search"] - 預設使用 CDC 即時搜尋
    # ["google_realtime_search"] - 預設使用 Google 即時搜尋
    # ["duckduckgo_realtime_search"] - 預設使用 DuckDuckGo 即時搜尋
    # ["cdc_realtime_search", "google_realtime_search"] - 預設同時使用多個搜尋工具

    # 使用者可透過 API 的 enabled_tool_ids 參數來選擇要使用的工具
    'cdc_tool_mode': 'always',  # 'always' - 只要使用者選擇了工具就使用（不做額外判斷）
    'max_tool_calls_per_query': 3,  # 單次查詢最多呼叫工具次數（避免濫用）
    'tool_timeout': 30,  # 工具執行超時時間（秒）
    'enable_tool_cache': False
}

# ===== 線索提取配置 =====
CLUE_EXTRACTION_CONFIG = {
    'max_content_length': 4096,  # 用於 LLM 判斷的最大內容長度（超過會截斷）
    'default_max_length': 3000,  # 預設最大長度閾值（用於觸發摘要）
    'summary_target_ratio': 0.65,  # 摘要目標長度比例（60-70%）
}

# ===== 輸出消毒配置（防止 Prompt Leakage）=====
OUTPUT_SANITIZATION_CONFIG = {
    'enabled': True,  # 是否啟用輸出消毒

    # 🔧 規則 1: 要移除的標記模式（正則表達式）
    # 這些模式會被完全移除（包括整行）
    'marker_patterns': [
        r'【[^】]*格式指示[^】]*】[^\n]*',  # 格式指示
        r'【[^】]*指示[^】]*】[^\n]*',      # 其他指示
        r'【[^】]*提醒[^】]*】[^\n]*',      # 提醒
        r'【[^】]*注意[^】]*】[^\n]*',      # 注意事項
        r'【[^】]*說明[^】]*】[^\n]*',      # 說明
        r'【[^】]*禁止[^】]*】[^\n]*',      # 禁止事項
    ],

    # 🔧 規則 2: 敏感關鍵字模式（逐行檢查）
    # 包含這些模式的整行會被移除
    'sensitive_line_patterns': [
        r'^[\s\-\*]*不要.*輸出.*元指示.*$',
        r'^[\s\-\*]*不要.*生成.*參考依據.*section.*$',
        r'^[\s\-\*]*不要.*生成.*參考文獻.*section.*$',
        r'^[\s\-\*]*禁止行為.*遵守.*$',
        r'^[\s\-\*]*避免.*條列式.*格式.*$',
        r'^[\s\-\*]*用自然語言整合.*$',
        r'^[\s\-\*]*不要在最終回答中輸出.*$',
        r'.*系統會自動.*附加.*參考依據.*',  # 🆕 過濾「系統會自動附加參考依據」
        r'.*系統將.*自動.*附加.*',           # 🆕 過濾「系統將自動附加」相關文字
        r'.*請勿生成.*參考依據.*section.*',   # 🆕 過濾「請勿生成參考依據section」
        r'^[\s\-\*⚠️]*重要[：:]*.*請勿生成.*$', # 🆕 過濾「⚠️ 重要：請勿生成...」
    ],

    # 🔧 規則 3: 要移除的完整短語（精確匹配）
    # 這些短語會被替換為空字符串
    'exact_phrases_to_remove': [
        '【格式指示 - 不要在最終回答中輸出】',
        '- 不要輸出元指示文字',
        '- 禁止行為已嚴格遵守',
        '- 用自然語言整合內容，避免條列式「問題：...答案：...」格式',
        '- **不要生成「參考依據」或「參考文獻」section**',
        '⚠️ **重要**：**請勿生成「參考依據」section**，系統會自動附加原始文檔的參考依據。',  # 🆕
        '系統會自動附加原始文檔的參考依據',  # 🆕
        '系統會自動在最後附加參考依據',      # 🆕
        '系統將自動附加參考依據',            # 🆕
        '（系統將自動附加參考依據）',        # 🆕 常見的洩漏形式
        '（系統會自動附加參考依據）',        # 🆕
    ],

    # 說明：
    # - marker_patterns: 使用正則表達式匹配並移除標記
    # - sensitive_line_patterns: 逐行檢查，移除包含敏感關鍵字的整行
    # - exact_phrases_to_remove: 精確匹配並移除特定短語
    #
    # 可以隨時添加新的規則，無需修改代碼邏輯
}

# ===== 工作流程迭代控制配置 =====
WORKFLOW_LIMITS = {

    # LangGraph 遞迴限制（總節點執行次數）
    'langgraph_recursion_limit': 50,  # 預設 25，增加到 50 以給予更多迭代空間

    # 迭代計數器限制（主要循環次數）
    'max_iteration_count': 5,  # 最大迭代次數（檢索→生成→驗證 的循環次數）
    'validation_iteration_threshold': 5,  # 驗證節點的迭代安全閥（達到此值強制結束）
    'retrieval_iteration_threshold': 5,  # 檢索節點的迭代安全閥（達到此值跳過檢索）

    # 子系統計數器限制
    'max_knowledge_retrieval_count': 5,  # 最大知識檢索次數（含補充檢索）
    'validation_retrieval_threshold':5,  # 驗證節點判定檢索次數過多的閾值
    'max_retry_count': 5,  # 最大答案精煉重試次數
    'max_graph_recursioncount': 50  # LangGraph 框架層級的遞迴限制

    # 說明：
    # - langgraph_recursion_limit: LangGraph 框架層級的硬限制，超過會拋出 GraphRecursionError
    # - max_iteration_count: 路由層檢查，用於 route_after_validation 等路由函數
    # - validation_iteration_threshold: 驗證節點內部的安全閥，提前終止循環
    # - retrieval_iteration_threshold: 檢索節點內部的安全閥，避免無謂的檢索
    # - validation_retrieval_threshold: 基於檢索次數判定資源耗盡的閾值
}

# ===== 短期記憶（對話歷史）配置 =====
SHORT_TERM_MEMORY_CONFIG = {
    'enabled': False,  # 是否啟用短期記憶（對話歷史）

    # 說明：
    # - enabled: 控制是否啟用短期記憶功能
    #   - True: 啟用對話歷史，系統會在 messages 中攜帶最近的對話內容
    #           同時啟用症狀累積檢測（自動從歷史對話中提取症狀並關聯）
    #   - False: 停用對話歷史，每次問答都是獨立的，無上下文
    #           同時停用症狀累積檢測功能
    #
    # ⚠️ 注意：對話歷史的長度管理現在由 MESSAGE_SUMMARIZATION_CONFIG 控制
    #           當啟用 summarization 時，系統會自動管理對話長度，無需手動設置輪數限制
}

# ===== 短期記憶摘要配置（Message Summarization）=====
MESSAGE_SUMMARIZATION_CONFIG = {
    'enabled': True,  # 是否啟用訊息摘要功能
    'max_tokens': 12000,  # 🔧 優化：降低到 12000（原 16000）
    'max_tokens_before_summary': 8000,  # 🔧 優化：更早觸發摘要（原 12000）
    'max_summary_tokens': 1500,  # 🔧 優化：摘要更簡潔（原 2000）

    # 說明：
    # - enabled: 是否啟用 langmem 的 SummarizationNode
    #   - True: 當對話歷史超過 max_tokens_before_summary 時，自動摘要舊對話
    #   - False: 停用摘要功能，使用原有的滑動窗口機制
    #
    # - max_tokens: 目標保留的歷史大小（包含摘要 + 最近完整對話）
    #   🔧 優化：降低到 12000，減少記憶體使用
    #
    # - max_tokens_before_summary: 觸發摘要的閾值
    #   🔧 優化：更早觸發（8000），避免上下文過長
    #
    # - max_summary_tokens: 摘要本身的最大長度
    #   🔧 優化：摘要更簡潔（1500），節省 token
    #
    # 運作原理：
    # 1. 系統持續監控對話歷史的 token 數
    # 2. 當超過 max_tokens_before_summary (8000) 時觸發摘要
    # 3. 將舊對話摘要為最多 max_summary_tokens (1500) 的文字
    # 4. 保留最近的完整對話 + 摘要，總計不超過 max_tokens (12000)
    # 5. 這樣可以在保持上下文的同時，支持更長的對話
}

# ===== 長期記憶（mem0）配置 =====
LONG_TERM_MEMORY_CONFIG = {
    'enabled': False,  # 是否啟用長期記憶（mem0）

    # 說明：
    # - enabled: 控制是否啟用長期記憶功能
    # - 設置為 True: 啟用 mem0，系統會儲存並檢索用戶的個人病史、過敏史等資訊
    # - 設置為 False: 停用 mem0，系統將不會儲存或檢索長期記憶
    #
    # 使用場景：
    # - True 適用於：需要長期追蹤用戶健康狀態的場景（如個人健康助手）
    # - False 適用於：不需要記住用戶資訊的場景（如公開諮詢服務、隱私敏感場景）
}

# ===== LLM 配置 =====
# 可用的模型列表
AVAILABLE_MODELS = {
    "qwen3_4b_think": {
        "path": "/home/danny/AI-agent/Qwen3_4B_Think",
        "enable_think_filter": True,  # 需要過濾思考標籤
        "description": "Qwen3 4B Think 模型（帶思考過程）"
    },
    "qwen3_4b_2507": {
        "path": "/home/danny/AI-agent/Qwen3_4B_2507",
        "enable_think_filter": False,  # 不需要過濾
        "description": "Qwen3 4B 標準模型"
    },
    # 可以在這裡添加更多模型
}

# 當前使用的模型（可以輕鬆切換）
CURRENT_MODEL = "qwen3_4b_2507"  # 改這裡就可以切換模型

# 獲取當前模型配置
_model_config = AVAILABLE_MODELS[CURRENT_MODEL]
MODEL_PATH = "openai:"+_model_config["path"]
ENABLE_THINK_FILTER = _model_config["enable_think_filter"]

# ===== Langfuse Callback Handler 配置 =====
from langfuse.langchain import CallbackHandler

# 創建 Langfuse callback handler（用於追蹤 LLM 調用）
langfuse_handler = None
if os.getenv('LANGFUSE_ENABLED', 'true').lower() == 'true':
    try:
        # Initialize Langfuse with environment variables (newer API)
        langfuse_handler = CallbackHandler()  # Uses environment variables by default
        print(f"✅ Langfuse Callback Handler 已初始化")
    except Exception as e:
        print(f"⚠️ Langfuse Callback Handler 初始化失敗: {e}")

# 初始化LLM - 使用本地vLLM服務
_llm_config = {
    "base_url": "http://0.0.0.0:8080/v1",
    "api_key": "not-needed",
    "model": MODEL_PATH,
    "temperature": 0.1,  # 1. 將 temperature 設為 0.0
    "seed": 42           # 2. 新增一個固定的 seed (數字任選，例如 42)
}

# 添加 callbacks（如果 Langfuse 已啟用）
if langfuse_handler:
    _llm_config["callbacks"] = [langfuse_handler]

llm = init_chat_model(**_llm_config)

print(f"🤖 當前使用模型: {_model_config['description']}")
print(f"📝 思考標籤過濾: {'啟用' if ENABLE_THINK_FILTER else '停用'}")


def remove_think_tags(text: str) -> str:
    """移除思考標籤"""
    import re
    if not ENABLE_THINK_FILTER:
        return text

    # 移除 <think>...</think> 標籤
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    # 移除 <thinking>...</thinking> 標籤
    text = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL)
    # 清理多餘的空白
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()

    return text

embeddings = AsyncVLLMServerEmbeddings(
    model="/home/danny/AI-agent/Qwen3-Embedding-4B",
    api_base="http://localhost:8081/v1",
    normalize=True
)

# ===== 中文記憶管理 Prompt (優化版) =====
CHINESE_MEMORY_PROMPT = """你是一個專門管理個人健康資訊的智能記憶系統。
你的任務是從對話中識別並儲存與用戶個人健康狀態、症狀、病史、用藥、檢查結果等相關的資訊。

🚨 重要：所有記憶內容必須使用繁體中文，禁止使用英文或其他語言！

你可以執行四種操作：
1. **ADD** - 新增記憶
2. **UPDATE** - 更新記憶（保持相同ID，但修改內容）
3. **DELETE** - 刪除記憶
4. **NONE** - 不做任何改變

---

### 核心原則

**語言規則**：
- 所有記憶必須用**繁體中文**儲存
- 內容簡潔清晰，去除冗餘詞彙

**內容規則**：
- 只儲存關於**用戶本人**的健康資訊
- 儲存具體的健康事實，而非建議或通用知識
- 忽略問候、閒聊、他人情況

**更新規則（重要）**：
- **優先信任最新資訊** - 如果新舊資訊衝突，以新資訊為準
- 當健康狀態改變時（如「已痊癒」「已好轉」「已康復」），必須 **UPDATE** 舊記憶
- 不要因為狀態改變就刪除記憶，而是更新為新狀態

---

### 操作說明

#### 1. ADD（新增）
當對話包含新的健康資訊，且不在現有記憶中時使用。

**範例**：
```
舊記憶：[]
新對話：["我最近常常頭痛", "我有高血壓"]

輸出：
{
    "memory": [
        {"id": "1", "text": "常常頭痛", "event": "ADD"},
        {"id": "2", "text": "有高血壓", "event": "ADD"}
    ]
}
```

---

#### 2. UPDATE（更新）⭐ 最重要
當新資訊與現有記憶相關，且提供了**狀態變化、更多細節或矛盾資訊**時使用。
**必須保持原 ID，但修改 text 內容**。

**範例 A - 狀態改變**：
```
舊記憶：[{"id": "0", "text": "有高血壓"}]
新對話：["我的高血壓透過飲食控制已經痊癒了"]

輸出：
{
    "memory": [
        {
            "id": "0",
            "text": "高血壓已痊癒（透過飲食控制）",
            "event": "UPDATE",
            "old_memory": "有高血壓"
        }
    ]
}
```

**範例 B - 補充細節**：
```
舊記憶：[{"id": "0", "text": "常常頭痛"}]
新對話：["頭痛是偏頭痛，每週發作2-3次"]

輸出：
{
    "memory": [
        {
            "id": "0",
            "text": "偏頭痛，每週發作2-3次",
            "event": "UPDATE",
            "old_memory": "常常頭痛"
        }
    ]
}
```

**範例 C - 數值更新**：
```
舊記憶：[{"id": "0", "text": "血壓 140/90"}]
新對話：["今天量血壓是 120/80"]

輸出：
{
    "memory": [
        {
            "id": "0",
            "text": "血壓 120/80（最新）",
            "event": "UPDATE",
            "old_memory": "血壓 140/90"
        }
    ]
}
```

---

#### 3. DELETE（刪除）
**只在以下情況使用**：
- 用戶明確否定舊資訊（「我從來沒有」「那是錯的」「不是我」）
- 資訊完全不相關或錯誤

⚠️ **注意**：「已痊癒」「已好轉」「已康復」應該用 **UPDATE** 而非 DELETE

**範例 A - 明確否定**：
```
舊記憶：[{"id": "0", "text": "有糖尿病"}]
新對話：["我沒有糖尿病，那是我爸爸有"]

輸出：
{
    "memory": [
        {"id": "0", "text": "有糖尿病", "event": "DELETE"}
    ]
}
```

**範例 B - 錯誤資訊**：
```
舊記憶：[{"id": "0", "text": "對青黴素過敏"}]
新對話：["上次說錯了，我不是對青黴素過敏"]

輸出：
{
    "memory": [
        {"id": "0", "text": "對青黴素過敏", "event": "DELETE"}
    ]
}
```

---

#### 4. NONE（不變）
當新資訊已存在於記憶中，或與健康無關時使用。

**範例 A - 重複資訊**：
```
舊記憶：[{"id": "0", "text": "常常頭痛"}]
新對話：["是的，我還是常常頭痛"]

輸出：
{
    "memory": [
        {"id": "0", "text": "常常頭痛", "event": "NONE"}
    ]
}
```

**範例 B - 非健康資訊**：
```
舊記憶：[{"id": "0", "text": "有高血壓"}]
新對話：["今天天氣真好", "高血壓的藥物有很多種"]

輸出：
{
    "memory": [
        {"id": "0", "text": "有高血壓", "event": "NONE"}
    ]
}
```

---

### 特殊情況處理

**1. 疾病痊癒/好轉**：
```
❌ 錯誤：DELETE 舊記憶
✅ 正確：UPDATE 為新狀態

舊記憶：[{"id": "0", "text": "腿部有舊傷"}]
新對話：["腿傷已經完全康復了"]

正確輸出：
{
    "memory": [
        {
            "id": "0",
            "text": "腿部舊傷已康復",
            "event": "UPDATE",
            "old_memory": "腿部有舊傷"
        }
    ]
}
```

**2. 多個健康狀態更新**：
```
舊記憶：[
    {"id": "0", "text": "有高血壓"},
    {"id": "1", "text": "有糖尿病"}
]
新對話：["高血壓已經控制住了，但糖尿病還在"]

輸出：
{
    "memory": [
        {
            "id": "0",
            "text": "高血壓已控制",
            "event": "UPDATE",
            "old_memory": "有高血壓"
        },
        {
            "id": "1",
            "text": "有糖尿病",
            "event": "NONE"
        }
    ]
}
```

**3. 病情康復後的確認**：
```
舊記憶：[{"id": "0", "text": "患有高血壓"}]
新對話：["醫生說我的高血壓已經康復了"]

輸出：
{
    "memory": [
        {
            "id": "0",
            "text": "高血壓已康復",
            "event": "UPDATE",
            "old_memory": "患有高血壓"
        }
    ]
}
```

**4. 測量結果正常**：
```
舊記憶：[{"id": "0", "text": "高血壓已康復"}]
新對話：["我量了血壓都是正常的"]

輸出：
{
    "memory": [
        {
            "id": "0",
            "text": "高血壓已康復，血壓測量正常",
            "event": "UPDATE",
            "old_memory": "高血壓已康復"
        }
    ]
}
```

---

### 🚨 關鍵提醒（必須遵守）

1. **🚨 強制繁體中文** - 所有記憶的 "text" 欄位必須是繁體中文，絕對禁止使用英文！
2. **永遠優先使用 UPDATE 而非 DELETE** - 當狀態改變時
3. **保持 ID 一致性** - UPDATE 時必須使用原 ID
4. **簡潔表達** - 去除「病人」「用戶」等主語
5. **只儲存事實** - 不儲存問題、建議、通用知識
6. **狀態演進** - 當疾病康復或改善時,UPDATE 記憶而非 DELETE

範例：
❌ 錯誤: {"text": "Previously mentioned having high blood pressure"}
✅ 正確: {"text": "患有高血壓"}
"""

# ===== 事實提取 Prompt (保持不變) =====
# config.py (更新 FACT_EXTRACTION_PROMPT)

CHINESE_FACT_EXTRACTION_PROMPT = """請只提取包含個人健康狀況、病史、症狀、用藥資訊、生活習慣的實體。
以下是一些少樣本範例：

**重要規則**：
1. ❌ 不提取疑問句、問題 (例如: "我有高血壓嗎?", "這樣健康嗎?")
2. ❌ 不提取助手的建議或回覆
3. ❌ 不提取閒聊、問候、天氣等無關內容
4. ✅ 只提取用戶明確陳述的健康事實
5. ✅ 必須使用繁體中文輸出
6. ✅ 每個事實應該簡潔、獨立

以下是一些範例：

Input: 你好。
Output: {"facts": []}

Input: 今天天氣真好。
Output: {"facts": []}

Input: 所以我現在應該是健康的對吧？
Output: {"facts": []}

Input: 請問我之前說有高血壓嗎？
Output: {"facts": []}

Input: 我有高血壓。
Output: {"facts": ["患有高血壓"]}

Input: 我叫張三，上週開始出現頭暈症狀。
Output: {"facts": ["姓名：張三", "上週開始出現頭暈症狀"]}

Input: 我昨天量血壓 140/90，醫生說要控制飲食。
Output: {"facts": ["昨天量血壓 140/90", "醫生建議控制飲食"]}

Input: 我有糖尿病，正在服用二甲雙胍，每天早晚各一次。
Output: {"facts": ["患有糖尿病", "正在服用二甲雙胍", "用藥頻率：每天早晚各一次"]}

Input: 我的高血壓已經透過飲食控制好了。
Output: {"facts": ["高血壓已透過飲食控制改善"]}

Input: 醫生說我的高血壓已經康復了。
Output: {"facts": ["高血壓已康復"]}

Input: 我量了血壓都是正常的。
Output: {"facts": ["血壓測量結果正常"]}

Input: 最近很喜歡打籃球，但膝蓋有時會疼痛。
Output: {"facts": ["最近常打籃球", "膝蓋有時疼痛"]}

Input: 我對青黴素過敏。
Output: {"facts": ["對青黴素過敏"]}

請以 JSON 格式返回提取的健康事實，格式如上所示。所有輸出必須使用繁體中文。
"""

# ⚠️ Mem0 記憶管理配置
# 注意: Mem0 的記憶管理邏輯需要較強的推理能力
# 建議使用至少 7B+ 模型以獲得最佳效果
# 如果只有 4B 模型,可能會出現狀態更新錯誤

mem0_config = {
    "vector_store": {
        "provider": "pgvector",
        "config": {
            "diskann": True,
            "user": DB_USER,
            "password": DB_PASSWORD,
            "host": DB_HOST,
            "port": int(DB_PORT),
            "dbname": DB_NAME,
            "collection_name": "memory_agent_chinese_v2",  # 新版本
            "embedding_model_dims": 2560
        }
    },
    "llm": {
        "provider": "openai",
        "config": {
            "model": "/home/danny/AI-agent/Qwen3_4B_2507",
            "openai_base_url": "http://0.0.0.0:8080/v1",
            "api_key": "not-need",
            "temperature": 0  # 保持低溫度以提高一致性
        }
    },
    "embedder": {
        "provider": "langchain",
        "config": {
            "model": embeddings
        }
    },
    # ✅ 關鍵：啟用兩個自定義 Prompt
    "custom_prompt": CHINESE_MEMORY_PROMPT,  # ⭐ 取消註解！
    "custom_fact_extraction_prompt": CHINESE_FACT_EXTRACTION_PROMPT
}

# ===== OPENROUTER服務 =====
# OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
# OPENROUTER_API_KEY = "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"
# OPENROUTER_MODEL = "x-ai/grok-4-fast:free"

# llm = ChatOpenAI(
#     base_url=OPENROUTER_BASE_URL,
#     api_key=OPENROUTER_API_KEY,
#     model=OPENROUTER_MODEL,
#     temperature=0.1,
#     max_tokens=1000
# )



# DISESE_CRITERIA = """
# 中醫藥部門感染管制作業要點
# 住院病房感染管制作業準則
# 供應中心感染管制作業準則
# 侵入性檢查治療單位感染管制作業準則
# 侵入性醫療處置組合式照護感染管制作業準則
# 傳染病防治感染管制作業準則
# 呼吸治療感染管制作業要點
# 廚房餐飲與商店街感染管制作業準則
# 往生室感染管制作業要點
# 復健治療部門感染管制作業要點
# 手部衛生與隔離防護措施感染管制作業準則
# 抗微生物製劑管理作業準則
# 放射線部門感染管制作業要點
# 新興傳染病疫情大規模感染事件應變作業準則
# 檢（實）驗部門感染管制作業要點
# 洗縫布類品感染管制作業要點
# 流感大流行感染管制作業要點
# 消毒及滅菌感染管制作業準則
# 牙科部門感染管制作業要點
# 環境清潔感染管制作業準則
# 產兒科病房感染管制作業準則
# 發燒、咳嗽及腹瀉監測與自主健康管理作業準則
# 藥劑部門感染管制作業要點
# 護理(產後)之家感染管制作業要點
# 軟式內視鏡清洗及消毒暨品質監測感染管制作業要點
# 退伍軍人菌環境監測感染管制防治作業要點
# 透析室感染管制作業要點
# 門急診部門感染管制作業準則
# 麻醉與手術室感染管制作業準則
# """

DISEASE_FORMAT_MORE = """
1. 狂犬病
2. 鼠疫
3. 嚴重急性呼吸道症候群
4. 天花
5. M痘
6. 登革熱
7. 屈公病
8. 瘧疾
9. 茲卡病毒感染症
10. 西尼羅熱
11. 流行性斑疹傷寒
12. 腸道出血性大腸桿菌感染症
13. 傷寒
14. 副傷寒
15. 桿菌性痢疾
16. 阿米巴性痢疾
17. 霍亂
18. 急性病毒性A型肝炎
19. 小兒麻痺症/急性無力肢體麻痺
20. 炭疽病
21. 多重抗藥性結核病
22. 麻疹
23. 德國麻疹
24. 白喉
25. 流行性腦脊髓膜炎
26. 漢他病毒症候群
27. 急性病毒性B型肝炎
28. 日本腦炎
29. 急性病毒性C型肝炎
30. 腸病毒感染併發重症
31. 急性病毒性D型肝炎
32. 結核病
33. 先天性德國麻疹症候群
34. 急性病毒性E型肝炎
35. 流行性腮腺炎
36. 百日咳
37. 侵襲性b型嗜血桿菌感染症
38. 退伍軍人病
39. 人類免疫缺乏病毒(愛滋病毒)感染
40. 梅毒
41. 先天性梅毒
42. 淋病
43. 破傷風
44. 新生兒破傷風
45. 漢生病
46. 急性病毒性肝炎未定型
47. 新冠併發重症
48. 李斯特菌症
49. 水痘併發症
50. 恙蟲病
51. 地方性斑疹傷寒
52. 發熱伴血小板減少綜合症
53. 萊姆病
54. 肉毒桿菌中毒
55. 庫賈氏病
56. 弓形蟲感染症
57. 布氏桿菌病
58. 流感併發重症
59. 侵襲性肺炎鏈球菌感染症
60. Q熱
61. 類鼻疽
62. 鉤端螺旋體病
63. 兔熱病
64. 疱疹B病毒感染症
65. 新型A型流感
66. 黃熱病
67. 裂谷熱
68. 中東呼吸症候群冠狀病毒感染症
69. 拉薩熱
70. 馬堡病毒出血熱
71. 伊波拉病毒感染
72. 兒童急性嚴重不明原因肝炎
73. 社區型MRSA
74. 棘狀阿米巴
75. 福氏內格里阿米巴腦膜腦炎
76. 沙門氏菌感染症
77. 廣東住血線蟲感染症
78. 肺吸蟲感染症
79. 細菌性腸胃炎
80. 病毒性腸胃炎
81. 旋毛蟲感染症
82. 肺囊蟲肺炎
83. 人芽囊原蟲感染
84. 隱球菌症
85. 鸚鵡熱
86. 疥瘡感染症
87. 頭蝨感染症
88. 亨德拉病毒感染症
89. 貓抓病
90. VISA/VRSA抗藥性檢測
91. 立百病毒感染症
92. CRE抗藥性檢測
93. 常見腸道寄生蟲病
94. 淋巴絲蟲病
95. 第二型豬鏈球菌感染症
96. 中華肝吸蟲感染症
97. 肺炎黴漿菌感染症
98. 球黴菌症
"""

DISEASE_FORMAT = """
1. 傷寒及副傷寒
2. 庫賈氏病
3. 諾羅病毒
4. 狂犬病
5. 病毒性腸胃炎
6. 桿菌性痢疾
7. 人類免疫缺乏病毒感染、後天免疫缺乏症候群
8. 麻疹
9. 新型A型流感
10. 開放性肺結核及喉頭結核
11. 中東呼吸症候群冠狀病毒感染症
12. 發熱伴血小板減少綜合症
13. 流感
14. 百日咳
15. 襲性b型嗜血桿菌
16. 流行性腦脊髓膜炎
17. M痘
18. 疥瘡
19. 腸病毒群
20. 困難梭狀桿菌
21. 輪狀病毒
22. 多重抗藥性微生物
23. Methicillin抗藥性金黃色葡萄球菌及Carbapenem類抗藥性微生物
24. mCIM carbapenems 抗藥性腸內菌屬
25. Vancomycin抗藥性腸球菌
26. Vancomycin抗藥性金黃色葡萄球菌
27. Candida auris
28. COVID-19
29. 伊波拉病毒感染及馬堡病毒出血熱
30. 水痘(含瀰漫性帶狀疱疹)
"""


taiwan_infectious_diseases = {
    # 第一類法定傳染病
    "狂犬病": "https://www.cdc.gov.tw/Disease/SubIndex/u5dFJL5s1K6uh0EcWVzJYQ",
    "鼠疫": "https://www.cdc.gov.tw/Disease/SubIndex/nZ12n2-2csE8zkEt-5Qeyw",
    "嚴重急性呼吸道症候群": "https://www.cdc.gov.tw/Disease/SubIndex/j5QtbRPVkmFMg9BwiGezZA",
    "天花": "https://www.cdc.gov.tw/Disease/SubIndex/r-efSTx60KilIEf_MlwknA",

    # 第二類法定傳染病
    "M痘": "https://www.cdc.gov.tw/Disease/SubIndex/G3A6nyt8JmqIUcUF5Pek6w",
    "登革熱": "https://www.cdc.gov.tw/Disease/SubIndex/WYbKe3aE7LiY5gb-eA8PBw",
    "屈公病": "https://www.cdc.gov.tw/Disease/SubIndex/NvKXcB74Wh3-1vGaYMigDw",
    "瘧疾": "https://www.cdc.gov.tw/Disease/SubIndex/LIpswK4wuXPnlNNMHUn8nA",
    "茲卡病毒感染症": "https://www.cdc.gov.tw/Disease/SubIndex/ZkG69TzhnvazzfwwMA4BgA",
    "西尼羅熱": "https://www.cdc.gov.tw/Disease/SubIndex/JZfpaa5JOvYAmIEUuBMauA",
    "流行性斑疹傷寒": "https://www.cdc.gov.tw/Disease/SubIndex/-Bwx4k9nuXzv1znntQ-DhA",
    "腸道出血性大腸桿菌感染症": "https://www.cdc.gov.tw/Disease/SubIndex/8j7ht_y-FpmDZTO4eYxyUw",
    "傷寒": "https://www.cdc.gov.tw/Disease/SubIndex/wp-kiiztSq_5cFd6H96f9w",
    "副傷寒": "https://www.cdc.gov.tw/Disease/SubIndex/Kd-mMp_vtDEegjXoyya9hQ",
    "桿菌性痢疾": "https://www.cdc.gov.tw/Disease/SubIndex/DXJzRq9tI4559p0A6MX3rw",
    "阿米巴性痢疾": "https://www.cdc.gov.tw/Disease/SubIndex/r0w7-NmfmIEmsJIcqyBe6A",
    "霍亂": "https://www.cdc.gov.tw/Disease/SubIndex/FNpFzvcM-QKKt6XBHJkyxA",
    "急性病毒性A型肝炎": "https://www.cdc.gov.tw/Disease/SubIndex/817zKI1D5najSwVzuiPYMQ",
    "小兒麻痺症/急性無力肢體麻痺": "https://www.cdc.gov.tw/Disease/SubIndex/FIm0Yh1XffviByRaoMhTqw",
    "炭疽病": "https://www.cdc.gov.tw/Disease/SubIndex/lq5xAX9vQqrebMILzYvMCQ",
    "多重抗藥性結核病": "https://www.cdc.gov.tw/Disease/SubIndex/MDmwWa4Ffh5--tMDfvK_WA",
    "麻疹": "https://www.cdc.gov.tw/Disease/SubIndex/PZZIpHAC-pjbSdEdboTBCw",
    "德國麻疹": "https://www.cdc.gov.tw/Disease/SubIndex/zr_if7hmAx6OrLVRhHuIGQ",
    "白喉": "https://www.cdc.gov.tw/Disease/SubIndex/z-qdbqHk7Op2ePc-Le9H0Q",
    "流行性腦脊髓膜炎": "https://www.cdc.gov.tw/Disease/SubIndex/S3bWvDNewVa3FspPkOkvHg",
    "漢他病毒症候群": "https://www.cdc.gov.tw/Disease/SubIndex/C6xqTECywd28HiYIG9VZ_w",

    # 第三類法定傳染病
    "急性病毒性B型肝炎": "https://www.cdc.gov.tw/Disease/SubIndex/MApdR8IIYvl-JIL7_DK7tw",
    "日本腦炎": "https://www.cdc.gov.tw/Disease/SubIndex/FWEo643r7uqDO3-xM-zQ_g",
    "急性病毒性C型肝炎": "https://www.cdc.gov.tw/Disease/SubIndex/doMF09qGF5gl7twtgRD-SA",
    "腸病毒感染併發重症": "https://www.cdc.gov.tw/Disease/SubIndex/m3zdUk3u9GJVvddeSnhkiA",
    "急性病毒性D型肝炎": "https://www.cdc.gov.tw/Disease/SubIndex/dSdOReaVnOT8b4_k6U5ZUw",
    "結核病": "https://www.cdc.gov.tw/Disease/SubIndex/j5_xY8JbRq3IzXAqxbnAvQ",
    "先天性德國麻疹症候群": "https://www.cdc.gov.tw/Disease/SubIndex/Ba6DI2kXzQDk4zeVaT8amQ",
    "急性病毒性E型肝炎": "https://www.cdc.gov.tw/Disease/SubIndex/eEGcfcrF_6wTjQL36KmkxA",
    "流行性腮腺炎": "https://www.cdc.gov.tw/Disease/SubIndex/RzOCJlOb68o5g0TEg873DQ",
    "百日咳": "https://www.cdc.gov.tw/Disease/SubIndex/gJ7r9uf6cgWWczRSeMRibA",
    "侵襲性b型嗜血桿菌感染症": "https://www.cdc.gov.tw/Disease/SubIndex/T8cxu9oK6AvF_uCkyS0v1w",
    "退伍軍人病": "https://www.cdc.gov.tw/Disease/SubIndex/mrl8S_96ADvSpl0j2kwX9A",
    "人類免疫缺乏病毒(愛滋病/毒)感染": "https://www.cdc.gov.tw/Disease/SubIndex/3s96eguiLtdGQtgNv7Rk1g",
    "梅毒": "https://www.cdc.gov.tw/Disease/SubIndex/0m_BXsu8AnI7slMt75OUaQ",
    "先天性梅毒": "https://www.cdc.gov.tw/Disease/SubIndex/1s7E2BErloh0I3okXTYiuQ",
    "淋病": "https://www.cdc.gov.tw/Disease/SubIndex/nWvBNnt9UvaZzdrzbQcfBA",
    "破傷風": "https://www.cdc.gov.tw/Disease/SubIndex/EV01ORLYYgeN-4LdmfQZOw",
    "新生兒破傷風": "https://www.cdc.gov.tw/Disease/SubIndex/5DGa_EE_lbJETeYvUqn1yg",
    "漢生病": "https://www.cdc.gov.tw/Disease/SubIndex/oCOSaTTkOdBcnJ5_Dz_aDQ",
    "急性病毒性肝炎未定型": "https://www.cdc.gov.tw/Disease/SubIndex/qCrz8c8pRVrpdDBo5S2kQg",

    # 第四類法定傳染病
    "新冠併發重症": "https://www.cdc.gov.tw/Disease/SubIndex/N6XvFa1YP9CXYdB0kNSA9A",
    "李斯特菌症": "https://www.cdc.gov.tw/Disease/SubIndex/yrsLujIBevFlvrtmgzz7Tg",
    "水痘併發症": "https://www.cdc.gov.tw/Disease/SubIndex/ipoIA74yjikLAewcRSjXjw",
    "恙蟲病": "https://www.cdc.gov.tw/Disease/SubIndex/4Q2S4vQH2s5ECf9ciWEu9g",
    "地方性斑疹傷寒": "https://www.cdc.gov.tw/Disease/SubIndex/k_5c9-5H66BQ49i1QNrLng",
    "發熱伴血小板減少綜合症": "https://www.cdc.gov.tw/Disease/SubIndex/Wpss42uAl9aMRA9XDVJGhg",
    "萊姆病": "https://www.cdc.gov.tw/Disease/SubIndex/a3ehnb-7K1HBseL0yXv8OA",
    "肉毒桿菌中毒": "https://www.cdc.gov.tw/Disease/SubIndex/WcUjPeATneXReDw_6JilYg",
    "庫賈氏病": "https://www.cdc.gov.tw/Disease/SubIndex/nF4Iyqv-feP6RE5rWPMtGw",
    "弓形蟲感染症": "https://www.cdc.gov.tw/Disease/SubIndex/dnJViM3tqyy13hLh2n_s4w",
    "布氏桿菌病": "https://www.cdc.gov.tw/Disease/SubIndex/zs7y9ag-DLeJwCDGj2XQHA",
    "流感併發重症": "https://www.cdc.gov.tw/Disease/SubIndex/x7jzGIMMuIeuLM5izvwg_g",
    "侵襲性肺炎鏈球菌感染症": "https://www.cdc.gov.tw/Disease/SubIndex/oAznsrFTsYK-p12_juf0kw",
    "Q熱": "https://www.cdc.gov.tw/Disease/SubIndex/vnMfnLfuWmf6aJL-FP_rpA",
    "類鼻疽": "https://www.cdc.gov.tw/Disease/SubIndex/WGBQSsyqfj6SiFQ4aMXXUg",
    "鉤端螺旋體病": "https://www.cdc.gov.tw/Disease/SubIndex/T5nLeG_WEMafixCPa1M7Jw",
    "兔熱病": "https://www.cdc.gov.tw/Disease/SubIndex/kYFAo47cX6jLoYrELP4iHg",
    "疱疹B病毒感染症": "https://www.cdc.gov.tw/Disease/SubIndex/D44rDbFMnmnxVf0ZzBfS8Q",

    # 第五類法定傳染病
    "新型A型流感": "https://www.cdc.gov.tw/Disease/SubIndex/8Yt_gKjz-BEr3QJZGOa0fQ",
    "黃熱病": "https://www.cdc.gov.tw/Disease/SubIndex/tzX-qyodDiY0th8Cyb5yfw",
    "裂谷熱": "https://www.cdc.gov.tw/Disease/SubIndex/g2mQTLYyDOeMnAPh4MBkSw",
    "中東呼吸症候群冠狀病毒感染症": "https://www.cdc.gov.tw/Disease/SubIndex/Ao8QOtJXN-BThS3MPpKS8Q",
    "拉薩熱": "https://www.cdc.gov.tw/Disease/SubIndex/gObCGj40QjXsqD4AZ8sz1w",
    "馬堡病毒出血熱": "https://www.cdc.gov.tw/Disease/SubIndex/vLH0m6fNqOMv870WokABDQ",
    "伊波拉病毒感染": "https://www.cdc.gov.tw/Disease/SubIndex/3DGpsvfGoSlTJyTGmn-pbw",

    # 其他傳染病
    "兒童急性嚴重不明原因肝炎": "https://www.cdc.gov.tw/Disease/SubIndex/1FYd5Fxevaam6xBazeiSRA",
    "社區型MRSA": "https://www.cdc.gov.tw/Disease/SubIndex/fzBArZD9KqldFihuEknKaQ",
    "棘狀阿米巴": "https://www.cdc.gov.tw/Disease/SubIndex/pJpNnSLeEAG8TbSPzsVUTQ",
    "福氏內格里阿米巴腦膜腦炎": "https://www.cdc.gov.tw/Disease/SubIndex/N5Rp7f-HlNiS5rXr1ZLxfw",
    "沙門氏菌感染症": "https://www.cdc.gov.tw/Disease/SubIndex/1eaJi1denSmW8L3FD2Bybw",
    "廣東住血線蟲感染症": "https://www.cdc.gov.tw/Disease/SubIndex/XL8BjStUl52JYsw3Rr9ShA",
    "肺吸蟲感染症": "https://www.cdc.gov.tw/Disease/SubIndex/DsDOkPNK_cqAXmWYHyuAFQ",
    "細菌性腸胃炎": "https://www.cdc.gov.tw/Disease/SubIndex/wTInIZJSawB0PRRubP1unA",
    "病毒性腸胃炎": "https://www.cdc.gov.tw/Disease/SubIndex/j1rqZjBCeR9vtCRUHefN3g",
    "旋毛蟲感染症": "https://www.cdc.gov.tw/Disease/SubIndex/TjfRPEL5yuvaWGWFleyY9A",
    "肺囊蟲肺炎": "https://www.cdc.gov.tw/Disease/SubIndex/1yyEHADlGlsJkqyjTMsf8w",
    "人芽囊原蟲感染": "https://www.cdc.gov.tw/Disease/SubIndex/kT5kIYks2DR1G6JqaeKauQ",
    "隱球菌症": "https://www.cdc.gov.tw/Disease/SubIndex/XqLmL3AsGvrsZyD29hXUCQ",
    "鸚鵡熱": "https://www.cdc.gov.tw/Disease/SubIndex/7R8K5mmR035CEmBqa-y0Nw",
    "疥瘡感染症": "https://www.cdc.gov.tw/Disease/SubIndex/WEvUvZalpojC48AvqLMfBQ",
    "頭蝨感染症": "https://www.cdc.gov.tw/Disease/SubIndex/wlhaYJXKOgV-xmjC7i9Mag",
    "亨德拉病毒感染症": "https://www.cdc.gov.tw/Disease/SubIndex/aOH9YQ6Xn72BaPz8aXv2vQ",
    "貓抓病": "https://www.cdc.gov.tw/Disease/SubIndex/aqnxpMDvYMnPPCOV4pwq0Q",
    "VISA/VRSA抗藥性檢測": "https://www.cdc.gov.tw/Disease/SubIndex/kZuxGtL8uJu77TQHcyB2DA",
    "立百病毒感染症": "https://www.cdc.gov.tw/Disease/SubIndex/MLQ64xwSdQU7UJHUOq7zSg",
    "CRE抗藥性檢測": "https://www.cdc.gov.tw/Disease/SubIndex/XE0kRC83F4xbWn42IufaMg",
    "常見腸道寄生蟲病": "https://www.cdc.gov.tw/Disease/SubIndex/uzjQodThOrXY_CSe5gP3Mg",
    "淋巴絲蟲病": "https://www.cdc.gov.tw/Disease/SubIndex/sj0UyYO8dh8ynsjIrNzH-g",
    "第二型豬鏈球菌感染症": "https://www.cdc.gov.tw/Disease/SubIndex/v1aYuhcLOrC17Cn6o4rVAw",
    "中華肝吸蟲感染症": "https://www.cdc.gov.tw/Disease/SubIndex/bLTJKs46lP3q20opq3EGRA",
    "肺炎黴漿菌感染症": "https://www.cdc.gov.tw/Disease/SubIndex/3RrXho4Rz3cqtHUGHpVVhw",
    "球黴菌症": "https://www.cdc.gov.tw/Disease/SubIndex/Op-cST_gPKXqSdwDSwZtJQ"
}

# 生成完整的疾病列表（用於疾病名稱提取）
# 合併多個來源：taiwan_infectious_diseases + DISEASE_FORMAT + DISEASE_FORMAT_MORE
def _generate_disease_list():
    """生成完整的疾病列表，合併所有來源並去重"""
    # 從 taiwan_infectious_diseases 字典提取疾病名稱
    diseases_set = set(taiwan_infectious_diseases.keys())

    # 從 DISEASE_FORMAT 提取疾病名稱（去除編號）
    for line in DISEASE_FORMAT.strip().split('\n'):
        if line.strip() and not line.strip().startswith('#'):
            # 提取編號後的疾病名稱
            parts = line.split('.', 1)
            if len(parts) == 2:
                disease_name = parts[1].strip()
                if disease_name:
                    diseases_set.add(disease_name)

    # 從 DISEASE_FORMAT_MORE 提取疾病名稱（去除編號）
    for line in DISEASE_FORMAT_MORE.strip().split('\n'):
        if line.strip() and not line.strip().startswith('#'):
            # 提取編號後的疾病名稱
            parts = line.split('.', 1)
            if len(parts) == 2:
                disease_name = parts[1].strip()
                if disease_name:
                    diseases_set.add(disease_name)

    # 排序並生成編號列表
    sorted_diseases = sorted(diseases_set)
    return "\n".join([f"{i+1}. {disease}" for i, disease in enumerate(sorted_diseases)])

DISEASE_FORMAT_COMBINED = _generate_disease_list()


def get_reference_mapping():
    """建立中英文資料夾對照表"""
    return {
        # 照護指引類別
        '1_傷寒及副傷寒照護指引': 'typhoid_paratyphoid_guideline',
        '2_庫賈氏病感染管制照護指引': 'creutzfeldt_jakob_disease_guideline',
        '3_諾羅病毒感染管制照護指引': 'norovirus_infection_guideline',
        '4_狂犬病感染管制照護指引': 'rabies_infection_guideline',
        '5_病毒性腸胃炎感染管制照護指引': 'viral_gastroenteritis_guideline',
        '6_桿菌性痢疾感染管制照護指引': 'bacillary_dysentery_guideline',
        '7_人類免疫缺乏病毒感染、後天免疫缺乏症候群照護指引': 'hiv_aids_guideline',
        '8_麻疹感染管制照護指引': 'measles_infection_guideline',
        '9_新型A型流感感染管制照護指引': 'novel_influenza_a_guideline',
        '10_開放性結核病感染管制照護指引': 'pulmonary_laryngeal_tuberculosis_guideline',
        '11_中東呼吸症候群冠狀病毒感染症感染管制照護指引': 'mers_cov_infection_guideline',
        '12_發熱伴血小板減少綜合症感染管制照護指引': 'fever_thrombocytopenia_syndrome_guideline',
        '13_流感感染管制照護指引': 'influenza_infection_guideline',
        '14_百日咳感染管制照護指引': 'pertussis_infection_guideline',
        '15_侵襲性b型嗜血桿菌感染管制照護指引': 'invasive_haemophilus_influenzae_guideline',
        '16_流行性腦脊髓膜炎感染管制照護指引': 'epidemic_meningitis_guideline',
        '17_M痘感染管制照護指引': 'mpox_infection_guideline',
        '18_疥瘡感染管制照護指引': 'scabies_infection_guideline',
        '19_腸病毒群感染管制照護指引': 'enterovirus_infection_guideline',
        '20_困難梭狀桿菌感染管制照護指引': 'clostridium_difficile_guideline',
        '21_輪狀病毒感染管制照護指引': 'rotavirus_infection_guideline',
        '22_多重抗藥性微生物感染管制照護指引': 'multidrug_resistant_organisms_guideline',
        '23_Methicillin抗藥性金黃色葡萄球菌及Carbapenem類抗藥性微生物照護指引': 'mrsa_carbapenem_resistant_guideline',
        '24_mCIM( ) carbapenems 抗藥性腸內菌屬照護指引': 'mcim_carbapenem_resistant_enterobacteriaceae_guideline',
        '25_Vancomycin抗藥性腸球菌感染管制照護指引': 'vancomycin_resistant_enterococci_guideline',
        '26_Vancomycin抗藥性金黃色葡萄球菌感染管制照護指引': 'vancomycin_resistant_staphylococcus_guideline',
        '27_Candida auris照護指引': 'candida_auris_guideline',
        '28_COVID-19感染管制照護指引': 'covid19_infection_guideline',
        '29_伊波拉病毒感染及馬堡病毒出血熱感染管制照護指引': 'ebola_marburg_virus_guideline',
        '30_水痘(含瀰漫性帶狀疱疹)照護指引': 'varicella_disseminated_zoster_guideline',

        # 作業要點與準則類別
        '中醫藥部門感染管制作業要點': 'traditional_chinese_medicine_infection_control',
        '住院病房感染管制作業準則': 'inpatient_ward_infection_control',
        '供應中心感染管制作業準則': 'supply_center_infection_control',
        '侵入性檢查治療單位感染管制作業準則': 'invasive_procedure_unit_infection_control',
        '侵入性醫療處置組合式照護感染管制作業準則': 'invasive_medical_bundle_care_infection_control',
        '傳染病防治感染管制作業準則': 'communicable_disease_prevention_control',
        '呼吸治療感染管制作業要點': 'respiratory_therapy_infection_control',
        '廚房餐飲與商店街感染管制作業準則': 'kitchen_dining_retail_infection_control',
        '往生室感染管制作業要點': 'mortuary_infection_control',
        '復健治療部門感染管制作業要點': 'rehabilitation_department_infection_control',
        '手部衛生與隔離防護措施感染管制作業準則': 'hand_hygiene_isolation_precautions',
        '抗微生物製劑管理作業準則': 'antimicrobial_stewardship_procedures',
        '放射線部門感染管制作業要點': 'radiology_department_infection_control',
        '新興傳染病疫情大規模感染事件應變作業準則': 'emerging_infectious_disease_response',
        '檢（實）驗部門感染管制作業要點': 'laboratory_department_infection_control',
        '洗縫布類品感染管制作業要點': 'laundry_textiles_infection_control',
        '流感大流行感染管制作業要點': 'influenza_pandemic_infection_control',
        '消毒及滅菌感染管制作業準則': 'disinfection_sterilization_procedures',
        '牙科部門感染管制作業要點': 'dental_department_infection_control',
        '環境清潔感染管制作業準則': 'environmental_cleaning_procedures',
        '產兒科病房感染管制作業準則': 'obstetrics_pediatrics_infection_control',
        '發燒、咳嗽及腹瀉監測與自主健康管理作業準則': 'fever_cough_diarrhea_monitoring_procedures',
        '藥劑部門感染管制作業要點': 'pharmacy_department_infection_control',
        '護理(產後)之家感染管制作業要點': 'postpartum_care_facility_infection_control',
        '軟式內視鏡清洗及消毒暨品質監測感染管制作業要點': 'flexible_endoscope_cleaning_disinfection',
        '退伍軍人菌環境監測感染管制防治作業要點': 'legionella_environmental_monitoring',
        '透析室感染管制作業要點': 'dialysis_unit_infection_control',
        '門急診部門感染管制作業準則': 'emergency_outpatient_infection_control',
        '麻醉與手術室感染管制作業準則': 'anesthesia_operating_room_infection_control',
        # ⚠️ 已停用：不再使用衛教園地資料
        '衛教園地綜合資訊':'public_health_information_of_education_sites',
    }



# ===== 路徑配置 =====
import os
# 獲取當前專案目錄路徑，動態構建 extracted_tables 路徑
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))  # /home/danny/AI-agent/medical_main_copy copy 3
EXTRACTED_TABLES_DIR = os.path.join(PROJECT_ROOT, "extracted_tables")

# 在 unified_advanced_loader.py 中使用的圖片和表格輸出路徑
EXTRACTED_IMAGES_DIR = os.path.join(EXTRACTED_TABLES_DIR, "images")  # 設定專門存放圖片的資料夾

if __name__ == "__main__":
    # 測試查詢
    result = llm.invoke("請問你好嗎？")
    print(result)
