#!/bin/bash
# LinkedIn Checker - Automated Windows EXE Builder for Linux
# Usage: ./build_linkedin_exe.sh

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}LinkedIn Checker - Windows EXE Builder${NC}"
echo "========================================"

# Check if script is run from correct directory
if [ ! -f "linkedin_checker.py" ]; then
    echo -e "${RED}Error: linkedin_checker.py not found in current directory${NC}"
    echo "Please run this script from the directory containing your Python file"
    exit 1
fi

# Function to print status
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    print_error "Don't run this script as root!"
    exit 1
fi

print_status "Starting automated build process..."

# Step 1: Install system dependencies
print_status "Installing system dependencies..."
sudo apt update
sudo apt install -y wget wine winetricks xvfb

# Step 2: Setup Wine environment
print_status "Setting up Wine environment..."
export WINEARCH=win64
export WINEPREFIX="$HOME/.wine_linkedin"

# Create new Wine prefix
if [ ! -d "$WINEPREFIX" ]; then
    print_status "Creating new Wine prefix..."
    winecfg &
    sleep 3
    pkill winecfg || true
fi

# Step 3: Download Python for Windows
PYTHON_VERSION="3.11.9"
PYTHON_INSTALLER="python-${PYTHON_VERSION}-amd64.exe"
PYTHON_URL="https://www.python.org/ftp/python/${PYTHON_VERSION}/${PYTHON_INSTALLER}"

print_status "Downloading Python ${PYTHON_VERSION} for Windows..."
cd /tmp

if [ ! -f "$PYTHON_INSTALLER" ]; then
    wget "$PYTHON_URL"
else
    print_warning "Python installer already exists, skipping download"
fi

# Step 4: Install Python in Wine
print_status "Installing Python in Wine..."
wine "$PYTHON_INSTALLER" /quiet InstallAllUsers=1 PrependPath=1 InstallLauncherAllUsers=1

# Wait for installation to complete
sleep 10

# Step 5: Verify Python installation
print_status "Verifying Python installation..."
PYTHON_PATH="$HOME/.wine_linkedin/drive_c/Program Files/Python311/python.exe"

if [ ! -f "$PYTHON_PATH" ]; then
    # Try alternative path
    PYTHON_PATH="$HOME/.wine_linkedin/drive_c/users/$USER/AppData/Local/Programs/Python/Python311/python.exe"
fi

if [ ! -f "$PYTHON_PATH" ]; then
    print_error "Python installation failed or not found"
    exit 1
fi

# Step 6: Install Python dependencies
print_status "Installing Python dependencies..."
wine "$PYTHON_PATH" -m pip install --upgrade pip
wine "$PYTHON_PATH" -m pip install selenium==4.15.2
wine "$PYTHON_PATH" -m pip install webdriver-manager==4.0.1
wine "$PYTHON_PATH" -m pip install customtkinter==5.2.0
wine "$PYTHON_PATH" -m pip install Pillow==10.1.0
wine "$PYTHON_PATH" -m pip install pyinstaller==6.2.0

# Step 7: Go back to project directory
cd - > /dev/null

# Step 8: Create requirements.txt for reference
print_status "Creating requirements.txt..."
cat > requirements.txt << EOF
selenium==4.15.2
webdriver-manager==4.0.1
customtkinter==5.2.0
Pillow==10.1.0
pyinstaller==6.2.0
EOF

# Step 9: Create sample input file if it doesn't exist
if [ ! -f "linkedin_links.txt" ]; then
    print_status "Creating sample linkedin_links.txt..."
    cat > linkedin_links.txt << EOF
# LinkedIn Premium Trial Links
# Add your links below (one per line)
# Example:
# https://www.linkedin.com/premium/survey/your-link-here
EOF
fi

# Step 10: Build Windows EXE
print_status "Building Windows EXE with PyInstaller..."

# Set Wine environment
export WINEPATH="$HOME/.wine_linkedin/drive_c/Program Files/Python311;$HOME/.wine_linkedin/drive_c/Program Files/Python311/Scripts"

# Find PyInstaller path
PYINSTALLER_PATH="$HOME/.wine_linkedin/drive_c/Program Files/Python311/Scripts/pyinstaller.exe"

# Build the EXE
wine "$PYINSTALLER_PATH" \
    --onedir \
    --windowed \
    --name "LinkedInChecker" \
    --icon=icon.ico \
    --add-data "linkedin_links.txt;." \
    --hidden-import customtkinter \
    --hidden-import PIL \
    --hidden-import selenium \
    --hidden-import webdriver_manager \
    --collect-all customtkinter \
    linkedin_checker.py

# Step 11: Check if build was successful
if [ -f "dist/LinkedInChecker/LinkedInChecker.exe" ]; then
    print_status "Build successful!"
    print_status "Your Windows EXE is located at: dist/LinkedInChecker/"
    
    # Create a portable package
    print_status "Creating portable package..."
    mkdir -p "LinkedInChecker_Portable"
    cp -r dist/LinkedInChecker/* "LinkedInChecker_Portable/"
    
    # Copy sample files
    cp linkedin_links.txt "LinkedInChecker_Portable/"
    mkdir -p "LinkedInChecker_Portable/results"
    
    # Create README
    cat > "LinkedInChecker_Portable/README.txt" << EOF
LinkedIn Premium Trial Link Checker
===================================

INSTALLATION:
1. Copy this entire folder to your Windows PC
2. Make sure Chrome or Firefox is installed on the target PC
3. Run LinkedInChecker.exe

USAGE:
1. Edit linkedin_links.txt with your links
2. Run LinkedInChecker.exe
3. Enter your LinkedIn credentials
4. Click "Start Checking"
5. Results will be saved in the 'results' folder

NOTES:
- No Python installation required on Windows
- Internet connection required
- Use responsibly and respect LinkedIn's terms of service

Built on: $(date)
EOF
    
    # Create zip package
    if command -v zip &> /dev/null; then
        print_status "Creating ZIP package..."
        zip -r "LinkedInChecker_Windows.zip" "LinkedInChecker_Portable/"
        print_status "ZIP package created: LinkedInChecker_Windows.zip"
    fi
    
    print_status "Package created: LinkedInChecker_Portable/"
    print_status ""
    print_status "To use on Windows:"
    print_status "1. Copy 'LinkedInChecker_Portable' folder to Windows PC"
    print_status "2. Run LinkedInChecker.exe"
    print_status ""
    print_status "Build completed successfully! 🎉"
    
else
    print_error "Build failed! Check the logs above for errors."
    exit 1
fi

# Clean up
print_status "Cleaning up temporary files..."
rm -f "/tmp/$PYTHON_INSTALLER"

print_status "All done! Your Windows executable is ready."

