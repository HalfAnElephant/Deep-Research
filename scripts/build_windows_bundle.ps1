param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if ($Clean) {
    Remove-Item -Recurse -Force (Join-Path $root "build\pyinstaller") -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force (Join-Path $root "dist\windows") -ErrorAction SilentlyContinue
}

Push-Location $root
try {
    Push-Location (Join-Path $root "frontend")
    npm ci
    npm run build
    Pop-Location

    python -m pip install --upgrade pip
    python -m pip install -e ".\backend[dev]" pyinstaller

    $distRoot = Join-Path $root "dist\windows"
    New-Item -ItemType Directory -Force -Path $distRoot | Out-Null

    pyinstaller --noconfirm --clean `
        --distpath $distRoot `
        --workpath (Join-Path $root "build\pyinstaller") `
        (Join-Path $root "packaging\windows\ResearchFlow.spec")

    Copy-Item `
        (Join-Path $root "packaging\windows\desktop.env.example") `
        (Join-Path $distRoot "ResearchFlow\desktop.env.example") `
        -Force

    $zipPath = Join-Path $distRoot "ResearchFlow-windows-portable.zip"
    if (Test-Path $zipPath) {
        Remove-Item -Force $zipPath
    }
    Compress-Archive -Path (Join-Path $distRoot "ResearchFlow\*") -DestinationPath $zipPath
}
finally {
    Pop-Location
}
