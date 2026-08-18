from __future__ import annotations

import json
from pathlib import Path

from planejador.multicurso import RegistroCurriculo
from planejador.trajetorias import construir_plano_trajetoria, gerar_relatorio_trajetoria_html


def _salvar_curriculo(base: Path, nome: str, disciplinas: list[dict]) -> tuple[str, str]:
    curr = base / f"{nome}.json"
    eq = base / f"{nome}_eq.json"
    curr.write_text(
        json.dumps(
            {
                "metadados": {
                    "curso": nome,
                    "versao": "teste",
                    "creditos_totais": 16,
                    "creditos_obrigatorios": 8,
                    "creditos_opcao_limitada": 4,
                    "creditos_livres": 0,
                    "duracoes_especiais": {},
                },
                "disciplinas": disciplinas,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    eq.write_text(json.dumps({"equivalencias_academicas": {}, "equivalencias_compostas": []}), encoding="utf-8")
    return curr.name, eq.name


def _disc(codigo: str, nome: str, categoria: str, q: int = 1) -> dict:
    return {
        "codigo": codigo,
        "nome": nome,
        "categoria": categoria,
        "creditos": 4,
        "t": 4,
        "p": 0,
        "e": 0,
        "i": 4,
        "quadrimestre_recomendado": q,
        "recomendacoes": [],
    }


def _analise(id_: str, rotulo: str) -> dict:
    return {
        "id": id_,
        "rotulo": rotulo,
        "grupo": "Teste",
        "cumpridas_apos_grade": [],
        "estimativa_formatura": {
            "percentual_conclusao": 0,
            "creditos_regulares_pendentes": 12,
            "opcao_limitada_pendente": 4,
            "livres_pendentes": 0,
            "quadrimestres_cadeia": 0,
            "quadrimestres_tg": 0,
            "quadrimestres_estagio": 0,
            "periodo_estimado_minimo": "2027.1",
            "gargalos": [],
            "extensao_pendente_maxima_horas": 0,
            "atividades_complementares_pendentes_horas": 0,
        },
    }


def test_plano_conjunto_desconta_disciplinas_compartilhadas(tmp_path: Path):
    a, aeq = _salvar_curriculo(
        tmp_path,
        "Curso A",
        [
            _disc("SH-A", "Disciplina Compartilhada", "obrigatoria"),
            _disc("A-1", "Obrigatória A", "obrigatoria"),
            _disc("OPT-A", "Optativa Compartilhada", "opcao_limitada"),
        ],
    )
    b, beq = _salvar_curriculo(
        tmp_path,
        "Curso B",
        [
            _disc("SH-B", "Disciplina Compartilhada", "obrigatoria"),
            _disc("B-1", "Obrigatória B", "obrigatoria"),
            _disc("OPT-B", "Optativa Compartilhada", "opcao_limitada"),
        ],
    )
    registros = {
        "a": RegistroCurriculo("a", "Curso A", a, aeq, "Teste"),
        "b": RegistroCurriculo("b", "Curso B", b, beq, "Teste"),
    }
    plano = construir_plano_trajetoria(
        base=tmp_path,
        comparacoes=[_analise("a", "Curso A"), _analise("b", "Curso B")],
        registro_curriculos=registros,
        ordem_ids=["a", "b"],
        periodo_planejamento="2026.3",
        ritmo=8,
        margem=1,
        estrategia="hibrida",
        curso_atual_id="a",
        ofertas_historicas=2,
    )
    assert plano["creditos_regulares_somados_separadamente"] == 24
    assert plano["creditos_regulares_unicos_estimados"] == 16
    assert plano["creditos_economizados_por_sobreposicao"] == 8
    assert plano["eficiencia_sobreposicao_percentual"] > 0
    assert any(x["disciplina"] == "Disciplina Compartilhada" for x in plano["disciplinas_compartilhadas"])


def test_estrategia_sequencial_prioriza_primeiro_diploma(tmp_path: Path):
    a, aeq = _salvar_curriculo(tmp_path, "Curso A", [_disc("A-1", "Obrigatória A", "obrigatoria")])
    b, beq = _salvar_curriculo(tmp_path, "Curso B", [_disc("B-1", "Obrigatória B", "obrigatoria")])
    registros = {
        "a": RegistroCurriculo("a", "Curso A", a, aeq, "Teste"),
        "b": RegistroCurriculo("b", "Curso B", b, beq, "Teste"),
    }
    ana = [_analise("a", "Curso A"), _analise("b", "Curso B")]
    for x in ana:
        x["estimativa_formatura"]["creditos_regulares_pendentes"] = 4
        x["estimativa_formatura"]["opcao_limitada_pendente"] = 0
    plano = construir_plano_trajetoria(
        tmp_path, ana, registros, ["a", "b"], "2026.3", 4, 0, "sequencial", "a", 1
    )
    cursos = {x["id"]: x for x in plano["cursos"]}
    assert cursos["a"]["quadrimestres_no_plano"] <= cursos["b"]["quadrimestres_no_plano"]
    assert plano["roadmap"][0]["focos"] == ["Obrigatória A"]


def test_relatorio_trajetoria_e_interface_expoem_planejamento_completo(tmp_path: Path):
    a, aeq = _salvar_curriculo(tmp_path, "Curso A", [_disc("A-1", "Obrigatória A", "obrigatoria")])
    registros = {"a": RegistroCurriculo("a", "Curso A", a, aeq, "Teste")}
    analise = _analise("a", "Curso A")
    analise["estimativa_formatura"]["creditos_regulares_pendentes"] = 4
    analise["estimativa_formatura"]["opcao_limitada_pendente"] = 0
    plano = construir_plano_trajetoria(
        tmp_path, [analise], registros, ["a"], "2026.3", 4, 1, "hibrida", "a", 1
    )
    saida = tmp_path / "trajetoria.html"
    gerar_relatorio_trajetoria_html(saida, plano, [])
    texto = saida.read_text(encoding="utf-8")
    assert "Plano de trajetória acadêmica" in texto
    assert "Quando cada diploma" in texto
    app = (Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8")
    assert "Analisar minha trajetória agora" in app
    assert "Fazer três formações" in app
    assert "Visualizar relatório completo nesta página" in app
