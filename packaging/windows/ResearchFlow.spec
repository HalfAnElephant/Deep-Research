from __future__ import annotations

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


project_root = Path(SPECPATH).resolve().parents[1]
backend_dir = project_root / "backend"
frontend_dist_dir = project_root / "frontend" / "dist"
launcher_script = backend_dir / "app" / "desktop.py"

sys.path.insert(0, str(project_root))
sys.path.insert(0, str(backend_dir))

datas = []
if frontend_dist_dir.exists():
    datas.append((str(frontend_dist_dir), "frontend_dist"))

hiddenimports = (
    collect_submodules("app")
    + collect_submodules("uvicorn")
    + collect_submodules("websockets")
)


a = Analysis(
    [str(launcher_script)],
    pathex=[str(project_root), str(backend_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ResearchFlow",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name="ResearchFlow",
)
