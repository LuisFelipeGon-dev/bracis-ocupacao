# Testes

## Testes rápidos (rodar antes de cada atualização)

Na pasta do projeto, com o ambiente virtual ativado:

    python testes/rodar_testes.py

Roda todos os testes abaixo e mostra um resumo. Precisa do Node.js instalado. Nenhum teste mexe no
banco do projeto: cada um cria um banco temporário.

| Pasta | Arquivo | O que confere |
|---|---|---|
| `unidade/` | `teste_publico.js` | Regras do totem (`comum.js`): nível de lotação pela %, ordem das salas, horário da próxima sessão. |
| `unidade/` | `teste_toques.js` | Tela do voluntário (`voluntario.js`) com um servidor falso e lento: toques rápidos não se perdem, sem conexão os toques ficam guardados e são reenviados, Desfazer e grupo. |
| `servidor/` | `teste_desfazer.py` | Cada voluntário só desfaz os próprios registros; a sala não fica negativa. |
| `servidor/` | `teste_bloqueio.py` | Bloqueio do login do voluntário depois de 5 PINs errados; "Novo PIN" destrava. |
| `servidor/` | `teste_coordenacao.py` | Login da coordenação: senha errada espera 1 s, sem bloquear ninguém. |
| `servidor/` | `teste_upsert.py` | Trocar o nome de uma sala na lista atualiza o banco sem perder a contagem nem a capacidade definida pela coordenação; salas que saíram da lista são apagadas (se não tiverem registros). |
| `servidor/` | `teste_capacidade.py` | Coordenação muda a capacidade; sem login é recusado; reiniciar o site não desfaz. |
| `servidor/` | `teste_memoria.py` | Memória de 2 s da resposta pública (a tela do voluntário continua exata). |

## Teste de carga (só quando precisar)

Ficam em `carga/` e acessam o **site no ar** (`https://bracis.ic.ufmt.br/live/`), então deixam o site
mais lento enquanto rodam. Não use durante o evento.

- `node testes/carga/carga.js 800 120`: simula 800 telas com a página pública aberta por 120 s
  (só leitura, não muda nenhum dado).
- `node testes/carga/voluntarios_carga.js <email> <pin> <sala> 10 120`: 10 voluntários registrando
  entradas e saídas numa sala por 120 s e, no fim, confere se a contagem bate. **Grava no banco de
  verdade**: use um voluntário de teste e apague os registros depois.
- `python testes/carga/medir_banco_cheio.py`: mede, no seu computador, quanto a lista das salas demora
  com 100, 20 mil e 80 mil registros.

Resultados de 27/09/2026: 800 participantes = 69 pedidos/s, resposta típica de 61 ms, nenhum erro;
com o banco cheio, a memória de 2 s levou a resposta típica de 676 ms para 4 ms; 10 voluntários
contando junto com 800 participantes = 761 registros, 66 ms, contagem exata.
