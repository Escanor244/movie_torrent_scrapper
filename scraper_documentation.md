# Torrent Scraper - Complete Documentation

This document explains the technical flow, ordering sequence, and operational commands for the Torrent Scraper.

---

## 1. How the Scraper Works (Order of Scraping)

The crawler operates in a structured pipeline designed to be polite, sequential, and chronologically ordered (newest first).

### Pipeline Flowchart

```mermaid
graph TD
    A[Start Auto Mode] --> B[Fetch Site Homepage]
    B --> C[Extract Topic URLs in Order of Appearance]
    C --> D{Check if URL Already Indexed in MongoDB}
    D -- Yes --> E[Skip Topic Page]
    D -- No --> F[Fetch Topic Page with Chrome 137 Headers]
    F --> G[Extract Movie Name & Torrent Info]
    G --> H{Are Torrents Found?}
    H -- No --> I[Log URL to no_torrents_*.log / Append to rejected.txt]
    H -- Yes --> J[Create Movie Folder & Save links.txt]
    J --> K[Filter Torrents < 2GB]
    K --> L[Download Selected Torrents & Save Movie to DB]
    I --> M[Save Empty Entry to DB to Avoid Re-crawling]
    L --> N[Wait 2.0s Rate-Limit Delay]
    M --> N
    N --> O{Cycle Target or Duration Limit Reached?}
    O -- No --> D
    O -- Yes --> P[Close Session & Print Run Summary]
```

### Scraping Order Details
1. **Homepage Loading:** The scraper fetches `WEBSITE_HOME_PAGE` (the 1TamilMV forum homepage).
2. **Chronological Sorting:** It parses the HTML source code from top to bottom. Because the homepage lists movie posts chronologically (newest updates/bumps first), the extracted links list preserves this order exactly.
3. **Database Guard (Deduplication):** Before fetching any movie page, the bot queries MongoDB. If the page URL exists in the database (whether it was successfully downloaded or previously rejected), it is skipped immediately to prevent redundant network requests.
4. **Rate Limiting:** A polite 2-second sleep delay is executed between page loads.
5. **Torrent Filtration:** It parses all torrent attachments on the page:
   - File size labels (e.g. `1.4GB`, `700MB`) are extracted.
   - If size is `< 2.0 GB`, the torrent is queued for download.
   - A backup index file `links.txt` containing the **source page URL** and **all available torrent links** is created in the movie folder for safety.
6. **Session Termination:** Once the cycle limit (default 10) or duration timeout is reached, the bot terminates and closes the HTTP connection pool safely.

---

## 2. CMD Commands to Use the Scraper

Run these commands in your Windows CMD or PowerShell terminal within the `web scrap` directory.

### Initialize/Setup
Make sure your MongoDB server is active, copy configuration variables, and install dependencies:
```cmd
copy .env.example .env
pip install -r requirements.txt
```

### Command 1: Run Auto Crawler (Chronological Scraping)
Starts indexing and downloading new torrents:
```cmd
python main.py auto
```
*Processes the default count of 10 movies.*

#### Custom Count Limit:
```cmd
python main.py auto --count 15
```
*Stops after checking 15 new movies.*

#### Custom Duration Limit (Seconds):
```cmd
python main.py auto --duration 120
```
*Stops after 120 seconds of running.*

#### Combined Count & Duration:
```cmd
python main.py auto --count 20 --duration 180
```
*Stops whichever limit is reached first.*

---

### Command 2: Search Database (Offline)
Instantly check if a movie was already scraped and retrieve all its torrent links under 2GB:
```cmd
python main.py search "Breakfast"
```
```cmd
python main.py search "Reign of Terror"
```

---

### Command 3: Search and Index Online
Query 1TamilMV online for a keyword, follow pagination through all pages, extract results, and download them to a dedicated `downloads/search` folder:
```cmd
python main.py search-online "Avengers"
```

---

## 3. Advanced Features

### TV Series Tracking & Alerts
When saving movie documents to MongoDB, the scraper checks for TV series keywords (`S1`, `S01`, `Season 01`, `Ep 01`, `EP(01-10)`, etc.). If classified as a TV series, it indexes additional fields:
- `is_tv_series`: `True`
- `tv_series_base_name`: (e.g. `Game of Thrones (2011)`)
- `season_str`: (e.g. `S01`)
- `episode_str`: (e.g. `EP(01-10)`)

If another episode or season of the same TV series is processed later, the scraper compares metadata and triggers a real-time console notification:
`>>> [NOTIFICATION] New TV Series content detected: '<Title>' (Base: '<Base>', Season: '<Season>', Ep: '<Ep>')!`
And logs the release in `new_tv_releases.log`.

### Non-Torrent Downloads
For pages containing direct, non-torrent download options (such as Google Drive/redirector links like `nowshort.com` or `manalinks.in`), the scraper extracts the links, pairs them with their filename/size contexts, and outputs a properly formatted `links.txt` file in the movie directory. If a page contains no torrent links but has direct links, the page is processed successfully rather than being rejected.
