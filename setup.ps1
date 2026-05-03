$base = "$env:USERPROFILE\Documents\matchpro-fit"

# Create all directories
$dirs = @(
    "backend\src\controllers",
    "backend\src\middleware",
    "backend\src\routes",
    "backend\src\services",
    "backend\src\utils",
    "backend\src\types",
    "backend\prisma",
    "frontend\src\components\card",
    "frontend\src\components\dashboard",
    "frontend\src\components\layout",
    "frontend\src\components\auth",
    "frontend\src\components\ui",
    "frontend\src\components\avatar",
    "frontend\src\components\challenges",
    "frontend\src\components\friends",
    "frontend\src\components\health",
    "frontend\src\components\leaderboard",
    "frontend\src\components\routine",
    "frontend\src\components\tests",
    "frontend\src\components\wearables",
    "frontend\src\components\workout",
    "frontend\src\pages",
    "frontend\src\hooks",
    "frontend\src\lib",
    "frontend\src\types",
    "frontend\src\store",
    "shared\types"
)

foreach ($dir in $dirs) {
    New-Item -ItemType Directory -Force -Path "$base\$dir" | Out-Null
}

Write-Host "Directories created!" -ForegroundColor Green

# Set up git
cd $base
git init 2>$null
git remote remove origin 2>$null
git remote add origin "https://github.com/matG203/matchpro-fit.git"

Write-Host "Git configured!" -ForegroundColor Green
Write-Host "Done! Now run: powershell -ExecutionPolicy Bypass -File setup.ps1" -ForegroundColor Cyan