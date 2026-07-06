import os
import sys
import time
import argparse
from datetime import datetime
from dotenv import load_dotenv

from db import save_movie, is_already_scraped, search_movies_by_title
from scraper import (
    fetch_html,
    get_topic_links_from_homepage,
    parse_topic_page,
    download_torrent,
    save_links_txt
)

load_dotenv()

DEFAULT_CYCLE_COUNT = int(os.getenv("DEFAULT_CYCLE_COUNT", "10"))
WEBSITE_HOME_PAGE = os.getenv("WEBSITE_HOME_PAGE", "https://www.1tamilmv.report/")
TORRENT_DOWNLOAD_DIR = os.getenv("TORRENT_DOWNLOAD_DIR", "./downloads")

REJECTED_FILE = "rejected.txt"

def append_to_rejected(movie_title, url):
    """
    Appends a rejected movie/series page to rejected.txt.
    """
    with open(REJECTED_FILE, "a", encoding="utf-8") as f:
        f.write(f"Title: {movie_title} | URL: {url} | Reason: No torrent links found\n")

def run_search(title_query):
    print(f"\nSearching database for movie: '{title_query}'")
    results = search_movies_by_title(title_query)
    
    if not results:
        print("No matching movies found in the database. You may want to run auto mode to index pages first.")
        return
        
    print(f"Found {len(results)} matching movie(s) in the database:\n")
    for movie in results:
        print(f"Movie Title: {movie['title']}")
        print(f"Source Page: {movie['page_url']}")
        
        # Get torrents below 2GB (selected = True)
        selected_torrents = [t for t in movie.get('torrents', []) if t.get('selected')]
        
        if not selected_torrents:
            print("  No torrent links under 2GB available for this movie.")
        else:
            print("  Selected Torrent Links (Less than 2GB):")
            for t in selected_torrents:
                print(f"    - [{t['size_str']}] {t['filename']}")
                print(f"      Link: {t['url']}")
        print("-" * 50)

def run_auto(count_limit, duration_seconds):
    from scraper import close_session
    start_time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    no_torrents_log_file = f"no_torrents_{start_time_str}.log"
    download_failures_log_file = f"download_failures_{start_time_str}.log"

    print("\n================== STARTING AUTO MODE ==================")
    print(f"Target count: {count_limit} movies")
    if duration_seconds:
        print(f"Target duration limit: {duration_seconds} seconds")
    print(f"Home page: {WEBSITE_HOME_PAGE}")
    print(f"Download directory: {TORRENT_DOWNLOAD_DIR}")
    print(f"No Torrents Log: {no_torrents_log_file}")
    print(f"Download Failures Log: {download_failures_log_file}")
    print("========================================================\n")
    
    start_time = time.time()
    
    try:
        # 1. Fetch homepage and extract topic links
        try:
            print("Fetching home page...")
            homepage_html = fetch_html(WEBSITE_HOME_PAGE)
            topic_urls = get_topic_links_from_homepage(homepage_html, WEBSITE_HOME_PAGE)
            print(f"Found {len(topic_urls)} topic URLs on the home page.")
        except Exception as e:
            print(f"Failed to fetch homepage: {e}")
            return
            
        scraped_count = 0
        skipped_count = 0
        rejected_count = 0
        downloaded_torrents_count = 0
        
        # Track what we processed in this cycle to report to the user
        cycle_scraped = []
        cycle_rejected = []
        
        for url in topic_urls:
            # Check time limit
            elapsed = time.time() - start_time
            if duration_seconds and elapsed >= duration_seconds:
                print(f"\nTime limit reached ({int(elapsed)}s >= {duration_seconds}s). Stopping crawler.")
                break
                
            # Check count limit
            if scraped_count >= count_limit:
                print(f"\nScrape count limit reached ({scraped_count}/{count_limit}). Stopping crawler.")
                break
                
            # Check if already scraped
            if is_already_scraped(url):
                skipped_count += 1
                continue
                
            print(f"\n[{scraped_count + 1}/{count_limit}] Processing URL: {url}")
            try:
                # Add delay to be polite
                time.sleep(2.0)
                
                # Fetch page HTML
                html = fetch_html(url)
                movie_data = parse_topic_page(html, url)
                movie_data["scraped_at"] = datetime.utcnow()
                
                title = movie_data["title"]
                torrents = movie_data["torrents"]
                
                if not torrents:
                    print(f"  --> Rejected: No torrent links found for '{title}'")
                    append_to_rejected(title, url)
                    cycle_rejected.append((title, url))
                    rejected_count += 1
                    
                    # Write to the specific no torrents log file
                    with open(no_torrents_log_file, "a", encoding="utf-8") as log_f:
                        log_f.write(f"Time: {datetime.now().isoformat()} | Title: {title} | URL: {url}\n")
                    
                    # Still save to DB with empty torrents so we don't re-crawl it next time
                    save_movie(movie_data)
                    scraped_count += 1
                    continue
                    
                # Filter and download torrent links
                selected_torrents = [t for t in torrents if t["selected"]]
                print(f"  Title: {title}")
                print(f"  Found {len(torrents)} torrent links. {len(selected_torrents)} are under 2GB.")
                
                movie_download_dir = os.path.join(TORRENT_DOWNLOAD_DIR, title)
                
                # Save the links.txt file with all available links and source page URL for safety
                save_links_txt(movie_download_dir, torrents, url)
                
                for t in selected_torrents:
                    try:
                        print(f"    Downloading {t['filename']} ({t['size_str']})...")
                        download_torrent(t['url'], movie_download_dir, t['filename'])
                        downloaded_torrents_count += 1
                    except Exception as dl_err:
                        print(f"      Error downloading torrent {t['filename']}: {dl_err}")
                        # Log torrent download failure
                        with open(download_failures_log_file, "a", encoding="utf-8") as log_f:
                            log_f.write(f"Time: {datetime.now().isoformat()} | Movie: {title} | Torrent: {t['filename']} | Link: {t['url']} | Error: {dl_err}\n")
                        
                # Save to Database
                save_movie(movie_data)
                cycle_scraped.append(title)
                scraped_count += 1
                
            except Exception as err:
                print(f"  Error processing page {url}: {err}")
                # Log page processing failure
                with open(download_failures_log_file, "a", encoding="utf-8") as log_f:
                    log_f.write(f"Time: {datetime.now().isoformat()} | URL: {url} | Error: {err}\n")
                
        # Final Cycle Summary
        elapsed_total = time.time() - start_time
        print("\n================== CYCLE COMPLETE SUMMARY ==================")
        print(f"Time Elapsed: {elapsed_total:.2f} seconds")
        print(f"Movies / Series Scraped & Indexed: {scraped_count}")
        print(f"  - Successfully processed and downloaded: {len(cycle_scraped)}")
        print(f"  - Rejected (No Torrents): {rejected_count}")
        print(f"Already Indexed (Skipped): {skipped_count}")
        print(f"Total Torrent files downloaded: {downloaded_torrents_count}")
        
        if cycle_rejected:
            print("\nRejected Pages in this Cycle:")
            for r_title, r_url in cycle_rejected:
                print(f"  * {r_title} -> {r_url}")
            print(f"Details saved to local files: {REJECTED_FILE} & {no_torrents_log_file}")
        print("============================================================\n")
    finally:
        close_session()

def flush_database_and_downloads():
    from db import get_db_client
    import shutil
    import glob
    
    print("\n================== FLUSHING SYSTEM ==================")
    # 1. Clear MongoDB Collection
    try:
        client, db = get_db_client()
        # Drop the movies collection
        db.movies.drop()
        print("MongoDB collection 'movies' dropped successfully.")
    except Exception as db_err:
        print(f"Error dropping MongoDB collection: {db_err}")
    finally:
        try:
            client.close()
        except:
            pass
            
    # 2. Clear Downloads Directory
    if os.path.exists(TORRENT_DOWNLOAD_DIR):
        try:
            shutil.rmtree(TORRENT_DOWNLOAD_DIR)
            print(f"Downloads folder '{TORRENT_DOWNLOAD_DIR}' deleted successfully.")
        except Exception as dir_err:
            print(f"Error deleting downloads folder: {dir_err}")
    else:
        print("Downloads folder does not exist. Nothing to delete.")
        
    # 3. Clear logs and rejected.txt
    for filename in [REJECTED_FILE]:
        if os.path.exists(filename):
            try:
                os.remove(filename)
                print(f"File '{filename}' deleted successfully.")
            except Exception as f_err:
                print(f"Error deleting '{filename}': {f_err}")
                
    # Clean any local log files
    for log_file in glob.glob("*.log"):
        try:
            os.remove(log_file)
            print(f"Log file '{log_file}' deleted successfully.")
        except Exception as log_err:
            print(f"Error deleting log file '{log_file}': {log_err}")
            
    print("=====================================================\n")

def main():
    parser = argparse.ArgumentParser(description="1TamilMV Torrent Scraper and Indexer")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Search sub-command
    search_parser = subparsers.add_parser("search", help="Search movie database for torrents under 2GB")
    search_parser.add_argument("title", type=str, help="Movie or series title to search for")
    
    # Auto sub-command
    auto_parser = subparsers.add_parser("auto", help="Run crawler in auto mode to index movies")
    auto_parser.add_argument("--count", type=int, default=DEFAULT_CYCLE_COUNT,
                            help=f"Number of movies to index in this cycle (default: {DEFAULT_CYCLE_COUNT})")
    auto_parser.add_argument("--duration", type=int, default=None,
                            help="Max duration for this cycle in seconds (optional)")
                            
    # Flush sub-command
    subparsers.add_parser("flush", help="Reset/Flush the database, downloads directory, and logs")
    
    args = parser.parse_args()
    
    if args.command == "search":
        run_search(args.title)
    elif args.command == "auto":
        run_auto(args.count, args.duration)
    elif args.command == "flush":
        flush_database_and_downloads()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
