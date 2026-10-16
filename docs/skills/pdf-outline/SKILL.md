---
name: pdf-outline
description: 使用 pdf-outline CLI 合併 PDF 並建立書籤、讀取或重建 PDF 目錄，以及依第一層書籤拆章。適用於 PDF outline/bookmark 與章節檔案操作；不處理 OCR、內文摘要或排版重製。
---

# PDF Outline

使用既有 CLI 執行操作，不另寫 PDF 處理程式。先辨識來源、輸出與所需子命令，再執行對應流程。

## 執行環境與輸出

- 先執行 `pdf-outline --help` 確認可用版本與命令。若未安裝，使用本機 checkout `/Users/kevinkuo/Source/pdf-outline`，先查其 `pyproject.toml` 與 `uv.lock`，再用 `uv run --frozen --project /Users/kevinkuo/Source/pdf-outline pdf-outline --help`。其他機器先定位 checkout；此專案需要 Python >=3.14。
- 下列範例假設 `pdf-outline` 已在 PATH；使用 checkout 時，以前述 `uv run --frozen --project ... pdf-outline` 取代。環境要求 RTK 時，外層加 `rtk proxy`，避免過濾 JSON 輸出。
- 路徑一律加引號。使用絕對來源與輸出路徑，避免執行目錄歧義；manifest 內的相對 `path` 依程序工作目錄解析，**不是 manifest 所在目錄**。
- 預設寫到新的輸出檔或空目錄；既有目的檔可能被覆寫。`create-manifest` 會拒絕覆寫，但其他命令沒有同等保護。只有使用者已要求覆寫時才使用原路徑。

## 讀取目錄：`toc`

```bash
pdf-outline toc "/absolute/book.pdf"
pdf-outline toc "/absolute/book.pdf" --json
```

`--json` 回傳陣列，含 `title`、`level`、`start_page`、`end_page`、`page_count`、`index` 與可能為 null 的 `path`。頁碼是 PDF 實體頁序，從 1 開始；`end_page` 包含該頁。

`index` 是所有第一層書籤的流水號，含封面、前言等，並非書上的章號。先用標題與頁面確認對應，不直接把「第三章」當成 index 3。

空陣列表示沒有可抽取的書籤，不代表沒有印刷目錄。CLI 不會 OCR 或辨識目錄頁。無法解析的目的地會回退為第 1 頁；可疑的起始頁、重複頁或非遞增順序，須核對原 PDF 後再用於拆章。

## 合併：`bind`

以下三種輸入模式擇一；合併順序就是列出的順序，CLI 不會自行排序。

```bash
# 從檔名產生第一層書籤
pdf-outline bind --output "/absolute/merged.pdf" "/absolute/01.pdf" "/absolute/02.pdf"

# 保留明確標題；--entry 可重複
pdf-outline bind --output "/absolute/merged.pdf" \
  --entry "Introduction::/absolute/01.pdf" \
  --entry "Chapter 1::/absolute/02.pdf"

# 階層書籤與完整順序
pdf-outline bind --output "/absolute/merged.pdf" --manifest "/absolute/bind.json"
```

自動標題優先取檔名第一個括號內的文字，否則清理檔名；底線轉空白並正規化大小寫。`--acronym GDP --acronym IMF` 可保留額外縮寫，只影響檔名產生的標題。精確文字用 `--entry` 或 manifest。

bind manifest 是 JSON 陣列：

```json
[
  {"title": "Introduction", "level": 1, "path": "/absolute/01.pdf"},
  {"title": "Background", "level": 2, "path": "/absolute/02.pdf"},
  {"title": "Chapter 1", "level": 1, "path": "/absolute/03.pdf"}
]
```

`level` 預設 1；階層須從 1 開始、不可跳過父層。省略 `path` 的項目只建立書籤，指向當前累計頁位置，不增加頁數；無檔案子項目的直接父項目必須有檔案。一般合併優先讓每項都有 `path`。來源內部書籤不會自動沿用，輸出使用本次建立的目錄。

完成後重讀輸出 `toc --json`，核對標題、階層與累計起始頁；以 pikepdf 核對輸出頁數等於來源頁數總和。

## 重建目錄：`set-toc`

先讀既有目錄。此命令會取代整份書籤樹；若要求保留某些項目，將它們納入新 manifest。

```json
[
  {"title": "Introduction", "level": 1, "start_page": 1},
  {"title": "Background", "level": 2, "start_page": 2},
  {"title": "Chapter 1", "level": 1, "start_page": 6}
]
```

```bash
pdf-outline set-toc "/absolute/book.pdf" \
  --manifest "/absolute/outline.json" --output "/absolute/book-with-outline.pdf"
```

每項必須有 `start_page`，使用 PDF 實體頁碼，不使用印刷頁碼或羅馬頁碼標籤。執行前核對 `1 <= start_page <= PDF 總頁數`，並檢查父層存在；CLI 對頁碼的檢查不足以取代此核對。空 manifest 會清除目錄，只在要求清除時使用。

省略 `--output` 會直接覆寫輸入 PDF，因此預設明確提供新路徑。完成後重讀輸出 `toc --json`，核對每項標題、層級與起始頁，並確認總頁數未變。

## 拆章：`split`

先執行 `toc --json`，確認第一層書籤的順序、起始頁與涵蓋範圍符合需求。

```bash
pdf-outline split "/absolute/book.pdf" --outdir "/absolute/new-chapters"
# 若確定標題轉檔名後仍唯一，可省略流水號
pdf-outline split "/absolute/book.pdf" --outdir "/absolute/new-chapters" --no-number
```

- 只依第一層書籤切割，不依子節或印刷目錄；沒有指定單章或任意頁範圍的選項。只需要幾章時，先拆到暫存目錄，再將已確認的章節複製到目的地。
- 每段從該項起始頁切到下一個第一層項目前一頁，最後一項切到文件結尾。第一項之前的頁面不會輸出，`page_count <= 0` 的項目會略過。
- 預設如 `01_Chapter-1.pdf`。標題中的空白、點與底線變成連字號，其他部分符號會移除；`--no-number` 可能讓不同標題變成同名。執行前檢查清理後檔名的唯一性，碰撞時保留編號。
- 無可拆書籤時會印出訊息並正常退出，因此 exit code 0 不保證產生檔案。核對實際輸出清單與各檔頁數是否符合預期 `page_count`；需要內容身分確認時，檢視各章首尾頁。輸出章節不會自動保留原書籤樹。

## 產生範本：`create-manifest`

```bash
pdf-outline create-manifest --mode bind --output "/absolute/bind.json"
pdf-outline create-manifest --mode set-toc --output "/absolute/outline.json"
```

預設 mode 是 `bind`、輸出是工作目錄的 `manifest.json`。範本含三筆範例，level 為 `[1, 2, 1]`；先換成真實標題、絕對檔案路徑或已核對的頁碼，再交給對應命令。父目錄必須存在；輸出已存在時選新檔名或編輯原檔。

## 交付

回報產物的絕對路徑、實際執行的命令及通過的核對。區分結構／頁數驗證與實際頁面內容檢視；未檢視頁面時明確說明。若請求涉及文獻庫、筆記或附件同步，先遵循該工作區的 owner contract；本 skill 僅處理 PDF 檔案，不授權修改共享資料或同步附件。
