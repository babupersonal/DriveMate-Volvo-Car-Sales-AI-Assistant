# DriveMate v0.5：評估、觀測與可重現性

## 新增內容

1. GitHub Actions 在 push 與 pull request 時執行後端離線測試與前端 production build。
2. `data/rag_eval.json` 提供 14 題可重跑的 RAG 評估集。
3. `backend.evaluation.evaluate_rag` 計算路由正確率、檢索命中率、車型隔離率，並可選擇驗證來源連結覆蓋率。
4. SQLite 新增 `route_events`，只保存路由模式、工具名稱、延遲與錯誤碼，不保存使用者問題或模型回答。
5. 新增 `/api/metrics/routes`，可查看各路由與工具的匿名統計。
6. 新增結構化錯誤碼，區分 Ollama 連線、模型 API、RAG、資料庫與未預期錯誤。
7. 新增 `config/agent_components.json` 與 `/api/system/components`，公開說明各專業元件的責任。
8. FastAPI 啟動流程改為 lifespan，移除舊式 startup event。

## 架構定位

本系統是 **hybrid single-agent application（混合式單 Agent 應用）**，不是多 Agent 系統。單一客服 Agent 搭配 Tool Calling、RAG、表單處理與確定性安全／備援路由。元件 JSON 是可驗證的架構中繼資料，不宣稱每個元件都是獨立 LLM Agent。

## 評估指令

```bash
# 先建立本機向量索引
python -m backend.app.rag --build

# 只評估路由與檢索（仍需 Ollama Embedding）
python -m backend.evaluation.evaluate_rag

# 另呼叫 Chat Model，驗證回答中的來源連結覆蓋率
python -m backend.evaluation.evaluate_rag --with-generation
```

報告會輸出至 `artifacts/rag_eval_report.json`，此執行結果不提交 GitHub；評估程式與題庫會提交。
