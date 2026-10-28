$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $repoRoot '.env'
if (Test-Path -LiteralPath $envPath) {
    Write-Output '.env ya existe; se conserva sin cambios.'
}
function New-RandomHex {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return ([BitConverter]::ToString($bytes)).Replace('-', '').ToLowerInvariant()
}
if (-not (Test-Path -LiteralPath $envPath)) {
    $example = Get-Content -Raw -LiteralPath (Join-Path $repoRoot '.env.example')
    $example = $example.Replace('replace-with-a-random-key-of-at-least-32-characters', (New-RandomHex))
    $example = $example.Replace('replace-with-a-random-hexadecimal-password', (New-RandomHex))
    [IO.File]::WriteAllText($envPath, $example, (New-Object Text.UTF8Encoding($false)))
}
$logDir = Join-Path $repoRoot '.local/logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
if (-not (Test-Path -LiteralPath (Join-Path $logDir 'app.log'))) {
    Copy-Item -LiteralPath (Join-Path $repoRoot 'collector/sample.txt') -Destination (Join-Path $logDir 'app.log')
}
Write-Output '.env creado con secretos aleatorios. Archivo de ejemplo: .local/logs/app.log'
Write-Output 'Consulta API_KEY en .env e introdúcela en la interfaz. No compartas ese archivo.'
