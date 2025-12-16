#!/bin/bash

# Snapchat Memories Downloader - macOS installer
# This script installs all required dependencies

set -e  # Exit on any error

echo "=========================================="
echo "Snapchat Memories Downloader - Installer"
echo "=========================================="
echo ""

# Colored output helpers
print_success() {
    echo "✅ $1"
}

print_error() {
    echo "❌ $1"
}

print_info() {
    echo "ℹ️  $1"
}

# Ensure we're on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    print_error "This script only works on macOS!"
    exit 1
fi

print_info "Installation startet..."
echo ""

# 1. Install Homebrew if missing
echo "Step 1/4: Checking Homebrew..."
if ! command -v brew &> /dev/null; then
    print_info "Installing Homebrew..."
    print_info "You might be asked for your password."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add Homebrew to PATH (Apple Silicon Macs)
    if [[ $(uname -m) == 'arm64' ]]; then
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
    
    print_success "Homebrew installed!"
else
    print_success "Homebrew already installed!"
fi
echo ""

# 2. Install Python3
echo "Step 2/4: Checking Python3..."
if ! command -v python3 &> /dev/null; then
    print_info "Installing Python3..."
    brew install python3
    print_success "Python3 installed!"
else
    print_success "Python3 already installed!"
    python3 --version
fi
echo ""

# 3. Install ExifTool
echo "Step 3/4: Checking ExifTool..."
if ! command -v exiftool &> /dev/null; then
    print_info "Installing ExifTool..."
    brew install exiftool
    print_success "ExifTool installed!"
else
    print_success "ExifTool already installed!"
fi
echo ""

# 4. Install Python libraries
echo "Step 4/4: Installing Python libraries..."
print_info "Installing: requests, beautifulsoup4..."

# Ensure pip3 is available
if ! command -v pip3 &> /dev/null; then
    print_error "pip3 not found. Please reinstall Python..."
    brew reinstall python3
fi

pip3 install --upgrade pip --quiet
pip3 install requests beautifulsoup4 --quiet

print_success "Python libraries installed!"
echo ""

# Installation abgeschlossen
echo "=========================================="
print_success "Installation completed successfully!"
echo "=========================================="
echo ""
echo "📝 Next steps:"
echo ""
echo "1. Download your Snapchat Memories HTML file"
echo "   (From Snapchat: Settings → My Data → Download My Data)"
echo ""
echo "2. Place the HTML file in the same folder as"
echo "   the 'snapchat_downloader.py' script"
echo ""
echo "3. Rename the HTML file to: memories_history.html"
echo ""
echo "4. Open Terminal and navigate to the folder:"
echo "   cd /Pfad/zum/Ordner"
echo ""
echo "5. Run the script:"
echo "   python3 snapchat_downloader.py"
echo ""
echo "=========================================="
echo ""

# Optional: open the script folder
read -p "Open the downloads folder now? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[JjYy]$ ]]; then
    # Open the folder containing the script
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    open "$SCRIPT_DIR"
fi

echo ""
print_success "Happy downloading! 📸"