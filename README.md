# Snapchat Memories Downloader
Since snapchat wants you to pay for more than 5gb of snapchat memories, I made a script to download all your memories since the version snapchat provided has a bug where it says 100% is downloaded but in reality it didn't download anything (at least in my case)

## Disclaimer
Everything i did here was vibe coded, i wanted it do be done quickly and it worked for me.
I think it's even better than the original, since I am adding metadata to the files, which snapchat doesn't
Feel free to contribute 👍🙏

# How to run
1. create a python venv
    ```bash
    python3 -m venv .venv
    ```
2. activate python venv
    ```bash
    # mac/linux
    source .venv/bin/activate

    # windows
    .\.venv\Scripts\Activate.ps1
    ```
3. check python venv
    ```bash
    # mac/linux
    which python

    # windows
    Get-Command python
    ```

4. run installer script (mac/linux)
    ```bash
    chmod +x ./installer.sh
    ./installer.sh
    ```
   1. helper if operation not permitted (mac):
        ```bash
        xattr -d com.apple.quarantine ./installer.sh
        ```

1. request the download from snapchat
- go to https://accounts.snapchat.com
- click on `My Data`
- select `Export your Memories` and click `Request Only Memories`
- select `All Time`
- confirm email and click `Submit`
- after some time you'll get a mail with the download link. Follow the instructions and download the data

6. paste the `memories_history.html` file in the project root (same folder as `snapchat-downloader.py`)
for some reason snapchat doesn't let you download all your memories in a single (or multiple) zip files, but just gives you a html file (which is buggy at least for me) which lets you download all your memories.

7. run download script
    ```bash
    python snapchat-downloader.py
    ```
The script then downloads all your memories
It creates the following folders/files 
- `./snapchat_memories/`: Folder where all your memories are stored. The script automatically edits the metadata, so your files have the correct date. Files also have the prefix with the correct date and time.
Snaps with text, emojis or stickers are downloaded as zips containing all the layers. These zip files are extracted automatically.
- `downloaded_files.json`: Json file containing some information about the downloaded files
- `download_errors.json`: Json file containing files which had a download error

8. Trying failed downloads again
- Simply run the download script again: `python snapchat-downloader.py`
- Successfully retried downloads will be automatically removed from `download_errors.json`
- If any files still fail, try visiting the download link in your browser to verify the file exists (might be a Snapchat issue)
- The script will continue to retry failed downloads on subsequent runs

9. Adding Location Metadata
    ```bash
    python metadata.py
    ```

10.  Managing Overlays

The `overlay-manager.py` script helps manage Snapchat memories that have text, stickers, or captions.

**Option A: Combine overlays with base files**
- If you want captions/text/stickers merged onto your photos and videos:
    ```bash
    # Preview what will be created (dry run)
    python overlay-manager.py combine

    # Actually create combined files (saved to snapchat_memories_combined/)
    python overlay-manager.py combine --execute

    # Optional - Custom JPEG quality (1-100, default: 100 for maximum quality)
    # Use lower values like 85-95 to save disk space with minimal quality loss
    python overlay-manager.py combine --execute --quality 90
    ```
- Combined files are saved to `snapchat_memories_combined/` folder. 
  - Originals remain unchanged.
- **Note:** Video processing requires ffmpeg (already installed if you used `installer.sh`). Manual install: `brew install ffmpeg` (macOS) or `sudo apt-get install ffmpeg` (Linux)

**Option B: Remove duplicate files**
- Clean up duplicates in folders with overlay layers:
    ```bash
    # Preview what will be deleted (dry run)
    python overlay-manager.py dedupe

    # Actually delete duplicates
    python overlay-manager.py dedupe --execute
    ```

11. You're Done! 🎉

---
Your Snapchat memories are now fully downloaded and organized in the `snapchat_memories/` folder with:
- ✅ Correct dates and timestamps (both EXIF metadata and file system dates)
- ✅ Location data (if available)
- ✅ No duplicates
- ✅ Properly indexed by Spotlight (macOS)

---

### Troubleshooting: If you ran scripts before the timestamp fixes

If you previously ran `metadata.py` or `overlay-manager.py` before these timestamp preservation fixes were added, your files might have incorrect dates. To fix them:

**Option 1: Re-run the scripts** (Recommended)
- The scripts now preserve original timestamps, so running them again will fix the dates

**Option 2: Manual timestamp correction** (If needed)
- Sync file system timestamps with EXIF metadata:
```bash
# For original memories
exiftool -progress "-FileCreateDate<CreateDate" "-FileModifyDate<CreateDate" -ext mp4 -r snapchat_memories/
exiftool -progress "-FileCreateDate<CreateDate" "-FileModifyDate<CreateDate" -ext jpg -r snapchat_memories/

# For combined files (if you used the combine option)
exiftool -progress "-FileCreateDate<CreateDate" "-FileModifyDate<CreateDate" -ext mp4 -r snapchat_memories_combined/
exiftool -progress "-FileCreateDate<CreateDate" "-FileModifyDate<CreateDate" -ext jpg -r snapchat_memories_combined/
```

- Re-index for Spotlight (macOS):
```bash
mdimport -r snapchat_memories/
mdimport -r snapchat_memories_combined/  # if applicable
```

---

### What to do next:

**Keep as Backup:**
Your memories are now in a standard format (MP4 and JPG files) that will work on any device or platform. Store them safely as a backup.

**Cloud Storage:**
Upload to Google Photos, iCloud, Dropbox, or any cloud service. The metadata will be preserved wherever you store them.
