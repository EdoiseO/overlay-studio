# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all


block_cipher = None

winrt_datas, winrt_binaries, winrt_hiddenimports = collect_all("winrt")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=winrt_binaries,
    datas=[
        ("config.example.json", "."),
        ("requirements.txt", "."),
        ("README.md", "."),
        ("check-media-session.py", "."),
    ] + winrt_datas,
    hiddenimports=[
        "soundcard",
        "aiohttp",
        "numpy",
        "winrt.runtime",
        "winrt.windows.media.control",
        "winrt.windows.storage.streams",
        *winrt_hiddenimports,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name="overlay-studio-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
