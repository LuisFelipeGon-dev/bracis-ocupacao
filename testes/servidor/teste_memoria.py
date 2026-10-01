"""Testa a memória de 2 s da resposta pública (lista das salas que o totem consulta)."""
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # pasta do projeto
os.chdir(RAIZ)
sys.path.insert(0, RAIZ)
import database
database.ARQUIVO_BANCO = os.path.join(tempfile.mkdtemp(), "teste.db")
database.criar_banco(True)

import main

falhas = 0
def confere(nome, obtido, esperado):
    global falhas
    ok = obtido == esperado
    falhas += not ok
    print(f"{'OK  ' if ok else 'FALHOU'} {nome}: {obtido!r}" + ("" if ok else f" (esperado {esperado!r})"))

# Relógio falso, para não precisar esperar de verdade
relogio = [1000.0]
main.time.monotonic = lambda: relogio[0]


def entra(sala, quantidade):
    with database.conectar() as conn:
        conn.execute("INSERT INTO eventos (ambiente_codigo, tipo, quantidade, horario, voluntario_id) "
                     "VALUES (?, 'entrada', ?, '2026-10-20T09:00:00-04:00', 1)", (sala, quantidade))


def ocupacao_publica(sala):
    return next(a for a in main.listar_ambientes() if a["codigo"] == sala)["ocupacao"]


confere("começa vazia", ocupacao_publica("A1"), 0)
entra("A1", 5)
confere("dentro de 2 s: resposta guardada", ocupacao_publica("A1"), 0)
confere("voluntário vê o número exato na hora (sem memória)", main.obter_ambiente("A1")["ocupacao"], 5)
relogio[0] += 2.1
confere("depois de 2 s: recalcula", ocupacao_publica("A1"), 5)
confere("7 ambientes no totem", len(main.listar_ambientes()), 7)

print("\nTudo certo." if not falhas else f"\n{falhas} FALHA(S)")
sys.exit(1 if falhas else 0)
