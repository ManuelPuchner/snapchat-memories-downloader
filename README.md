# Snapchat Memories Downloader

Since Snapchat wants you to pay for more than 5GB of memories, this script downloads all your memories. The version Snapchat provides has bugs where it says 100% downloaded but actually downloaded nothing (at least in some cases).

## Credits

This is a fork of [ManuelPuchner/snapchat-memories-downloader](https://github.com/ManuelPuchner/snapchat-memories-downloader) with improvements for zero-setup usage and test mode. Thanks to Manuel for the original implementation! 🙏

Feel free to contribute! 👍

## 🚀 Quick Start (Zero Setup Required)

### 1. Get your data from Snapchat

1. Go to https://accounts.snapchat.com
2. Click **My Data**
3. Select **Export your Memories** → **Request Only Memories**
4. Select **All Time**
5. Confirm email and click **Submit**
6. Wait for the email (may take hours/days) with download link
7. Download the data and place `memories_history.html` in this folder

### 2. Test first (recommended)

```bash
python3 run_all.py --test
```

This downloads just 5 files and runs them through the complete pipeline. Check the `snapchat_memories/` folder to verify everything works.

### 3. Run the full download

```bash
python3 run_all.py --full
```

**That's it.** No venv, no manual dependency installation - the script handles everything automatically.

## 📋 What it does

1. **📥 Downloads** all memories from the HTML file (parallel downloads for speed)
2. **📍 Adds GPS metadata** to files with location data
3. **🔧 Combines overlays** - merges text/sticker overlays with base images/videos
4. **🗑️ Removes duplicates** in extracted folders
5. **📅 Writes proper dates** to file metadata (so they sort correctly in Photos)

## ⚡ Command Line Options

```bash
python3 run_all.py              # Interactive menu
python3 run_all.py --test       # Test mode: download 5 files
python3 run_all.py --test 10    # Test mode: download 10 files
python3 run_all.py --full       # Skip menu, run all steps immediately
```

## 🔧 Optional Tools (for best results)

```bash
brew install exiftool ffmpeg
```

- **exiftool** - Writes date/GPS metadata to files (required for Photos app to show correct dates)
- **ffmpeg** - Combines video overlays (text/stickers on videos)

## 📁 Files Created

- `snapchat_memories/` - Your downloaded memories (organized by date). Snaps with text/emojis/stickers are downloaded as ZIPs containing layers and extracted automatically.
- `downloaded_files.json` - Progress tracker (resume downloads after interruptions)
- `download_errors.json` - Failed downloads (if any)
- `metadata.json` - Extracted metadata

## 🔄 Trying failed downloads again

If some files fail to download:
1. Delete the `download_errors.json` file
2. Run the download script again
3. If files still fail, try visiting the download link in your browser - maybe Snapchat's servers don't have the file anymore

## 🐛 Troubleshooting

**Downloads failing?**
- Delete `download_errors.json` and run again
- Some files may be missing on Snapchat's servers (try again later)

**Metadata not being written?**
- Install exiftool: `brew install exiftool`

**Video overlays not combining?**
- Install ffmpeg: `brew install ffmpeg`

**Script won't run?**
- Make sure you have Python 3: `python3 --version`
- The script creates its own virtual environment automatically

## 📸 File Organization

Files are saved as: `YYYYMMDD_HHMMSS_uniqueid.ext`

Example: `20231214_143022_abcd1234.jpg`

This ensures proper chronological sorting in your Photos app.

## 🔄 Resume Downloads

If your download gets interrupted, just run the script again - it will resume from where it left off using the progress files.

## 📊 Manual Steps (if needed)

If you prefer to run steps individually:

```bash
# Just download memories
python3 run_all.py --test  # or --full

# Just add GPS metadata
python3 metadata.py

# Just combine overlays
python3 combine_overlays.py

# Just delete duplicates
python3 delete-dupes.py
```

## 🖥️ macOS-Specific Tips

**Reimport data into Photos:**
```bash
mdimport -r snapchat_memories/
```

**Correct file timestamps to match creation dates:**
```bash
exiftool "-FileCreateDate<CreateDate" "-FileModifyDate<CreateDate" -ext mp4 -r snapchat_memories/
exiftool "-FileCreateDate<CreateDate" "-FileModifyDate<CreateDate" -ext jpg -r snapchat_memories/
```
