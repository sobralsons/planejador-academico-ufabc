import copy
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

import pytest

from scripts import dev_local as dev


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    monkeypatch.setattr(dev, "ROOT", tmp_path)
    (tmp_path / "supabase").mkdir()
    (tmp_path / "supabase/config.toml").write_text('project_id = "test-local"\n')
    for key in ("DATABASE_URL", "DOCKER_HOST", "DOCKER_CONTEXT"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("API_HOST", "127.0.0.1")
    monkeypatch.setenv("API_PORT", "8000")
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    return dev.config()


@pytest.mark.parametrize("value", [
    "https://remote.supabase.co", "http://0.0.0.0:54321", "http://[::]:54321",
    "http://localhost.evil:54321", "http://localhost:54321?host=remote",
    "http://user:secret@localhost:54321", "http://localhost:54321/auth",
    "http://localhost", "http://localhost:invalid", "http://[bad",
])
def test_endpoint_rejects_nonlocal_or_ambiguous(value):
    with pytest.raises(RuntimeError):
        dev.endpoint(value, {"http"})


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "[::1]"])
def test_endpoint_accepts_loopback(host):
    assert dev.endpoint(f"http://{host}:54321", {"http"}) == 54321


@pytest.mark.parametrize("key,value", [
    ("APP_ENV", "production"), ("API_HOST", "0.0.0.0"), ("API_HOST", "::"),
    ("API_PORT", "65536"), ("SUPABASE_URL", "http://localhost:1234"),
    ("DATABASE_URL", "postgresql://postgres:secret@remote:54322/postgres"),
    ("DATABASE_URL", "postgresql://localhost:54322/postgres?host=remote"),
])
def test_config_fails_closed(cfg, monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(RuntimeError):
        dev.config()


def container(cfg):
    return {
        "Config": {"Labels": {"com.supabase.cli.project": cfg["project"],
                              "com.supabase.cli.workdir": str(dev.ROOT)}},
        "HostConfig": {"NetworkMode": dev.NETWORK,
                       "PortBindings": {"5432/tcp": [{"HostIp": "", "HostPort": "54322"}]}},
        "NetworkSettings": {"Networks": {dev.NETWORK: {}},
                            "Ports": {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "54322"}]}},
    }


def test_network_default_with_actual_loopback_is_accepted(cfg):
    dev.validate_containers([container(cfg)], cfg)


@pytest.mark.parametrize("ip", ["0.0.0.0", "::", "", "192.168.1.2"])
def test_actual_published_bind_must_be_loopback(cfg, ip):
    data = container(cfg)
    data["NetworkSettings"]["Ports"]["5432/tcp"][0]["HostIp"] = ip
    with pytest.raises(RuntimeError, match="Porta Docker"):
        dev.validate_containers([data], cfg)


def test_stopped_container_with_explicit_wildcard_is_rejected(cfg):
    data = container(cfg)
    data["NetworkSettings"]["Ports"] = {}
    data["HostConfig"]["PortBindings"]["5432/tcp"][0]["HostIp"] = "0.0.0.0"
    with pytest.raises(RuntimeError):
        dev.validate_containers([data], cfg)


def test_other_container_on_relevant_port_is_checked(cfg):
    data = container(cfg)
    data["Config"]["Labels"] = {}
    data["NetworkSettings"]["Networks"] = {"bridge": {}}
    with pytest.raises(RuntimeError):
        dev.validate_containers([data], cfg)


def test_unrelated_ports_and_networks_are_not_changed(cfg):
    data = container(cfg)
    data["Config"]["Labels"] = {}
    data["NetworkSettings"]["Networks"] = {"bridge": {}}
    for source in (data["HostConfig"]["PortBindings"], data["NetworkSettings"]["Ports"]):
        source["5432/tcp"][0] = {"HostIp": "0.0.0.0", "HostPort": "12345"}
    before = copy.deepcopy(data)
    dev.validate_containers([data], cfg)
    assert before == data


def test_other_checkout_cannot_be_stopped(cfg):
    data = container(cfg)
    data["Config"]["Labels"]["com.supabase.cli.workdir"] = "/another-checkout"
    with pytest.raises(RuntimeError, match="outra pasta"):
        dev.validate_containers([data], cfg, safety=False)


@pytest.mark.parametrize("remote", ["tcp://127.0.0.1:2375", "ssh://remote", "tcp://remote:2376"])
def test_remote_docker_context_is_rejected(monkeypatch, cfg, remote):
    monkeypatch.setattr(dev, "run", lambda _: json.dumps([{"Endpoints": {"docker": {"Host": remote}}}]))
    with pytest.raises(RuntimeError, match="Docker"):
        dev.docker_local()


def test_docker_override_is_rejected(monkeypatch, cfg):
    monkeypatch.setenv("DOCKER_HOST", "tcp://remote")
    with pytest.raises(RuntimeError):
        dev.docker_local()


def test_unsafe_network_is_not_recreated(monkeypatch):
    calls = []
    def run(args):
        calls.append(args)
        if args[2] == "ls":
            return dev.NETWORK
        return json.dumps([{"Driver": "bridge", "Options": {}}])
    monkeypatch.setattr(dev, "run", run)
    with pytest.raises(RuntimeError):
        dev.network(create=True)
    assert not any("create" in args or "rm" in args for args in calls)


@pytest.fixture
def commands(cfg, monkeypatch):
    calls = []
    monkeypatch.setattr(dev, "docker_local", lambda: calls.append("docker"))
    monkeypatch.setattr(dev, "network", lambda **kw: calls.append("network"))
    monkeypatch.setattr(dev, "ports", lambda *a, **kw: calls.append("ports"))
    def supabase(*args, **kwargs):
        calls.append(args)
        return json.dumps({"API_URL": "http://127.0.0.1:54321", "DB_URL": "postgresql://localhost:54322/postgres"})
    monkeypatch.setattr(dev, "supabase", supabase)
    return calls


def test_start_guards_precede_start_and_repeat_afterwards(commands):
    dev.execute("start")
    assert commands[:5] == ["docker", "network", "ports", ("start",), "ports"]
    assert not any("reset" in call for call in commands)


def test_failed_preflight_never_starts(cfg, monkeypatch, commands):
    monkeypatch.setattr(dev, "ports", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("unsafe")))
    with pytest.raises(RuntimeError):
        dev.execute("start")
    assert ("start",) not in commands


def test_failed_postflight_stops_only_project_without_deleting_volumes(commands, monkeypatch):
    checks = 0
    def ports(*args, safety=True):
        nonlocal checks
        checks += 1
        if checks == 2 and safety:
            raise RuntimeError("unsafe after start")
    monkeypatch.setattr(dev, "ports", ports)
    with pytest.raises(RuntimeError, match="unsafe"):
        dev.execute("start")
    assert ("start",) in commands
    assert commands[-1] == ("stop", "--project-id", "test-local")


def test_remote_status_is_rejected(commands, monkeypatch):
    monkeypatch.setattr(dev, "supabase", lambda *a, **kw: json.dumps({
        "API_URL": "https://remote.supabase.co", "DB_URL": "postgresql://localhost:54322/postgres"}))
    with pytest.raises(RuntimeError):
        dev.execute("status")


@pytest.mark.parametrize("answer", ["", "yes", "reset"])
def test_reset_requires_exact_confirmation(commands, monkeypatch, answer):
    monkeypatch.setattr("builtins.input", lambda _: answer)
    with pytest.raises(RuntimeError, match="cancelado"):
        dev.execute("reset-db")
    assert not any("reset" in call for call in commands)


def test_reset_explicitly_targets_local(commands, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "RESET")
    dev.execute("reset-db")
    assert ("db", "reset", "--local") in commands


def test_pgtap_explicitly_targets_local(commands):
    dev.execute("test-db")
    assert ("test", "db", "--local") in commands


def test_stop_preserves_volumes_even_with_invalid_api_env(commands, monkeypatch):
    monkeypatch.setenv("API_HOST", "0.0.0.0")
    dev.execute("stop")
    assert ("stop", "--project-id", "test-local") in commands
    assert "network" not in commands


def test_run_decodifica_saida_utf8_sem_depender_do_locale_do_windows(tmp_path, monkeypatch):
    monkeypatch.setattr(dev, "ROOT", tmp_path)

    saida = dev.run([
        sys.executable,
        "-c",
        "import sys; sys.stdout.buffer.write('А'.encode('utf-8'))",
    ])

    assert saida == "А"


def test_command_failure_does_not_print_secrets(monkeypatch, capsys):
    monkeypatch.setattr(dev.subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(a, 1, "SECRET", "SECRET"))
    with pytest.raises(RuntimeError) as error:
        dev.run(["supabase", "start"])
    assert "SECRET" not in str(error.value) + capsys.readouterr().out


@pytest.mark.skipif(os.name != "nt", reason="Identidade de processo Windows")
def test_powershell_refuses_reused_pid_and_accepts_owned_process(tmp_path):
    # Carrega as funcoes reais pelo AST, sem executar comandos de servico.
    source = Path(__file__).resolve().parents[1] / "dev.ps1"
    script = tmp_path / "check.ps1"
    script.write_text(r'''
param($Source, $State)
$ErrorActionPreference = 'Stop'
$tokens = $null; $errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($Source, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Syntax error' }
$ast.FindAll({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst]}, $false) | ForEach-Object { . ([scriptblock]::Create($_.Extent.Text)) }
$statePath = $State
$process = Get-Process -Id $PID
$python = $process.Path
@{pid=$PID; started='0'} | ConvertTo-Json | Set-Content $State
$rejected = $false
try { Get-OwnedApi } catch { $rejected = $true }
if (-not $rejected) { throw 'Reused PID accepted' }
@{pid=$PID; started=$process.StartTime.ToUniversalTime().Ticks.ToString()} | ConvertTo-Json | Set-Content $State
if ((Get-OwnedApi).Id -ne $PID) { throw 'Owned process not recognized' }
''', encoding="utf-8")
    result = subprocess.run([shutil.which("powershell.exe"), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), str(source), str(tmp_path / "api.json")], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(os.name != "nt", reason="Launcher de venv e processos Windows")
def test_real_windows_launcher_child_and_safe_stop(tmp_path):
    root = Path(__file__).resolve().parents[1]
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    script = tmp_path / "lifecycle.ps1"
    script.write_text(r'''
param($Source, $PythonPath, $BasePath, $Root, $Port, $Logs)
$ErrorActionPreference = 'Stop'
$tokens = $null; $errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($Source, [ref]$tokens, [ref]$errors)
$ast.FindAll({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst]}, $false) | ForEach-Object { . ([scriptblock]::Create($_.Extent.Text)) }
$python = $PythonPath; $basePython = $BasePath
$env:API_HOST = '127.0.0.1'; $env:API_PORT = $Port
$owned = Start-Process -FilePath $python -ArgumentList @('-m','scripts.executar_api_local') -WorkingDirectory $Root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $Logs 'out.log') -RedirectStandardError (Join-Path $Logs 'err.log')
try {
    $ready = $false
    for ($i=0; $i -lt 30; $i++) {
        if ($owned.HasExited) { throw 'Launcher exited' }
        Assert-Listeners -Port $Port -Owner $owned
        try { $null = Invoke-RestMethod "http://127.0.0.1:$Port/health" -TimeoutSec 1; $ready = $true; break } catch { Start-Sleep -Milliseconds 200 }
    }
    if (-not $ready) { throw 'Not ready' }
    Assert-Listeners -Port $Port -Owner $owned
    $rejected = $false
    try { Assert-Listeners -Port $Port } catch { $rejected = $true }
    if (-not $rejected) { throw 'Unowned listener accepted' }
} finally {
    if (-not $owned.HasExited) { Stop-OwnedApi -Owner $owned }
}
if (-not $owned.HasExited) { throw 'Launcher still running' }
$listeners = @(Get-NetTCPConnection -State Listen | Where-Object LocalPort -eq $Port)
if ($listeners.Count) { throw 'Orphan child still listening' }
''', encoding="utf-8")
    result = subprocess.run([
        shutil.which("powershell.exe"), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
        str(script), str(root / "dev.ps1"), sys.executable, sys._base_executable,
        str(root), str(port), str(tmp_path),
    ], capture_output=True, text=True, timeout=90, env=dict(os.environ))
    assert result.returncode == 0, result.stdout + result.stderr


def test_dev_ps1_isola_temporarios_do_pytest_em_dev_local():
    raiz = Path(__file__).resolve().parents[1]
    conteudo = (raiz / "dev.ps1").read_text(encoding="utf-8")

    assert "$pytestTemp = Join-Path $stateDir 'pytest-temp'" in conteudo
    assert "$pytestCache = Join-Path $stateDir 'pytest-cache'" in conteudo
    assert "'--basetemp',$pytestTemp" in conteudo
    assert '"cache_dir=$pytestCache"' in conteudo


def test_dev_ps1_expoe_comando_e2e_sem_bloco_powershell_fragil():
    raiz = Path(__file__).resolve().parents[1]
    conteudo = (raiz / "dev.ps1").read_text(encoding="utf-8")

    assert "'test-e2e'" in conteudo
    assert "scripts.testar_persistencia_e2e_local" in conteudo
