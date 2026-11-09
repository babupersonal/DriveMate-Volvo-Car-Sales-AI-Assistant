# DriveMate — Volvo 車型智慧客服（深度學習期中專題）

[![CI](https://github.com/babupersonal/DriveMate-Volvo-Car-Sales-AI-Assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/babupersonal/DriveMate-Volvo-Car-Sales-AI-Assistant/actions/workflows/ci.yml)

**學術獨立示範專案，非 Volvo 官方系統。** 使用 Volvo 台灣官網公開資料查詢車型與起始建議售價，搭配**虛構**庫存和**虛構**試乘需求。任何操作不會連結 Volvo 經銷商或下單。

## 專題功能（第 0.5 版）
- React/Vite 聊天介面：開場白、範例問題、多輪訊息。
- FastAPI + 本地 Ollama Agent：Tool Calling 自動選擇 `search_vehicles`、`get_vehicle_details`、`check_demo_stock`。
- SQLite：車型公開資料 + **模擬**庫存 + **模擬**試乘預約紀錄。
- 可查核的來源：CSV 中每筆資料都有官方網址與查核日期。
- 已有基本防亂編限制：LLM 沒有呼叫工具時，若問題符合明確模式，由後端備援路由使用相同的資料查詢工具，不讓 LLM 自行猜答案；無法安全辨識的問題仍會拒絕編造。
- 聊天介面支援 Markdown 格式化顯示，並顯示 `LLM Tool Calling` 與 `後端備援路由` 的差別（**後端備援路由不是模型自主 Tool Calling**）。
- **RAG 已實作**：本機 Embedding、向量檢索與公開文件摘要回答；需先執行 `python -m backend.app.rag --build`。
- **可重跑評估**：14 題 RAG 題庫評估路由、檢索命中、車型隔離與來源引用。
- **匿名可觀測性**：統計路由、工具、延遲與錯誤碼，不保存問題或回答內容。
- **持續整合**：GitHub Actions 自動執行 28 項後端測試與前端 production build。

## 架構定位

DriveMate 是 **hybrid single-agent application（混合式單 Agent 應用）**，不是多 Agent 系統。單一客服 Agent 依問題使用 Tool Calling、RAG、模擬預約表單或確定性安全／備援路由。`config/agent_components.json` 用來公開記錄專業元件分工，並由後端啟動時驗證、由 `/api/system/components` 提供查詢。

## 環境準備（Mac / Conda）
先確認已安裝 Python 3.11+、Node.js 18+、Ollama。建議使用你原有的 Conda 環境。

```bash
# 1. 解壓縮專案並進入資料夾
cd DriveMate_Volvo_Midterm

# 2. 安裝 Python 套件
python -m pip install -r backend/requirements.txt

# 3. 啟動／確認 Ollama；使用另一個終端開啟 Ollama 服務
ollama serve

# 4. 首次執行需要下載對話與 Embedding 模型
ollama pull qwen3:1.7b
ollama pull qwen3-embedding:0.6b

# 5. 建立本機 RAG 向量索引
python -m backend.app.rag --build

# 6. 開新終端，進入專案根目錄啟動後端
uvicorn backend.app.main:app --reload --port 8000

# 7. 再開一個終端啟動前端
cd frontend
npm ci
npm run dev
```

打開 http://127.0.0.1:5173 。後端 API 文件：http://127.0.0.1:8000/docs 。

> 如果已有 Ollama 背景服務，執行 `ollama list` 確認模型即可，不需要重複啟動 `ollama serve`。

> 請在專案根目錄執行 `cp .env.example .env`，視情況改 `OLLAMA_MODEL`。`.env` 不可上傳 GitHub。

## 執行離線測試

```bash
python -m pytest -q backend/tests
```

目前預期結果為 `28 passed`。這些測試不需要 Ollama 或網路。

## 執行 RAG 評估

RAG 評估採用「題庫 + 目標函式 + 程式化評分」設計。請先啟動 Ollama 並建立向量索引：

```bash
# 路由、檢索命中率與車型隔離率
python -m backend.evaluation.evaluate_rag

# 再呼叫 Chat Model，檢查回答是否完整附上檢索來源
python -m backend.evaluation.evaluate_rag --with-generation
```

評估結果輸出到 `artifacts/rag_eval_report.json`，此報告是本機執行產物，不提交 GitHub。

## 路由統計與架構資訊

- `GET /api/metrics/routes`：各路由使用次數、平均延遲、成功率與工具次數。
- `GET /api/system/components`：讀取經驗證的專業元件分工。
- 每次 `/api/chat` 回傳 `request_id`，方便對照錯誤紀錄。
- 路由紀錄不保存使用者問題、回答、姓名或其他對話內容。

## 試乘模擬紀錄驗證
在前端右側填寫虛構暱稱、未來日期、勾選「模擬」確認，會儲存到 SQLite。可以在 `http://127.0.0.1:8000/api/demo-bookings` 看到測試紀錄。**請勿輸入真實姓名、電話或其他個資**。

## 資料正確性注意

1. CSV 的 `price_from_twd` 是 Volvo **車系建議售價起**，不是特定 `example_variant` 的成交價。
2. 部分電動車續航來自官網特定動力版本且有測試標準；測試值不等於實際行駛里程。
3. `demo_stock.csv` 的數值是自行虛構；**不是**真實 Volvo 庫存。
4. 當官方價格更新時，請同步更新 `data/vehicles.csv`，後端重新啟動時會更新 SQLite 車型資料。
5. UI 中不使用 Volvo 官方品牌 Logo，不宣稱授權或經銷關係。

## 專案結構
```
DriveMate_Volvo_Midterm/
├── .env.example
├── .gitignore
├── .github/workflows/ci.yml
├── README.md
├── config/
│   └── agent_components.json
├── data/
│   ├── vehicles.csv
│   ├── demo_stock.csv
│   ├── rag_knowledge.json
│   └── rag_eval.json
├── docs/
│   ├── PROJECT_SCOPE.md
│   ├── AGENT_DESIGN.md
│   └── CHANGELOG_v0.2～v0.5.md
├── backend/
│   ├── requirements.txt
│   ├── evaluation/
│   │   └── evaluate_rag.py
│   ├── app/
│   │   ├── db.py
│   │   ├── tools.py
│   │   ├── agent.py
│   │   ├── components.py
│   │   ├── fallback_router.py
│   │   ├── rag.py
│   │   └── main.py
│   └── tests/
│       ├── test_core.py
│       ├── test_rag.py
│       ├── test_routing_v04.py
│       └── test_observability.py
└── frontend/
    ├── package.json
    └── src/
        ├── App.jsx
        └── style.css               # React/Vite 網頁
```

## 已完成驗證
- 已完成本機 Ollama 對話測試
- 已完成 Tool Calling 與 Python 備援路由測試
- 已完成 RAG 索引、檢索與官方來源引用
- 已完成模擬試乘資料庫寫入
- 已完成 28 項後端自動化測試
- 已完成 React production build
- 已加入 GitHub Actions 自動驗證
- 已加入 RAG 評估題庫與匿名路由統計
- 已上傳公開 GitHub

## 官方資料引用
[Volvo Taiwan City Cars](https://www.volvocars.com/tw/cars/city-cars/) · [Electric Cars](https://www.volvocars.com/tw/cars/electric-cars/) · [Family Cars](https://www.volvocars.com/tw/cars/family-cars/) · 更多逐筆官方資料請見 `data/vehicles.csv`。

資料查核：2026-11-03。價格／規格隨時間可能更新，正式資訊以官方公告為準。

## 0.2 版測試修正（對應使用者實測）

- `200 萬以內有哪些車型`：保留模型 `search_vehicles` 呼叫；若模型漏掉工具，備援路由從 SQLite 篩選。
- `XC40 和 XC60 哪個馬力較高`：模型漏掉工具時，後端分別執行兩次 `get_vehicle_details`，用 Python 比較數值；示例版本為 XC40 B3 163 hp 與 XC60 B5 AWD 250 hp。
- `EX40 目前有幾台庫存`：使用 `check_demo_stock`，只呈現 **課堂模擬庫存**，絕非官方現車數。
- `XC999 售價多少`：仍查詢 `get_vehicle_details`，並呈現「查無車型」而非模型杜撰。
- API 回傳 `routing_mode`：`llm_tool_call`、`backend_fallback` 或 `none`，利於測試紀錄。
- 建議每一道測試題使用**新的對話**，避免測試互相干擾。

新版安裝前端套件後請執行 `npm install`、`npm run dev`；更新 Python 後端則重啟 `uvicorn` 即可。

> 備援是為提升客服穩定性，不可拿備援成功的問題聲稱「LLM 自行正確選擇工具」。老師報告中要區分兩種工具執行來源。


## 0.3：Volvo 公開支援文件 RAG（新功能）

**重要：** RAG 使用的是本專題自行撰寫的「官方網頁重點摘要」，不是官方完整手冊，也不是 Volvo 提供的客戶資料。本資料集包含 9 篇可溯源的公開文件摘要，例如 EX30 AC/DC 充電、充電安全、警告燈，XC60 保養與預約保養，以及 Volvo Cars App。每筆都標示官方 URL 和查核日期。未收錄的保固年限、購車退訂、實際預約或貸款利率 **不得編造**。

### 安裝（Mac：請在專案根目錄執行）

```bash
# 第一次才需要下載；此 0.6B 版約 639 MB，適合本地中文語意檢索
ollama pull qwen3-embedding:0.6b

# 如尚未安裝 Python 套件
python -m pip install -r backend/requirements.txt

# 將文件切分成 chunk，呼叫本機 Ollama Embedding，建立向量索引
python -m backend.app.rag --build

# 預期輸出：document_count、chunk_count、embedding_model
# 更新後端並測試
uvicorn backend.app.main:app --reload --port 8000
```

若原本的 uvicorn 正在執行，請在原終端 Ctrl+C 後重啟。前端新版則在 `frontend` 目錄執行 `npm install && npm run dev`。本版本不需重建 SQLite，**既有模擬預約紀錄可保留**。

驗證 `http://127.0.0.1:8000/api/rag/status`，預期 `ready: true`。若 `ready: false`，請先執行建立索引命令。若更換或修改 `data/rag_knowledge.json`，必須重新建索引。自建索引 `backend/rag_index.json` 已列入 `.gitignore`，不會上傳 GitHub；使用者可依 README 重建。

**三種示範問題：**

1. `EX30 使用 DC 快充要注意什麼？`（預期：RAG 文件檢索，回覆附官方來源）
2. `XC60 要如何預約回廠保養？`（預期：RAG 文件檢索，強調不能代辦真實預約）
3. `XC60 的保固一定是幾年？`（預期：說明資料不足，不得憑空編造保固期間）

原先的 `EX40 有幾台庫存？` / `XC40 和 XC60 馬力比較？` 仍走 SQLite Tool Calling 或後端備援，**不是 RAG**。回答下方標註 `RAG 文件檢索`、`LLM Tool Calling`、`後端備援路由`，不可混淆。

### RAG 實際處理流程

`data/rag_knowledge.json`（公開來源摘要）→ `chunk_documents()` 切段 → `qwen3-embedding:0.6b` 向量化 → `backend/rag_index.json` → 使用者問題產生 embedding → cosine similarity 取 top-3 → 將檢索段落交給 `qwen3:1.7b` 整理 → 由後端附上官方來源 URL。未查得足夠文件時回覆資料不足，不可自行補充。

這是正式的「索引→檢索→增強→生成」流程，而不是把 FAQ 直接塞進 System Prompt。小模型是否會產生未經來源支持的句子仍需要人工檢查，不能因為附有引用就認定完全正確。

### 相關檔案

- `data/rag_knowledge.json`：9 篇來源摘要與官方連結
- `backend/app/rag.py`：切塊、Embedding、向量檢索、生成與來源附加
- `backend/tests/test_rag.py`：不依賴網路的索引、檢索、路由與引用測試
- `backend/rag_index.json`：在你的 Mac 產生，不隨 ZIP 提供

官方資料來源詳見 `data/rag_knowledge.json`；所有內容皆由公開官方頁面摘要改寫，非官方逐字文件。資料查核日期：2026-11-03。


## v0.4 測試引導與充電安全修正

- 「我想預約 EX30 試乘」會引導使用右側**模擬試乘預約**表單，並預先選取 EX30；僅在表單經明確確認提交後，才會寫入本地 SQLite。此行為標示為 `booking_guidance`，不是 Agent 自己成功呼叫工具。
- EX30 充電線接頭損壞且使用者詢問能否自行清理時，若檢索段落確實有安全禁令，RAG 會先回覆明確禁止使用工具清理、停止使用損壞接頭並提供官方來源；若檢索不到支持資料就不生成這段指示。
- 修改只涉及 Python 路由、RAG 回答、React 引導和測試；**RAG 知識庫本身未改動，不需要重建向量索引**。
- 新版 API 版本為 `0.4.0`，查看 `/openapi.json` 即可確認。

## v0.5 評估與可觀測性

- 新增 GitHub Actions，自動執行 pytest 與 React build。
- 新增 14 題 RAG 評估集與本機評估程式。
- 新增匿名路由統計，不儲存對話內容。
- 新增穩定錯誤碼，區分模型連線、RAG、資料庫與系統錯誤。
- 新增專業元件分工 JSON；它描述混合式單 Agent 架構，不冒充多 Agent。
- 新版 API 版本為 `0.5.0`，查看 `/openapi.json` 即可確認。

詳細變更請見 `docs/CHANGELOG_v0.5.md`。

Agent 的設計依據、評估方式與元件分工請見 `docs/AGENT_DESIGN.md`。
