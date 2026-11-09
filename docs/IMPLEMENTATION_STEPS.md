# DriveMate 專題實作步驟

## 階段一：建立專題基礎（本次已完成）
1. 決定專題範圍：Volvo 公開車型資料查詢、模擬庫存、模擬試乘需求。
2. 整理四款車資料與官方來源：EX30 / XC40 / EX40 / XC60。
3. 使用 SQLite 將官方車輛資料與虛構庫存拆成獨立資料表。
4. 實作三個只讀工具：`search_vehicles` / `get_vehicle_details` / `check_demo_stock`。
5. 建立 Ollama Tool Calling 代理人與五段式 System Prompt。
6. 建立 React 介面、FastAPI API、寫入模擬試乘需求功能。
7. RAG 已正式完成，已有 Tool Calling、備援路由、RAG 與試乘引導。
8. 建立 14 題 RAG 評估集，支援路由、檢索、車型隔離與引用評估。
9. 新增匿名路由統計與穩定錯誤碼，不保存對話內容。
10. GitHub Actions 自動執行 28 項後端測試與 React production build。

## 階段二：Mac 本機實測（已完成）
1. 啟動 Ollama 和 `qwen3:1.7b`，安裝後端 requirements。
2. 執行 `uvicorn backend.app.main:app --reload --port 8000`。
3. 執行前端 `npm install && npm run dev`。
4. 測試多組問題，區分 LLM Tool Calling、後端備援路由、RAG 與拒答。
5. 依測試結果調整模型、提示詞與工具描述，並將失敗案例加入回歸測試。

## 階段三：期中報告
1. 截圖正確查詢範例、模擬庫存正確標註的案例、查無資料/越界案例。
2. 若包含模擬預約，截圖表單和 SQLite 查詢紀錄。
3. 使用老師提供的 Word 報告範本填寫 1–4 部分與 Checklist。
4. 上傳公開 GitHub，確認不包含 `.env`；轉存 PDF 繳交。

## v0.5 專業化提升

- `config/agent_components.json` 說明各專業元件的責任；後端會驗證這份設定。
- `data/rag_eval.json` 保存可重跑的評估問題與預期文件。
- `route_events` 僅記錄路由、工具、延遲及錯誤碼，不保存對話內容。
- GitHub Actions 提供跨環境的自動回歸測試。

如果之後進行階層式 Agent 研究，可保留此單 Agent 系統作為基準組，再與多 Agent 架構比較。
