# PyInstaller spec for the standalone NOVA executable.
#
# Build with:  pyinstaller packaging/nova.spec --clean --noconfirm
# Output:      dist/nova.exe  (Windows)  |  dist/nova  (macOS, Linux)

from PyInstaller.utils.hooks import collect_submodules

hidden = []
# uvicorn resolves its protocol and lifespan implementations by string name at
# runtime, so PyInstaller's static analysis cannot see them.
hidden += collect_submodules("uvicorn")
# anyio picks its backend by name too.
hidden += collect_submodules("anyio")
hidden += [
    "nova.cli",
    "nova.server",
    "nova.mcp_server",
    "encodings.idna",
]

a = Analysis(
    ["../src/nova/__main__.py"],
    pathex=["../src"],
    binaries=[],
    datas=[],
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pytest", "PIL"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="nova",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
