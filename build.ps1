<#
  Builds WinFloat-Setup-<version>.exe:  icon -> PyInstaller (dist\WinFloat) -> Inno Setup (installer\Output).
  Usage:  .\build.ps1                 full build
          .\build.ps1 -Version 1.2.0  set the installer version
          .\build.ps1 -SkipInstaller  only build dist\WinFloat\WinFloat.exe
#>
param(
    [string]$Version = "1.0.0",
    [switch]$SkipInstaller
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Invoke-Step([string]$Title, [scriptblock]$Action) {
    Write-Host "`n==> $Title" -ForegroundColor Cyan
    # Tools like PyInstaller log progress to stderr; judge success by exit code, not by stderr output.
    $ErrorActionPreference = "Continue"
    $global:LASTEXITCODE = 0
    & $Action
    $code = $LASTEXITCODE
    $ErrorActionPreference = "Stop"
    if ($code -ne 0) { throw "$Title failed (exit code $code)" }
}

Invoke-Step "Generating icon" { python installer\make_icon.py }

Invoke-Step "Building WinFloat.exe with PyInstaller" {
    python -m PyInstaller --noconfirm --clean --windowed --name WinFloat `
        --icon installer\WinFloat.ico --exclude-module tkinter main.py
}
if (-not (Test-Path dist\WinFloat\WinFloat.exe)) { throw "dist\WinFloat\WinFloat.exe was not produced" }

if ($SkipInstaller) { Write-Host "`nDone: dist\WinFloat\WinFloat.exe" -ForegroundColor Green; return }

$candidates = @(
    "$env:ProgramFiles\Inno Setup 7\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 7\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 7\ISCC.exe", "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
)
$iscc = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup compiler (ISCC.exe) not found. Install Inno Setup from https://jrsoftware.org/isdl.php" }

Invoke-Step "Building installer with Inno Setup" { & $iscc "/DMyAppVersion=$Version" installer\WinFloat.iss }

$setup = Get-Item "installer\Output\WinFloat-Setup-$Version.exe"
Write-Host ("`nDone: {0}  ({1:N1} MB)" -f $setup.FullName, ($setup.Length / 1MB)) -ForegroundColor Green
