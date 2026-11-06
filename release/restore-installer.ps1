$ErrorActionPreference = 'Stop'

$installerName = 'Voxa-Setup-0.7.2.exe'
$expectedHash = '386a169b1f808a86e5fd741ea1c36cc2e656f5159dd4809fa3b49235ddbb502a'
$expectedSize = 702908156
$partCount = 68
$outputPath = Join-Path $PSScriptRoot $installerName

if (Test-Path -LiteralPath $outputPath) {
    throw "$installerName already exists. Move it before restoring."
}

$parts = @(Get-ChildItem -LiteralPath $PSScriptRoot -File -Filter "$installerName.*" |
    Where-Object { $_.Name -match '\.(\d{3})$' } |
    Sort-Object Name)
if ($parts.Count -ne $partCount) {
    throw "Expected $partCount installer parts, found $($parts.Count). Download all parts first."
}

for ($i = 0; $i -lt $partCount; $i++) {
    $expectedName = '{0}.{1:D3}' -f $installerName, ($i + 1)
    if ($parts[$i].Name -ne $expectedName) {
        throw "Missing or out-of-order part: $expectedName"
    }
}

$output = [System.IO.File]::Open($outputPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write)
try {
    foreach ($part in $parts) {
        $input = [System.IO.File]::OpenRead($part.FullName)
        try {
            $input.CopyTo($output, 1MB)
        }
        finally {
            $input.Dispose()
        }
    }
}
finally {
    $output.Dispose()
}

$actualSize = (Get-Item -LiteralPath $outputPath).Length
if ($actualSize -ne $expectedSize) {
    throw "Installer size mismatch: expected $expectedSize bytes, got $actualSize."
}

$actualHash = (Get-FileHash -LiteralPath $outputPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualHash -ne $expectedHash) {
    throw "Installer SHA256 mismatch: $actualHash"
}

Write-Host "Restored and verified $installerName."
