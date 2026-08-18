# Validação do módulo de trajetórias

## Escopo

Foram validados:

- curso único;
- mudança de curso;
- dupla formação;
- tríplice formação;
- estratégia simultânea, híbrida e sequencial;
- unificação de obrigatórias compartilhadas;
- uso de obrigatória de um curso como OL/livre de outro;
- escolha estratégica de componentes flexíveis comuns;
- marcos de conclusão por diploma;
- relatório HTML e visualização na interface.

## Testes automatizados

A suíte completa contém **47 testes**, todos aprovados.

Os testes específicos do novo módulo verificam que:

1. duas matrizes com uma obrigatória comum não somam a disciplina duas vezes;
2. uma opção limitada comum é escolhida uma única vez no plano conjunto;
3. a economia por sobreposição é calculada pela diferença entre a soma isolada e a carga única;
4. a estratégia sequencial conclui a primeira prioridade antes da segunda quando não há compartilhamento;
5. o roteiro acadêmico contém períodos, focos e marcos de diploma;
6. o relatório completo é gerado e a interface expõe mudança, dupla e tríplice formação.

## Teste integrado com arquivos reais

O motor foi executado de ponta a ponta com:

- histórico estruturado do SIGAA;
- oferta real de turmas;
- Engenharia de Materiais 2017 como formação prioritária;
- BCC 2023 e BCD 2023 como formações adicionais;
- cenário otimista;
- estratégia híbrida.

O teste confirmou:

- geração das grades padrão;
- comparação das três matrizes;
- cálculo de créditos únicos e sobreposição;
- roteiro de múltiplos quadrimestres;
- seis cenários alternativos;
- geração de `relatorio_trajetoria_academica.html`;
- persistência do plano no `resultado_resumo.json`.

Os arquivos pessoais usados no teste não integram o pacote distribuído.

## Teste de combinações

Também foram executados cenários com:

- somente Engenharia de Materiais;
- somente Ciência de Dados;
- Materiais + Ciência de Dados;
- Materiais + BCC + BCD;
- Materiais + Engenharia de Informação.

Todos produziram roteiro, marcos, créditos únicos e faixa de conclusão sem exceções.

## Limites conhecidos

- O roteiro não presume ofertas futuras específicas.
- A correspondência entre cursos usa equivalências estruturadas e nome curricular normalizado.
- Disciplinas flexíveis são escolhidas por heurística de cobertura, não por preferência pessoal completa.
- Extensão, atividades complementares e situações administrativas exigem confirmação oficial.
- A estimativa conjunta representa uma trajetória otimizada; mudanças de ritmo, reprovações e indisponibilidade de turmas alteram a data.
