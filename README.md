# 1TamilMV Torrent Scraper

A robust web scraper designed to cron/auto crawl 1TamilMV topic links, index movie pages into a local MongoDB instance, and download torrent files below 2GB into nicely structured directories with safety log summaries.

---

## Features
- **Chronological Crawling:** Sequentially crawls the website, starting with the newest posts at the top of the homepage.
- **2GB Filter:** Automatically parses torrent sizes (GB/MB/KB) and only downloads torrents under 2.0 GB.
- **Safety Backups:** Creates a `links.txt` in each downloaded movie folder detailing the **source page URL** and **all available torrent links** on that page.
- **Anti-Bot Protection Recovery:** Uses a persistent `requests.Session` with a **Chrome 137 user-agent** and an **exponential backoff retry mechanism** to recover from Connection Resets (Error 10054).
- **Run-Specific Log Files:** 
  - `no_torrents_<start_time>.log` lists posts lacking any torrent attachments.
  - `download_failures_<start_time>.log` records page fetch and download issues.
- **Deduplication:** Queries MongoDB before crawling a URL. Skip processing previously crawled pages.

---

## Installation & Setup

1. **Configure Environment Variables:**
   Create a `.env` file in the root directory (you can copy `.env.example` as a starting template):
   ```env
   MONGODB_URI=mongodb://localhost:27017/torrent_scraper
   WEBSITE_HOME_PAGE=https://www.1tamilmv.report/
   TORRENT_DOWNLOAD_DIR=./downloads
   DEFAULT_CYCLE_COUNT=10
   ```

2. **Install Dependencies:**
   Ensure you have Python 3 installed, then run:
   ```cmd
   pip install -r requirements.txt
   ```

---

## CMD Commands

### 1. Run Auto Mode (Index & Download)
Crawl the main page chronologically and index new movies/series:
```cmd
python main.py auto
```
*Processes the default count of 10 movies.*

#### Custom Count Limit:
```cmd
python main.py auto --count 15
```

#### Custom Duration Limit (in Seconds):
```cmd
python main.py auto --duration 180
```

#### Combined Limits:
```cmd
python main.py auto --count 20 --duration 300
```
*Stops scraping whichever limit is hit first.*

---

### 2. Search Database
Check if a movie or series has already been indexed and retrieve all download links under 2GB:
```cmd
python main.py search "Breakfast"
```

---

### 3. Reset / Flush System
To clear the database (drop MongoDB collection), delete the `downloads` directory, and wipe out all local run logs:
```cmd
python main.py flush
```
This is useful when you want to reset everything back to zero.
