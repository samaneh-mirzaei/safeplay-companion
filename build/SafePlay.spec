# Run from the project root: pyinstaller --noconfirm build/SafePlay.spec
from pathlib import Path

root = Path(SPECPATH).parent
a = Analysis([str(root / 'main.py')], pathex=[str(root)], binaries=[], datas=[],
             hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[],
             noarchive=False)
a.binaries = [entry for entry in a.binaries
              if Path(entry[0]).name.lower() not in {'icuuc.dll', 'icudt78.dll'}]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='SafePlayCompanion',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, icon=str(root / 'assets' / 'safeplay.ico'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False,
               name='SafePlayCompanion')
