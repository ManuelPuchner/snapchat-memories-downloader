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
TEST_MODE = False  # Set to True for test mode
TEST_FILES_PER_THREAD = 5  # Number of files per thread in test mode
USE_EXIFTOOL = True  # Set to False if exiftool is not available
# ----------------------------------------

os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Thread-lock for JSON write access
json_lock = threading.Lock()
error_lock = threading.Lock()

# Load already downloaded files (now with unique_id as key)
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

# Extract all downloadMemories links and associated data
pattern = r"downloadMemories\('(.+?)',\s*this,\s*(true|false)\)"
matches = re.findall(pattern, html_content)

# Extract capture date from table
def extract_dates_from_table():
    """Extracts all capture dates from the table"""
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

# Check if exiftool is available
def check_exiftool():
    """Checks if exiftool is installed"""
    try:
        subprocess.run(['exiftool', '-ver'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

exiftool_available = check_exiftool() if USE_EXIFTOOL else False
if USE_EXIFTOOL and not exiftool_available:
    print("WARNING: exiftool not found. Metadata will not be written.")
    print("Installation: https://exiftool.org/")
elif exiftool_available:
    print("exiftool found - Metadata will be written to files.")

def extract_unique_id_from_url(url):
    """Extracts the unique ID (mid) from the URL"""
    mid_match = re.search(r'mid=([a-zA-Z0-9\-]+)', url)
    if mid_match:
        return mid_match.group(1)
    else:
        # Fallback: Hash of entire URL
        import hashlib
        return hashlib.md5(url.encode()).hexdigest()

def get_file_extension_from_url(url):
    """Ermittelt die Dateierweiterung aus der URL oder dem Content-Type"""
    url_path = url.split('?')[0]
    if '.' in url_path.split('/')[-1]:
        ext = os.path.splitext(url_path)[1]
        if ext in ['.mp4', '.jpg', '.jpeg', '.png', '.zip']:
            return ext
    return None

def build_filename(unique_id, date_str=None, content_type=None, url=None):
    """Erstellt einen Dateinamen basierend auf unique_id, Datum und Content-Type"""
    base_name = unique_id
    
    # Datum hinzufügen, falls vorhanden
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
    
    # Erweiterung bestimmen
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
    """Entpackt ZIP-Datei und löscht die ZIP"""
    try:
        extract_folder = os.path.splitext(zip_path)[0]
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_folder)
        os.remove(zip_path)
        print(f"[ZIP] Entpackt und ZIP gelöscht: {os.path.basename(zip_path)}")
        return extract_folder
    except Exception as e:
        print(f"[ZIP ERROR] Error extracting {os.path.basename(zip_path)}: {e}")
        return None

def parse_date_string(date_str):
    """Parst Datum-String in datetime-Objekt"""
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
    """Schreibt Aufnahmedatum in die Metadaten der Datei"""
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
                print(f"[SKIP] Überspringe Metadaten für: {filename}")
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
    """Schreibt Metadaten für alle Dateien in einem Ordner (für entpackte ZIPs)"""
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
        print(f"[ZIP-INHALT] {success_count} Dateien mit Metadaten versehen, {skip_count} übersprungen.")

def log_error(unique_id, url, date_str, error_message, index):
    """Speichert fehlgeschlagene Downloads in separater JSON-Datei"""
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
            print(f"[ERROR LOG] Error saving error list: {e}")

def download_file(url, is_get_request, date_str=None, index=None):
    """Lädt eine Datei herunter mit korrekter Dateierweiterung"""
    unique_id = extract_unique_id_from_url(url)
    
    # Prüfe ob bereits heruntergeladen (anhand unique_id)
    if unique_id in downloaded_files:
        print(f"[SKIP] {unique_id} bereits heruntergeladen.")
        return unique_id, 'skipped'
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                         'AppleWebKit/537.36 (KHTML, like Gecko) '
                         'Chrome/119.0.0.0 Safari/537.36'
        }
        
        # Anfrage um Content-Type zu ermitteln
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
        
        # Dateinamen generieren (ohne Suffix-Logik)
        filepath, filename = build_filename(unique_id, date_str, content_type, url)
        
        # Datei herunterladen
        with open(filepath, 'wb') as f:
            for chunk in r.iter_content(1024*1024):
                f.write(chunk)
        
        # Metadaten schreiben
        metadata_written = write_metadata_to_file(filepath, date_str)
        
        # Wenn ZIP, entpacken und Metadaten für Inhalte schreiben
        if filepath.endswith('.zip'):
            extract_folder = extract_and_cleanup_zip(filepath)
            if extract_folder:
                process_files_in_folder(extract_folder, date_str)
        
        # Speichere mit unique_id als Key
        downloaded_files[unique_id] = {
            'filename': filename,
            'url': url,
            'date': date_str,
            'content_type': content_type,
            'metadata_written': metadata_written,
            'timestamp': datetime.now().isoformat()
        }
        
        print(f"[OK] {filename} heruntergeladen{' (Metadaten geschrieben)' if metadata_written else ''}.")
        return unique_id, 'downloaded'
        
    except Exception as e:
        print(f"[ERROR] Download fehlgeschlagen für {unique_id} (Index {index}): {e}")
        log_error(unique_id, url, date_str, e, index)
        return unique_id, 'error'

def save_progress():
    """Speichert den aktuellen Fortschritt in die JSON-Datei (Thread-safe)"""
    with json_lock:
        try:
            with open(LOG_FILE, 'w', encoding='utf-8') as f:
                json.dump(downloaded_files, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[JSON ERROR] Error saving: {e}")
            return False

# Download-Liste vorbereiten
download_tasks = []
for i, (url, is_get) in enumerate(matches):
    date_str = dates[i] if i < len(dates) else None
    download_tasks.append((url, is_get == 'true', date_str, i))

# Test-Modus: Begrenze Anzahl der Downloads
if TEST_MODE:
    total_test_files = MAX_WORKERS * TEST_FILES_PER_THREAD
    download_tasks = download_tasks[:total_test_files]
    print(f"\n*** TEST-MODUS AKTIV: Lade nur {len(download_tasks)} Dateien ({TEST_FILES_PER_THREAD} pro Thread) ***\n")

# Statistiken
print(f"\nBereits heruntergeladen: {len(downloaded_files)} Dateien")
print(f"Fehlerhafte Downloads: {len(error_log)} Dateien")
print(f"Zu bearbeiten: {len(download_tasks)} Dateien\n")

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
            
        # Fortschrittsanzeige
        if completed_count % 10 == 0 or completed_count == total_count:
            print(f"\n[FORTSCHRITT] {completed_count}/{total_count} Dateien bearbeitet "
                  f"(Downloaded: {downloaded_count}, Skipped: {skipped_count}, Errors: {error_count})\n")

# Finale Speicherung
save_progress()

print("\n=== Download-Zusammenfassung ===")
print(f"Gesamt bearbeitet: {len(download_tasks)} Dateien")
print(f"Neu heruntergeladen: {downloaded_count} Dateien")
print(f"Übersprungen (bereits vorhanden): {skipped_count} Dateien")
print(f"Errors: {error_count} files")
print(f"Total successful: {len(downloaded_files)} files")
if error_count > 0:
    print(f"\nFailed downloads saved in '{ERROR_LOG_FILE}'.")
print("\nAlle Downloads bearbeitet.")
