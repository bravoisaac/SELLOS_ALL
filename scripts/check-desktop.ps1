$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Set-Location (Split-Path $PSScriptRoot -Parent)
$version = (Get-Content package.json -Raw | ConvertFrom-Json).version
$archive = (Resolve-Path "dist/desktop/SelloPDF-Escritorio-$version-Windows-x64.zip").Path
$reportPath = Join-Path $PWD 'dist/desktop/validation.json'
$report = [ordered]@{ status = 'pending'; archive = [IO.Path]::GetFileName($archive); sha256 = (Get-FileHash -LiteralPath $archive).Hash; stage = 'scan' }
try {
    # Reutilizar solo el control de Defender, sin ejecutar la compilación antigua.
    $tokens = $null
    $errors = $null
    $ast = [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $PWD 'build.ps1'), [ref]$tokens, [ref]$errors)
    $gate = $ast.Find({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Assert-DefenderClean' }, $true)
    if (-not $gate) { throw 'No se encontró el control de Defender.' }
    . ([scriptblock]::Create($gate.Extent.Text))
    Assert-DefenderClean $archive
    $report.stage = 'extract'
    $extractDir = Join-Path $PWD ('tmp/Escritorio prueba ' + [guid]::NewGuid().ToString('N'))
    Expand-Archive -LiteralPath $archive -DestinationPath $extractDir
    Assert-DefenderClean $extractDir
    $exe = Join-Path $extractDir 'Sello PDF Escritorio.exe'
    if (-not (Test-Path -LiteralPath $exe)) { throw 'El ZIP no contiene la aplicación esperada.' }
    $report.stage = 'packaged-test'
    $env:SELLO_PACKAGED_EXE = $exe
    try {
        & node tests/desktop-smoke.mjs
        if ($LASTEXITCODE -ne 0) { throw 'La aplicación extraída no superó las pruebas.' }
    } finally { Remove-Item Env:SELLO_PACKAGED_EXE -ErrorAction SilentlyContinue }
    if ((Get-FileHash -LiteralPath $archive).Hash -ne $report.sha256) { throw 'El ZIP cambió durante las pruebas.' }
    $report['executable_sha256'] = (Get-FileHash -LiteralPath $exe).Hash
    $report['signature'] = (Get-AuthenticodeSignature -LiteralPath $exe).Status.ToString()
    $report.status = 'portable-validated'
    $report.stage = 'complete'
    "$($report.sha256.ToLower())  $($report.archive)" | Set-Content dist/desktop/SHA256SUMS.txt -Encoding ascii
} catch {
    $report.status = 'blocked'
    $report['error'] = $_.Exception.Message
    throw
} finally {
    $report | ConvertTo-Json | Set-Content -LiteralPath $reportPath -Encoding utf8
    Write-Output "Informe: $reportPath"
}
