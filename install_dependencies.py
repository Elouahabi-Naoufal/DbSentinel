#!/usr/bin/env python3
"""
Dependency installer for SQLite Database Explorer
================================================

Installs required dependencies for the desktop application.

Usage: python install_dependencies.py
"""

import subprocess
import sys
import platform

def install_package(package):
    """Install a package using pip."""
    try:
        print(f"Installing {package}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"✅ {package} installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install {package}: {e}")
        return False

def main():
    """Install dependencies."""
    print("🚀 Installing SQLite Database Explorer dependencies...")
    
    packages = ["PyQt5", "pysqlcipher3"]
    success = 0
    
    for package in packages:
        if install_package(package):
            success += 1
    
    if success == len(packages):
        print("\n🎉 All dependencies installed! Run: python sqlite_explorer.py")
    else:
        print("\n⚠️ Some packages failed. App will work with regular SQLite databases.")
        
        system = platform.system()
        if system == "Linux":
            print("\nFor SQLCipher support on Ubuntu/Debian:")
            print("sudo apt-get install libsqlcipher-dev python3-dev")
        elif system == "Darwin":
            print("\nFor SQLCipher support on macOS:")
            print("brew install sqlcipher")

if __name__ == "__main__":
    main()