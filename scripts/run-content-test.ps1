param(
    [switch]$Execute,
    [switch]$AskForKeys
)
$ErrorActionPreference = 'Stop'
$projectDir = Split-Path -Parent $PSScriptRoot
$venvDir = Join-Path $projectDir '.venv'
$pythonPath = Join-Path $venvDir 'Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    python -m venv $venvDir
    if ($LASTEXITCODE -ne 0) { throw 'Die lokale Python-Umgebung konnte nicht erstellt werden.' }
}
& $pythonPath -m pip install --quiet -r (Join-Path $projectDir 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Die lokalen Abhängigkeiten konnten nicht installiert werden.' }
$oldResearchKey = $env:ANTHROPIC_API_KEY
$oldMediaKey = $env:RUNWAYML_API_SECRET
try {
    if ($AskForKeys) {
        foreach ($keyName in @('ANTHROPIC_API_KEY', 'RUNWAYML_API_SECRET')) {
            $secretValue = Read-Host "$keyName (Eingabe unsichtbar, nur für diesen Lauf)" -AsSecureString
            $secretPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secretValue)
            try {
                [Environment]::SetEnvironmentVariable($keyName, [Runtime.InteropServices.Marshal]::PtrToStringBSTR($secretPointer), 'Process')
            } finally {
                [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($secretPointer)
                $secretValue.Dispose()
            }
        }
    }
    Push-Location -LiteralPath $projectDir
    try {
        $runArgs = @('-X', 'utf8', '-m', 'content_pipeline.runner', '--news-json', 'news.json')
        if ($Execute) { $runArgs += @('--execute', '--watch') }
        & $pythonPath @runArgs
        if ($LASTEXITCODE -ne 0) { throw 'Die Pipeline wurde mit einem Fehler beendet.' }
    } finally { Pop-Location }
} finally {
    $env:ANTHROPIC_API_KEY = $oldResearchKey
    $env:RUNWAYML_API_SECRET = $oldMediaKey
}
