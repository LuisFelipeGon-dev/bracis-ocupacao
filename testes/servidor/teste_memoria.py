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


def estima(sala, porcentagem):
    # Grava direto no banco (sem passar pela rota, que limparia a memória)
    with database.conectar() as conn:
        conn.execute("INSERT INTO estimativas (ambiente_codigo, porcentagem, horario, voluntario_id) "
                     "VALUES (?, ?, ?, 1)", (sala, porcentagem, main.datetime.now(main.FUSO_CUIABA).isoformat()))


def estimativa_publica(sala):
    estimativa = next(a for a in main.listar_ambientes() if a["codigo"] == sala)["estimativa"]
    return estimativa and estimativa["porcentagem"]


confere("começa sem estimativa", estimativa_publica("A1"), None)
estima("A1", 50)
confere("dentro de 2 s: resposta guardada", estimativa_publica("A1"), None)
confere("voluntário vê na hora (sem memória)", main.obter_ambiente("A1")["estimativa"]["porcentagem"], 50)
relogio[0] += 2.1
confere("depois de 2 s: recalcula", estimativa_publica("A1"), 50)
confere("7 ambientes no totem", len(main.listar_ambientes()), 7)

print("\nTudo certo." if not falhas else f"\n{falhas} FALHA(S)")
sys.exit(1 if falhas else 0)
