# Agent 設計與實作依據

## 為什麼保留原生 Ollama Tool Calling

Ollama `/api/chat` 原生支援 `tools` JSON Schema、assistant `tool_calls` 與 `tool` role 回傳結果。DriveMate 直接實作這個循環，避免為小型期中專題加入額外 Agent framework，讓工具選擇、執行結果與備援行為都能在程式碼中清楚查核。

官方參考：<https://github.com/ollama/ollama/blob/main/docs/api.md#generate-a-chat-completion>

## 採用的 Agent 專案實務

### 1. 明確工具契約

每個工具皆包含名稱、用途、參數型別與必要欄位。工具實際能接收的參數也會在後端再次過濾，避免模型傳入未定義參數。

### 2. Agent loop 與確定性保護

模型最多進行四輪工具呼叫。若車型問題沒有取得必要的工具證據，後端不接受模型直接回答；可明確判斷的查詢走備援路由，其餘則拒絕亂編。

### 3. 離線評估與回歸測試

LLM 應用可能因提示詞、模型或輸入的小幅變動而產生不同結果，因此專案保留固定資料集、預期路由／文件與程式化評分。這對應常見的離線 benchmark、unit test 與 regression test 做法。

概念參考：<https://docs.langchain.com/langsmith/evaluation-types>

### 4. 線上觀測與失敗回饋

專案匿名記錄 routing mode、工具名稱、延遲、成功與錯誤碼。失敗案例可再加入 `data/rag_eval.json` 或 pytest，形成「實際失敗 → 評估題庫 → 修正 → 回歸測試」循環。

### 5. 安全與最小資料保存

路由統計不保存使用者問題與模型回答；試乘功能只要求虛構暱稱，並明確標示不會向 Volvo 送出。外部公開來源與課堂模擬資料分開保存。

## 元件分工，而不是假裝成多 Agent

`config/agent_components.json` 將系統責任拆成車型、模擬庫存、支援文件、預約與安全備援五個元件。它們是同一個客服 Agent 背後的專業元件，不是五個彼此對話的 LLM Agent。這樣描述與實際程式一致，也避免因追求「多 Agent」名稱而增加無法驗證的複雜度。

## 目前評估指標

- Route accuracy：問題是否被送到 RAG。
- Retrieval hit rate：預期文件是否出現在 top-k。
- Model isolation rate：指定車型問題是否避免引用其他車型文件。
- Citation coverage rate：生成回答是否包含檢索結果的官方來源網址。
- Route distribution：Tool Calling、備援、RAG、預約引導、拒答與錯誤的使用次數。
- Average latency：各路由平均處理時間。
