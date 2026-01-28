$Python = "py"; $PythonVer = "-3.11"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   ROSE UPDATER BUILD SCRIPT             " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

Write-Host "`n[1/3] Cleaning old updater build..."
if (Test-Path "dist_updater") { Remove-Item "dist_updater" -Recurse -Force }
if (Test-Path "build_updater") { Remove-Item "build_updater" -Recurse -Force }

Write-Host "`n[2/3] Compiling updater with Nuitka (minimal build)..."
& $Python $PythonVer -m nuitka --standalone --mingw64 `
    --windows-console-mode=disable `
    --windows-icon-from-ico=assets/icon.ico `
    --company-name="Rose" `
    --product-name="Rose Updater" `
    --file-description="Rose Update Installer" `
    --product-version=1.0.0.0 `
    --output-dir=dist_updater `
    --nofollow-import-to=test `
    --nofollow-import-to=unittest `
    --nofollow-import-to=distutils `
    --nofollow-import-to=setuptools `
    --nofollow-import-to=pytest `
    --nofollow-import-to=pip `
    --module-name-choice=original `
    updater

if (-not (Test-Path "dist_updater/updater.dist/updater.exe")) {
    Write-Host "Error: Nuitka compilation failed." -ForegroundColor Red
    exit 1
}

Write-Host "`n[3/3] Build complete!"
Write-Host "  Output: dist_updater/updater.dist/updater.exe" -ForegroundColor Gray

# Calculate size
$exeSize = [math]::Round((Get-Item "dist_updater/updater.dist/updater.exe").Length / 1MB, 2)
Write-Host "  Size: $exeSize MB" -ForegroundColor Gray
