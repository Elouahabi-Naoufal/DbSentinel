#!/usr/bin/env python3
"""
SQLite Database Explorer - Desktop Application Launcher
=======================================================

This script provides a simple way to launch the SQLite Database Explorer
with proper dependency checking and user guidance.

Usage:
------
python run_desktop_app.py

Features:
---------
- Dependency verification before launch
- Clear error messages and installation guidance
- Graceful fallback when dependencies are missing
- User-friendly startup experience
"""

import sys
import subprocess
import importlib.util

def check_dependency(package_name, import_name=None):
    """Check if a Python package is available."""
    if import_name is None:
        import_name = package_name
    
    try:
        importlib.import_module(import_name)
        return True, None
    except ImportError as e:
        return False, str(e)

def install_package(package_name):
    """Attempt to install a package using pip."""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        return True
    except subprocess.CalledProcessError:
        return False

def main():
    """Main launcher function."""
    print("🚀 SQLite Database Explorer - Desktop Application")
    print("=" * 55)
    
    # Check dependencies
    dependencies = [
        ("PyQt5", "PyQt5.QtWidgets"),
        ("pysqlcipher3", "pysqlcipher3.dbapi2")
    ]
    
    missing_deps = []
    optional_missing = []
    
    for package, import_name in dependencies:
        available, error = check_dependency(package, import_name)
        if not available:
            if package == "pysqlcipher3":
                optional_missing.append((package, error))
            else:
                missing_deps.append((package, error))
    
    # Handle missing critical dependencies
    if missing_deps:
        print("❌ Missing required dependencies:")
        for package, error in missing_deps:
            print(f"   - {package}: {error}")
        
        print("\n🔧 Installing missing dependencies...")
        for package, _ in missing_deps:
            print(f"Installing {package}...")
            if install_package(package):
                print(f"✅ {package} installed successfully")
            else:
                print(f"❌ Failed to install {package}")
                print(f"\nPlease install manually: pip install {package}")
                return 1
    
    # Handle optional SQLCipher dependency
    if optional_missing:
        print("⚠️  Optional dependency missing:")
        for package, error in optional_missing:
            print(f"   - {package}: {error}")
        print("\nThe application will work with regular SQLite databases.")
        print("For encrypted database support, install: pip install pysqlcipher3")
        print("(You may need system dependencies - see README.md)\n")
    
    # Import and launch the application
    try:
        print("🎯 Launching SQLite Database Explorer...")
        
        # Import the main application
        from sqlite_explorer import main as run_app
        
        # Launch the application
        run_app()
        
    except ImportError as e:
        print(f"❌ Failed to import application: {e}")
        print("\nPlease ensure sqlite_explorer.py is in the same directory.")
        return 1
    
    except Exception as e:
        print(f"❌ Application error: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code or 0)