# Walkthrough - Online Search & TV Series Tracking

Here is a summary of the implementation for the new search and tracking features:

## Completed Features

### 1. Dynamic Online Search Mode (`search-online`)
- Added `get_topic_links_from_search(query)` in [scraper.py](file:///c:/Users/deepa/OneDrive/Desktop/web%20scrap/scraper.py) to perform search queries on the forum. It dynamically walks through search result pages (supporting pagination via `&page=X`) and extracts topic links (`topic/`).
- If a local HTML file is provided (e.g. `search1bestcase.html` or `search2worstcase.html`), the search mode automatically extracts topics from the local file instead of fetching from the web, which is ideal for testing.
- Created `run_search_online(query)` in [main.py](file:///c:/Users/deepa/OneDrive/Desktop/web%20scrap/main.py) which indexes all search result pages, checks if they are already in the DB, and downloads the links and files under the `downloads/search/Movie_Title` subdirectory.
- Registered the new CLI command `search-online` (e.g., `python main.py search-online "Avengers"`).

### 2. TV Series Tracking
- Added TV series pattern detection (`extract_tv_series_info(title_text)`) in [db.py](file:///c:/Users/deepa/OneDrive/Desktop/web%20scrap/db.py). It detects combinations of season and episode indicators (`S01`, `S1`, `Season 01`, `Ep 01`, `EP(01-10)`, etc.) and extracts a clean base name.
- Implemented `check_and_notify_new_tv_release` in [db.py](file:///c:/Users/deepa/OneDrive/Desktop/web%20scrap/db.py). When saving a movie, if it's a TV series, the database checks if we already have other episodes or seasons. If a new season/episode is detected, it prints a message:
  `>>> [NOTIFICATION] New TV Series content detected: '<Title>' (Base: '<Base>', Season: '<Season>', Ep: '<Ep>')!`
  and logs the release in `new_tv_releases.log`.

## Verification Results
- Ran the test suite verifying search-online behaves correctly with `search1bestcase.html` and mock loaders.
- Tested TV Series detection and notifications using mockup inputs for `Loki S01` and `Loki S02` to confirm proper indexing and real-time console/file notifications.
