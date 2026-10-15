# Testes

## Testes rápidos (rodar antes de cada atualização)

Na pasta do projeto, com o ambiente virtual ativado:

    python testes/rodar_testes.py

Roda todos os testes abaixo e mostra um resumo. Precisa do Node.js instalado. Nenhum teste mexe no
banco do projeto: cada um cria um banco temporário.

| Pasta | Arquivo | O que confere |
|---|---|---|
| `unidade/` | `teste_publico.js` | Regras do totem (`comum.js`): nível de lotação pela %, ordem das salas, horário da próxima sessão. |
| `servidor/` | `teste_estimativas.py` | Estimativa vale até a sessão mudar (com 15 min de antecedência); registro pelo voluntário (só de 10 em 10, ou gente em pé); relatório por sessão. |
| `servidor/` | `teste_bloqueio.py` | Bloqueio do login do voluntário depois de 5 PINs errados; "Novo PIN" destrava. |
| `servidor/` | `teste_coordenacao.py` | Login da coordenação: senha errada espera 1 s, sem bloquear ninguém. |
| `servidor/` | `teste_upsert.py` | Trocar o nome de uma sala na lista atualiza o banco sem perder as estimativas; salas que saíram da lista são apagadas (se não tiverem registros). |
| `servidor/` | `teste_memoria.py` | Memória de 2 s da resposta pública (a tela do voluntário continua exata). |

## Teste de carga (só quando precisar)

Ficam em `carga/` e acessam o **site no ar** (`https://bracis.ic.ufmt.br/live/`), então deixam o site
mais lento enquanto rodam. Não use durante o evento.

- `node testes/carga/carga.js 800 120`: simula 800 telas com a página pública aberta por 120 s
  (só leitura, não muda nenhum dado).
- `python testes/carga/medir_banco_cheio.py`: mede, no seu computador, quanto a lista das salas e o
  relatório demoram com 100, 5 mil e 20 mil estimativas (o evento todo deve ter uns 3 mil).

Resultados de 27/09/2026: 800 participantes = 69 pedidos/s, resposta típica de 61 ms, nenhum erro;
com o banco cheio, a memória de 2 s levou a resposta típica de 676 ms para 4 ms.
Em 15/10/2026, com a estimativa no lugar da contagem: 20 mil estimativas, lista das salas em 5 ms.
