#!/bin/bash

# Build script for DbSentinel AppImage

set -e

APP_NAME="DbSentinel"
APP_VERSION="1.0"
ARCH="x86_64"

echo "Building $APP_NAME AppImage..."

# Create AppDir structure
APP_DIR="${APP_NAME}.AppDir"
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR"

# Create directory structure
mkdir -p "$APP_DIR/usr/bin"
mkdir -p "$APP_DIR/usr/lib/python3/site-packages"
mkdir -p "$APP_DIR/usr/share/applications"
mkdir -p "$APP_DIR/usr/share/icons/hicolor/256x256/apps"

# Copy application files
cp sqlite_explorer.py "$APP_DIR/"
cp requirements.txt "$APP_DIR/"
cp README.md "$APP_DIR/"

# Copy desktop file and icon
cp DbSentinel.desktop "$APP_DIR/"
cp DbSentinel.png "$APP_DIR/"
cp DbSentinel.png "$APP_DIR/usr/share/icons/hicolor/256x256/apps/"

# Copy AppRun
cp AppRun "$APP_DIR/"

# Install Python dependencies locally
echo "Installing Python dependencies..."
pip3 install --target "$APP_DIR/usr/lib/python3/site-packages" PyQt5 || echo "PyQt5 installation failed"
pip3 install --target "$APP_DIR/usr/lib/python3/site-packages" pysqlcipher3 || echo "pysqlcipher3 installation failed"

# Download appimagetool if not present
if [ ! -f "appimagetool-x86_64.AppImage" ]; then
    echo "Downloading appimagetool..."
    wget -q "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x appimagetool-x86_64.AppImage
fi

# Build AppImage
echo "Building AppImage..."
ARCH=$ARCH ./appimagetool-x86_64.AppImage "$APP_DIR" "${APP_NAME}-${APP_VERSION}-${ARCH}.AppImage"

echo "AppImage built successfully: ${APP_NAME}-${APP_VERSION}-${ARCH}.AppImage"
echo "You can now run: ./${APP_NAME}-${APP_VERSION}-${ARCH}.AppImage"