#!/bin/bash

# Snapchat Memories Downloader - Installer for Mac
# This script installs all necessary dependencies

set -e  # Exit on error

echo "=========================================="
echo "Snapchat Memories Downloader - Installer"
echo "=========================================="
echo ""

# Function for colored output
print_success() {
    echo "✅ $1"
}

print_error() {
    echo "❌ $1"
}

print_info() {
    echo "ℹ️  $1"
}

# Check if we're on a Mac
if [[ "$OSTYPE" != "darwin"* ]]; then
    print_error "This script only works on macOS!"
    exit 1
fi

print_info "Installation starting..."
echo ""

# 1. Install Homebrew (if not present)
echo "Step 1/5: Checking Homebrew..."
if ! command -v brew &> /dev/null; then
    print_info "Installing Homebrew..."
    print_info "You may be asked for your password."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add Homebrew to PATH (for Apple Silicon Macs)
    if [[ $(uname -m) == 'arm64' ]]; then
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
    
    print_success "Homebrew installed!"
else
    print_success "Homebrew is already installed!"
fi
echo ""

# 2. Install Python3
echo "Step 2/5: Checking Python3..."
if ! command -v python3 &> /dev/null; then
    print_info "Installing Python3..."
    brew install python3
    print_success "Python3 installed!"
else
    print_success "Python3 is already installed!"
    python3 --version
fi
echo ""

# 3. Install ExifTool
echo "Step 3/5: Checking ExifTool..."
if ! command -v exiftool &> /dev/null; then
    print_info "Installing ExifTool..."
    brew install exiftool
    print_success "ExifTool installed!"
else
    print_success "ExifTool is already installed!"
fi
echo ""

# 4. Install ffmpeg
echo "Step 4/5: Checking ffmpeg..."
if ! command -v ffmpeg &> /dev/null; then
    print_info "Installing ffmpeg (for video processing)..."
    brew install ffmpeg
    print_success "ffmpeg installed!"
else
    print_success "ffmpeg is already installed!"
fi
echo ""

# 5. Install Python libraries
echo "Step 5/5: Installing Python libraries..."
print_info "Installing: requests, beautifulsoup4, Pillow..."

# Check if pip3 is available
if ! command -v pip3 &> /dev/null; then
    print_error "pip3 not found. Reinstalling Python..."
    brew reinstall python3
fi

pip3 install --upgrade pip --quiet
pip3 install requests beautifulsoup4 Pillow --quiet

print_success "Python libraries installed!"
echo ""

# Installation complete
echo "=========================================="
print_success "Installation completed successfully!"
echo "=========================================="
echo ""
echo "📝 Next steps:"
echo ""
echo "1. Download your Snapchat Memories HTML file"
echo "   (from Snapchat: Settings → My Data → Download Data)"
echo ""
echo "2. Place the HTML file in the same folder as"
echo "   the 'snapchat-downloader.py' script"
echo ""
echo "3. Rename the HTML file to: memories_history.html"
echo ""
echo "4. Open Terminal and navigate to the folder:"
echo "   cd /path/to/folder"
echo ""
echo "5. Run the script:"
echo "   python3 snapchat-downloader.py"
echo ""
echo "=========================================="
echo ""

# Optional: Open script folder
read -p "Would you like to open the downloads folder now? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[JjYy]$ ]]; then
    # Open the folder where the script is located
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    open "$SCRIPT_DIR"
fi

echo ""
print_success "Good luck downloading your memories! 📸"
