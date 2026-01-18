# Build Scripts

This directory contains all build-related files for creating standalone executables.

## Structure

```
build/
├── windows/               # Windows build files
│   ├── TranslateBook.spec    # PyInstaller spec for Windows
│   ├── build_exe.bat         # Windows build script
│   └── install_chatterbox.bat # Chatterbox TTS installer
├── macos/                 # macOS build files
│   ├── TranslateBook-macOS.spec # PyInstaller spec for macOS
│   └── build_macos.sh           # macOS build script
└── README.md              # This file
```

## Building Executables

### Windows

```bash
cd build/windows
build_exe.bat
```

The executable will be created at: `../../dist/TranslateBook.exe`

### macOS

```bash
cd build/macos
./build_macos.sh
```

The executable will be created at: `../../dist/TranslateBook`

## GitHub Workflows

The GitHub Actions workflows automatically use these files:
- [.github/workflows/build-windows.yml](../../.github/workflows/build-windows.yml)
- [.github/workflows/build-macos.yml](../../.github/workflows/build-macos.yml)

## Output

All builds output to the root `dist/` directory, which is git-ignored.
