$Python = "py"; $PythonVer = "-3.11"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   ROSE BUILD SCRIPT                      "      -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

Write-Host "`n[1/7] Cleaning old build folders..."
if (Test-Path "dist") { Remove-Item "dist" -Recurse -Force }
if (Test-Path "build") { Remove-Item "build" -Recurse -Force }
if (Test-Path "dist_updater") { Remove-Item "dist_updater" -Recurse -Force }

Write-Host "`n[2/7] Compiling with Nuitka (This may take a while)..."
& $Python $PythonVer -m nuitka --standalone --mingw64 `
     --enable-plugin=tk-inter `
     --windows-console-mode=disable `
     --include-package=websockets `
     --include-data-dir=assets=assets `
     --include-data-dir="Pengu Loader"="Pengu Loader" `
     --windows-icon-from-ico=assets/icon.ico `
     --company-name="Rose" `
     --product-name="Rose" `
     --file-description="Rose - Effortless Skin Changer" `
     --product-version=1.1.9.0 `
     --output-dir=dist `
     --nofollow-import-to=test `
     --nofollow-import-to=unittest `
     --nofollow-import-to=distutils `
     --nofollow-import-to=setuptools `
     --nofollow-import-to=pytest `
     --nofollow-import-to=IPython `
     --nofollow-import-to=matplotlib `
     --nofollow-import-to=numpy `
     --nofollow-import-to=pandas `
     main.py

if (-not (Test-Path "dist/main.dist/main.exe")) {
    Write-Host "Error: Nuitka compilation failed." -ForegroundColor Red
    exit
}

Write-Host "`n[3/7] Building standalone updater..."
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
    Write-Host "Warning: Updater compilation failed, skipping inclusion" -ForegroundColor Yellow
} else {
    Write-Host "  Updater built successfully" -ForegroundColor Gray
}

Write-Host "`n[4/7] Preparing folder structure..."
Rename-Item -Path "dist/main.dist" -NewName "Rose"
Rename-Item -Path "dist/Rose/main.exe" -NewName "Rose.exe"

Write-Host "`n[5/7] Copying Injection Tools, DLLs & Updater..."

New-Item -ItemType Directory -Force -Path "dist/Rose/injection" | Out-Null
Copy-Item -Path "injection\*" -Destination "dist/Rose/injection" -Recurse -Force

New-Item -ItemType Directory -Force -Path "dist/Rose/Pengu Loader" | Out-Null
Copy-Item -Path "Pengu Loader\*" -Destination "dist/Rose/Pengu Loader" -Recurse -Force

# Copy standalone updater if it was built successfully
if (Test-Path "dist_updater/updater.dist/updater.exe") {
    Write-Host "  Copying updater.exe..." -ForegroundColor Gray
    Copy-Item -Path "dist_updater/updater.dist/updater.exe" -Destination "dist/Rose/updater.exe" -Force
}

Write-Host "`n[6/7] Generating Installer..."
& $Python $PythonVer create_installer.py

Write-Host "`n[7/7] Creating update ZIP (for in-app updater / GitHub release)..."
$installerDir = "installer"
if (-not (Test-Path $installerDir)) { New-Item -ItemType Directory -Path $installerDir -Force | Out-Null }
$updateZip = Join-Path $installerDir "Rose_update.zip"
if (Test-Path $updateZip) { Remove-Item $updateZip -Force }
# Flat structure (Rose.exe + _internal / DLLs at root) so updater finds exe immediately
Compress-Archive -Path "dist\Rose\*" -DestinationPath $updateZip -Force
$sizeMb = [math]::Round((Get-Item $updateZip).Length / 1MB, 1)
Write-Host "  $updateZip ($sizeMb MB)" -ForegroundColor Gray

Write-Host "`nDone! Check the 'installer' folder." -ForegroundColor Green
Write-Host "  - Rose_Setup*.exe  = full installer" -ForegroundColor Gray
Write-Host "  - Rose_update.zip  = attach to GitHub release for in-app updates" -ForegroundColor Gray