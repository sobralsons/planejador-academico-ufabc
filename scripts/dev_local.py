"""Guardas e comandos Supabase locais; nunca imprime credenciais da CLI."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib
from urllib.parse import urlsplit

from scripts.executar_api_local import carregar_env_local

ROOT = Path(__file__).resolve().parents[1]
NETWORK = "app-ufabc-local"
BIND_OPTION = "com.docker.network.bridge.host_binding_ipv4"
LOCAL = {"127.0.0.1", "::1", "localhost"}


def run(args: list[str], *, visible: bool = False) -> str:
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    if visible:
        print(result.stdout, end="")
    if result.returncode:
        # Docker inspect/status/start podem conter segredos. Nao ecoar stderr.
        raise RuntimeError(f"Falha em {Path(args[0]).stem}; verifique o servico local.")
    return result.stdout


def endpoint(value: str, schemes: set[str], *, credentials: bool = False) -> int:
    try:
        url = urlsplit(value)
        if (url.scheme not in schemes or url.hostname not in LOCAL
                or url.query or url.fragment
                or (not credentials and (url.username or url.password or url.path not in {"", "/"}))):
            raise ValueError
        if url.port is None:
            raise ValueError
        return url.port
    except ValueError:
        raise RuntimeError("Endpoint deve ser local, com porta explicita e sem parametros.") from None


def project_config() -> dict:
    path = ROOT / "supabase/config.toml"
    if not path.exists():
        raise RuntimeError("Execute npx --yes supabase@2.117.0 init uma vez; preserve seu config.toml.")
    cfg = tomllib.loads(path.read_text(encoding="utf-8-sig"))
    project = cfg.get("project_id", "")
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", project):
        raise RuntimeError("project_id local invalido.")
    return cfg


def config() -> dict:
    carregar_env_local(ROOT / ".env.local")
    if os.environ.get("APP_ENV") != "development":
        raise RuntimeError("APP_ENV deve ser development.")
    host = os.environ.get("API_HOST", "127.0.0.1").strip()
    port = int(os.environ.get("API_PORT", "8000"))
    if host not in LOCAL or not 1 <= port <= 65535:
        raise RuntimeError("API deve escutar somente em loopback, em porta valida.")
    cfg = project_config()
    api_port = cfg.get("api", {}).get("port", 54321)
    db_port = cfg.get("db", {}).get("port", 54322)
    if endpoint(os.environ.get("SUPABASE_URL", ""), {"http"}) != api_port:
        raise RuntimeError("SUPABASE_URL diverge da porta local do config.toml.")
    database = os.environ.get("DATABASE_URL", "")
    if database and endpoint(database, {"postgres", "postgresql"}, credentials=True) != db_port:
        raise RuntimeError("DATABASE_URL diverge da porta local do config.toml.")
    ports = {port, api_port, db_port, cfg.get("db", {}).get("shadow_port", 54320)}
    for section, default in (("studio", 54323), ("inbucket", 54324), ("analytics", 54327)):
        ports.add(cfg.get(section, {}).get("port", default))
    ports.add(cfg.get("db", {}).get("pooler", {}).get("port", 54329))
    return {"project": cfg["project_id"], "host": host, "port": port, "ports": ports}


def docker_local() -> None:
    # CLI e guardas devem usar o mesmo daemon; rejeitar overrides ambiguos.
    if os.environ.get("DOCKER_HOST") or os.environ.get("DOCKER_CONTEXT"):
        raise RuntimeError("Remova DOCKER_HOST/DOCKER_CONTEXT; use um contexto Docker local.")
    context = json.loads(run(["docker", "context", "inspect"]))[0]
    host = context["Endpoints"]["docker"]["Host"]
    if not (host.startswith("npipe:////./pipe/") or host.startswith("unix:///")):
        raise RuntimeError("Docker deve usar socket/pipe local, nunca TCP/SSH.")
    run(["docker", "info", "--format", "{{.OSType}}"])


def network(create: bool = False) -> None:
    names = run(["docker", "network", "ls", "--format", "{{.Name}}"] ).splitlines()
    if NETWORK not in names:
        if not create:
            raise RuntimeError("Rede local ausente; execute dev.ps1 start.")
        run(["docker", "network", "create", "--driver", "bridge", "--opt",
             f"{BIND_OPTION}=127.0.0.1", NETWORK])
    data = json.loads(run(["docker", "network", "inspect", NETWORK]))[0]
    if data.get("Driver") != "bridge" or data.get("Options", {}).get(BIND_OPTION) != "127.0.0.1":
        raise RuntimeError("Rede app-ufabc-local insegura; nao sera recriada automaticamente.")


def validate_containers(containers: list[dict], cfg: dict, *, safety: bool = True) -> None:
    for container in containers:
        labels = container.get("Config", {}).get("Labels") or {}
        own = labels.get("com.supabase.cli.project") == cfg["project"]
        if own and os.path.normcase(labels.get("com.supabase.cli.workdir", "")) != os.path.normcase(str(ROOT)):
            raise RuntimeError("project_id pertence a outra pasta; use a copia original ou um ID e portas distintos.")
        if not safety:
            continue
        relevant = own or NETWORK in container.get("NetworkSettings", {}).get("Networks", {})
        if own and (container.get("HostConfig", {}).get("NetworkMode") == "host"
                    or NETWORK not in container.get("NetworkSettings", {}).get("Networks", {})):
            raise RuntimeError("Container do projeto fora da rede segura.")
        # HostConfig inclui containers parados que a CLI pode reutilizar.
        for is_config, source in ((True, container.get("HostConfig", {}).get("PortBindings")),
                                  (False, container.get("NetworkSettings", {}).get("Ports"))):
            for bindings in (source or {}).values():
                for bind in bindings or []:
                    if relevant or int(bind["HostPort"]) in cfg["ports"]:
                        # HostIp vazio herda o bind da rede, validada antes desta funcao.
                        inherits_safe = (is_config and bind.get("HostIp") == ""
                                         and NETWORK in container.get("NetworkSettings", {}).get("Networks", {}))
                        if not inherits_safe and bind.get("HostIp") not in {"127.0.0.1", "::1"}:
                            raise RuntimeError("Porta Docker relevante fora de loopback; inicializacao recusada.")


def ports(cfg: dict, *, safety: bool = True) -> None:
    ids = run(["docker", "ps", "-aq"]).split()
    validate_containers(json.loads(run(["docker", "inspect", *ids])) if ids else [], cfg, safety=safety)


def supabase(*args: str, visible: bool = False) -> str:
    executable = shutil.which("npx.cmd" if os.name == "nt" else "npx")
    if not executable:
        raise RuntimeError("Instale Node.js/npm para usar a CLI Supabase fixada.")
    return run([executable, "--yes", "supabase@2.117.0", *args,
                "--network-id", NETWORK], visible=visible)


def execute(action: str) -> None:
    cfg = {"project": project_config()["project_id"]} if action == "stop" else config()
    if action == "config":
        print(json.dumps({"host": cfg["host"], "port": cfg["port"]}))
        return
    docker_local()
    if action == "stop":
        # Parar tambem deve funcionar quando uma porta existente esta insegura.
        ports(cfg, safety=False)
        supabase("stop", "--project-id", cfg["project"])
        print("Supabase local parado; volumes preservados.")
        return
    network(create=action == "start")
    ports(cfg)
    try:
        if action == "start":
            supabase("start")
        ports(cfg)
        status = json.loads(supabase("status", "--output", "json"))
        if endpoint(status.get("API_URL", ""), {"http"}) != endpoint(os.environ["SUPABASE_URL"], {"http"}):
            raise RuntimeError("Supabase iniciado diverge do endpoint configurado.")
        if endpoint(status.get("DB_URL", ""), {"postgres", "postgresql"}, credentials=True) != project_config().get("db", {}).get("port", 54322):
            raise RuntimeError("Banco iniciado diverge da porta configurada.")
    except (RuntimeError, ValueError, KeyError, OSError):
        if action == "start":
            # Falha apos subir: conter somente este projeto, preservando volumes.
            ports(cfg, safety=False)
            supabase("stop", "--project-id", cfg["project"])
        raise
    if action == "test-db":
        supabase("test", "db", "--local", visible=True)
    elif action == "reset-db":
        if input("Apaga dados do banco LOCAL. Digite RESET para continuar: ") != "RESET":
            raise RuntimeError("Reset cancelado; nenhum dado apagado.")
        supabase("db", "reset", "--local")
        ports(cfg)
    print("Supabase local: OK; portas Docker em loopback.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["config", "start", "status", "test-db", "reset-db", "stop"])
    args = parser.parse_args()
    try:
        execute(args.action)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (ValueError, KeyError, OSError, EOFError):
        # Nao imprimir valores de config/URLs que podem conter credenciais.
        print("Falha na operacao local. Confira .env.local, config.toml, Docker local e portas em loopback.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
