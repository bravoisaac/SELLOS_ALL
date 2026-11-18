param([string]$Python = "python")
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
Set-Location $PSScriptRoot

function Assert-DefenderClean([string]$Target) {
    $resolvedTarget = (Resolve-Path -LiteralPath $Target).Path
    $status = Get-MpComputerStatus -ErrorAction Stop
    if (-not $status.AntivirusEnabled -or -not $status.RealTimeProtectionEnabled) {
        throw 'Defender debe estar activo. No se publicará una compilación sin analizar.'
    }
    Write-Host "Analizando con Defender: $resolvedTarget"
    Start-MpScan -ScanType CustomScan -ScanPath $resolvedTarget -ErrorAction Stop
    # No basta con que el análisis termine: Defender puede haber remediado un archivo.
    $pathPattern = [regex]::Escape($resolvedTarget) + '(?:[\\|;]|$)'
    $detections = @(Get-MpThreatDetection -ErrorAction Stop | Where-Object {
        @($_.Resources | Where-Object { $_ -match $pathPattern }).Count -gt 0
    })
    if ($detections.Count -gt 0 -or -not (Test-Path -LiteralPath $resolvedTarget)) {
        throw 'Defender detectó o retiró un archivo. Compilación detenida; no lo restaures ni añadas exclusiones.'
    }
}

function Assert-AppStarts([string]$Executable) {
    $appPath = (Resolve-Path -LiteralPath $Executable).Path
    $started = $null
    try {
        $started = Start-Process -FilePath $appPath -WindowStyle Hidden -PassThru
        $deadline = (Get-Date).AddSeconds(20)
        $window = $null
        do {
            Start-Sleep -Milliseconds 250
            # PyInstaller crea un proceso hijo: verificar la ruta exclusiva de esta compilación.
            $window = Get-Process SelloPDF -ErrorAction SilentlyContinue | Where-Object {
                $_.Path -eq $appPath -and $_.MainWindowTitle -eq 'Sello PDF' -and $_.Responding
            } | Select-Object -First 1
        } while (-not $window -and (Get-Date) -lt $deadline)
        if (-not $window) { throw 'El ejecutable no abrió la ventana de la app.' }
        $null = $window.CloseMainWindow()
        if (-not $started.WaitForExit(5000)) { throw 'La app no pudo cerrarse normalmente.' }
        if ($started.ExitCode -ne 0) { throw 'La app terminó con un error.' }
    } finally {
        Get-Process SelloPDF -ErrorAction SilentlyContinue | Where-Object {
            $_.Path -eq $appPath
        } | Stop-Process
    }
}

# Un entorno nuevo por intento: no reutilizar dependencias ni binarios de la entrega detectada.
& $Python -c "import sys, struct; assert sys.version_info[:2] == (3, 12) and struct.calcsize('P') == 8, 'Se requiere Python 3.12 de 64 bits.'"
if ($LASTEXITCODE -ne 0) { throw 'El intérprete no es compatible con requirements-windows.lock.' }
$releaseDir = Join-Path $PSScriptRoot ('build/release-' + [guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $releaseDir
$environmentDir = Join-Path $releaseDir 'venv'
$buildPython = Join-Path $environmentDir 'Scripts/python.exe'
$reportPath = Join-Path $releaseDir 'validation.json'
$report = [ordered]@{ status = 'pending'; stage = 'environment'; executable = $null; sha256 = $null }
try {
    & $Python -m venv $environmentDir
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el entorno limpio.' }
    & $buildPython -m pip --isolated install --no-cache-dir --no-index --only-binary=:all: --require-hashes -r requirements-windows.lock
    if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias verificadas.' }
    & $buildPython -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Las dependencias son incompatibles.' }
    & $buildPython -c "from importlib.metadata import version; from pathlib import Path; pins = [line.strip().split('==') for line in Path('requirements.txt').read_text().splitlines() if line.strip() and not line.lstrip().startswith('#')]; assert all(version(name) == expected for name, expected in pins), 'requirements.txt y requirements-windows.lock no coinciden.'"
    if ($LASTEXITCODE -ne 0) { throw 'Actualiza el archivo de bloqueo para que coincida con requirements.txt.' }

    $report.stage = 'dependency-scan'
    Assert-DefenderClean $environmentDir
    $report.stage = 'gui-dependencies'
    & $buildPython -c "import tkinter; import PIL._imagingtk; t = tkinter.Tk(); t.withdraw(); t.update_idletasks(); t.destroy()"
    if ($LASTEXITCODE -ne 0) { throw 'La interfaz gráfica está bloqueada o incompleta. Revisa Tcl/Tk, Pillow y la política de firmas de Windows.' }
    $report.stage = 'tests'
    & (Join-Path $PSScriptRoot 'tests/release_checks.ps1')
    & $buildPython -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Las pruebas fallaron.' }
    & $buildPython tests/gui_smoke.py
    if ($LASTEXITCODE -ne 0) { throw 'La prueba de vista previa y exportación de PDF falló.' }

    $report.stage = 'compile'
    $outputDir = Join-Path $releaseDir 'dist'
    & $buildPython -m PyInstaller --noconfirm --clean --onefile --windowed --name SelloPDF --collect-all pymupdf --exclude-module matplotlib --exclude-module numpy --distpath $outputDir --workpath (Join-Path $releaseDir 'work') --specpath $releaseDir (Join-Path $PSScriptRoot 'app.py')
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo generar el ejecutable.' }
    $candidate = Join-Path $outputDir 'SelloPDF.exe'
    $report.executable = $candidate
    $report.sha256 = (Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash
    if ($report.sha256 -eq 'E3687EC15C8846366545481DE1137A488DEBA16631FD41438CC552D40CF0D778') {
        throw 'El resultado coincide con la compilación detectada. Requiere revisión del proveedor de antivirus.'
    }
    $report.stage = 'executable-scan'
    Assert-DefenderClean $candidate
    if ((Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash -ne $report.sha256) {
        throw 'El ejecutable cambió durante la validación.'
    }
    $report.stage = 'executable-startup'
    Assert-AppStarts $candidate
    # Mantener el resultado como candidato: un análisis limpio no revoca la detección anterior.
    $report.status = 'candidate-validated'
    $report.stage = 'vendor-review-and-signing'
    Write-Host "Candidato validado localmente: $candidate"
    Write-Host 'No se publica automáticamente. Falta resolver la detección con el proveedor y la firma para los equipos que la exigen.'
} catch {
    $report.status = 'blocked'
    $report['error'] = $_.Exception.Message
    throw
} finally {
    $report | ConvertTo-Json | Set-Content -LiteralPath $reportPath -Encoding utf8
    Write-Host "Informe: $reportPath"
}
