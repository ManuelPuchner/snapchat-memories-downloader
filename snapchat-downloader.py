import os
import re
import json
import requests
import zipfile
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path

# ---------------- CONFIG ----------------
HTML_FILE = 'memories_history.html'
DOWNLOAD_FOLDER = 'snapchat_memories'
LOG_FILE = 'downloaded_files.json'
ERROR_LOG_FILE = 'download_errors.json'
MAX_WORKERS = 5  # Number of parallel downloads
TEST_MODE = False  # Set to True to enable test mode
TEST_FILES_PER_THREAD = 5  # Number of files per thread when test mode is enabled
USE_EXIFTOOL = True  # Set to False if exiftool is not available
# ----------------------------------------

os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Thread lock for JSON writes
json_lock = threading.Lock()
error_lock = threading.Lock()

# Load already-downloaded files (using unique_id as the key)
if os.path.exists(LOG_FILE):
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        downloaded_files = json.load(f)
else:
    downloaded_files = {}

# Load failed downloads
if os.path.exists(ERROR_LOG_FILE):
    with open(ERROR_LOG_FILE, 'r', encoding='utf-8') as f:
        error_log = json.load(f)
else:
    error_log = {}

# Read and parse HTML
with open(HTML_FILE, 'r', encoding='utf-8') as f:
    html_content = f.read()

soup = BeautifulSoup(html_content, 'html.parser')

# Extract all downloadMemories links and related data
pattern = r"downloadMemories\('(.+?)',\s*this,\s*(true|false)\)"
matches = re.findall(pattern, html_content)

# Extract capture dates from the table
def extract_dates_from_table():
    """Extract all capture dates from the table."""
    dates = []
    table = soup.select_one('body > div.rightpanel > table > tbody')
    if table:
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all('td')
            if cells:
                date_text = cells[0].get_text(strip=True)
                dates.append(date_text)
    return dates

dates = extract_dates_from_table()
print(f"{len(matches)} files found, {len(dates)} date entries found.")

# Check whether exiftool is available
def check_exiftool():
    """Check whether exiftool is installed."""
    try:
        subprocess.run(['exiftool', '-ver'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

exiftool_available = check_exiftool() if USE_EXIFTOOL else False
if USE_EXIFTOOL and not exiftool_available:
    print("WARNING: exiftool not found. Metadata will not be written.")
    print("Install from https://exiftool.org/")
elif exiftool_available:
    print("exiftool found - metadata will be written to files.")

def extract_unique_id_from_url(url):
    """Extract the unique ID (mid) from the URL."""
    mid_match = re.search(r'mid=([a-zA-Z0-9\-]+)', url)
    if mid_match:
        return mid_match.group(1)
    else:
        # Fallback: Hash der gesamten URL
        import hashlib
        return hashlib.md5(url.encode()).hexdigest()

def get_file_extension_from_url(url):
    """Determine file extension from the URL or Content-Type."""
    url_path = url.split('?')[0]
    if '.' in url_path.split('/')[-1]:
        ext = os.path.splitext(url_path)[1]
        if ext in ['.mp4', '.jpg', '.jpeg', '.png', '.zip']:
            return ext
    return None

def build_filename(unique_id, date_str=None, content_type=None, url=None):
    """Build a filename from unique_id, date, and content type."""
    base_name = unique_id
    
    # Add date if available
    if date_str:
        try:
            date_cleaned = date_str.strip()
            for fmt in ['%Y-%m-%d %H:%M:%S %Z', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                try:
                    dt = datetime.strptime(date_cleaned.replace('UTC', '').strip(), fmt.replace(' %Z', ''))
                    date_prefix = dt.strftime('%Y%m%d_%H%M%S')
                    base_name = f"{date_prefix}_{base_name}"
                    break
                except:
                    continue
        except:
            pass
    
    # Determine extension
    ext = get_file_extension_from_url(url) if url else None
    if not ext and content_type:
        if 'video' in content_type:
            ext = '.mp4'
        elif 'image/jpeg' in content_type or 'image/jpg' in content_type:
            ext = '.jpg'
        elif 'image/png' in content_type:
            ext = '.png'
        elif 'zip' in content_type:
            ext = '.zip'
    
    if not ext:
        ext = '.mp4'  # Fallback
    
    filename = base_name + ext
    filepath = os.path.join(DOWNLOAD_FOLDER, filename)
    
    return filepath, filename

def extract_and_cleanup_zip(zip_path):
    """Extract a ZIP file and delete the archive."""
    try:
        extract_folder = os.path.splitext(zip_path)[0]
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_folder)
        os.remove(zip_path)
        print(f"[ZIP] Extracted and deleted archive: {os.path.basename(zip_path)}")
        return extract_folder
    except Exception as e:
        print(f"[ZIP ERROR] Failed to extract {os.path.basename(zip_path)}: {e}")
        return None

def parse_date_string(date_str):
    """Parse a date string into a datetime object."""
    if not date_str:
        return None
    
    try:
        date_cleaned = date_str.strip()
        for fmt in ['%Y-%m-%d %H:%M:%S %Z', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d', 
                    '%d.%m.%Y %H:%M:%S', '%d.%m.%Y']:
            try:
                dt = datetime.strptime(date_cleaned.replace('UTC', '').strip(), fmt.replace(' %Z', ''))
                return dt
            except:
                continue
    except:
        pass
    return None

def write_metadata_to_file(filepath, date_str, silent=False):
    """Write capture date into the file metadata."""
    if not exiftool_available or not date_str:
        return False
    
    dt = parse_date_string(date_str)
    if not dt:
        return False
    
    try:
        exif_date = dt.strftime('%Y:%m:%d %H:%M:%S')
        
        file_ext = os.path.splitext(filepath)[1].lower()
        filename = os.path.basename(filepath)
        
        if '-overlay' in filename.lower() or 'thumbnail' in filename.lower():
            if not silent:
                print(f"[SKIP] Skipping metadata for: {filename}")
            try:
                timestamp = dt.timestamp()
                os.utime(filepath, (timestamp, timestamp))
            except:
                pass
            return False
        
        if file_ext in ['.jpg', '.jpeg', '.png']:
            result = subprocess.run([
                'exiftool',
                '-overwrite_original',
                '-q',
                f'-DateTimeOriginal={exif_date}',
                f'-CreateDate={exif_date}',
                f'-ModifyDate={exif_date}',
                filepath
            ], capture_output=True)
            
            if result.returncode != 0 and not silent:
                return False
            
        elif file_ext in ['.mp4', '.mov', '.avi']:
            result = subprocess.run([
                'exiftool',
                '-overwrite_original',
                '-q',
                f'-CreateDate={exif_date}',
                f'-MediaCreateDate={exif_date}',
                f'-TrackCreateDate={exif_date}',
                f'-ModifyDate={exif_date}',
                filepath
            ], capture_output=True)
            
            if result.returncode != 0 and not silent:
                return False
        
        timestamp = dt.timestamp()
        os.utime(filepath, (timestamp, timestamp))
        
        return True
        
    except Exception as e:
        if not silent:
            print(f"[METADATA] Could not write metadata for: {os.path.basename(filepath)}")
        return False

def process_files_in_folder(folder_path, date_str):
    """Write metadata for all files in a folder (for extracted ZIPs)."""
    if not os.path.isdir(folder_path):
        return
    
    success_count = 0
    skip_count = 0
    
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            if file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.mp4', '.mov', '.avi')):
                result = write_metadata_to_file(file_path, date_str, silent=True)
                if result:
                    success_count += 1
                else:
                    skip_count += 1
    
    if success_count > 0 or skip_count > 0:
        print(f"[ZIP-CONTENT] {success_count} files updated with metadata, {skip_count} skipped.")

def log_error(unique_id, url, date_str, error_message, index):
    """Store failed downloads in a separate JSON file."""
    with error_lock:
        error_log[unique_id] = {
            'url': url,
            'date': date_str,
            'error': str(error_message),
            'index': index,
            'timestamp': datetime.now().isoformat()
        }
        try:
            with open(ERROR_LOG_FILE, 'w', encoding='utf-8') as f:
                json.dump(error_log, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[ERROR LOG] Failed to save error list: {e}")

def download_file(url, is_get_request, date_str=None, index=None):
    """Download a file with the correct extension."""
    unique_id = extract_unique_id_from_url(url)
    
    # Check if already downloaded (by unique_id)
    if unique_id in downloaded_files:
        print(f"[SKIP] {unique_id} already downloaded.")
        return unique_id, 'skipped'
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                         'AppleWebKit/537.36 (KHTML, like Gecko) '
                         'Chrome/119.0.0.0 Safari/537.36'
        }
        
        # Request to determine Content-Type
        if is_get_request:
            r = requests.get(url, headers=headers, stream=True, allow_redirects=True, timeout=60)
        else:
            parts = url.split('?')
            post_url = parts[0]
            post_data = parts[1] if len(parts) > 1 else ''
            r = requests.post(post_url, headers=headers, data=post_data,
                            stream=True, allow_redirects=True, timeout=60)
        
        r.raise_for_status()
        
        content_type = r.headers.get('Content-Type', '')

        # Generate filename (without suffix logic)
        filepath, filename = build_filename(unique_id, date_str, content_type, url)
        
        # Download file
        with open(filepath, 'wb') as f:
            for chunk in r.iter_content(1024*1024):
                f.write(chunk)
        
        # Write metadata
        metadata_written = write_metadata_to_file(filepath, date_str)
        
        # If ZIP, extract and write metadata for contents
        if filepath.endswith('.zip'):
            extract_folder = extract_and_cleanup_zip(filepath)
            if extract_folder:
                process_files_in_folder(extract_folder, date_str)
        
        # Store with unique_id as key
        downloaded_files[unique_id] = {
            'filename': filename,
            'url': url,
            'date': date_str,
            'content_type': content_type,
            'metadata_written': metadata_written,
            'timestamp': datetime.now().isoformat()
        }
        
        print(f"[OK] {filename} downloaded{' (metadata written)' if metadata_written else ''}.")
        return unique_id, 'downloaded'
        
    except Exception as e:
        print(f"[ERROR] Download failed for {unique_id} (index {index}): {e}")
        log_error(unique_id, url, date_str, e, index)
        return unique_id, 'error'

def save_progress():
    """Save current progress to the JSON file (thread-safe)."""
    with json_lock:
        try:
            with open(LOG_FILE, 'w', encoding='utf-8') as f:
                json.dump(downloaded_files, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[JSON ERROR] Failed to save: {e}")
            return False

# Prepare download list
download_tasks = []
for i, (url, is_get) in enumerate(matches):
    date_str = dates[i] if i < len(dates) else None
    download_tasks.append((url, is_get == 'true', date_str, i))

# Test mode: limit number of downloads
if TEST_MODE:
    total_test_files = MAX_WORKERS * TEST_FILES_PER_THREAD
    download_tasks = download_tasks[:total_test_files]
    print(f"\n*** TEST MODE ACTIVE: only downloading {len(download_tasks)} files ({TEST_FILES_PER_THREAD} per thread) ***\n")

# Statistics
print(f"\nAlready downloaded: {len(downloaded_files)} files")
print(f"Failed downloads: {len(error_log)} files")
print(f"To process: {len(download_tasks)} files\n")

# Parallel Downloads
completed_count = 0
downloaded_count = 0
skipped_count = 0
error_count = 0
total_count = len(download_tasks)

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = [executor.submit(download_file, url, is_get, date, idx) 
               for url, is_get, date, idx in download_tasks]
    
    for future in as_completed(futures):
        unique_id, status = future.result()
        completed_count += 1
        
        if status == 'downloaded':
            downloaded_count += 1
            save_progress()
        elif status == 'skipped':
            skipped_count += 1
        elif status == 'error':
            error_count += 1
            
        # Progress output
        if completed_count % 10 == 0 or completed_count == total_count:
            print(f"\n[PROGRESS] {completed_count}/{total_count} files processed "
                  f"(Downloaded: {downloaded_count}, Skipped: {skipped_count}, Errors: {error_count})\n")

# Final save
save_progress()

print("\n=== Download Summary ===")
print(f"Total processed: {len(download_tasks)} files")
print(f"Newly downloaded: {downloaded_count} files")
print(f"Skipped (already present): {skipped_count} files")
print(f"Errors: {error_count} files")
print(f"Total successful: {len(downloaded_files)} files")
if error_count > 0:
    print(f"\nFailed downloads were saved to '{ERROR_LOG_FILE}'.")
print("\nAll downloads processed.")