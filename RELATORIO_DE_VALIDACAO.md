# Relatório de validação — Planejador Multicurso UFABC

## Resultado da suíte

**47 testes automatizados aprovados.**

A execução é feita por:

```text
validar_windows.bat
```

O atalho instala as dependências e executa `python -m pytest -q`, cobrindo também os testes funcionais escritos fora de classes `unittest`.

## Matrizes validadas estruturalmente

O arquivo `dados/validacao_curriculos.json` fixa, por currículo:

- quantidade de componentes obrigatórios e de opção limitada;
- soma dos créditos cadastrados;
- SHA-256 da lista ordenada de códigos;
- fontes documentais utilizadas.

Currículos verificados:

1. BC&T 2015;
2. Engenharia de Materiais 2017;
3. BCC 2017;
4. BCC 2023;
5. BCD 2023;
6. Engenharia de Informação 2017;
7. Engenharia de Informação 2023.

## Cobertura dos testes

- leitura e normalização de códigos;
- T-P-I e T-P-E-I;
- horários adjacentes, sobrepostos e quinzenais;
- janelas internas versus extremidades livres;
- histórico, conceitos, reprovações e recuperações;
- equivalências 2017/2023;
- código canônico de Programação Estruturada no BCC 2023;
- código canônico e alias do TCC do BCD;
- totais oficiais versus créditos usados na projeção da EI 2023;
- PGC/TCC/TG e suas durações mínimas;
- estágio em andamento por currículo;
- curso-base impedindo conclusão do curso específico antes do BC&T;
- créditos de disciplina equivalente sem dupla contagem como livre;
- ranking curricular e projeção otimista;
- busca exaustiva mesmo quando o limite de retenção é atingido;
- aviso correto quando candidatas são truncadas;
- avaliações docentes e preferência flexível;
- editor de grade e diagnóstico de conflitos;
- relatório multicurso e cartões de formatura;
- curso único, mudança, dupla e tríplice formação;
- créditos únicos, sobreposição curricular e roteiro por diploma;
- estratégias simultânea, híbrida e sequencial;
- relatório completo de trajetória e visualização embutida.

## Testes integrados com histórico e oferta reais

Todas as sete matrizes foram usadas como currículo principal, mantendo a mesma oferta e o mesmo histórico. Em todas as execuções foram geradas pelo menos três grades.

| Currículo principal | Candidatas analisadas | Conjuntos únicos | Cobertura global | Pareto |
|---|---:|---:|---|---|
| Materiais 2017 | 13/13 | 198 | completa | completa |
| BCC 2017 | 14/14 | 432 | completa | completa |
| BCC 2023 | 15/15 | 531 | completa | completa |
| BCD 2023 | 10/10 | 24 | completa | completa |
| EI 2017 | 16/16 | 898 | completa | completa |
| EI 2023 | 20/20 | 2.324 | completa | parcial por retenção |
| BC&T 2015 | 20/52 no teste conservador | 1.110 | limitada por candidatas | completa no subconjunto |

Na EI 2023, o limite de retenção não interrompeu a enumeração: o ranking padrão permaneceu exato, enquanto somente o Pareto foi calculado sobre 1.200 grades retidas.

O BC&T possui uma lista de opção limitada muito ampla. O certificado identifica corretamente quando o limite de candidatas reduz a garantia global. A interface permite aumentar esse limite.

## Correções detectadas pelos testes

- o estágio do currículo principal agora respeita `estagios_status[curso]`, em vez de sempre usar o campo legado;
- equivalências na grade não são somadas novamente como créditos livres;
- o limite do pool deixou de encerrar a busca antecipadamente;
- rankings padrão e perfis são calculados sobre todas as combinações válidas das candidatas analisadas;
- a previsão de um curso específico não pode anteceder a previsão do BC&T.

## Validação da interface

O código da interface foi compilado e verificado por testes estáticos que confirmam a presença do Laboratório de Trajetórias, mudança de curso, dupla e tríplice formação, cartões de previsão, visualização do relatório completo, certificado da busca e ausência de widgets duplicados. O motor, os relatórios HTML/TXT/JSON e as sete execuções integradas foram executados de ponta a ponta no ambiente de testes.

A abertura do Streamlit no navegador depende da instalação das dependências no computador do usuário, realizada automaticamente por `executar_windows.bat`.

## Limites acadêmicos

A validação confirma a coerência do software com as matrizes estruturadas. Ela não substitui a conferência oficial de:

- integralização no SIGAA;
- equivalências excepcionais;
- lista de OL aplicável a cada vínculo;
- extensão e atividades complementares;
- deferimento de estágio e trabalho final;
- vagas e oferta futura.
