# AGENTS.md

## Produto

Este repositório contém o Planejador Acadêmico UFABC. O objetivo é construir uma plataforma pública confiável para estudantes de todos os cursos de graduação e de todas as matrizes ainda aplicáveis a estudantes ativos.

BC&T 2015 e Bacharelado em Ciência de Dados 2023 são matrizes-piloto de desenvolvimento. Não declarar suporte público universal enquanto o inventário, a modelagem, a revisão e os testes de todas as matrizes aplicáveis não estiverem concluídos.

`app.py` é a entrada pública e deve falhar fechado enquanto a cobertura acadêmica não estiver integralmente aprovada. `app_interno.py` preserva a interface de protótipo para desenvolvimento e validação e não deve ser tratada como entrada pública.

## Prioridades

Ao tomar decisões, respeite esta ordem:

1. correção acadêmica;
2. confiabilidade e transparência;
3. segurança e privacidade;
4. facilidade de uso;
5. cobertura de cursos e matrizes;
6. desempenho;
7. manutenção dos dados;
8. qualidade visual;
9. novas funcionalidades.

Nunca melhore uma prioridade inferior sacrificando uma superior.

## Arquitetura

- Preserve o núcleo acadêmico em Python.
- Mantenha regras acadêmicas fora de `app.py` e de componentes visuais.
- Separe domínio acadêmico, parsing, currículos, busca, trajetória, persistência, API e interface.
- Faça alterações pequenas e retrocompatíveis quando isso não preservar um erro.
- Não substitua o solver atual nem introduza OR-Tools sem testes diferenciais e benchmarks.
- Streamlit pode continuar como protótipo e ferramenta administrativa; a interface pública planejada deve consumir o núcleo por API.

## Fontes e regras acadêmicas

- Não invente regras, equivalências, requisitos, ofertas ou informações da UFABC.
- Não considere uma regra correta apenas porque ela já existe no código.
- Priorize PPCs, catálogos, resoluções, atos decisórios, SIGAA e documentos oficiais.
- Registre fonte, versão, matriz, vigência e estado de revisão sempre que o modelo permitir.
- Diferencie informação oficial, interpretação, heurística, estimativa e preferência do usuário.
- Uma estimativa nunca deve ser apresentada como garantia.
- Ausência de informação pode produzir resultado indeterminado; não a converta automaticamente em pendência ou cumprimento.
- Nomes iguais não autorizam equivalência.
- Regras de transição, equivalências direcionadas, extensão, atividades complementares, estágio e TCC exigem fonte e testes próprios.
- Dados importados automaticamente devem permitir revisão humana antes de publicação.

## Modelo curricular

O modelo deve evoluir para representar, sem código específico por curso:

- obrigatórias, opção limitada e livres;
- grupos de escolha e requisitos aninhados;
- mínimos de créditos, horas ou componentes;
- regras de compartilhamento e alocação de evidências;
- equivalências simples, compostas e direcionadas;
- versões curriculares e transições;
- extensão, atividades complementares, estágio e TCC;
- requisitos condicionais quando comprovados por fonte.

Não multiplique regras simplificadas para muitos cursos. Primeiro prove que o modelo representa famílias diferentes de currículos.

## Privacidade e segurança

- Nunca adicione ao Git históricos reais, RA, notas, credenciais, tokens, sessões ou comentários integrais identificáveis.
- Use fixtures sintéticas ou anonimizadas.
- Não registre dados pessoais desnecessários em logs ou mensagens de erro.
- Arquivos do SIGAA devem ser tratados com minimização de dados e, no produto público, processados de forma temporária por padrão.
- Acesso autenticado, persistência e uploads exigem isolamento entre usuários e testes de autorização.
- Histórico bruto, registros detalhados e evidências acadêmicas derivadas são temporários por padrão; persistência desses dados exige decisão explícita posterior, minimização e novos testes.
- Tabelas de domínio da aplicação devem usar identificador opaco do provedor de autenticação e não duplicar RA, nome ou e-mail sem necessidade comprovada.
- Um banco multiusuário só pode ser conectado após políticas de isolamento/RLS, exclusão por usuário e testes adversariais de acesso cruzado.
- Não disponibilize coleta autenticada do UFABC Next sem fonte autorizada e revisão específica.
- Não crie workflows que extraiam pacotes ocultos e escrevam automaticamente na branch principal.
- Segredos ficam fora do repositório.

## Branches de desenvolvimento

- `main` é a linha de integração/release e não deve receber desenvolvimento direto.
- `develop` é a base estável de desenvolvimento enquanto o produto ainda estiver em construção.
- Novas tarefas devem sair de `develop` em branches curtas e voltar por PR.
- Não fazer push direto em `main` ou `develop`; usar PR e CI.
- A pilha histórica de PRs #4–#22 permanece como trilha auditável das etapas que originaram o checkpoint de `develop`.
- A existência de código em `develop` não significa suporte público nem validação acadêmica da matriz.

## Fluxo de trabalho

Para uma alteração relevante, siga:

1. localizar o módulo responsável;
2. confirmar o comportamento atual;
3. identificar problema, causa e impacto;
4. fazer a menor alteração segura;
5. criar ou atualizar teste específico;
6. executar testes relacionados;
7. executar a suíte completa quando o impacto for amplo ou antes de merge;
8. relatar limitações e o que não foi validado.

Não transforme uma correção localizada em refatoração geral. Não gere ZIP, build, screenshot ou documentação a cada mudança pequena.

## Testes

Ambiente de referência: Python 3.12.

Instalação para testes:

```bash
python -m pip install -r requirements-test.txt
```

Verificação principal:

```bash
python -m compileall -q app.py app_interno.py main.py planejador ferramentas api persistencia scripts
python -m pytest -q
```

Regras adicionais:

- Correções de bug devem reproduzir o erro em teste sempre que possível.
- Novas regras acadêmicas devem cobrir casos válidos, inválidos, limites, dados ausentes, equivalências e versões relevantes.
- Alterações de parser devem testar entrada válida, trecho incompleto e rejeição explícita.
- Uma suíte passando não certifica integralização oficial.
- Ao relatar a validação, informe quantidade de testes, resultado, escopo e limitações.
- Não altere expectativas de testes apenas para fazê-los passar sem documentar mudança de contrato.

## Interface

- Use linguagem compreensível para estudantes e progressive disclosure.
- Use “quadrimestre” na experiência da UFABC.
- Pergunte somente o que não puder ser inferido com segurança.
- Configurações raras ficam em “Personalizar planejamento”.
- Mostre fonte e versão dos dados, motivos das recomendações e completude ou limitação da busca.
- A interface não decide regras acadêmicas.
- Preserve acessibilidade e funcionamento mobile.

## Pull requests

- Mantenha cada PR focado em um problema ou etapa coerente.
- Explique problema, impacto, alteração, testes e limitações.
- Não misture mudanças acadêmicas independentes com mudanças visuais.
- Não marque uma matriz como validada sem fontes, revisão humana e casos de teste.
- Antes de modificar a branch principal, confirme que a base analisada é a mais recente.
