#!/usr/bin/env python3
"""
Dependency Installation Script for SQLite Database Explorer
==========================================================

This script helps install the required dependencies for the SQLite Database Explorer.

Required packages:
- PyQt5: GUI framework
- pysqlcipher3: SQLCipher encrypted database support

Usage:
------
python install_dependencies.py

Or manually install:
pip install PyQt5 pysqlcipher3

System Dependencies (Linux):
-----------------------------
Ubuntu/Debian:
    sudo apt-get update
    sudo apt-get install libsqlcipher-dev libssl-dev python3-dev

CentOS/RHEL/Fedora:
    sudo yum install sqlcipher-devel openssl-devel python3-devel
    # or on newer systems:
    sudo dnf install sqlcipher-devel openssl-devel python3-devel

macOS (with Homebrew):
    brew install sqlcipher

Windows:
    SQLCipher support may require additional setup.
    Consider using conda: conda install pysqlcipher3
"""

import subprocess
import sys
import platform

def install_package(package):
    """Install a Python package using pip."""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"✅ Successfully installed {package}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install {package}: {e}")
        return False

def check_system_dependencies():
    """Check and provide guidance for system dependencies."""
    system = platform.system()
    
    print(f"Detected system: {system}")
    
    if system == "Linux":
        print("\n📋 Linux System Dependencies:")
        print("Ubuntu/Debian:")
        print("  sudo apt-get update")
        print("  sudo apt-get install libsqlcipher-dev libssl-dev python3-dev")
        print("\nCentOS/RHEL/Fedora:")
        print("  sudo yum install sqlcipher-devel openssl-devel python3-devel")
        print("  # or: sudo dnf install sqlcipher-devel openssl-devel python3-devel")
        
    elif system == "Darwin":  # macOS
        print("\n📋 macOS System Dependencies:")
        print("With Homebrew:")
        print("  brew install sqlcipher")
        
    elif system == "Windows":
        print("\n📋 Windows System Dependencies:")
        print("SQLCipher support on Windows can be complex.")
        print("Consider using conda instead:")
        print("  conda install pysqlcipher3")
        print("Or install from conda-forge:")
        print("  conda install -c conda-forge pysqlcipher3")

def main():
    """Main installation function."""
    print("🔧 SQLite Database Explorer - Dependency Installation")
    print("=" * 55)
    
    # Check system and provide guidance
    check_system_dependencies()
    
    print("\n🚀 Installing Python packages...")
    
    # List of required packages
    packages = [
        "PyQt5",
        "pysqlcipher3"
    ]
    
    success_count = 0
    for package in packages:
        print(f"\n📦 Installing {package}...")
        if install_package(package):
            success_count += 1
    
    print(f"\n{'='*55}")
    print(f"Installation Summary: {success_count}/{len(packages)} packages installed successfully")
    
    if success_count == len(packages):
        print("✅ All dependencies installed successfully!")
        print("\nYou can now run the SQLite Database Explorer:")
        print("python sqlite_explorer.py")
    else:
        print("⚠️  Some dependencies failed to install.")
        print("Please check the error messages above and install system dependencies if needed.")
        print("\nFor SQLCipher support issues, you may need to:")
        print("1. Install system dependencies (see above)")
        print("2. Use conda instead of pip")
        print("3. Compile from source")
    
    print("\n📚 Documentation:")
    print("- PyQt5: https://pypi.org/project/PyQt5/")
    print("- pysqlcipher3: https://pypi.org/project/pysqlcipher3/")

if __name__ == "__main__":
    main()