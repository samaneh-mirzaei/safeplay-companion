# Run from the project root: pyinstaller --noconfirm build/SafePlayOneFile.spec
from pathlib import Path

root = Path(SPECPATH).parent
a = Analysis([str(root / 'main.py')], pathex=[str(root)], binaries=[], datas=[],
             hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[],
             noarchive=False)
# The build host can have Poppler's incompatible icuuc.dll on PATH. QtCore
# uses the Windows ICU API; bundling Poppler's ICU shadows it and breaks import.
a.binaries = [entry for entry in a.binaries
              if Path(entry[0]).name.lower() not in {'icuuc.dll', 'icudt78.dll'}]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='SafePlayCompanion',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, icon=str(root / 'assets' / 'safeplay.ico'))
