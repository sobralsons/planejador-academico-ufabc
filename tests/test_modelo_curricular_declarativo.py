from planejador.alocacao_evidencias import (
    ConjuntoEvidencias,
    EvidenciaAcademica,
    avaliar_modelo_com_evidencias,
)
from planejador.modelo_curricular_json import carregar_modelo_curricular
from planejador.requisitos_curriculares import UnidadeRequisito


def test_lec_2024_carrega_grupo_de_escolha_e_executa_no_avaliador_generico():
    modelo = carregar_modelo_curricular(
        "dados/modelos_curriculares/lec_ciencias_humanas_sociais_2024.json"
    )
    conjunto = ConjuntoEvidencias(
        evidencias=(
            EvidenciaAcademica(
                id="historico:estagio_ch_iv",
                codigos=frozenset({"ESTAGIO_CH_IV"}),
                quantidades={UnidadeRequisito.COMPONENTES: 1},
            ),
        ),
        unidades_completas=frozenset({UnidadeRequisito.COMPONENTES}),
    )

    resultado = avaliar_modelo_com_evidencias(modelo, conjunto)

    assert modelo.curso_id == "lec_ciencias_humanas_sociais"
    assert dict(modelo.metadados)["estado"] == "nao_publicavel"
    assert resultado.avaliacao.por_id["escolha_historia"].estado.value == "cumprido"
    assert resultado.avaliacao.por_id["modulo_viii"].estado.value == "pendente"


def test_lec_2024_mantem_estagio_e_extensao_em_unidades_distintas():
    modelo = carregar_modelo_curricular(
        "dados/modelos_curriculares/lec_ciencias_humanas_sociais_2024.json"
    )
    requisitos = {item.id: item for item in modelo.requisitos}

    assert requisitos["estagio_total"].limite.unidade == UnidadeRequisito.HORAS_CARGA_HORARIA
    assert requisitos["extensao_estagio"].limite.unidade == UnidadeRequisito.HORAS_EXTENSAO
    assert modelo.compartilhamentos == ()


def test_lec_2024_sem_modulo_iv_ou_viii_nao_cumpre_grupo_de_escolha():
    modelo = carregar_modelo_curricular(
        "dados/modelos_curriculares/lec_ciencias_humanas_sociais_2024.json"
    )
    conjunto = ConjuntoEvidencias(
        evidencias=(),
        unidades_completas=frozenset({UnidadeRequisito.COMPONENTES}),
    )

    resultado = avaliar_modelo_com_evidencias(modelo, conjunto)

    assert resultado.avaliacao.por_id["escolha_historia"].estado.value == "pendente"
import json

import pytest



def test_loader_rejeita_versao_de_schema_desconhecida(tmp_path):
    caminho = tmp_path / "modelo.json"
    caminho.write_text(json.dumps({"schema_version": 999}), encoding="utf-8")

    with pytest.raises(ValueError, match="schema_version"):
        carregar_modelo_curricular(caminho)


def test_loader_rejeita_secao_ainda_nao_suportada(tmp_path):
    caminho = tmp_path / "modelo.json"
    caminho.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "curso_id": "curso",
                "matriz_id": "2026",
                "requisitos": [],
                "sequencias": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="não suportados.*sequencias"):
        carregar_modelo_curricular(caminho)
