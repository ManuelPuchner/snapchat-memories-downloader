#!/usr/bin/env python3
"""
Script to detect and remove duplicates in extracted ZIP folders.
"""

import os
import hashlib
from pathlib import Path

# Configuration
DOWNLOAD_FOLDER = 'snapchat_memories'
DRY_RUN = True  # Set to False to actually delete files

def calculate_file_hash(filepath):
    """Calculate SHA256 hash for a file."""
    sha256_hash = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception as e:
        print(f"❌ Error while computing hash for {filepath}: {e}")
        return None

def find_duplicates_in_folder(folder_path):
    """Find duplicates in a folder based on file hashes."""
    files = []
    
    for item in os.listdir(folder_path):
        item_path = os.path.join(folder_path, item)
        if os.path.isfile(item_path):
            files.append(item_path)
    
    if len(files) < 2:
        return []
    
    # Calculate hashes for all files
    file_hashes = {}
    for filepath in files:
        file_hash = calculate_file_hash(filepath)
        if file_hash:
            if file_hash not in file_hashes:
                file_hashes[file_hash] = []
            file_hashes[file_hash].append(filepath)
    
    # Find duplicates (hash present for multiple files)
    duplicates = []
    for file_hash, filepaths in file_hashes.items():
        if len(filepaths) > 1:
            # Keep the file whose name matches the folder name
            folder_name = os.path.basename(folder_path)
            
            # Extract UUID/ID from folder name (format: YYYYMMDD_HHMMSS_UUID)
            folder_uuid = folder_name.split('_', 2)[-1] if '_' in folder_name else folder_name
            
            primary = None
            to_delete = []
            
            for filepath in filepaths:
                filename = os.path.basename(filepath)
                # Check if filename starts with the folder UUID
                if filename.startswith(folder_uuid):
                    primary = filepath
                else:
                    to_delete.append(filepath)
            
            # If no match with folder UUID, keep the first file
            if primary is None:
                primary = filepaths[0]
                to_delete = filepaths[1:]
            
            if to_delete:
                duplicates.append({
                    'hash': file_hash,
                    'keep': primary,
                    'delete': to_delete
                })
    
    return duplicates

def process_folders(directory, dry_run=True):
    """Process all folders and find duplicates."""
    if not os.path.exists(directory):
        print(f"❌ Folder '{directory}' does not exist!")
        return
    
    folders_with_duplicates = []
    total_duplicates = 0
    deleted_count = 0
    
    # Iterate through all subfolders
    for item in os.listdir(directory):
        item_path = os.path.join(directory, item)
        
        if os.path.isdir(item_path):
            duplicates = find_duplicates_in_folder(item_path)
            
            if duplicates:
                folders_with_duplicates.append({
                    'folder': item,
                    'path': item_path,
                    'duplicates': duplicates
                })
                
                # Count all files to delete
                for dup in duplicates:
                    total_duplicates += len(dup['delete'])
    
    if not folders_with_duplicates:
        print("✅ No duplicates found!")
        return
    
    print(f"📊 Found {len(folders_with_duplicates)} folder(s) with duplicates")
    print(f"🗑️  Total duplicates to delete: {total_duplicates}\n")
    print("=" * 80)
    print()
    
    # Process each folder
    for folder_info in folders_with_duplicates:
        folder_name = folder_info['folder']
        duplicates = folder_info['duplicates']
        
        print(f"📁 {folder_name}/")
        print(f"   Found: {len(duplicates)} duplicate group(s)")
        print()
        
        for dup in duplicates:
            keep_file = os.path.basename(dup['keep'])
            print(f"   ✅ KEEP: {keep_file}")
            
            for delete_file in dup['delete']:
                delete_filename = os.path.basename(delete_file)
                print(f"   🗑️  DELETE:  {delete_filename}")
                
                if not dry_run:
                    try:
                        os.remove(delete_file)
                        deleted_count += 1
                        print(f"      → Deleted!")
                    except Exception as e:
                        print(f"      ❌ Error: {e}")
            
            print()
        
        print("-" * 80)
        print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    if dry_run:
        print("⚠️  DRY RUN MODE - No files deleted!")
        print()
        print(f"📊 Folders with duplicates: {len(folders_with_duplicates)}")
        print(f"🗑️  Files to delete: {total_duplicates}")
        print()
        print("💡 To delete the duplicates:")
        print("   Set DRY_RUN = False in the script")
    else:
        print(f"✅ Successfully deleted: {deleted_count} files")
        if deleted_count < total_duplicates:
            print(f"⚠️  Errors on: {total_duplicates - deleted_count} files")

def main():
    print("=" * 80)
    print("Deduplicate ZIP Folder Contents")
    print("=" * 80)
    print()
    
    if DRY_RUN:
        print("⚠️  DRY RUN MODE - Preview only, no changes")
        print()
    else:
        print("⚠️  WARNING: Duplicates will actually be deleted!")
        response = input("Continue? (y/n): ")
        if response.lower() not in ['j', 'y', 'ja', 'yes']:
            print("Cancelled.")
            return
        print()
    
    process_folders(DOWNLOAD_FOLDER, dry_run=DRY_RUN)

if __name__ == '__main__':
    main()