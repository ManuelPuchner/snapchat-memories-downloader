#!/usr/bin/env python3
"""
Script to extract GPS coordinates from HTML and write them to files.
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
    """Check whether exiftool is installed."""
    try:
        subprocess.run(['exiftool', '-ver'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

exiftool_available = check_exiftool() if USE_EXIFTOOL else False

def extract_locations_from_html(html_file):
    """Extract GPS coordinates from the HTML table."""
    if not os.path.exists(html_file):
        print(f"❌ '{html_file}' not found!")
        return []
    
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    locations = []
    
    # Find the table
    table = soup.select_one('body > div.rightpanel > table > tbody')
    if not table:
        print("⚠️  Table not found in the HTML!")
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
                break  # Nur eine Location pro Zeile
    
    return locations

def extract_urls_from_html(html_file):
    """Extract URLs and create an index mapping."""
    if not os.path.exists(html_file):
        return []
    
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    pattern = r"downloadMemories\('(.+?)',\s*this,\s*(true|false)\)"
    matches = re.findall(pattern, html_content)
    
    return [url for url, _ in matches]

def extract_unique_id_from_url(url):
    """Extract the unique ID (mid) from the URL."""
    mid_match = re.search(r'mid=([a-zA-Z0-9\-]+)', url)
    if mid_match:
        return mid_match.group(1)
    else:
        import hashlib
        return hashlib.md5(url.encode()).hexdigest()

def write_gps_to_file(filepath, latitude, longitude):
    """Write GPS coordinates into the file's EXIF data."""
    if not exiftool_available:
        return False
    
    if not os.path.exists(filepath):
        return False
    
    try:
        file_ext = os.path.splitext(filepath)[1].lower()
        filename = os.path.basename(filepath)
        
        # Skip overlay/thumbnail helper files
        if '-overlay' in filename.lower() or 'thumbnail' in filename.lower():
            return False
        
        # Convert to EXIF GPS format
        # GPSLatitude and GPSLongitude need refs (N/S, E/W)
        lat_ref = 'N' if latitude >= 0 else 'S'
        lon_ref = 'E' if longitude >= 0 else 'W'
        
        abs_lat = abs(latitude)
        abs_lon = abs(longitude)
        
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
            
            return result.returncode == 0
            
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
            
            return result.returncode == 0
        
        return False
        
    except Exception as e:
        print(f"[GPS ERROR] Failed to write for {os.path.basename(filepath)}: {e}")
        return False

def process_files_in_folder(folder_path, latitude, longitude):
    """Write GPS data for all files in a folder (extracted ZIPs)."""
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
    print("Location Metadata Extractor & Writer")
    print("=" * 60)
    print()
    
    # Check exiftool
    if USE_EXIFTOOL and not exiftool_available:
        print("❌ exiftool not found!")
        print("Install from https://exiftool.org/")
        print("Metadata will only be stored in JSON, not in files.")
        response = input("\nContinue anyway? (y/n): ")
        if response.lower() not in ['j', 'y', 'ja', 'yes']:
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
    
    print(f"📄 Found {len(downloaded_files)} entries in downloaded_files.json")
    
    # Extract locations from HTML
    print(f"📍 Extracting GPS coordinates from '{HTML_FILE}'...")
    locations = extract_locations_from_html(HTML_FILE)
    print(f"✅ {len(locations)} GPS coordinates found")
    
    # Extract URLs for mapping
    urls = extract_urls_from_html(HTML_FILE)
    print(f"✅ {len(urls)} URLs found")
    print()
    
    # Erstelle Metadata
    metadata = {}
    files_with_location = 0
    files_without_location = 0
    gps_written_count = 0
    gps_failed_count = 0
    
    for i, url in enumerate(urls):
        unique_id = extract_unique_id_from_url(url)
        
        # Ensure the file was downloaded
        if unique_id not in downloaded_files:
            continue
        
        file_info = downloaded_files[unique_id]
        filename = file_info.get('filename')
        
        # Add GPS coordinates when available
        location = locations[i] if i < len(locations) else None
        
        metadata[unique_id] = {
            'filename': filename,
            'date': file_info.get('date'),
            'content_type': file_info.get('content_type'),
            'location': location
        }
        
        if location:
            files_with_location += 1
            
            # Write GPS into file
            if exiftool_available:
                filepath = os.path.join(DOWNLOAD_FOLDER, filename)
                
                # Check whether it's a file or an extracted ZIP folder
                if os.path.isfile(filepath):
                    if write_gps_to_file(filepath, location['latitude'], location['longitude']):
                        gps_written_count += 1
                        print(f"✅ GPS written: {filename}")
                    else:
                        gps_failed_count += 1
                        print(f"⚠️  GPS failed: {filename}")
                
                elif os.path.isdir(filepath.replace('.zip', '')):
                    # Extracted ZIP folder
                    folder_path = filepath.replace('.zip', '')
                    count = process_files_in_folder(folder_path, location['latitude'], location['longitude'])
                    gps_written_count += count
                    print(f"✅ GPS written for {count} files in: {os.path.basename(folder_path)}/")
        else:
            files_without_location += 1
    
    # Save metadata.json
    print()
    print(f"💾 Saving '{METADATA_JSON}'...")
    
    with open(METADATA_JSON, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    # Summary
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"📊 Total processed: {len(metadata)} files")
    print(f"📍 With GPS coordinates: {files_with_location} files")
    print(f"❌ Without GPS coordinates: {files_without_location} files")
    
    if exiftool_available:
        print()
        print(f"✅ GPS written to files: {gps_written_count}")
        if gps_failed_count > 0:
            print(f"⚠️  GPS write errors: {gps_failed_count}")
    
    print()
    print(f"✅ '{METADATA_JSON}' created successfully!")

if __name__ == '__main__':
    main()