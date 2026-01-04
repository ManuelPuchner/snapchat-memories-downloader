#!/usr/bin/env python3
"""
Script for extracting GPS coordinates from HTML and writing them to files
"""

import os
import re
import json
import subprocess
from bs4 import BeautifulSoup
from datetime import datetime

# Configuration
HTML_FILE = 'memories_history.html'
DOWNLOADED_FILES_JSON = 'downloaded_files.json'
METADATA_JSON = 'metadata.json'
DOWNLOAD_FOLDER = 'snapchat_memories'
USE_EXIFTOOL = True

def check_exiftool():
    """Checks if exiftool is installed"""
    try:
        subprocess.run(['exiftool', '-ver'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

exiftool_available = check_exiftool() if USE_EXIFTOOL else False

def extract_locations_from_html(html_file):
    """Extracts GPS coordinates from the HTML table"""
    if not os.path.exists(html_file):
        print(f"❌ '{html_file}' not found!")
        return []
    
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    locations = []
    
    # Search for all tables
    table = soup.select_one('body > div.rightpanel > table > tbody')
    if not table:
        print("⚠️  Table not found in HTML!")
        return locations
    
    rows = table.find_all('tr')
    
    # Pattern for coordinates: "Latitude, Longitude: 48.26275, 13.296288"
    coord_pattern = re.compile(r'Latitude,\s*Longitude:\s*([+-]?\d+\.?\d*),\s*([+-]?\d+\.?\d*)')
    
    for row in rows:
        cells = row.find_all('td')
        
        # Search all cells for coordinates
        for cell in cells:
            text = cell.get_text(strip=True)
            match = coord_pattern.search(text)
            
            if match:
                latitude = float(match.group(1))
                longitude = float(match.group(2))
                locations.append({
                    'latitude': latitude,
                    'longitude': longitude
                })
                break  # Only one location per row
    
    return locations

def extract_urls_from_html(html_file):
    """Extracts URLs and creates mapping to index"""
    if not os.path.exists(html_file):
        return []
    
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    pattern = r"downloadMemories\('(.+?)',\s*this,\s*(true|false)\)"
    matches = re.findall(pattern, html_content)
    
    return [url for url, _ in matches]

def extract_unique_id_from_url(url):
    """Extracts the unique ID (mid) from the URL"""
    mid_match = re.search(r'mid=([a-zA-Z0-9\-]+)', url)
    if mid_match:
        return mid_match.group(1)
    else:
        import hashlib
        return hashlib.md5(url.encode()).hexdigest()

def write_gps_to_file(filepath, latitude, longitude):
    """Writes GPS coordinates to the EXIF data of the file and preserves timestamps"""
    if not exiftool_available:
        return False
    
    if not os.path.exists(filepath):
        return False
    
    try:
        file_ext = os.path.splitext(filepath)[1].lower()
        filename = os.path.basename(filepath)
        
        # Skip special files
        if '-overlay' in filename.lower() or 'thumbnail' in filename.lower():
            return False
        
        # IMPORTANT: Save original timestamps BEFORE modifying the file
        stat_info = os.stat(filepath)
        original_atime = stat_info.st_atime  # Access time
        original_mtime = stat_info.st_mtime  # Modification time
        original_birthtime = stat_info.st_birthtime if hasattr(stat_info, 'st_birthtime') else None
        
        # Convert to EXIF GPS format
        # GPSLatitude and GPSLongitude require Ref (N/S, E/W)
        lat_ref = 'N' if latitude >= 0 else 'S'
        lon_ref = 'E' if longitude >= 0 else 'W'
        
        abs_lat = abs(latitude)
        abs_lon = abs(longitude)
        
        result = None
        
        if file_ext in ['.jpg', '.jpeg', '.png']:
            result = subprocess.run([
                'exiftool',
                '-overwrite_original',
                '-q',
                f'-GPSLatitude={abs_lat}',
                f'-GPSLatitudeRef={lat_ref}',
                f'-GPSLongitude={abs_lon}',
                f'-GPSLongitudeRef={lon_ref}',
                filepath
            ], capture_output=True)
            
        elif file_ext in ['.mp4', '.mov', '.avi']:
            result = subprocess.run([
                'exiftool',
                '-overwrite_original',
                '-q',
                f'-GPSLatitude={abs_lat}',
                f'-GPSLatitudeRef={lat_ref}',
                f'-GPSLongitude={abs_lon}',
                f'-GPSLongitudeRef={lon_ref}',
                filepath
            ], capture_output=True)
        
        if result and result.returncode == 0:
            # Restore the original timestamps after exiftool modifies the file
            os.utime(filepath, (original_atime, original_mtime))
            
            # On macOS, also restore birth time (creation date) using SetFile command
            if original_birthtime is not None:
                try:
                    from datetime import datetime
                    dt = datetime.fromtimestamp(original_birthtime)
                    # SetFile format: "MM/DD/YYYY HH:MM:SS"
                    date_str = dt.strftime('%m/%d/%Y %H:%M:%S')
                    # Try SetFile first (from Xcode Command Line Tools)
                    subprocess.run(['SetFile', '-d', date_str, filepath], 
                                 capture_output=True, check=False)
                except Exception:
                    # If birth time restoration fails, at least we have mtime/atime restored
                    pass
            
            return True
        
        return False
        
    except Exception as e:
        print(f"❌ GPS Error writing for {os.path.basename(filepath)}: {e}")
        return False

def process_files_in_folder(folder_path, latitude, longitude):
    """Writes GPS data for all files in a folder (unpacked ZIPs)"""
    if not os.path.isdir(folder_path):
        return 0
    
    success_count = 0
    
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            if file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.mp4', '.mov', '.avi')):
                if write_gps_to_file(file_path, latitude, longitude):
                    success_count += 1
    
    return success_count

def main():
    print("=" * 60)
    print("📍 Location Metadata Extractor & Writer")
    print("=" * 60)
    print()
    
    # Check exiftool
    if USE_EXIFTOOL and not exiftool_available:
        print("❌ exiftool not found!")
        print("Installation: https://exiftool.org/")
        print("Metadata will only be saved in JSON, not in files.")
        response = input("\nContinue anyway? (y/n): ")
        if response.lower() not in ['y', 'yes']:
            return
        print()
    elif exiftool_available:
        print("✅ exiftool found - GPS data will be written to files")
        print()
    
    # Load downloaded_files.json
    if not os.path.exists(DOWNLOADED_FILES_JSON):
        print(f"❌ '{DOWNLOADED_FILES_JSON}' not found!")
        return
    
    with open(DOWNLOADED_FILES_JSON, 'r', encoding='utf-8') as f:
        downloaded_files = json.load(f)
    
    print(f"📄 {len(downloaded_files)} entries found in downloaded_files.json")
    
    # Extract locations from HTML
    print(f"📍 Extracting GPS coordinates from '{HTML_FILE}'...")
    locations = extract_locations_from_html(HTML_FILE)
    print(f"✅ {len(locations)} GPS coordinates found")
    
    # Extract URLs for mapping
    urls = extract_urls_from_html(HTML_FILE)
    print(f"✅ {len(urls)} URLs found")
    print()
    
    # Create metadata
    metadata = {}
    files_with_location = 0
    files_without_location = 0
    gps_written_count = 0
    gps_failed_count = 0
    gps_errors = []  # Track detailed error information
    
    total_urls = len(urls)
    print(f"🔄 Processing {total_urls} URLs...")
    print()
    
    for i, url in enumerate(urls, 1):
        unique_id = extract_unique_id_from_url(url)
        
        # Check if file was downloaded
        if unique_id not in downloaded_files:
            print(f"[{i}/{total_urls}] ⏭️  Skipped (not downloaded)")
            continue
        
        file_info = downloaded_files[unique_id]
        filename = file_info.get('filename')
        
        # Add GPS coordinates (if available)
        location = locations[i-1] if i-1 < len(locations) else None
        
        metadata[unique_id] = {
            'filename': filename,
            'date': file_info.get('date'),
            'content_type': file_info.get('content_type'),
            'location': location
        }
        
        if location:
            files_with_location += 1
            
            # Write GPS to file
            if exiftool_available:
                filepath = os.path.join(DOWNLOAD_FOLDER, filename)
                
                # Check if it's a file or folder (unpacked ZIP)
                if os.path.isfile(filepath):
                    if write_gps_to_file(filepath, location['latitude'], location['longitude']):
                        gps_written_count += 1
                        print(f"[{i}/{total_urls}] ✅ {filename} - GPS written")
                    else:
                        gps_failed_count += 1
                        gps_errors.append({
                            'filename': filename,
                            'unique_id': unique_id,
                            'latitude': location['latitude'],
                            'longitude': location['longitude']
                        })
                        print(f"[{i}/{total_urls}] ⚠️  {filename} - GPS write failed")
                
                elif os.path.isdir(filepath.replace('.zip', '')):
                    # Unpacked ZIP folder
                    folder_path = filepath.replace('.zip', '')
                    count = process_files_in_folder(folder_path, location['latitude'], location['longitude'])
                    gps_written_count += count
                    print(f"[{i}/{total_urls}] ✅ {filename} - GPS written to {count} files in folder")
                else:
                    print(f"[{i}/{total_urls}] 📄 {filename} - Processed (file not found)")
            else:
                print(f"[{i}/{total_urls}] 📄 {filename} - Processed (no exiftool)")
        else:
            files_without_location += 1
            print(f"[{i}/{total_urls}] 📄 {filename} - No GPS data")
    
    # Save metadata.json
    print()
    print("🔄 Generating final report...")
    print()
    print(f"💾 Saving '{METADATA_JSON}'...")
    
    with open(METADATA_JSON, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    # Summary
    print()
    print("=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    print(f"Total processed: {len(metadata)} files")
    print(f"📍 With GPS coordinates: {files_with_location} files")
    print(f"❌ Without GPS coordinates: {files_without_location} files")
    
    if exiftool_available:
        print()
        print(f"✅ GPS written to files: {gps_written_count}")
        if gps_failed_count > 0:
            print(f"⚠️  GPS write errors: {gps_failed_count}")
    
    print()
    print(f"✅ '{METADATA_JSON}' successfully created!")
    
    # Print detailed error list if there were GPS errors
    if gps_failed_count > 0 and gps_errors:
        print()
        print("=" * 60)
        print("⚠️  FAILED GPS WRITES")
        print("=" * 60)
        for error_info in gps_errors:
            print(f"\n📄 File: {error_info['filename']}")
            print(f"   ID: {error_info['unique_id']}")
            print(f"   Location: {error_info['latitude']}, {error_info['longitude']}")
        print(f"\n💡 These files may be in unsupported formats or have other issues.")

if __name__ == '__main__':
    main()
