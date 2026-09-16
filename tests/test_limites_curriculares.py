import pytest

from planejador.requisitos_curriculares import (
    GrupoRequisitos, LimiteQuantitativo, OperadorGrupo,
    RegraCompartilhamento, UnidadeRequisito,
)


@pytest.mark.parametrize("valor", [0.5, float("nan"), float("inf"), True, "4"])
@pytest.mark.parametrize("campo", ["minimo", "maximo"])
def test_limites_rejeitam_quantidades_fora_do_contrato_inteiro(valor, campo):
    dados = {"minimo": 0, "maximo": 4, campo: valor}
    with pytest.raises(ValueError, match="inteiro"):
        LimiteQuantitativo(UnidadeRequisito.COMPONENTES, **dados)


def test_limite_aceita_zero_e_intervalo_exato():
    assert LimiteQuantitativo(UnidadeRequisito.HORAS, 0, 0).maximo == 0
    assert LimiteQuantitativo(UnidadeRequisito.HORAS, 120, 120).minimo == 120


@pytest.mark.parametrize("operador,minimo", [
    (OperadorGrupo.QUALQUER, 3), (OperadorGrupo.TODOS, 1),
    (OperadorGrupo.MINIMO, 1.5), ("inexistente", 1),
])
def test_grupo_rejeita_contagem_contraditoria_ou_operador_desconhecido(operador, minimo):
    with pytest.raises(ValueError):
        GrupoRequisitos("g", "Escolha", ("a", "b"), operador, minimo)


@pytest.mark.parametrize("valor", [True, 1.5, float("nan"), float("inf")])
def test_compartilhamento_rejeita_teto_invalido(valor):
    with pytest.raises(ValueError, match="inteiro"):
        RegraCompartilhamento("a", "b", UnidadeRequisito.HORAS, valor)
