# Building DbSentinel AppImage

## Quick Build

Run the build script:

```bash
./build_appimage.sh
```

This will create `DbSentinel-1.0-x86_64.AppImage` that you can run on any Linux system.

## Manual Build

If you prefer to build manually:

1. Install dependencies:
   ```bash
   python install_dependencies.py
   ```

2. Download appimagetool:
   ```bash
   wget https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
   chmod +x appimagetool-x86_64.AppImage
   ```

3. Create AppDir and build:
   ```bash
   mkdir DbSentinel.AppDir
   # Copy files and dependencies
   ./appimagetool-x86_64.AppImage DbSentinel.AppDir
   ```

## Running the AppImage

```bash
./DbSentinel-1.0-x86_64.AppImage
```

The AppImage is portable and includes all dependencies.