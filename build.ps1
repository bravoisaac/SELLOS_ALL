param([string]$Python = "python")
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path '.venv/Scripts/python.exe')) {
    & $Python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el entorno Python.' }
}
& '.venv/Scripts/python.exe' -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias.' }
& '.venv/Scripts/python.exe' -c "import tkinter; import PIL._imagingtk; t = tkinter.Tk(); t.withdraw(); t.update_idletasks(); t.destroy()"
if ($LASTEXITCODE -ne 0) { throw 'La interfaz gráfica no está disponible. Revisa Tcl/Tk, Pillow y las políticas de Control de aplicaciones antes de compilar.' }
& '.venv/Scripts/python.exe' -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Las pruebas fallaron.' }
& '.venv/Scripts/python.exe' -m PyInstaller --noconfirm --clean --onefile --windowed --name SelloPDF --collect-all pymupdf --exclude-module matplotlib --exclude-module numpy app.py
if ($LASTEXITCODE -ne 0) { throw 'No se pudo generar el ejecutable.' }
Copy-Item -LiteralPath 'dist/SelloPDF.exe' -Destination 'SelloPDF.exe' -Force
Write-Host 'Ejecutable generado: SelloPDF.exe (copia de dist/SelloPDF.exe lista para publicar)'
