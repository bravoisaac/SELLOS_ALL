param([string]$Python = "python")
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path '.venv/Scripts/python.exe')) {
    & $Python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el entorno Python.' }
}
& '.venv/Scripts/python.exe' -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias.' }
& '.venv/Scripts/python.exe' -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Las pruebas fallaron.' }
& '.venv/Scripts/python.exe' -m PyInstaller --noconfirm --clean --onefile --windowed --name SelloPDF --collect-all pymupdf --exclude-module matplotlib --exclude-module numpy app.py
if ($LASTEXITCODE -ne 0) { throw 'No se pudo generar el ejecutable.' }
Write-Host 'Ejecutable generado: dist/SelloPDF.exe'
