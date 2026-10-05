[CmdletBinding()]
param(
    [ValidateSet("fake", "local", "openai", "openrouter")]
    [string]$Provider = "fake",

    [switch]$Setup,

    [switch]$CheckOnly,

    [switch]$DebugTrace
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
$frontendRoot = Join-Path $projectRoot "frontend"
$virtualEnvironment = Join-Path $projectRoot ".venv"
$logsRoot = Join-Path $projectRoot "logs"
$composePath = Join-Path $projectRoot "compose.yaml"
$apiProcess = $null
$uiProcess = $null
$apiOutputLog = $null
$apiErrorLog = $null
$uiOutputLog = $null
$uiErrorLog = $null
$debugTracePath = Join-Path $logsRoot "debug.log"
$debugTraceEnabledWasDefined = Test-Path Env:DEBUG_TRACE_ENABLED
$debugTracePathWasDefined = Test-Path Env:DEBUG_TRACE_PATH
$previousDebugTraceEnabled = $env:DEBUG_TRACE_ENABLED
$previousDebugTracePath = $env:DEBUG_TRACE_PATH

function Write-Step {
    param([Parameter(Mandatory = $true)][string]$Message)

    Write-Host "[startup] $Message" -ForegroundColor Cyan
}

function Resolve-CommandPath {
    param([Parameter(Mandatory = $true)][string[]]$Names)

    foreach ($name in $Names) {
        $command = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($null -ne $command) {
            return $command.Source
        }
    }

    return $null
}

function Resolve-VenvPython {
    $environmentRoots = @($virtualEnvironment, (Join-Path $projectRoot ".venv-uv"))
    foreach ($environmentRoot in $environmentRoots) {
        foreach ($relativePath in @("Scripts\python.exe", "bin/python")) {
            $candidate = Join-Path $environmentRoot $relativePath
            if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
                continue
            }
            & $candidate -c "import sys; raise SystemExit(0)" *> $null
            if ($LASTEXITCODE -eq 0) {
                return $candidate
            }
        }
    }

    return $null
}

function New-VirtualEnvironment {
    $pythonLauncher = Resolve-CommandPath -Names @("py.exe", "py")
    if ($null -ne $pythonLauncher) {
        Write-Step "Creating Python 3.12 virtual environment..."
        & $pythonLauncher -3.12 -m venv $virtualEnvironment
        if ($LASTEXITCODE -ne 0) {
            throw "Python failed to create .venv. Confirm Python 3.12 is installed."
        }
        return
    }

    $python312 = Resolve-CommandPath -Names @("python3.12", "python.exe", "python")
    if ($null -eq $python312) {
        throw "Python 3.12 was not found. Install it, then run .\start.ps1 -Setup again."
    }

    Write-Step "Creating Python virtual environment..."
    & $python312 -m venv $virtualEnvironment
    if ($LASTEXITCODE -ne 0) {
        throw "Python failed to create .venv. Confirm Python 3.12 or newer is installed."
    }
}

function Resolve-NodeTools {
    $nodePath = Resolve-CommandPath -Names @("node.exe", "node")
    $npmPath = Resolve-CommandPath -Names @("npm.cmd", "npm")

    if (($null -eq $nodePath -or $null -eq $npmPath) -and (Test-Path (Join-Path $projectRoot ".tools"))) {
        $portableNode = Get-ChildItem -Path (Join-Path $projectRoot ".tools") `
            -Filter "node.exe" -File -Recurse -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($null -ne $portableNode) {
            $nodePath = $portableNode.FullName
            $portableNpm = Join-Path $portableNode.DirectoryName "npm.cmd"
            if (Test-Path -LiteralPath $portableNpm -PathType Leaf) {
                $npmPath = $portableNpm
            }
        }
    }

    if ($null -eq $nodePath -or $null -eq $npmPath) {
        throw "Node.js 22 and npm were not found. Install Node.js 22, then rerun the command."
    }

    return @{
        Node = $nodePath
        Npm = $npmPath
    }
}

function Assert-NativeSuccess {
    param([Parameter(Mandatory = $true)][string]$Action)

    if ($LASTEXITCODE -ne 0) {
        throw "$Action failed with exit code $LASTEXITCODE."
    }
}

function New-ChildProcess {
    param(
        [Parameter(Mandatory = $true)][string]$FileName,
        [Parameter(Mandatory = $true)][string]$Arguments,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [Parameter(Mandatory = $true)][string]$StandardOutputPath,
        [Parameter(Mandatory = $true)][string]$StandardErrorPath
    )

    $process = Start-Process -FilePath $FileName -ArgumentList $Arguments `
        -WorkingDirectory $WorkingDirectory -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $StandardOutputPath `
        -RedirectStandardError $StandardErrorPath
    if ($null -eq $process) {
        throw "Failed to start $FileName."
    }

    return $process
}

function Get-ChildProcessExitCode {
    param([Parameter(Mandatory = $true)][System.Diagnostics.Process]$ChildProcess)

    try {
        if (-not $ChildProcess.HasExited) {
            return "unknown"
        }

        $ChildProcess.WaitForExit()
        $ChildProcess.Refresh()
        return "$($ChildProcess.ExitCode)"
    }
    catch {
        return "unknown"
    }
}

function Get-PortOwnerDescription {
    param([Parameter(Mandatory = $true)][int]$Port)

    try {
        $connection = Get-NetTCPConnection -State Listen -LocalPort $Port `
            -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($null -eq $connection) {
            return ""
        }

        $ownerProcess = Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
        if ($null -ne $ownerProcess) {
            return " PID $($connection.OwningProcess) ($($ownerProcess.ProcessName)) is listening."
        }
        return " PID $($connection.OwningProcess) is listening."
    }
    catch {
        return ""
    }
}

function Assert-PortAvailable {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][int]$Port
    )

    $listener = [System.Net.Sockets.TcpListener]::new(
        [System.Net.IPAddress]::Loopback,
        $Port
    )
    $listener.Server.ExclusiveAddressUse = $true
    try {
        $listener.Start()
    }
    catch [System.Net.Sockets.SocketException] {
        $owner = Get-PortOwnerDescription -Port $Port
        throw "$Name cannot start because http://127.0.0.1:$Port is already in use.$owner " +
            "Stop the existing process, then rerun start.ps1."
    }
    finally {
        $listener.Stop()
    }
}

function Wait-ForUrl {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][System.Diagnostics.Process]$ChildProcess,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $ChildProcess.Refresh()
        if ($ChildProcess.HasExited) {
            $exitCode = Get-ChildProcessExitCode -ChildProcess $ChildProcess
            throw "$Name stopped during startup with exit code $exitCode."
        }

        $isReady = $false
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) {
                $isReady = $true
            }
        }
        catch {
            Start-Sleep -Milliseconds 300
        }

        if ($isReady) {
            Start-Sleep -Milliseconds 250
            $ChildProcess.Refresh()
            if ($ChildProcess.HasExited) {
                $exitCode = Get-ChildProcessExitCode -ChildProcess $ChildProcess
                throw "$Name stopped during startup with exit code $exitCode."
            }
            return
        }
    }

    throw "$Name did not become ready at $Url within $TimeoutSeconds seconds."
}

function Stop-ChildProcess {
    param([System.Diagnostics.Process]$ChildProcess)

    if ($null -ne $ChildProcess -and -not $ChildProcess.HasExited) {
        Stop-Process -Id $ChildProcess.Id -Force -ErrorAction SilentlyContinue
        $ChildProcess.WaitForExit(5000) | Out-Null
    }
}

function Show-LogTail {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [string]$Path,
        [int]$Lines = 25
    )

    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return
    }

    $content = Get-Content -LiteralPath $Path -Tail $Lines -ErrorAction SilentlyContinue
    if ($null -eq $content -or @($content).Count -eq 0) {
        return
    }

    Write-Host ""
    Write-Host "----- $Label (last $Lines lines) -----" -ForegroundColor Yellow
    $content | ForEach-Object { Write-Host $_ }
    Write-Host "----- end $Label -----" -ForegroundColor Yellow
}

function Get-PersistenceTarget {
    param([Parameter(Mandatory = $true)][string]$PythonPath)

    $target = & $PythonPath -m `
        smb_requirement_agent.infrastructure.persistence.startup_check --target
    Assert-NativeSuccess -Action "Persistence target detection"
    return "$target".Trim()
}

function Test-PersistenceReady {
    param([Parameter(Mandatory = $true)][string]$PythonPath)

    & $PythonPath -m `
        smb_requirement_agent.infrastructure.persistence.startup_check --quiet
    return $LASTEXITCODE -eq 0
}

function Wait-ForPersistence {
    param(
        [Parameter(Mandatory = $true)][string]$PythonPath,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-PersistenceReady -PythonPath $PythonPath) {
            return
        }
        Start-Sleep -Milliseconds 500
    }

    & $PythonPath -m smb_requirement_agent.infrastructure.persistence.startup_check
    throw "PostgreSQL did not become ready within $TimeoutSeconds seconds."
}

Push-Location $projectRoot
try {
    if ($Setup -and $null -eq (Resolve-VenvPython)) {
        New-VirtualEnvironment
    }

    $pythonPath = Resolve-VenvPython
    if ($null -eq $pythonPath) {
        throw "The .venv environment is missing. Run .\start.ps1 -Setup first."
    }

    $nodeTools = Resolve-NodeTools

    if ($Setup) {
        Write-Step "Installing backend dependencies..."
        & $pythonPath -m pip install -e ".[dev]"
        Assert-NativeSuccess -Action "Backend dependency installation"

        Write-Step "Installing locked frontend dependencies..."
        Push-Location $frontendRoot
        try {
            & $nodeTools.Npm ci
            Assert-NativeSuccess -Action "Frontend dependency installation"
        }
        finally {
            Pop-Location
        }
    }

    $viteScript = Join-Path $frontendRoot "node_modules/vite/bin/vite.js"
    if (-not (Test-Path -LiteralPath $viteScript -PathType Leaf)) {
        throw "Frontend dependencies are missing. Run .\start.ps1 -Setup first."
    }

    $env:LLM_PROVIDER = $Provider
    if ($DebugTrace) {
        $env:DEBUG_TRACE_ENABLED = "true"
        $env:DEBUG_TRACE_PATH = $debugTracePath
    }
    Write-Step "Validating model configuration..."
    $profileCheckArguments = @("-m", "smb_requirement_agent.interfaces.cli.llm", "check")
    if ($PSBoundParameters.ContainsKey("Provider")) {
        $profileCheckArguments += @("--explicit-provider", $Provider)
    }
    & $pythonPath @profileCheckArguments
    Assert-NativeSuccess -Action "Application configuration validation"

    $persistenceTarget = Get-PersistenceTarget -PythonPath $pythonPath

    if ($CheckOnly) {
        Write-Step "Checking persistence readiness..."
        & $pythonPath -m smb_requirement_agent.infrastructure.persistence.startup_check
        Assert-NativeSuccess -Action "Persistence readiness check"
        Write-Step "Startup prerequisites and configuration are valid."
        return
    }

    Write-Step "Checking local API and UI ports..."
    Assert-PortAvailable -Name "API" -Port 8000
    Assert-PortAvailable -Name "Review UI" -Port 5173

    if ($persistenceTarget -eq "local-postgres") {
        if (-not (Test-PersistenceReady -PythonPath $pythonPath)) {
            $dockerPath = Resolve-CommandPath -Names @("docker.exe", "docker")
            if ($null -eq $dockerPath) {
                throw "Local PostgreSQL is not ready and Docker was not found. Install/start " +
                    "Docker Desktop, or set PERSISTENCE_PROVIDER=memory."
            }
            Write-Step "Starting local PostgreSQL with Docker Compose..."
            & $dockerPath compose --file $composePath up --detach postgres
            Assert-NativeSuccess -Action "PostgreSQL Compose startup"
            Write-Step "Waiting for PostgreSQL to become ready..."
            Wait-ForPersistence -PythonPath $pythonPath
        }
    }
    elseif ($persistenceTarget -eq "external-postgres") {
        Write-Step "Checking external PostgreSQL readiness..."
        & $pythonPath -m smb_requirement_agent.infrastructure.persistence.startup_check
        Assert-NativeSuccess -Action "Persistence readiness check"
    }

    if ($persistenceTarget -ne "memory") {
        Write-Step "Applying pending database migrations..."
        & $pythonPath -m smb_requirement_agent.infrastructure.persistence.migrate
        Assert-NativeSuccess -Action "Database migration"
    }

    New-Item -ItemType Directory -Path $logsRoot -Force | Out-Null
    $runTimestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $apiOutputLog = Join-Path $logsRoot "api-$runTimestamp.log"
    $apiErrorLog = Join-Path $logsRoot "api-error-$runTimestamp.log"
    $uiOutputLog = Join-Path $logsRoot "ui-$runTimestamp.log"
    $uiErrorLog = Join-Path $logsRoot "ui-error-$runTimestamp.log"

    Write-Step "Starting API on http://127.0.0.1:8000..."
    $apiArguments = "-m uvicorn smb_requirement_agent.interfaces.api.main:app --host 127.0.0.1 --port 8000"
    $apiProcess = New-ChildProcess -FileName $pythonPath -Arguments $apiArguments `
        -WorkingDirectory $projectRoot -StandardOutputPath $apiOutputLog `
        -StandardErrorPath $apiErrorLog
    Wait-ForUrl -Name "API" -Url "http://127.0.0.1:8000/health" `
        -ChildProcess $apiProcess

    Write-Step "Starting review UI on http://127.0.0.1:5173..."
    $uiArguments = "`"$viteScript`" --host 127.0.0.1 --port 5173"
    $uiProcess = New-ChildProcess -FileName $nodeTools.Node -Arguments $uiArguments `
        -WorkingDirectory $frontendRoot -StandardOutputPath $uiOutputLog `
        -StandardErrorPath $uiErrorLog
    Wait-ForUrl -Name "Review UI" -Url "http://127.0.0.1:5173" `
        -ChildProcess $uiProcess

    Write-Host ""
    Write-Host "Application ready" -ForegroundColor Green
    Write-Host "  Review UI:  http://127.0.0.1:5173"
    Write-Host "  API docs:   http://127.0.0.1:8000/docs"
    Write-Host "  Health:     http://127.0.0.1:8000/health"
    Write-Host "  Provider:   $Provider"
    $knowledgeTarget = & $pythonPath -m smb_requirement_agent.interfaces.knowledge_target
    Write-Host "  Knowledge:  $knowledgeTarget"
    Write-Host "  API log:    $apiOutputLog"
    Write-Host "  API errors: $apiErrorLog"
    Write-Host "  UI log:     $uiOutputLog"
    Write-Host "  UI errors:  $uiErrorLog"
    if ($DebugTrace) {
        Write-Host "  Debug trace: $debugTracePath"
        Write-Host "  WARNING: includes requirement text and final LLM completions."
    }
    Write-Host ""
    Write-Host "Press Ctrl+C to stop both servers."

    while (-not $apiProcess.HasExited -and -not $uiProcess.HasExited) {
        Start-Sleep -Milliseconds 500
    }

    if ($apiProcess.HasExited) {
        $exitCode = Get-ChildProcessExitCode -ChildProcess $apiProcess
        throw "API stopped unexpectedly with exit code $exitCode."
    }
    $exitCode = Get-ChildProcessExitCode -ChildProcess $uiProcess
    throw "Review UI stopped unexpectedly with exit code $exitCode."
}
catch {
    $apiDied = ($null -ne $apiProcess) -and $apiProcess.HasExited
    $uiDied = ($null -ne $uiProcess) -and $uiProcess.HasExited
    if ($apiDied -or $uiDied) {
        Write-Host ""
        Write-Host "Startup failed: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "Showing the last log lines so you can see the real cause:" -ForegroundColor Red
        Show-LogTail -Label "API stderr" -Path $apiErrorLog
        Show-LogTail -Label "API stdout" -Path $apiOutputLog
        Show-LogTail -Label "Review UI stderr" -Path $uiErrorLog
        Show-LogTail -Label "Review UI stdout" -Path $uiOutputLog
    }
    throw
}
finally {
    Stop-ChildProcess -ChildProcess $uiProcess
    Stop-ChildProcess -ChildProcess $apiProcess
    if ($DebugTrace) {
        if ($debugTraceEnabledWasDefined) {
            $env:DEBUG_TRACE_ENABLED = $previousDebugTraceEnabled
        }
        else {
            Remove-Item Env:DEBUG_TRACE_ENABLED -ErrorAction SilentlyContinue
        }
        if ($debugTracePathWasDefined) {
            $env:DEBUG_TRACE_PATH = $previousDebugTracePath
        }
        else {
            Remove-Item Env:DEBUG_TRACE_PATH -ErrorAction SilentlyContinue
        }
    }
    Pop-Location
}
