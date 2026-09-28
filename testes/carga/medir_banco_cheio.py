"""Quanto a lista das salas demora com o banco cheio como no fim do evento?"""
import os
import random
import sys
import tempfile
import time
from datetime import datetime, timedelta

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # pasta do projeto
os.chdir(RAIZ)
sys.path.insert(0, RAIZ)
import database
import programacao

database.ARQUIVO_BANCO = os.path.join(tempfile.mkdtemp(), "cheio.db")
database.criar_banco(True)
salas = [a[0] for a in database.AMBIENTES_EXEMPLO]


def medir(nome, funcao, vezes=200):
    inicio = time.perf_counter()
    for _ in range(vezes):
        funcao()
    ms = (time.perf_counter() - inicio) / vezes * 1000
    print(f"  {nome:40} {ms:6.2f} ms por pedido")
    return ms


def lista_salas():
    with database.conectar() as conn:
        database.listar_ambientes(conn)
        programacao.agora_e_depois(conn, datetime(2026, 10, 21, 14, 30))


def pagina_sala():
    with database.conectar() as conn:
        database.obter_ambiente(conn, "A1")
        database.movimento_do_dia(conn, "A1", "2026-10-21")


for total in [100, 20_000, 80_000]:
    with database.conectar() as conn:
        conn.execute("DELETE FROM eventos")
        base = datetime(2026, 10, 19, 8, 0)
        conn.executemany(
            "INSERT INTO eventos (ambiente_codigo, tipo, quantidade, horario, voluntario_id) VALUES (?, ?, 1, ?, 1)",
            [(random.choice(salas), "entrada" if i % 2 == 0 else "saida",
              (base + timedelta(seconds=i * 13)).strftime("%Y-%m-%dT%H:%M:%S-04:00")) for i in range(total)])
    print(f"{total:,} registros no banco:".replace(",", "."))
    medir("lista das salas (/ambientes)", lista_salas)
    medir("página de uma sala (/detalhes)", pagina_sala, vezes=100)
