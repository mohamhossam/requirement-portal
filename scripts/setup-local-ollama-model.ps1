[CmdletBinding()]
param(
    [string]$SourceModel = "qwen3-vl:8b",
    [string]$ProjectModel = "smb-qwen3-vl:8b-16k",
    [string]$OllamaBaseUrl = "http://127.0.0.1:11434"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-OllamaPath {
    $command = Get-Command ollama.exe -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -ne $command) {
        return $command.Source
    }

    $process = Get-Process -Name ollama -ErrorAction SilentlyContinue |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_.Path) } |
        Select-Object -First 1
    if ($null -ne $process) {
        return $process.Path
    }

    $installed = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
    if (Test-Path -LiteralPath $installed -PathType Leaf) {
        return $installed
    }

    throw "Ollama was not found. Install or start Ollama, then rerun this script."
}

function Get-ModelDetails {
    param([Parameter(Mandatory = $true)][string]$Model)

    $body = @{ model = $Model } | ConvertTo-Json -Compress
    return Invoke-RestMethod -Method Post -Uri "$OllamaBaseUrl/api/show" `
        -ContentType "application/json" -Body $body -TimeoutSec 30
}

$ollamaPath = Resolve-OllamaPath
$modelfile = Join-Path $PSScriptRoot "ollama\Modelfile.smb-qwen3-vl-8b-16k"
if (-not (Test-Path -LiteralPath $modelfile -PathType Leaf)) {
    throw "Project Modelfile is missing: $modelfile"
}

$source = Get-ModelDetails -Model $SourceModel
if (@($source.capabilities) -notcontains "vision") {
    throw "Source model '$SourceModel' is not reported as vision-capable by Ollama."
}

Write-Host "[ollama-setup] Creating or updating $ProjectModel..." -ForegroundColor Cyan
& $ollamaPath create $ProjectModel -f $modelfile
if ($LASTEXITCODE -ne 0) {
    throw "Ollama failed to create '$ProjectModel' (exit code $LASTEXITCODE)."
}

$created = Get-ModelDetails -Model $ProjectModel
$parameters = "$($created.parameters)"
if ($parameters -notmatch "(?m)^num_ctx\s+16384\s*$") {
    throw "Created model does not report num_ctx 16384."
}
if ($parameters -notmatch "(?m)^temperature\s+0(?:\.0+)?\s*$") {
    throw "Created model does not report temperature 0."
}
if (@($created.capabilities) -notcontains "vision") {
    throw "Created model is not reported as vision-capable."
}

Write-Host "[ollama-setup] Loading the alias and checking its allocated context..." `
    -ForegroundColor Cyan
$probe = @{
    model = $ProjectModel
    messages = @(@{ role = "user"; content = "Reply with OK." })
    max_tokens = 1
    reasoning_effort = "none"
    stream = $false
} | ConvertTo-Json -Depth 10
Invoke-RestMethod -Method Post -Uri "$OllamaBaseUrl/v1/chat/completions" `
    -ContentType "application/json" -Body $probe -TimeoutSec 120 | Out-Null

$running = Invoke-RestMethod -Method Get -Uri "$OllamaBaseUrl/api/ps" -TimeoutSec 30
$loaded = @($running.models) |
    Where-Object { $_.name -eq $ProjectModel -or $_.model -eq $ProjectModel } |
    Select-Object -First 1
if ($null -eq $loaded) {
    throw "Ollama did not report '$ProjectModel' as loaded after the probe."
}
if ([int64]$loaded.context_length -lt 16384) {
    throw "Ollama allocated only $($loaded.context_length) tokens; at least 16384 are required."
}

Write-Host "[ollama-setup] Ready: $ProjectModel (context $($loaded.context_length))." `
    -ForegroundColor Green
