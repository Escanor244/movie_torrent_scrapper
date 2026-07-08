import os
import re
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/torrent_scraper")

def get_db_client():
    client = MongoClient(MONGODB_URI)
    db = client.get_database() # gets database name from URI, e.g. torrent_scraper
    return client, db

def extract_tv_series_info(title_text):
    """
    Checks if a title has TV series patterns (Season, Episode, EP).
    Returns dict with is_tv_series, season_str, episode_str, base_name.
    """
    title_upper = title_text.upper()
    season_match = re.search(r'\b(?:S|SEASON)\s*(\d+)(?:\s*-\s*(?:S|SEASON\s*)?(\d+))?\b', title_upper)
    ep_match = re.search(r'\b(?:E|EP|EPISODE)\s*(\d+)(?:\s*-\s*(\d+))?\b', title_upper)
    ep_range_match = re.search(r'\bEP\s*\((\d+-\d+)\)', title_upper)
    
    is_tv = False
    season_str = "Unknown"
    episode_str = "Unknown"
    
    if season_match:
        is_tv = True
        start_season = int(season_match.group(1))
        end_season = season_match.group(2)
        if end_season:
            season_str = f"S{start_season:02d}-S{int(end_season):02d}"
        else:
            season_str = f"S{start_season:02d}"
            
    if ep_range_match:
        is_tv = True
        episode_str = f"EP({ep_range_match.group(1)})"
    elif ep_match:
        is_tv = True
        start_ep = int(ep_match.group(1))
        end_ep = ep_match.group(2)
        if end_ep:
            episode_str = f"EP{start_ep:02d}-EP{int(end_ep):02d}"
        else:
            episode_str = f"E{start_ep:02d}"
            
    if any(x in title_upper for x in ['COMPLETE', 'SEASON', 'EPISODE', 'EPISODES', 'EP(', 'MERGED']):
        is_tv = True

    if is_tv:
        base_name = title_text
        base_name = re.sub(r'(?i)\b(?:S|SEASON)\s*\d+(?:\s*-\s*(?:S|SEASON\s*)?\d+)?\b', '', base_name)
        base_name = re.sub(r'(?i)\b(?:E|EP|EPISODE)\s*\d+(?:\s*-\s*\d+)?\b', '', base_name)
        base_name = re.sub(r'(?i)\bEP\s*\(\d+-\d+\)', '', base_name)
        base_name = re.sub(r'(?i)\b(?:Complete|Merged|EP|EPs|Season|Seasons|Episodes?)\b', '', base_name)
        base_name = re.sub(r'\s+', ' ', base_name).strip()
        base_name = re.sub(r'\s*-\s*$', '', base_name)
        base_name = re.sub(r'^\s*-\s*', '', base_name)
        base_name = re.sub(r'\s*\[\s*\]\s*', '', base_name)
        base_name = re.sub(r'\s*\(\s*\)\s*', '', base_name)
        base_name = re.sub(r'\s+', ' ', base_name).strip()
        
        return {
            "is_tv_series": True,
            "season_str": season_str,
            "episode_str": episode_str,
            "base_name": base_name
        }
    return {"is_tv_series": False}

def check_and_notify_new_tv_release(movie_data, db):
    """
    Checks if this movie_data represents a TV series and if it is a new release
    compared to existing documents in the DB.
    """
    title = movie_data.get("title", "")
    tv_info = extract_tv_series_info(title)
    if tv_info.get("is_tv_series"):
        movie_data.update(tv_info)
        base_name = tv_info["base_name"]
        season = tv_info["season_str"]
        episode = tv_info["episode_str"]
        
        existing = list(db.movies.find({"is_tv_series": True, "base_name": base_name}))
        if existing:
            match_found = False
            for doc in existing:
                if doc.get("season_str") == season and doc.get("episode_str") == episode:
                    match_found = True
                    break
            
            if not match_found:
                print(f"\n>>> [NOTIFICATION] New TV Series content detected: '{title}' (Base: '{base_name}', Season: '{season}', Ep: '{episode}')!")
                with open("new_tv_releases.log", "a", encoding="utf-8") as f:
                    import datetime
                    f.write(f"{datetime.datetime.now().isoformat()} | New TV Release: {title} | Season: {season} | Ep: {episode} | URL: {movie_data['page_url']}\n")

def save_movie(movie_data):
    """
    Saves or updates movie details.
    """
    client, db = get_db_client()
    try:
        # Check and extract TV series metadata first
        check_and_notify_new_tv_release(movie_data, db)
        
        # Upsert based on page_url to avoid duplicates
        db.movies.update_one(
            {"page_url": movie_data["page_url"]},
            {"$set": movie_data},
            upsert=True
        )
    finally:
        client.close()

def is_already_scraped(page_url):
    client, db = get_db_client()
    try:
        doc = db.movies.find_one({"page_url": page_url})
        return doc is not None
    finally:
        client.close()

def search_movies_by_title(title_query):
    """
    Searches movies by title (case insensitive).
    Returns list of matched movies.
    """
    client, db = get_db_client()
    try:
        # Use regex search for matching title
        query = {"title": {"$regex": re.escape(title_query), "$options": "i"}}
        results = list(db.movies.find(query))
        # Convert _id to string for convenience
        for doc in results:
            doc["_id"] = str(doc["_id"])
        return results
    finally:
        client.close()
