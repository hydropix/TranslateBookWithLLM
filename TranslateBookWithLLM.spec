# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for TranslateBookWithLLM
Builds a standalone Windows executable with all dependencies
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect all submodules for packages that need dynamic imports
hidden_imports = [
    'flask',
    'flask_cors',
    'flask_socketio',
    'engineio.async_drivers.threading',
    'socketio',
    'httpx',
    'httpx._transports.default',
    'lxml',
    'lxml.etree',
    'lxml._elementpath',
    'tqdm',
    'dotenv',
    'aiofiles',
    'tiktoken',
    'tiktoken_ext',
    'tiktoken_ext.openai_public',
    'requests',
    'urllib3',
    'charset_normalizer',
    'certifi',
    'idna',
    'werkzeug',
    'jinja2',
    'markupsafe',
    'click',
    'itsdangerous',
    'blinker',
    'colorama',
    'regex',
    # src modules
    'src',
    'src.api',
    'src.api.routes',
    'src.api.websocket',
    'src.api.handlers',
    'src.api.translation_state',
    'src.core',
    'src.core.translator',
    'src.core.llm_client',
    'src.core.llm_providers',
    'src.core.epub_processor',
    'src.core.srt_processor',
    'src.core.text_processor',
    'src.core.post_processor',
    'src.core.chunking',
    'src.core.epub',
    'src.utils',
    'src.utils.file_utils',
    'src.utils.file_detector',
    'src.utils.unified_logger',
    'src.utils.security',
    'src.web',
    'src.config',
    'prompts',
    'prompts.prompts',
]

# Data files to include
datas = [
    # Web interface files
    ('src/web/static', 'src/web/static'),
    ('src/web/templates', 'src/web/templates'),
    # Configuration example
    ('.env.example', '.'),
]

# Check if optional files exist before adding
optional_files = [
    ('README.md', '.'),
    ('LICENSE', '.'),
    ('SIMPLE_MODE_README.md', '.'),
    ('TRANSLATION_SIGNATURE.md', '.'),
    ('DOCKER.md', '.'),
]

for src, dst in optional_files:
    if os.path.exists(src):
        datas.append((src, dst))

# Collect tiktoken data files (encoding files)
try:
    datas += collect_data_files('tiktoken')
except Exception:
    pass

a = Analysis(
    ['translation_api.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'tkinter',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='TranslateBookWithLLM',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Keep console for server logs
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='src/web/static/favicon.ico' if os.path.exists('src/web/static/favicon.ico') else None,
    version='version_info.txt' if os.path.exists('version_info.txt') else None,
)
