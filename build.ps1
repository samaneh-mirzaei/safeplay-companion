$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
python -c "import sys; assert sys.version_info >= (3, 12), 'Python 3.12+ required'"
python -m pip install -r requirements.txt
python -m pytest -q
python -m PyInstaller --noconfirm --clean build/SafePlayOneFile.spec
Write-Host 'Standalone executable: dist\SafePlayCompanion.exe'
