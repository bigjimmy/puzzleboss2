#!/usr/bin/env python3
"""
Wiki Indexer for PuzzleBoss RAG

This script fetches all pages from a MediaWiki installation,
chunks the content, creates embeddings using Google Gemini,
and stores them in ChromaDB for retrieval.

Usage:
    python wiki_indexer.py [--full]

Options:
    --full    Force full re-index (delete existing data first)

Intended to be run periodically via cron (e.g., hourly).
"""

import os
import sys
import argparse
import requests
import re
import yaml
import MySQLdb
from html import unescape
import urllib3

# Suppress SSL warnings for localhost wiki access
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pblib import debug_log

# Configuration
CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "puzzleboss.yaml")

# ChromaDB and Gemini - optional imports
CHROMADB_AVAILABLE = False
GEMINI_AVAILABLE = False

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    debug_log(1, "chromadb not installed - wiki indexer unavailable")

try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    debug_log(1, "google-genai not installed - wiki indexer unavailable")


def load_config():
    """Load configuration from YAML file and database."""
    with open(CONFIG_FILE, 'r') as f:
        yaml_config = yaml.safe_load(f)
    
    # Connect to database to get config values
    conn = MySQLdb.connect(
        host=yaml_config['MYSQL']['HOST'],
        user=yaml_config['MYSQL']['USERNAME'],
        passwd=yaml_config['MYSQL']['PASSWORD'],
        db=yaml_config['MYSQL']['DATABASE'],
        charset='utf8mb4'
    )
    cursor = conn.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT `key`, `val` FROM config")
    db_config = {row['key']: row['val'] for row in cursor.fetchall()}
    conn.close()
    
    return db_config


def get_all_wiki_pages(wiki_url, exclude_prefixes=None):
    """Fetch all page titles from MediaWiki with last modified times."""
    debug_log(3, f"Fetching page list from {wiki_url}")
    
    if exclude_prefixes is None:
        exclude_prefixes = []
    
    api_url = wiki_url.rstrip('/') + '/api.php'
    pages = []
    apcontinue = None
    
    while True:
        params = {
            'action': 'query',
            'list': 'allpages',
            'aplimit': '500',
            'format': 'json'
        }
        if apcontinue:
            params['apcontinue'] = apcontinue
        
        response = requests.get(api_url, params=params, verify=False)
        data = response.json()
        
        for page in data.get('query', {}).get('allpages', []):
            title = page['title']
            
            # Skip excluded pages
            skip = False
            for prefix in exclude_prefixes:
                if title.startswith(prefix) or title.lower().startswith(prefix.lower()):
                    debug_log(4, f"Skipping excluded page: {title}")
                    skip = True
                    break
            if skip:
                continue
            
            pages.append({
                'pageid': page['pageid'],
                'title': title
            })
        
        if 'continue' in data:
            apcontinue = data['continue'].get('apcontinue')
        else:
            break
    
    debug_log(3, f"Found {len(pages)} wiki pages (after exclusions)")
    return pages


def get_page_content(wiki_url, title):
    """Fetch the content and last modified time of a specific wiki page."""
    api_url = wiki_url.rstrip('/') + '/api.php'
    
    params = {
        'action': 'query',
        'titles': title,
        'prop': 'revisions',
        'rvprop': 'content|timestamp',  # Also get timestamp
        'rvslots': 'main',
        'format': 'json'
    }
    
    response = requests.get(api_url, params=params, verify=False)
    data = response.json()
    
    pages = data.get('query', {}).get('pages', {})
    for page_id, page_data in pages.items():
        if page_id == '-1':
            return None, None
        revisions = page_data.get('revisions', [])
        if revisions:
            revision = revisions[0]
            timestamp = revision.get('timestamp', '')  # e.g., "2024-01-15T12:30:00Z"
            slots = revision.get('slots', {})
            main = slots.get('main', {})
            content = main.get('*', '')
            return content, timestamp
    
    return None, None


def clean_wiki_content(content):
    """Clean wiki markup to plain text."""
    if not content:
        return ""
    
    # Remove categories
    content = re.sub(r'\[\[Category:[^\]]+\]\]', '', content)
    
    # Remove file/image links
    content = re.sub(r'\[\[(File|Image):[^\]]+\]\]', '', content, flags=re.IGNORECASE)
    
    # Convert wiki links to just the text: [[Link|Text]] -> Text, [[Link]] -> Link
    content = re.sub(r'\[\[([^\]|]+)\|([^\]]+)\]\]', r'\2', content)
    content = re.sub(r'\[\[([^\]]+)\]\]', r'\1', content)
    
    # Remove external links markup: [http://... text] -> text
    content = re.sub(r'\[https?://[^\s\]]+ ([^\]]+)\]', r'\1', content)
    content = re.sub(r'\[https?://[^\]]+\]', '', content)
    
    # Remove templates (simplified - won't handle nested)
    content = re.sub(r'\{\{[^}]+\}\}', '', content)
    
    # Remove HTML tags
    content = re.sub(r'<[^>]+>', '', content)
    
    # Remove wiki formatting
    content = re.sub(r"'''?", '', content)  # Bold/italic
    content = re.sub(r'={2,}', '', content)  # Headers
    
    # Clean up whitespace
    content = re.sub(r'\n{3,}', '\n\n', content)
    content = content.strip()
    
    # Unescape HTML entities
    content = unescape(content)
    
    return content


def chunk_content(title, content, chunk_size=1000, overlap=200):
    """Split content into overlapping chunks for embedding."""
    if not content:
        return []
    
    chunks = []
    
    # If content is short enough, return as single chunk
    if len(content) <= chunk_size:
        return [{
            'title': title,
            'content': content,
            'chunk_index': 0
        }]
    
    # Split into chunks with overlap
    start = 0
    chunk_index = 0
    while start < len(content):
        end = start + chunk_size
        
        # Try to break at a paragraph or sentence boundary
        if end < len(content):
            # Look for paragraph break
            para_break = content.rfind('\n\n', start, end)
            if para_break > start + chunk_size // 2:
                end = para_break
            else:
                # Look for sentence break
                sentence_break = content.rfind('. ', start, end)
                if sentence_break > start + chunk_size // 2:
                    end = sentence_break + 1
        
        chunk_text = content[start:end].strip()
        if chunk_text:
            chunks.append({
                'title': title,
                'content': chunk_text,
                'chunk_index': chunk_index
            })
            chunk_index += 1
        
        start = end - overlap if end < len(content) else len(content)
    
    return chunks


def create_embeddings(chunks, api_key):
    """Create embeddings for chunks using Google Gemini."""
    if not chunks:
        return []
    
    client = genai.Client(api_key=api_key)
    
    embeddings = []
    for i, chunk in enumerate(chunks):
        try:
            # Combine title and content for embedding
            text = f"{chunk['title']}: {chunk['content']}"
            
            result = client.models.embed_content(
                model="text-embedding-004",
                contents=text
            )
            
            embeddings.append(result.embeddings[0].values)
            
            if (i + 1) % 10 == 0:
                debug_log(4, f"Created {i + 1}/{len(chunks)} embeddings")
                
        except Exception as e:
            debug_log(2, f"Error creating embedding for chunk {i}: {e}")
            embeddings.append(None)
    
    return embeddings


def index_wiki(config, full_reindex=False):
    """Main function to index wiki content."""
    if not CHROMADB_AVAILABLE:
        debug_log(1, "ChromaDB not available - cannot index wiki")
        return False
    
    if not GEMINI_AVAILABLE:
        debug_log(1, "Google Gemini not available - cannot index wiki")
        return False
    
    wiki_url = config.get('WIKI_URL', '')
    chromadb_path = config.get('WIKI_CHROMADB_PATH', '/var/lib/puzzleboss/chromadb')
    api_key = config.get('GEMINI_API_KEY', '')
    
    if not wiki_url:
        debug_log(1, "WIKI_URL not configured - cannot index wiki")
        return False
    
    if not api_key:
        debug_log(1, "GEMINI_API_KEY not configured - cannot create embeddings")
        return False
    
    # Get optional config for page filtering
    # WIKI_EXCLUDE_PREFIXES: comma-separated list of page title prefixes to skip
    # e.g., "Hunt 2023,Hunt 2022,Archive:"
    exclude_prefixes_str = config.get('WIKI_EXCLUDE_PREFIXES', '')
    exclude_prefixes = [p.strip() for p in exclude_prefixes_str.split(',') if p.strip()]
    
    # WIKI_PRIORITY_PAGES: comma-separated list of important page titles
    # e.g., "Main Page,Team Info,Current Hunt"
    priority_pages_str = config.get('WIKI_PRIORITY_PAGES', '')
    priority_pages = [p.strip().lower() for p in priority_pages_str.split(',') if p.strip()]
    
    debug_log(3, f"Starting wiki indexing from {wiki_url}")
    if exclude_prefixes:
        debug_log(3, f"Excluding pages with prefixes: {exclude_prefixes}")
    if priority_pages:
        debug_log(3, f"Priority pages: {priority_pages}")
    
    # Ensure ChromaDB directory exists
    os.makedirs(chromadb_path, exist_ok=True)
    
    # Initialize ChromaDB
    client = chromadb.PersistentClient(
        path=chromadb_path,
        settings=Settings(anonymized_telemetry=False)
    )
    
    # Get or create collection
    collection_name = "wiki_pages"
    
    if full_reindex:
        # Delete existing collection
        try:
            client.delete_collection(collection_name)
            debug_log(3, "Deleted existing collection for full reindex")
        except Exception:
            pass
    
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"description": "MediaWiki page chunks for RAG"}
    )
    
    # Fetch all wiki pages
    try:
        pages = get_all_wiki_pages(wiki_url, exclude_prefixes)
    except Exception as e:
        debug_log(1, f"Error fetching wiki pages: {e}")
        return False
    
    # Process each page
    all_chunks = []
    all_ids = []
    all_metadatas = []
    
    for page in pages:
        title = page['title']
        debug_log(4, f"Processing: {title}")
        
        try:
            content, timestamp = get_page_content(wiki_url, title)
            if not content:
                continue
            
            cleaned = clean_wiki_content(content)
            if not cleaned or len(cleaned) < 50:  # Skip very short pages
                continue
            
            # Check if this is a priority page
            is_priority = title.lower() in priority_pages
            
            chunks = chunk_content(title, cleaned)
            
            for chunk in chunks:
                chunk_id = f"{page['pageid']}_{chunk['chunk_index']}"
                
                # Skip if already indexed (unless full reindex)
                if not full_reindex:
                    existing = collection.get(ids=[chunk_id])
                    if existing and existing['ids']:
                        continue
                
                all_chunks.append(chunk)
                all_ids.append(chunk_id)
                all_metadatas.append({
                    'title': title,
                    'pageid': page['pageid'],
                    'chunk_index': chunk['chunk_index'],
                    'last_modified': timestamp or '',
                    'is_priority': is_priority
                })
                
        except Exception as e:
            debug_log(2, f"Error processing page '{title}': {e}")
    
    if not all_chunks:
        debug_log(3, "No new chunks to index")
        return True
    
    debug_log(3, f"Creating embeddings for {len(all_chunks)} chunks")
    
    # Create embeddings
    embeddings = create_embeddings(all_chunks, api_key)
    
    # Filter out failed embeddings
    valid_data = [
        (chunk, chunk_id, metadata, embedding)
        for chunk, chunk_id, metadata, embedding in zip(all_chunks, all_ids, all_metadatas, embeddings)
        if embedding is not None
    ]
    
    if not valid_data:
        debug_log(2, "No valid embeddings created")
        return False
    
    # Add to collection
    debug_log(3, f"Adding {len(valid_data)} chunks to ChromaDB")
    
    collection.add(
        ids=[d[1] for d in valid_data],
        embeddings=[d[3] for d in valid_data],
        metadatas=[d[2] for d in valid_data],
        documents=[d[0]['content'] for d in valid_data]
    )
    
    debug_log(3, f"Wiki indexing complete. Total documents in collection: {collection.count()}")
    return True


def main():
    parser = argparse.ArgumentParser(description='Index MediaWiki content for RAG')
    parser.add_argument('--full', action='store_true', help='Force full re-index')
    args = parser.parse_args()
    
    try:
        config = load_config()
        success = index_wiki(config, full_reindex=args.full)
        sys.exit(0 if success else 1)
    except Exception as e:
        debug_log(0, f"Wiki indexer error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

