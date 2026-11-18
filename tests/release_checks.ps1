# Exercise the release gate without invoking or changing Windows Defender.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$projectDir = Split-Path $PSScriptRoot -Parent
$parseTokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    (Join-Path $projectDir 'build.ps1'), [ref]$parseTokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw $parseErrors }
$gate = $ast.Find({ param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
    $node.Name -eq 'Assert-DefenderClean'
}, $true)
if (-not $gate) { throw 'Release gate missing.' }
# Load only the function under test, not the build/install commands.
. ([scriptblock]::Create($gate.Extent.Text))
$testDir = Join-Path $projectDir ('tmp/release-check-' + [guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $testDir
$script:testFile = Join-Path $testDir 'harmless.txt'
$script:scenario = ''

function Get-MpComputerStatus {
    param($ErrorAction)
    if ($script:scenario -eq 'status-error') { throw 'Status unavailable' }
    [pscustomobject]@{
        AntivirusEnabled = $script:scenario -ne 'disabled'
        RealTimeProtectionEnabled = $true
    }
}
function Start-MpScan {
    param($ScanType, $ScanPath, $ErrorAction)
    if ($script:scenario -eq 'scan-error') { throw 'Scan failed' }
    if ($script:scenario -eq 'removed') { Remove-Item -LiteralPath $script:testFile }
}
function Get-MpThreatDetection {
    param($ErrorAction)
    if ($script:scenario -eq 'detection-error') { throw 'History unavailable' }
    if ($script:scenario -eq 'detected') {
        # A successful remediation is still a detected artifact, never a clean release.
        [pscustomobject]@{ Resources = @("file:_$script:testFile"); ActionSuccess = $true }
    }
    if ($script:scenario -eq 'unrelated') {
        [pscustomobject]@{ Resources = @("file:_$script:testFile.other"); ActionSuccess = $true }
    }
}

foreach ($case in @('clean', 'unrelated', 'disabled', 'status-error', 'scan-error', 'detection-error', 'detected', 'removed')) {
    $script:scenario = $case
    Set-Content -LiteralPath $script:testFile -Value 'Harmless test fixture'
    $blocked = $false
    try { Assert-DefenderClean $script:testFile } catch { $blocked = $true }
    $expectedBlock = $case -notin @('clean', 'unrelated')
    if ($blocked -ne $expectedBlock) { throw "Incorrect release gate result: $case" }
}
Write-Host 'OK: 8 release gate scenarios, no real Defender changes.'
