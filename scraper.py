import os
import re
import urllib.parse
from bs4 import BeautifulSoup
import requests
from dotenv import load_dotenv

load_dotenv()

TORRENT_DOWNLOAD_DIR = os.getenv("TORRENT_DOWNLOAD_DIR", "./downloads")

def parse_size_to_bytes(text):
    """
    Extracts size in bytes and string description from text.
    Matches patterns like '1.4GB', '700MB', etc.
    Avoids matching Mbps or Kbps.
    """
    matches = re.findall(r'(\d+(?:\.\d+)?)\s*(GB|MB|KB|B)(?!ps)\b', text, re.IGNORECASE)
    if not matches:
        return None, None
    
    size_val, size_unit = matches[-1]
    size_val = float(size_val)
    unit = size_unit.upper()
    
    if unit == 'GB':
        bytes_val = int(size_val * 1024 * 1024 * 1024)
    elif unit == 'MB':
        bytes_val = int(size_val * 1024 * 1024)
    elif unit == 'KB':
        bytes_val = int(size_val * 1024)
    else:
        bytes_val = int(size_val)
        
    return bytes_val, f"{size_val} {size_unit}"

def extract_movie_name(title_text):
    """
    Cleans page title or topic name to get a clean movie/series folder name.
    e.g. 'Breakfast (2026) Tamil TRUE WEB-DL - ...' -> 'Breakfast (2026)'
    """
    # Clean multiple consecutive whitespaces/newlines
    title_text = re.sub(r'\s+', ' ', title_text).strip()
    
    match = re.search(r'^(.*?)\s*\((\d{4})\)', title_text)
    if match:
        name = match.group(1).strip()
        year = match.group(2)
        # Remove any invalid characters for paths
        name = re.sub(r'[\\/*?:"<>|]', "", name)
        return f"{name} ({year})"
    
    # Fallback to splitting at common separators
    fallback = re.split(r'[-–\[]', title_text)[0].strip()
    fallback = re.sub(r'[\\/*?:"<>|]', "", fallback)
    return fallback

def extract_non_torrent_links(soup):
    container = soup.find('div', class_='ipsType_richText')
    if not container:
        return []
        
    non_torrent_links = []
    for a in container.find_all('a', href=True):
        href = a['href']
        if (not href.endswith('.torrent') and 
            'attachment.php?id=' not in href and 
            not any(x in href.lower() for x in ['.jpg', '.jpeg', '.png', '.gif', '.webp']) and
            not any(x in href.lower() for x in ['1tamilmv', 'themoviedb.org', 'imdb.com', 'google.com', 'youtube.com'])):
            non_torrent_links.append(a)
            
    results = []
    all_elements = []
    def walk(node):
        if node.name == 'a' and node in non_torrent_links:
            all_elements.append(node)
            return
        if isinstance(node, str):
            txt = re.sub(r'\s+', ' ', node).strip()
            txt = txt.replace('\u00a0', ' ').replace('\u200b', '')
            if txt:
                all_elements.append(txt)
            return
        for child in node.children:
            walk(child)
            
    walk(container)
    
    current_text_blocks = []
    for el in all_elements:
        if isinstance(el, str):
            current_text_blocks.append(el)
        else:
            href = el['href']
            context = ''
            for txt in reversed(current_text_blocks):
                if '.mkv' in txt or '.mp4' in txt or '[' in txt or '@' in txt:
                    context = txt
                    break
            if not context and current_text_blocks:
                context = current_text_blocks[-1]
            
            if '@' in context:
                idx = context.find('@')
                context = context[idx:]
            
            results.append({
                "context": context,
                "url": href
            })
            current_text_blocks = []
            
    return results

def parse_topic_page(html_content, page_url):
    """
    Parses a topic page for:
    - Movie name
    - Torrent links (url, filename, size, selection status)
    - Non-torrent links (url, context)
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Get title
    h1_tag = soup.find('h1')
    title_text = ""
    if h1_tag:
        title_text = h1_tag.text.strip()
    elif soup.title:
        title_text = soup.title.text.strip()
        # strip site suffix if present
        if " - 1TamilMV" in title_text:
            title_text = title_text.split(" - 1TamilMV")[0].strip()
            
    if not title_text:
        title_text = "Unknown Movie"
        
    movie_name = extract_movie_name(title_text)
    
    # Find all torrent links using multiple combined strategies
    torrents = []
    seen_hrefs = set()
    anchors = []
    
    # 1. Look for tags with data-fileext="torrent"
    for a in soup.find_all('a', attrs={"data-fileext": "torrent"}):
        href = a.get('href')
        if href and href not in seen_hrefs:
            seen_hrefs.add(href)
            anchors.append(a)
            
    # 2. Look for attachment.php links
    for a in soup.find_all('a', href=re.compile(r'attachment\.php\?id=\d+')):
        href = a.get('href')
        if href and href not in seen_hrefs:
            # Skip image attachments
            fileext = a.get('data-fileext')
            if fileext and fileext.lower() != 'torrent':
                continue
            # Get text to filter out images (torrborder.gif, uTorrent.png)
            link_text = a.text.strip()
            if not link_text:
                span = a.find('span')
                if span:
                    link_text = span.text.strip()
            if any(ext in link_text.lower() for ext in ['.gif', '.png', '.jpg', '.jpeg', '.webp']):
                continue
                
            seen_hrefs.add(href)
            anchors.append(a)
            
    # 3. Look for direct links ending with .torrent
    for a in soup.find_all('a', href=re.compile(r'\.torrent$', re.IGNORECASE)):
        href = a.get('href')
        if href and href not in seen_hrefs:
            seen_hrefs.add(href)
            anchors.append(a)
        
    for a in anchors:
        href = a.get('href')
        if not href:
            continue
            
        # Ensure absolute URL
        if not href.startswith('http') and not href.startswith('file:'):
            href = urllib.parse.urljoin(page_url, href)
            
        # Get the text inside the link (often has filename and size)
        link_text = a.text.strip()
        # If text is empty, check span inside it
        if not link_text:
            span = a.find('span')
            if span:
                link_text = span.text.strip()
                
        # Parse size from link_text
        size_bytes, size_str = parse_size_to_bytes(link_text)
        
        # If size couldn't be parsed from the link text itself, look at the parent element or nearby text
        if size_bytes is None:
            parent_text = a.parent.text if a.parent else ""
            size_bytes, size_str = parse_size_to_bytes(parent_text)
            
        # Decide selection (less than 2GB)
        selected = False
        if size_bytes is not None:
            selected = size_bytes < 2 * 1024 * 1024 * 1024
            
        torrents.append({
            "url": href,
            "filename": link_text if link_text else "download.torrent",
            "size_bytes": size_bytes,
            "size_str": size_str if size_str else "Unknown",
            "selected": selected
        })
        
    # Extract non-torrent links
    non_torrents = extract_non_torrent_links(soup)
        
    return {
        "title": movie_name,
        "raw_title": title_text,
        "page_url": page_url,
        "torrents": torrents,
        "non_torrents": non_torrents
    }

# Persistent Session with Chrome 137 headers
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive"
})

def close_session():
    """Closes the persistent HTTP session."""
    session.close()

def requests_retry_get(url, headers=None, timeout=20, max_retries=5, backoff_factor=2.0):
    """
    Performs GET request with retries and exponential backoff.
    Catches ConnectionResetError (10054) and other requests exceptions.
    """
    import time
    last_err = None
    for attempt in range(max_retries):
        try:
            # headers are already set on the session, but we allow override
            response = session.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response
        except (requests.exceptions.RequestException, ConnectionResetError) as e:
            last_err = e
            wait_time = backoff_factor * (1.5 ** attempt)
            print(f"      [Attempt {attempt+1}/{max_retries}] Connection failed: {e}. Retrying in {wait_time:.1f}s...")
            time.sleep(wait_time)
    raise last_err

def save_links_txt(dest_folder, torrents, page_url):
    """
    Saves a links.txt file containing all available torrent links in the movie folder.
    """
    os.makedirs(dest_folder, exist_ok=True)
    dest_path = os.path.join(dest_folder, "links.txt")
    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(f"Source Page: {page_url}\n")
        f.write("All available torrent links for this page:\n\n")
        for i, t in enumerate(torrents, 1):
            status = "[SELECTED (<2GB)]" if t["selected"] else "[REJECTED (>2GB)]"
            f.write(f"{i}. Filename: {t['filename']}\n")
            f.write(f"   Size: {t['size_str']} ({t['size_bytes']} bytes)\n")
            f.write(f"   Status: {status}\n")
            f.write(f"   Link: {t['url']}\n\n")

def save_non_torrent_links_txt(dest_folder, non_torrents, page_url):
    """
    Saves a links.txt file containing all available non-torrent links in the movie folder
    with their context formatted like the user requested.
    """
    os.makedirs(dest_folder, exist_ok=True)
    dest_path = os.path.join(dest_folder, "links.txt")
    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(f"Source Page: {page_url}\n\n")
        for t in non_torrents:
            context = t["context"]
            url = t["url"]
            # Formatting logic:
            # ex1: If it's a manalinks or other, use double spacing / blank line between context and url
            # ex2: If it's nowshort or similar, put them on the same line (separated by space)
            # We can check if 'nowshort' in url or 'nowshort' in context
            if 'nowshort' in url or 'nowshort' in context:
                f.write(f"{context} {url}\n\n")
            else:
                f.write(f"{context}\n\n{url}\n\n")

def fetch_html(url_or_path):
    """
    Fetches HTML content from a URL or a local file path.
    """
    if os.path.exists(url_or_path):
        with open(url_or_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
            
    # Clean file:/// prefix if present
    if url_or_path.startswith('file:///'):
        path = url_or_path.replace('file:///', '')
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
                
    # Otherwise, perform HTTP request with retries
    response = requests_retry_get(url_or_path)
    return response.text

def download_torrent(url, dest_folder, filename):
    """
    Downloads a torrent file. Handles file:/// urls for local testing.
    """
    os.makedirs(dest_folder, exist_ok=True)
    
    # Avoid illegal characters in filename first to prevent folder hierarchy pollution (e.g. D/o -> D_o)
    clean_filename = re.sub(r'[\\/*?:"<>|]', "_", filename)
    dest_path = os.path.join(dest_folder, clean_filename)
    
    # If local file URL
    if url.startswith('file:///'):
        src_path = url.replace('file:///', '')
        if os.path.exists(src_path):
            import shutil
            shutil.copy(src_path, dest_path)
            return dest_path
        else:
            with open(dest_path, 'w') as f:
                f.write("mock torrent content")
            return dest_path
            
    # HTTP download with retries
    response = requests_retry_get(url)
    with open(dest_path, 'wb') as f:
        f.write(response.content)
    return dest_path

def get_topic_links_from_homepage(html_content, base_url):
    """
    Extracts all forum topic links from the homepage.
    Filters links matching index.php?/forums/topic/
    Preserves chronological order (newest updates first).
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    links = []
    seen = set()
    
    # 1TamilMV forum topics URLs
    for a in soup.find_all('a', href=True):
        href = a['href']
        # Match topic URLs: index.php?/forums/topic/12345-title/
        if 'forums/topic/' in href:
            # Normalize to absolute URL
            abs_url = urllib.parse.urljoin(base_url, href)
            # Remove query fragments if any
            clean_url = abs_url.split('#')[0].split('&findComment=')[0]
            if clean_url not in seen:
                seen.add(clean_url)
                links.append(clean_url)
            
    return links
