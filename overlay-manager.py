#!/usr/bin/env python3
"""
Snapchat Memories Manager - Unified utility for managing Snapchat memories
Combines deduplication and overlay merging functionality
"""

import os
import sys
import argparse
import hashlib
import subprocess
from pathlib import Path
from PIL import Image

# Configuration
SOURCE_FOLDER = 'snapchat_memories'
OUTPUT_FOLDER = 'snapchat_memories_combined'
DEFAULT_JPEG_QUALITY = 95

# ==============================================================================
# DEDUPLICATION FUNCTIONS (from delete-dupes.py)
# ==============================================================================

def calculate_file_hash(filepath):
    """Calculate SHA256 hash of a file"""
    sha256_hash = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception as e:
        print(f"❌ Error calculating hash for {filepath}: {e}")
        return None

def find_duplicates_in_folder(folder_path):
    """Find duplicates in a folder based on hash"""
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
    
    # Find duplicates (hash with multiple files)
    duplicates = []
    for file_hash, filepaths in file_hashes.items():
        if len(filepaths) > 1:
            # Sort: Keep the file that matches the folder name
            folder_name = os.path.basename(folder_path)
            
            # Extract UUID/ID from folder name (format: YYYYMMDD_HHMMSS_UUID)
            folder_uuid = folder_name.split('_', 2)[-1] if '_' in folder_name else folder_name
            
            primary = None
            to_delete = []
            
            for filepath in filepaths:
                filename = os.path.basename(filepath)
                # Check if filename starts with folder UUID
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

def process_deduplication(directory, dry_run=True):
    """Process all folders and find duplicates"""
    if not os.path.exists(directory):
        print(f"❌ Folder '{directory}' does not exist!")
        return
    
    folders_with_duplicates = []
    total_duplicates = 0
    deleted_count = 0
    
    # Search all subfolders
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
    
    print(f"📊 {len(folders_with_duplicates)} folders with duplicates found")
    print(f"🗑️  Total {total_duplicates} duplicates to delete\n")
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
            print(f"   ✅ KEEP:   {keep_file}")
            
            for delete_file in dup['delete']:
                delete_filename = os.path.basename(delete_file)
                print(f"   🗑️  DELETE: {delete_filename}")
                
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
        print("💡 To actually delete duplicates, rerun with --execute flag:")
        print("   python overlay-manager.py dedupe --execute")
    else:
        print(f"✅ Successfully deleted: {deleted_count} files")
        if deleted_count < total_duplicates:
            print(f"⚠️  Errors with: {total_duplicates - deleted_count} files")

# ==============================================================================
# OVERLAY COMBINING FUNCTIONS (from combine-overlays.py)
# ==============================================================================

def check_ffmpeg_available():
    """Check if ffmpeg is installed and available"""
    try:
        subprocess.run(['ffmpeg', '-version'], 
                      capture_output=True, 
                      check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def find_overlay_folders(directory):
    """
    Scan directory and find all folders containing overlay files
    Returns list of dicts with folder info and file paths
    """
    overlay_folders = []
    
    if not os.path.exists(directory):
        print(f"❌ Folder '{directory}' does not exist!")
        return overlay_folders
    
    print("🔍 Scanning for memories with overlays...")
    
    for item in os.listdir(directory):
        item_path = os.path.join(directory, item)
        
        # Only process directories
        if not os.path.isdir(item_path):
            continue
        
        # Look for overlay files in this folder
        files = os.listdir(item_path)
        
        # Find overlay and main files
        overlay_files = [f for f in files if '-overlay.png' in f.lower()]
        main_images = [f for f in files if '-main.jpg' in f.lower()]
        main_videos = [f for f in files if '-main.mp4' in f.lower()]
        
        if overlay_files:
            folder_info = {
                'folder_name': item,
                'folder_path': item_path,
                'overlays': [os.path.join(item_path, f) for f in overlay_files],
                'base_image': os.path.join(item_path, main_images[0]) if main_images else None,
                'base_video': os.path.join(item_path, main_videos[0]) if main_videos else None,
                'is_image': bool(main_images),
                'is_video': bool(main_videos)
            }
            overlay_folders.append(folder_info)
    
    return overlay_folders

def combine_image(base_path, overlay_path, output_path, quality=DEFAULT_JPEG_QUALITY):
    """
    Composite overlay PNG onto base JPG image
    Preserves EXIF metadata from base image
    """
    try:
        # Load base image and overlay
        base_img = Image.open(base_path)
        base = base_img.convert('RGB')
        overlay = Image.open(overlay_path).convert('RGBA')
        
        # Resize overlay to match base image dimensions if needed
        if overlay.size != base.size:
            overlay = overlay.resize(base.size, Image.Resampling.LANCZOS)
        
        # Composite: paste overlay on top of base using alpha channel
        base.paste(overlay, (0, 0), overlay)
        
        # Try to preserve EXIF data using Pillow's built-in methods
        exif_data = None
        try:
            exif_data = base_img.info.get('exif')
        except Exception:
            pass
        
        # Save combined image
        if exif_data:
            base.save(output_path, 'JPEG', quality=quality, exif=exif_data)
        else:
            base.save(output_path, 'JPEG', quality=quality)
        
        return True
    except Exception as e:
        print(f"      ❌ Error combining image: {e}")
        return False

def combine_video(base_path, overlay_path, output_path):
    """
    Burn overlay PNG onto video using ffmpeg
    Preserves video codec, audio, and metadata
    """
    try:
        # ffmpeg command to overlay PNG on video
        # Using overlay filter to composite the PNG on top
        cmd = [
            'ffmpeg',
            '-i', base_path,           # Input video
            '-i', overlay_path,        # Input overlay
            '-filter_complex', '[0:v][1:v]overlay=0:0',  # Overlay at position 0,0
            '-c:a', 'copy',            # Copy audio without re-encoding
            '-y',                      # Overwrite output file
            output_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"      ❌ ffmpeg error: {e.stderr}")
        return False
    except Exception as e:
        print(f"      ❌ Error combining video: {e}")
        return False

def process_overlay_combining(source_dir, output_dir, dry_run=True, quality=DEFAULT_JPEG_QUALITY, has_ffmpeg=False):
    """
    Main processing function for combining overlays
    Finds all overlay folders and combines them
    """
    # Find all folders with overlays
    overlay_folders = find_overlay_folders(source_dir)
    
    if not overlay_folders:
        print("✅ No memories with overlays found!")
        return
    
    # Count what we found
    image_count = sum(1 for f in overlay_folders if f['is_image'])
    video_count = sum(1 for f in overlay_folders if f['is_video'])
    
    print(f"\n📊 Found {len(overlay_folders)} memories with overlays:")
    print(f"   📷 Images: {image_count}")
    print(f"   🎥 Videos: {video_count}")
    
    if video_count > 0 and not has_ffmpeg:
        print("\n⚠️  WARNING: ffmpeg not found!")
        print("   Videos with overlays will be skipped.")
        print("   Install ffmpeg to process videos: brew install ffmpeg (macOS)")
    
    print("\n" + "=" * 80)
    print()
    
    # Create output directory if not dry run
    if not dry_run:
        os.makedirs(output_dir, exist_ok=True)
    
    # Process each folder
    processed_images = 0
    processed_videos = 0
    skipped_videos = 0
    errors = 0
    
    for idx, folder_info in enumerate(overlay_folders, 1):
        folder_name = folder_info['folder_name']
        print(f"[{idx}/{len(overlay_folders)}] 📁 {folder_name}")
        
        # Determine output filename
        # Remove trailing slash and use folder name as base
        output_filename = f"{folder_name}_combined"
        
        if folder_info['is_image']:
            output_filename += '.jpg'
            output_path = os.path.join(output_dir, output_filename)
            
            if dry_run:
                print(f"   Would create: {output_filename}")
            else:
                print(f"   Creating: {output_filename}")
                success = combine_image(
                    folder_info['base_image'],
                    folder_info['overlays'][0],  # Use first overlay
                    output_path,
                    quality
                )
                if success:
                    processed_images += 1
                    print(f"   ✅ Saved!")
                else:
                    errors += 1
        
        elif folder_info['is_video']:
            if not has_ffmpeg:
                print(f"   ⏭️  Skipping video (ffmpeg not available)")
                skipped_videos += 1
            else:
                output_filename += '.mp4'
                output_path = os.path.join(output_dir, output_filename)
                
                if dry_run:
                    print(f"   Would create: {output_filename}")
                else:
                    print(f"   Creating: {output_filename}")
                    success = combine_video(
                        folder_info['base_video'],
                        folder_info['overlays'][0],  # Use first overlay
                        output_path
                    )
                    if success:
                        processed_videos += 1
                        print(f"   ✅ Saved!")
                    else:
                        errors += 1
        
        print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    if dry_run:
        print("⚠️  DRY RUN MODE - No files created!")
        print()
        print(f"📊 Would create:")
        print(f"   📷 Images: {image_count}")
        print(f"   🎥 Videos: {video_count if has_ffmpeg else 0}")
        if skipped_videos > 0:
            print(f"   ⏭️  Skipped videos: {skipped_videos} (ffmpeg not available)")
        print()
        print("💡 To actually create the combined files, rerun with --execute flag:")
        print("   python overlay-manager.py combine --execute")
    else:
        print(f"✅ Successfully created:")
        print(f"   📷 Images: {processed_images}")
        print(f"   🎥 Videos: {processed_videos}")
        if skipped_videos > 0:
            print(f"   ⏭️  Skipped videos: {skipped_videos} (ffmpeg not available)")
        if errors > 0:
            print(f"   ❌ Errors: {errors}")
        print()
        print(f"📂 Files saved to: {output_dir}/")

# ==============================================================================
# CLI INTERFACE
# ==============================================================================

def handle_dedupe_command(args):
    """Handle the dedupe subcommand"""
    dry_run = not args.execute
    
    print("=" * 80)
    print("Deduplicate Snapchat Memories")
    print("=" * 80)
    print()
    
    if dry_run:
        print("⚠️  DRY RUN MODE - Preview only, no changes")
        print()
    else:
        print("⚠️  WARNING: Duplicates will actually be deleted!")
        if not args.skip_prompt:
            response = input("Continue? (y/n): ")
            if response.lower() not in ['y', 'yes']:
                print("Cancelled.")
                return
        print()
    
    process_deduplication(SOURCE_FOLDER, dry_run=dry_run)

def handle_combine_command(args):
    """Handle the combine subcommand"""
    dry_run = not args.execute
    
    # Validate quality
    if not 1 <= args.quality <= 100:
        print("❌ Quality must be between 1 and 100")
        sys.exit(1)
    
    print("=" * 80)
    print("Combine Snapchat Overlays")
    print("=" * 80)
    print()
    
    # User-friendly prompt (unless skipped)
    if not args.skip_prompt and not dry_run:
        print("This script combines Snapchat captions, text, emojis, and stickers")
        print("with your base photos and videos into single files.")
        print()
        print("The combined files will be saved to a separate folder:")
        print(f"  → {OUTPUT_FOLDER}/")
        print()
        print("Your original files in 'snapchat_memories/' will NOT be modified.")
        print()
        response = input("Do you want to keep your Snapchat captions/text/stickers on your memories? (y/n): ")
        if response.lower() not in ['y', 'yes']:
            print("Cancelled.")
            return
        print()
    
    # Check for ffmpeg
    has_ffmpeg = check_ffmpeg_available()
    if not has_ffmpeg:
        print("⚠️  ffmpeg not found - videos will be skipped")
        print("   To process videos, install ffmpeg:")
        print("   macOS: brew install ffmpeg")
        print("   Linux: sudo apt-get install ffmpeg")
        print()
    
    if dry_run:
        print("⚠️  DRY RUN MODE - Preview only, no files will be created")
        print()
    else:
        print(f"Creating combined files in: {OUTPUT_FOLDER}/")
        print()
    
    process_overlay_combining(SOURCE_FOLDER, OUTPUT_FOLDER, dry_run=dry_run, quality=args.quality, has_ffmpeg=has_ffmpeg)

def main():
    """Main entry point with subcommand parsing"""
    parser = argparse.ArgumentParser(
        description='Snapchat Memories Manager - Unified utility for managing Snapchat memories',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Deduplicate files (dry run)
  python overlay-manager.py dedupe
  
  # Actually delete duplicates
  python overlay-manager.py dedupe --execute
  
  # Combine overlays (dry run)
  python overlay-manager.py combine
  
  # Actually create combined files
  python overlay-manager.py combine --execute
  
  # Custom JPEG quality
  python overlay-manager.py combine --execute --quality 90
        """
    )
    
    # Create subparsers for dedupe and combine commands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    subparsers.required = True
    
    # Dedupe subcommand
    dedupe_parser = subparsers.add_parser(
        'dedupe',
        help='Remove duplicate files from Snapchat memories folders'
    )
    dedupe_parser.add_argument(
        '--execute',
        action='store_true',
        help='Actually delete duplicates (default is dry run mode)'
    )
    dedupe_parser.add_argument(
        '--skip-prompt',
        action='store_true',
        help='Skip the confirmation prompt (for automation)'
    )
    dedupe_parser.set_defaults(func=handle_dedupe_command)
    
    # Combine subcommand
    combine_parser = subparsers.add_parser(
        'combine',
        help='Combine overlay layers with base images and videos'
    )
    combine_parser.add_argument(
        '--execute',
        action='store_true',
        help='Actually create combined files (default is dry run mode)'
    )
    combine_parser.add_argument(
        '--quality',
        type=int,
        default=DEFAULT_JPEG_QUALITY,
        help=f'JPEG quality for combined images (1-100, default: {DEFAULT_JPEG_QUALITY})'
    )
    combine_parser.add_argument(
        '--skip-prompt',
        action='store_true',
        help='Skip the initial confirmation prompt (for automation)'
    )
    combine_parser.set_defaults(func=handle_combine_command)
    
    # Parse arguments and call appropriate handler
    args = parser.parse_args()
    args.func(args)

if __name__ == '__main__':
    main()

