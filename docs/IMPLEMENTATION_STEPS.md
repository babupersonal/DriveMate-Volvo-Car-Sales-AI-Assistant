# DriveMate 專題實作步驟

## 階段一：建立專題基礎（本次已完成）
1. 決定專題範圍：Volvo 公開車型資料查詢、模擬庫存、模擬試乘需求。
2. 整理四款車資料與官方來源：EX30 / XC40 / EX40 / XC60。
3. 使用 SQLite 將官方車輛資料與虛構庫存拆成獨立資料表。
4. 實作三個只讀工具：`search_vehicles` / `get_vehicle_details` / `check_demo_stock`。
5. 建立 Ollama Tool Calling 代理人與五段式 System Prompt。
6. 建立 React 介面、FastAPI API、寫入模擬試乘需求功能。
7. 離線單元測試：10 項通過；Ollama 工具呼叫流程已用 mock 驗證。

## 階段二：Mac 本機實測（使用者執行）
1. 啟動 Ollama 和 `qwen3:1.7b`，安裝後端 requirements。
2. 執行 `uvicorn backend.app.main:app --reload --port 8000`。
3. 執行前端 `npm install && npm run dev`。
4. 測試 8 組問題，紀錄 Tool Calling 是否正確。
5. 依測試結果調整模型、提示詞與工具描述；本機小模型可能無法每次選對工具。

## 階段三：期中報告
1. 截圖正確查詢範例、模擬庫存正確標註的案例、查無資料/越界案例。
2. 若包含模擬預約，截圖表單和 SQLite 查詢紀錄。
3. 使用老師提供的 Word 報告範本填寫 1–4 部分與 Checklist。
4. 上傳公開 GitHub，確認不包含 `.env`；轉存 PDF 繳交。

## 自願擴充
- 如果有足夠長的公開文字資料，再加入 RAG，與 Tool Calling 分開測試。
- 如果之後進行階層式 Agent 研究，保留原始資料庫、工具和測試題目作為比較基準。
