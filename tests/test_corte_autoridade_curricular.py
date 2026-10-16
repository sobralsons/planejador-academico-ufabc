from dataclasses import replace

import pytest

from planejador.autoridade_curricular import (
    AutoridadeCurricular,
    BloqueioCorteAutoridade,
    EvidenciasCorteAutoridade,
    decidir_corte_autoridade,
)


def _evidencias_completas() -> EvidenciasCorteAutoridade:
    return EvidenciasCorteAutoridade(
        fontes_versionadas=True,
        aplicabilidade_resolvida=True,
        conversao_preserva_incertezas=True,
        completude_unidades_comprovada=True,
        ambiguidades_alocacao_tratadas=True,
        equivalencia_diferencial_aprovada=True,
        casos_adversariais_aprovados=True,
        revisao_humana_registrada=True,
        sem_fallback_silencioso=True,
    )


def test_corte_promove_somente_quando_todas_as_evidencias_estao_aprovadas():
    decisao = decidir_corte_autoridade("piloto_sintetico", _evidencias_completas())

    assert decisao.autoridade is AutoridadeCurricular.GENERICO
    assert decisao.promovido is True
    assert decisao.bloqueios == ()


@pytest.mark.parametrize(
    ("campo", "bloqueio"),
    [
        ("fontes_versionadas", BloqueioCorteAutoridade.FONTES_VERSIONADAS),
        ("aplicabilidade_resolvida", BloqueioCorteAutoridade.APLICABILIDADE),
        (
            "conversao_preserva_incertezas",
            BloqueioCorteAutoridade.CONVERSAO_HISTORICO,
        ),
        (
            "completude_unidades_comprovada",
            BloqueioCorteAutoridade.COMPLETUDE_UNIDADES,
        ),
        (
            "ambiguidades_alocacao_tratadas",
            BloqueioCorteAutoridade.ALOCACAO_EVIDENCIAS,
        ),
        (
            "equivalencia_diferencial_aprovada",
            BloqueioCorteAutoridade.EQUIVALENCIA_DIFERENCIAL,
        ),
        (
            "casos_adversariais_aprovados",
            BloqueioCorteAutoridade.CASOS_ADVERSARIAIS,
        ),
        (
            "revisao_humana_registrada",
            BloqueioCorteAutoridade.REVISAO_HUMANA,
        ),
        (
            "sem_fallback_silencioso",
            BloqueioCorteAutoridade.FALLBACK_SILENCIOSO,
        ),
    ],
)
def test_cada_evidencia_ausente_mantem_o_legado_com_bloqueio_explicito(
    campo: str,
    bloqueio: BloqueioCorteAutoridade,
):
    evidencias = replace(_evidencias_completas(), **{campo: False})

    decisao = decidir_corte_autoridade("piloto_sintetico", evidencias)

    assert decisao.autoridade is AutoridadeCurricular.LEGADO
    assert decisao.promovido is False
    assert decisao.bloqueios == (bloqueio,)


def test_corte_vazio_e_fail_closed_e_expoe_todos_os_bloqueios():
    decisao = decidir_corte_autoridade(
        "piloto_sintetico",
        EvidenciasCorteAutoridade(),
    )

    assert decisao.autoridade is AutoridadeCurricular.LEGADO
    assert decisao.promovido is False
    assert decisao.bloqueios == tuple(BloqueioCorteAutoridade)


@pytest.mark.parametrize("curriculo_id", ["", " ", "\tbct_2015\n"])
def test_corte_rejeita_identificador_de_escopo_ausente_ou_nao_canonico(
    curriculo_id: str,
):
    with pytest.raises(ValueError, match="curriculo_id"):
        decidir_corte_autoridade(curriculo_id, _evidencias_completas())


def test_corte_rejeita_confirmacao_que_nao_seja_booleana_exata():
    with pytest.raises(ValueError, match="booleana"):
        EvidenciasCorteAutoridade(fontes_versionadas=1)  # type: ignore[arg-type]
