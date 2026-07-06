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

def save_movie(movie_data):
    """
    Saves or updates movie details.
    movie_data format:
    {
        "title": str,
        "page_url": str,
        "scraped_at": datetime,
        "torrents": [
            {
                "url": str,
                "filename": str,
                "size_bytes": int,
                "size_str": str,
                "selected": bool
            }
        ]
    }
    """
    client, db = get_db_client()
    try:
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
