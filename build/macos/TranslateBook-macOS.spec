# -*- mode: python ; coding: utf-8 -*-
import os
import tiktoken_ext.openai_public

block_cipher = None

# Get tiktoken_ext data directory (contains pre-bundled encodings)
tiktoken_ext_dir = os.path.dirname(tiktoken_ext.openai_public.__file__)

# Prepare datas list
datas_list = [
    ('../../src/web/static', 'src/web/static'),
    ('../../src/web/templates', 'src/web/templates'),
    ('../../src', 'src'),
    ('../../.env.example', '.'),
]

# Add tiktoken_ext if directory exists
if os.path.exists(tiktoken_ext_dir):
    datas_list.append((tiktoken_ext_dir, 'tiktoken_ext/openai_public'))

a = Analysis(
    ['../../launcher.py'],
    pathex=[],
    binaries=[],
    datas=datas_list,
    hiddenimports=[
        'flask',
        'flask_cors',
        'flask_socketio',
        'python_socketio',
        'socketio',
        'engineio',
        'engineio.async_drivers.threading',
        'requests',
        'tqdm',
        'httpx',
        'lxml',
        'lxml.etree',
        'lxml._elementpath',
        'dotenv',
        'aiofiles',
        'tiktoken',
        'tiktoken_ext',
        'tiktoken_ext.openai_public',
        'pyyaml',
        'jinja2',
        'langdetect',
        'PIL',
        'dns',
        'dns.resolver',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='TranslateBook',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=True,  # Enable for macOS compatibility
    target_arch=None,  # Will build for current architecture (arm64 or x86_64)
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
