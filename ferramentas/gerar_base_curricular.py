from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
CATALOGO = BASE / "catalogo_disciplinas_graduacao_2024_2025.xlsx"
SAIDA = BASE / "dados" / "curriculo_engenharia_materiais_2017.json"


def norm(valor: object) -> str:
    texto = str(valor or "")
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"\s+", " ", texto).upper().strip()
    return texto


# Fonte: PPC das Engenharias 2017, tabelas MAT2 e MAT3, páginas 230–234.
OBRIGATORIAS = [
    ("BCJ0204-15", "Fenômenos Mecânicos", 4, 1, 0, 6, 5),
    ("BCJ0205-15", "Fenômenos Térmicos", 3, 1, 0, 4, 4),
    ("BCJ0203-15", "Fenômenos Eletromagnéticos", 4, 1, 0, 6, 5),
    ("BIJ0207-15", "Bases Conceituais da Energia", 2, 0, 0, 4, 2),
    ("BIL0304-15", "Evolução e Diversificação da Vida na Terra", 3, 0, 0, 4, 3),
    ("BCL0307-15", "Transformações Químicas", 3, 2, 0, 6, 5),
    ("BCL0306-15", "Biodiversidade: Interações entre Organismos e Ambiente", 3, 0, 0, 4, 3),
    ("BCN0404-15", "Geometria Analítica", 3, 0, 0, 6, 3),
    ("BCN0402-15", "Funções de Uma Variável", 4, 0, 0, 6, 4),
    ("BCN0407-15", "Funções de Várias Variáveis", 4, 0, 0, 4, 4),
    ("BCN0405-15", "Introdução às Equações Diferenciais Ordinárias", 4, 0, 0, 4, 4),
    ("BIN0406-15", "Introdução à Probabilidade e à Estatística", 3, 0, 0, 4, 3),
    ("BCM0504-15", "Natureza da Informação", 3, 0, 0, 4, 3),
    ("BCM0505-15", "Processamento da Informação", 3, 2, 0, 5, 5),
    ("BCM0506-15", "Comunicação e Redes", 3, 0, 0, 4, 3),
    ("BIK0102-15", "Estrutura da Matéria", 3, 0, 0, 4, 3),
    ("BCK0103-15", "Física Quântica", 3, 0, 0, 4, 3),
    ("BCK0104-15", "Interações Atômicas e Moleculares", 3, 0, 0, 4, 3),
    ("BCL0308-15", "Bioquímica: Estrutura, Propriedade e Funções de Biomoléculas", 3, 2, 0, 6, 5),
    ("BIR0004-15", "Bases Epistemológicas da Ciência Moderna", 3, 0, 0, 4, 3),
    ("BIQ0602-15", "Estrutura e Dinâmica Social", 3, 0, 0, 4, 3),
    ("BIR0603-15", "Ciência, Tecnologia e Sociedade", 3, 0, 0, 4, 3),
    ("BCS0001-15", "Base Experimental das Ciências Naturais", 0, 3, 0, 2, 3),
    ("BCS0002-15", "Projeto Dirigido", 0, 2, 0, 10, 2),
    ("BIS0005-15", "Bases Computacionais da Ciência", 0, 2, 0, 2, 2),
    ("BIS0003-15", "Bases Matemáticas", 4, 0, 0, 5, 4),
    ("MCTB001-17", "Álgebra Linear", 6, 0, 0, 5, 6),
    ("MCTB009-17", "Cálculo Numérico", 4, 0, 0, 4, 4),
    ("ESTO013-17", "Engenharia Econômica", 4, 0, 0, 4, 4),
    ("ESTO011-17", "Fundamentos de Desenho Técnico", 2, 0, 0, 4, 2),
    ("ESTO005-17", "Introdução às Engenharias", 2, 0, 0, 4, 2),
    ("ESTO006-17", "Materiais e Suas Propriedades", 3, 1, 0, 5, 4),
    ("ESTO008-17", "Mecânica dos Sólidos I", 3, 1, 0, 5, 4),
    ("ESTO012-17", "Princípios de Administração", 2, 0, 0, 4, 2),
    ("ESTO016-17", "Fenômenos de Transporte", 4, 0, 0, 4, 4),
    ("ESTO017-17", "Métodos Experimentais em Engenharia", 2, 2, 0, 4, 4),
    ("ESTO001-17", "Circuitos Elétricos e Fotônica", 3, 1, 0, 5, 4),
    ("ESTO004-17", "Instrumentação e Controle", 3, 1, 0, 5, 4),
    ("MCTB010-13", "Cálculo Vetorial e Tensorial", 4, 0, 0, 4, 4),
    ("ESTO902-17", "Engenharia Unificada I", 0, 2, 0, 5, 2),
    ("ESTO903-17", "Engenharia Unificada II", 0, 2, 0, 5, 2),
    ("ESTM016-17", "Química Inorgânica de Materiais", 4, 2, 0, 6, 6),
    ("NHT4017-15", "Funções e Reações Orgânicas", 4, 0, 0, 6, 4),
    ("ESTM001-17", "Estado Sólido", 4, 0, 0, 4, 4),
    ("ESTM002-17", "Tópicos Experimentais em Materiais I", 0, 4, 0, 4, 4),
    ("ESTM003-17", "Tópicos Computacionais em Materiais", 2, 2, 0, 5, 4),
    ("ESTM004-17", "Ciência dos Materiais", 4, 0, 0, 4, 4),
    ("ESTM005-17", "Materiais Metálicos", 4, 0, 0, 4, 4),
    ("ESTM006-17", "Materiais Poliméricos", 3, 1, 0, 4, 4),
    ("ESTM017-17", "Materiais Cerâmicos", 4, 0, 0, 4, 4),
    ("ESTM008-17", "Materiais Compósitos", 3, 1, 0, 4, 4),
    ("ESTM009-17", "Termodinâmica Estatística de Materiais", 4, 0, 0, 4, 4),
    ("ESTM010-17", "Propriedades Mecânicas e Térmicas", 3, 1, 0, 4, 4),
    ("ESTM011-17", "Propriedades Elétricas, Magnéticas e Ópticas", 4, 0, 0, 4, 4),
    ("ESTM015-17", "Reologia", 3, 1, 0, 4, 4),
    ("ESTM013-17", "Seleção de Materiais", 4, 0, 0, 4, 4),
    ("ESTM014-17", "Caracterização de Materiais", 3, 1, 0, 4, 4),
    ("ESTM018-17", "Termodinâmica de Materiais", 4, 0, 0, 6, 4),
    ("ESTM905-17", "Estágio Curricular em Engenharia de Materiais", 0, 14, 0, 0, 14),
    ("ESTM902-17", "Trabalho de Graduação I em Engenharia de Materiais", 0, 2, 0, 4, 2),
    ("ESTM903-17", "Trabalho de Graduação II em Engenharia de Materiais", 0, 2, 0, 4, 2),
    ("ESTM904-17", "Trabalho de Graduação III em Engenharia de Materiais", 0, 2, 0, 4, 2),
]

LIMITADAS = [
    ("ESZM001-17", "Seminários em Materiais Avançados", 2, 0, 0, 2, 2),
    ("ESZM002-17", "Nanociência e Nanotecnologia", 2, 0, 0, 2, 2),
    ("ESZM033-17", "Reciclagem e Ambiente", 3, 1, 0, 4, 4),
    ("ESZM034-17", "Design de Dispositivos", 4, 0, 0, 4, 4),
    ("ESZM007-17", "Elementos Finitos Aplicados em Materiais", 3, 1, 0, 4, 4),
    ("ESZM008-17", "Dinâmica Molecular e Monte Carlo", 3, 1, 0, 4, 4),
    ("ESZM009-17", "Diagramas de Fase", 4, 0, 0, 4, 4),
    ("ESZM012-17", "Tópicos Experimentais em Materiais II", 0, 4, 0, 4, 4),
    ("ESZM013-17", "Tecnologia de Elastômeros", 4, 0, 0, 4, 4),
    ("ESZM014-17", "Engenharia de Polímeros", 4, 0, 0, 4, 4),
    ("ESZM035-17", "Aditivação de Polímeros", 4, 0, 0, 4, 4),
    ("ESZM036-17", "Blendas Poliméricas", 3, 1, 0, 4, 4),
    ("ESZM016-17", "Síntese de Polímeros", 3, 1, 0, 4, 4),
    ("ESZM037-17", "Processamento de Polímeros", 3, 1, 0, 4, 4),
    ("ESZM038-17", "Engenharia de Cerâmicas", 2, 2, 0, 4, 4),
    ("ESZM039-17", "Processamento de Materiais Cerâmicos", 3, 1, 0, 4, 4),
    ("ESZM021-17", "Matérias Primas Cerâmicas", 4, 0, 0, 4, 4),
    ("ESZM022-17", "Cerâmicas Especiais e Refratárias", 4, 0, 0, 4, 4),
    ("ESZM023-17", "Metalurgia Física", 4, 0, 0, 4, 4),
    ("ESZM024-17", "Engenharia de Metais", 3, 1, 0, 4, 4),
    ("ESZM025-17", "Siderurgia e Engenharia dos Aços", 4, 0, 0, 4, 4),
    ("ESZM040-17", "Processamento e Conformação de Metais I", 3, 1, 0, 4, 4),
    ("ESZM041-17", "Processamento e Conformação de Metais II", 3, 1, 0, 4, 4),
    ("ESZM027-17", "Materiais para Energia e Ambiente", 4, 0, 0, 4, 4),
    ("ESZM028-17", "Materiais para Tecnologia da Informação", 4, 0, 0, 4, 4),
    ("ESZM029-17", "Engenharia de Filmes Finos", 3, 1, 0, 4, 4),
    ("ESZM030-17", "Materiais Nanoestruturados", 4, 0, 0, 4, 4),
    ("ESZM031-17", "Nanocompósitos", 4, 0, 0, 4, 4),
    ("ESZM032-17", "Biomateriais", 3, 1, 0, 4, 4),
    ("ESTO015-17", "Mecânica dos Fluidos I", 4, 0, 0, 5, 4),
    ("ESTO014-17", "Termodinâmica Aplicada I", 4, 0, 0, 5, 4),
]

# Fonte: tabela MAT4, páginas 234–236. ESTM002-17 corrige um erro gráfico do PPC,
# que mostra ESZM012-17 com o nome de Tópicos Experimentais em Materiais I.
QUADRIMESTRES = {
    "BCS0001-15": 1, "BIS0005-15": 1, "BIS0003-15": 1, "BIK0102-15": 1,
    "BIL0304-15": 1, "BIJ0207-15": 1,
    "BCJ0204-15": 2, "BCN0402-15": 2, "BCN0404-15": 2, "BCM0504-15": 2,
    "BCL0306-15": 2,
    "BCN0407-15": 3, "BCJ0205-15": 3, "BCL0307-15": 3, "BCM0505-15": 3,
    "ESTO005-17": 3,
    "BCM0506-15": 4, "BIN0406-15": 4, "BCN0405-15": 4, "BCJ0203-15": 4,
    "BIR0004-15": 4,
    "BCL0308-15": 5, "BIQ0602-15": 5, "BCK0103-15": 5, "ESTO001-17": 5,
    "ESTO006-17": 5,
    "BCK0104-15": 6, "BIR0603-15": 6, "MCTB010-13": 6, "ESTO011-17": 6,
    "ESTO004-17": 6,
    "NHT4017-15": 7, "ESTO017-17": 7, "ESTM018-17": 7, "MCTB001-17": 7,
    "MCTB009-17": 8, "ESTO016-17": 8, "ESTM009-17": 8, "ESTM004-17": 8,
    "ESTO013-17": 8,
    "BCS0002-15": 9, "ESTM002-17": 9, "ESTO008-17": 9, "ESTM016-17": 9,
    "ESTO012-17": 9,
    "ESTM006-17": 10, "ESTM005-17": 10, "ESTM017-17": 10, "ESTO902-17": 10,
    "ESTM003-17": 11, "ESTM010-17": 11, "ESTM011-17": 11, "ESTO903-17": 11,
    "ESTM008-17": 11,
    "ESTM014-17": 12, "ESTM015-17": 12, "ESTM001-17": 12, "ESTM902-17": 12,
    "ESTM013-17": 13, "ESTM903-17": 13, "ESTM905-17": 13,
    "ESTM904-17": 14,
}


def carregar_catalogo() -> pd.DataFrame:
    frames = [
        pd.read_excel(CATALOGO, sheet_name="Disciplinas"),
        pd.read_excel(CATALOGO, sheet_name="Componentes_Curriculares"),
    ]
    return pd.concat(frames, ignore_index=True)


def main() -> None:
    catalogo = carregar_catalogo()
    por_codigo = {
        str(r["SIGLA"]).strip(): r
        for _, r in catalogo.iterrows()
        if pd.notna(r.get("SIGLA"))
    }
    por_nome: dict[str, list[pd.Series]] = {}
    for _, r in catalogo.iterrows():
        por_nome.setdefault(norm(r.get("DISCIPLINA")), []).append(r)

    todos = OBRIGATORIAS + LIMITADAS
    codigo_por_nome = {norm(nome): codigo for codigo, nome, *_ in todos}
    disciplinas = []

    for categoria, lista in (("obrigatoria", OBRIGATORIAS), ("opcao_limitada", LIMITADAS)):
        for codigo, nome, t, p, e, i, creditos in lista:
            linha = por_codigo.get(codigo)
            catalogo_codigo = codigo if linha is not None else None
            if linha is None:
                candidatos = por_nome.get(norm(nome), [])
                if len(candidatos) == 1:
                    linha = candidatos[0]
                    catalogo_codigo = str(linha["SIGLA"]).strip()

            rec_texto = ""
            requisito_manual = ""
            recomendacoes: list[str] = []
            observacoes: list[str] = []
            if linha is not None:
                rec_texto = str(linha.get("RECOMENDAÇÃO") or "").strip()
                if rec_texto.lower().startswith("requisito:"):
                    requisito_manual = rec_texto
                elif norm(rec_texto) not in {"", "NAO HA", "NAN"}:
                    for parte in rec_texto.split(";"):
                        codigo_rec = codigo_por_nome.get(norm(parte))
                        if codigo_rec:
                            recomendacoes.append(codigo_rec)
                        elif parte.strip():
                            observacoes.append(
                                f"Recomendação não convertida automaticamente em código: {parte.strip()}"
                            )
            else:
                observacoes.append("Disciplina não localizada no catálogo 2024–2025 por código ou nome exato.")

            if codigo == "ESTM002-17":
                observacoes.append(
                    "A tabela gráfica MAT4 contém aparente erro de sigla: mostra ESZM012-17 com o nome de Tópicos Experimentais em Materiais I. A tabela MAT2 confirma ESTM002-17 como obrigatória."
                )
            if codigo == "ESTM011-17" and catalogo_codigo == "ESTM019-17":
                observacoes.append(
                    "O catálogo 2024–2025 usa ESTM019-17 para o mesmo nome. Isto é apenas referência de consulta; não é equivalência acadêmica automática."
                )

            disciplinas.append(
                {
                    "codigo": codigo,
                    "nome": nome,
                    "categoria": categoria,
                    "creditos": creditos,
                    "t": t,
                    "p": p,
                    "e": e,
                    "i": i,
                    "quadrimestre_recomendado": QUADRIMESTRES.get(codigo),
                    "recomendacoes": sorted(set(recomendacoes)),
                    "recomendacao_texto": rec_texto,
                    "requisito_manual": requisito_manual,
                    "catalogo_codigo_consulta": catalogo_codigo,
                    "observacoes": observacoes,
                }
            )

    soma_obr = sum(d[6] for d in OBRIGATORIAS)
    assert soma_obr == 232, soma_obr
    assert len(OBRIGATORIAS) == 62
    assert len(LIMITADAS) == 31

    bruto = {
        "metadados": {
            "curso": "Engenharia de Materiais — UFABC",
            "versao": "2017",
            "creditos_totais": 300,
            "creditos_obrigatorios": 232,
            "creditos_opcao_limitada": 40,
            "creditos_livres": 28,
            "fontes": {
                "disciplinas_obrigatorias": "PPC Engenharias 2017, tabelas MAT2, páginas 230–232",
                "opcao_limitada": "PPC Engenharias 2017, tabela MAT3, páginas 232–234",
                "perfil_formacao": "PPC Engenharias 2017, tabela MAT4, páginas 234–236",
                "recomendacoes": "Catálogo de disciplinas 2024–2025",
            },
        },
        "disciplinas": disciplinas,
    }
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps(bruto, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Base criada em {SAIDA}")


if __name__ == "__main__":
    main()
