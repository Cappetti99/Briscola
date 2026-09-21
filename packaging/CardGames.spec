# PyInstaller specification for the macOS desktop build.

from PyInstaller.utils.hooks import collect_submodules


hiddenimports = collect_submodules("cardgames")

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="CardGames",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

app = BUNDLE(
    exe,
    name="CardGames.app",
    icon=None,
    bundle_identifier="com.cappetti99.cardgames",
    info_plist={
        "CFBundleDisplayName": "Card Games",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "11.0",
    },
)
