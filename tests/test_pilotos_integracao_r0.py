import json
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]


def test_pilotos_r0_sao_minimos_distintos_e_respeitam_dependencia_do_curso_base():
    pilotos = json.loads(
        (BASE / "dados/pilotos_integracao_r0.json").read_text(encoding="utf-8")
    )
    registro = json.loads(
        (BASE / "dados/registro_curriculos.json").read_text(encoding="utf-8")
    )["curriculos"]

    itens = pilotos["pilotos"]

    assert [item["curriculo_id"] for item in itens] == ["bct_2015", "bcd_2023"]
    assert len({item["familia"] for item in itens}) == 2
    assert itens[0]["depende_de"] is None
    assert itens[1]["depende_de"] == "bct_2015"

    assert "bct_2015" in registro
    assert "bcd_2023" in registro
    assert registro["bcd_2023"]["curso_base_id"] == "bct_2015"

    assert "Não declara suporte" in pilotos["escopo"]
    assert "referencia_a_curso_base" in itens[1]["capacidades_alvo"]
    assert "extensao_em_dimensao_propria" in itens[1]["capacidades_alvo"]
    assert "trabalho_final" in itens[1]["capacidades_alvo"]
