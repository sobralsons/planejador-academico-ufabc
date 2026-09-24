from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_env_example_e_versionavel_mas_env_local_permanece_ignorado():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env.*" in gitignore
    assert "!.env.example" in gitignore

    exemplo = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "SUPABASE_URL=" in exemplo
    assert "SUPABASE_ANON_KEY=" in exemplo
    assert "DATABASE_URL=" in exemplo
    assert "SUPABASE_SERVICE_ROLE_KEY=" in exemplo

    for linha in exemplo.splitlines():
        if linha.startswith(("SUPABASE_", "DATABASE_URL=")):
            assert linha.endswith("=")


def test_acervo_documental_real_fica_fora_do_git():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "documentos-fonte/*" in gitignore
    assert "!documentos-fonte/README.md" in gitignore

    readme = (ROOT / "documentos-fonte" / "README.md").read_text(
        encoding="utf-8"
    )
    assert "históricos de estudantes" in readme
    assert "não normativas" in readme


def test_ambiente_local_instala_interface_api_e_testes():
    local = (ROOT / "requirements-local.txt").read_text(encoding="utf-8")
    assert "-r requirements-test.txt" in local
    assert "-r requirements.txt" in local


def test_guia_local_nao_orienta_trabalho_direto_na_main():
    guia = (ROOT / "docs" / "AMBIENTE_LOCAL.md").read_text(encoding="utf-8")
    assert "Não trabalhar diretamente na `main` nem na `develop`" in guia
    assert "git checkout develop" in guia
    assert "PR para develop" in guia
    assert "preparar_ambiente_windows.bat" in guia
    assert "validar_windows.bat" in guia
    assert ".env.local" in guia
    assert "documentos-fonte/" in guia


def test_validacao_local_compila_novas_fronteiras_e_scripts():
    bat = (ROOT / "validar_windows.bat").read_text(encoding="utf-8")
    assert "planejador ferramentas api persistencia scripts" in bat
    assert "scripts\\verificar_ambiente_local.py" in bat
    assert "-m pytest -q" in bat


def test_inicializadores_exigem_ambiente_virtual_local():
    for arquivo in ("executar_windows.bat", "executar_api_windows.bat"):
        conteudo = (ROOT / arquivo).read_text(encoding="utf-8")
        assert '.venv\\Scripts\\python.exe' in conteudo
        assert "preparar_ambiente_windows.bat" in conteudo
