# 📊 全球總經戰情室 (Global Macro Dashboard)

![Dashboard Preview](https://via.placeholder.com/1200x600?text=AI+Macro+Analysis+Dashboard+Snapshot) 
> *註：此預覽圖為示意，實際內容由 Gemini AI 每日自動生成。*

這是一個自動化、AI 驅動的全球總體經濟分析專案。透過結合 Google News RSS 抓取即時資訊，並利用 Google Gemini 3 Flash 模型進行智能推論，為投資者提供與機構同等級的週度深度分析報告。

## 🚀 核心功能

- **自動化新聞抓取**：每日自動搜集過去 7 天全球關鍵財經新聞（Fed、美債、美元、黃金、亞幣）。
- **AI 智能分析引擎**：使用最新的 **Gemini 3 Flash** 模型，將零散新聞轉化為結構化的分析 JSON。
- **動態戰情儀表板**：自動生成 RWD 響應式網頁，整合 TradingView 即時數據工具（經濟日曆、貨幣熱力圖）。
- **GitHub Actions 自動化部署**：完全無人值守，每日 7:00 (UTC+8) 定時更新並發布至 GitHub Pages。

## 🛠️ 技術棧

- **語言**: Python 3.10+
- **AI 模型**: Google Gemini 3 Flash (v1beta)
- **數據源**: Google News RSS, TradingView Widgets
- **前端**: HTML5 / CSS3 (Vanilla CSS, 針對閱覽體驗進行深度優화)
- **CI/CD**: GitHub Actions

## 📖 安裝與設定

如果您想在自己的環境執行此專案，請參考以下步驟：

### 1. 取得 API 金鑰
請前往 [Google AI Studio](https://aistudio.google.com/) 申請免費的 Gemini API Key。

### 2. 環境變數設定
本腳本優先讀取環境變數 `GEMINI_API_KEY`。

**在地端測試 (Windows PowerShell):**
```powershell
$env:GEMINI_API_KEY="您的金鑰"
python update_dashboard.py
```

**在 GitHub 部署:**
請進入倉庫的 `Settings` -> `Secrets and variables` -> `Actions`，新增一個名為 `GEMINI_API_KEY` 的 Secret。

### 3. 自動更新排程
GitHub workflow 定義在 `.github/workflows/daily_update.yml`，預設為每日台灣時間上午 7 點執行。

## 📄 專案結構

- `update_dashboard.py`: 核心 Python 腳本（抓取 -> 分析 -> 生成）。
- `index.html`: 自動生成的戰情網頁入口。
- `macro_analysis.csv`: 用於數據存檔與後續處理的結構化資料。
- `.github/workflows/`: GitHub Actions 自動化腳本。

---

*© 2026 Macro Strategy Lab. 僅供教學與學術研究參考。*
