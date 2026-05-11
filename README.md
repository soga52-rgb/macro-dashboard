# 📊 全球總經戰情室
## AI Macro Intelligence Dashboard — v3.7 Causal Engine

這是一套 AI 驅動的全球總經敘事分析系統。  
核心目標不是單純摘要新聞，而是協助使用者理解市場正在交易的宏觀敘事（Market Narrative）、跨資產傳導鏈（Macro Transmission）與市場狀態（Market Regime）。

系統每日自動抓取全球總經新聞、市場報價與官方總經數據，透過 Gemini 模型進行結構化分析，並自動輸出 Dashboard、Podcast 與每日歷史版本留存。

> ⚠️ 本專案內容僅供總體經濟研究、資料視覺化與 AI 自動化實驗使用，不構成任何投資建議。

---

## 🚀 核心功能

- **自動化新聞抓取**：每日透過 Google News RSS 以 Rolling 48-Hour Window 抓取全球總經新聞，優先追蹤 Bloomberg、CNBC、Reuters、WSJ、FT、MarketWatch。
- **市場數據整合**：結合 Yahoo Finance Chart API、FRED API 與 TradingView Widgets，追蹤美債殖利率、美元指數、黃金、原油、股市與亞洲匯率（台幣/日圓/韓元）。
- **AI 總經敘事分析**：利用 Gemini 模型與 Google Search Grounding 將新聞與市場數據轉換為結構化 JSON，判斷市場主旋律、利率路徑、通膨壓力與美元傳導。
- **Market Regime Engine**：自動判斷目前市場狀態，例如 `Stagflation Risk`、`Higher for Longer`、`Risk-Off / Flight to Safety`、`Soft Landing Trade` 等。
- **Anomaly Signal Detection**：偵測異常跨資產定價現象，例如「美元↑黃金↑」、「殖利率↑科技股↑」等非典型市場訊號。
- **Macro Causal Engine Lite**：內建 5 條核心因果傳導鏈（Fed Policy、Real Yield、USD Anchor、Energy Inflation、VIX Risk-Off），每日由 AI 選出最相關的 1-3 條啟動。
- **Visual Macro Scene**：自動生成總經傳導圖解，將「事件 → 預期 → 資產價格」的傳導路徑視覺化呈現。
- **AI Podcast（雙主持人）**：產生 Tom（主持人）與 Miranda（總經策略師）雙角色對談腳本，透過 Multi-Speaker edge-TTS 生成每日總經 Podcast。
- **每週影音回顧**：每逢週四由 GitHub Actions 自動產製雙主播週報影片（FFmpeg 合成，9:16 直式格式）。
- **歷史回顧**：Dashboard 保留最近 7 日每日分析快照，可透過下拉選單切換歷史版本。
- **GitHub Actions 全自動部署**：每日定時排程，從資料抓取到 Dashboard 更新，完全無人值守。

---

## 🛠 技術棧

| 類別 | 技術 |
|------|------|
| **語言** | Python 3.10+ |
| **AI 模型** | Google Gemini 3.1 Pro Preview（主力）/ Gemini 2.5 Pro（fallback） |
| **AI 工具** | Google Search Grounding |
| **新聞來源** | Google News RSS（Rolling 48-Hour Window） |
| **市場資料** | Yahoo Finance Chart API v8、FRED API |
| **前端** | HTML5 / CSS3 / Vanilla JavaScript |
| **圖表工具** | TradingView Widgets（殖利率、DXY、黃金、原油、亞幣） |
| **Podcast TTS** | edge-tts，Tom（zh-TW-YunJheNeural）/ Miranda（zh-TW-HsiaoChenNeural） |
| **影音合成** | FFmpeg（音波視覺化、B-Roll 底圖、字幕疊加） |
| **CI/CD** | GitHub Actions |
| **部署** | GitHub Pages |

---

## ⏰ 自動更新排程

每日台灣時間約 **06:13** 由 GitHub Actions 進入排程，實際完成時間視 GitHub 排隊與 Gemini API 回應速度而定（通常 06:20～07:10 之間完成）。

每逢週四額外產製每週總經回顧影片。

---

## 📖 安裝與設定

### 1. 取得 API 金鑰

| 金鑰 | 申請來源 |
|------|----------|
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/) |
| `FRED_API_KEY` | [FRED API](https://fred.stlouisfed.org/docs/api/api_key.html)（免費，可選） |

### 2. 環境變數設定

**本機測試 (Windows PowerShell)：**
```powershell
$env:GEMINI_API_KEY="您的金鑰"
$env:FRED_API_KEY="您的FRED金鑰"  # 可選
python update_dashboard.py
```

**GitHub 部署：**  
進入倉庫 `Settings` → `Secrets and variables` → `Actions`，新增：
- `GEMINI_API_KEY`（必填）
- `FRED_API_KEY`（選填，未設定時自動降級為僅使用 Yahoo Finance）

### 3. 安裝依賴

```bash
pip install -r requirements.txt
sudo apt-get install -y ffmpeg fonts-wqy-microhei  # Linux / GitHub Actions
```

---

## 📁 專案結構

```
macro_dashboard/
├── update_dashboard.py        # 核心引擎：新聞抓取 → AI 分析 → Dashboard 生成 → Podcast TTS
├── generate_weekly_video.py   # 週四專用：雙主播週報影片產製（FFmpeg 合成）
├── index.html                 # 自動生成的 Dashboard 網頁（每日覆寫）
├── historical_data.json       # 最近 7 日分析快照（支援歷史回顧切換）
├── macro_analysis.csv         # 核心指標結構化存檔
├── macro_skills.json          # Macro Skills Library（Regime 模板，首次執行自動建立）
├── macro_causal_graphs.json   # Macro Causal Engine 傳導鏈庫（首次執行自動建立）
├── requirements.txt           # Python 套件依賴
└── .github/workflows/
    └── daily_update.yml       # GitHub Actions 排程設定
```

---

## 📊 Dashboard 功能區塊

| 區塊 | 說明 |
|------|------|
| **Market Regime Bar** | 顯示當前市場狀態標籤與異常定價訊號 |
| **Macro Causal Graph** | 今日啟動的 1-3 條因果傳導鏈 |
| **Visual Macro Scene** | 總經傳導圖解（Transmission Chain / Regime Dashboard / Risk Radar） |
| **新聞剖析** | 3 則精選新聞的深度解析（傳導路徑、方向判讀、一句話結論） |
| **總經分析摘要** | AI 撰寫的市場敘事摘要與下週預測 |
| **市場走勢圖** | TradingView 即時圖表（US10Y、DXY、Gold、Oil、USD/JPY、USD/TWD、USD/KRW） |
| **全球市場熱力圖** | S&P 500 板塊熱圖 + 主要貨幣強弱矩陣 |
| **每日 Podcast** | Tom × Miranda AI 雙主播語音摘要，支援歷史版本切換 |
| **每週影音回顧** | 週四更新，雙主播週報影片（9:16 直式） |
| **歷史回顧** | 下拉選單切換最近 7 日分析快照 |

---

*© 2026 Macro Strategy Lab. 僅供總體經濟研究與 AI 自動化實驗使用。*
