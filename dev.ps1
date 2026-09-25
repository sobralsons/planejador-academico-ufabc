param([Parameter(Mandatory=$true)][ValidateSet('start','status','test','test-db','reset-db','stop')][string]$Command)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$stateDir = Join-Path $PSScriptRoot '.dev-local'
$statePath = Join-Path $stateDir 'api.json'

function Invoke-Python {
    param([string[]]$Arguments)
    & $python @Arguments
    if ($LASTEXITCODE -ne 0) { throw 'Comando local falhou.' }
}

function Get-OwnedApi {
    if (-not (Test-Path -LiteralPath $statePath)) { return $null }
    $saved = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    $process = Get-Process -Id $saved.pid -ErrorAction SilentlyContinue
    if ($null -eq $process) { return $null }
    # Materializar o handle antes de verificar identidade evita encerrar PID reutilizado.
    $null = $process.Handle
    if ($process.StartTime.ToUniversalTime().Ticks.ToString() -ne $saved.started -or
        $process.Path -ne $python) { throw 'PID pertence a outro processo; API nao sera encerrada.' }
    return $process
}

function Assert-Listeners {
    param([int]$Port, $Owner = $null)
    $listeners = @(Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object LocalPort -eq $Port)
    foreach ($listener in $listeners) {
        if ($listener.LocalAddress -notin @('127.0.0.1','::1')) { throw 'API fora de loopback.' }
        if ($null -eq $Owner) { throw 'Porta da API ocupada por outro processo.' }
        if ($listener.OwningProcess -ne $Owner.Id) {
            $child = Get-ApiChild -Owner $Owner
            if ($null -eq $child -or $listener.OwningProcess -ne $child.Id) { throw 'Porta da API ocupada por outro processo.' }
        }
    }
}

function Get-ApiChild {
    param($Owner)
    # O redirector da venv no Windows pode manter um unico interpretador filho.
    $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$($Owner.Id)" -ErrorAction Stop |
        Where-Object { $_.ExecutablePath -ne (Join-Path $env:SystemRoot 'System32\conhost.exe') })
    if ($children.Count -eq 0) { return $null }
    if ($children.Count -ne 1 -or $children[0].ExecutablePath -ne $basePython -or
        $children[0].CommandLine -notmatch '\s-m\s+scripts\.executar_api_local\s*$') {
        throw 'Filho inesperado do launcher; operacao recusada.'
    }
    $child = Get-Process -Id $children[0].ProcessId -ErrorAction Stop
    $null = $child.Handle
    if ($child.Path -ne $basePython -or $child.StartTime -lt $Owner.StartTime) { throw 'Identidade do filho mudou.' }
    return $child
}

function Stop-OwnedApi {
    param($Owner)
    $child = Get-ApiChild -Owner $Owner
    if ($null -ne $child) { $child.Kill(); $child.WaitForExit() }
    if (-not $Owner.HasExited) { $Owner.Kill(); $Owner.WaitForExit() }
}

Push-Location $PSScriptRoot
$lock = $null
try {
    if (-not (Test-Path -LiteralPath $python)) { throw 'Execute preparar_ambiente_windows.bat (Python 3.12).' }
    Invoke-Python -Arguments @('-c', 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)')
    $basePython = (Invoke-Python -Arguments @('-c', 'import sys; print(sys._base_executable)')).Trim()
    $null = New-Item -ItemType Directory -Force -Path $stateDir
    $lock = [IO.File]::Open((Join-Path $stateDir 'command.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    if ($Command -eq 'test') {
        Invoke-Python -Arguments @('-m','compileall','-q','app.py','app_interno.py','main.py','planejador','ferramentas','api','persistencia','scripts')
        Invoke-Python -Arguments @('-m','pytest','-q')
    } elseif ($Command -eq 'stop') {
        $owned = Get-OwnedApi
        if ($null -ne $owned) { Stop-OwnedApi -Owner $owned }
        if (Test-Path -LiteralPath $statePath) { Remove-Item -LiteralPath $statePath }
        Invoke-Python -Arguments @('-m','scripts.dev_local','stop')
    } else {
        $cfg = (Invoke-Python -Arguments @('-m','scripts.dev_local','config')) | ConvertFrom-Json
        $owned = Get-OwnedApi
        Assert-Listeners -Port $cfg.port -Owner $owned
        Invoke-Python -Arguments @('-m','scripts.dev_local',$Command)
        if ($Command -eq 'start' -and $null -eq $owned) {
            $owned = Start-Process -FilePath $python -ArgumentList @('-m','scripts.executar_api_local') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $stateDir 'api.log') -RedirectStandardError (Join-Path $stateDir 'api-error.log')
            try {
                @{pid=$owned.Id; started=$owned.StartTime.ToUniversalTime().Ticks.ToString()} | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8
                $ready = $false
                for ($attempt=0; $attempt -lt 30; $attempt++) {
                    if ($owned.HasExited) { throw 'API encerrou durante inicializacao.' }
                    Assert-Listeners -Port $cfg.port -Owner $owned
                    try {
                        $hostAddress = if ($cfg.host -eq '::1') { '[::1]' } else { $cfg.host }
                        $null = Invoke-RestMethod -Uri "http://${hostAddress}:$($cfg.port)/health" -TimeoutSec 1 -MaximumRedirection 0
                        $ready = $true
                        break
                    } catch { Start-Sleep -Milliseconds 300 }
                }
                if (-not $ready) { throw 'API nao ficou pronta.' }
            } catch {
                if (-not $owned.HasExited) { Stop-OwnedApi -Owner $owned }
                Remove-Item -LiteralPath $statePath -ErrorAction SilentlyContinue
                throw
            }
        }
        if ($Command -in @('start','status')) {
            if ($null -eq $owned -or $owned.HasExited) { throw 'API parada. Execute dev.ps1 start.' }
            Assert-Listeners -Port $cfg.port -Owner $owned
            $hostAddress = if ($cfg.host -eq '::1') { '[::1]' } else { $cfg.host }
            $null = Invoke-RestMethod -Uri "http://${hostAddress}:$($cfg.port)/health" -TimeoutSec 3 -MaximumRedirection 0
            Write-Host "API local: OK ($($cfg.host):$($cfg.port))."
        }
    }
} catch {
    Write-Error $_ -ErrorAction Continue
    exit 1
} finally {
    if ($null -ne $lock) { $lock.Dispose() }
    Pop-Location
}
