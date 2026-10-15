"""Quanto a lista das salas demora com muitas estimativas no banco (bem mais que no evento todo)?"""
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
import estimativas
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
        estimativas.estimativas_atuais(conn, datetime(2026, 10, 21, 14, 30))


def relatorio():
    with database.conectar() as conn:
        estimativas.relatorio(conn)


# 7 salas x 4 dias x uma estimativa a cada 5 min = uns 2.700; testamos bem mais que isso.
for total in [100, 5_000, 20_000]:
    with database.conectar() as conn:
        conn.execute("DELETE FROM estimativas")
        base = datetime(2026, 10, 19, 8, 0)
        conn.executemany(
            "INSERT INTO estimativas (ambiente_codigo, porcentagem, horario, voluntario_id) VALUES (?, ?, ?, 1)",
            [(random.choice(salas), random.choice(estimativas.PORCENTAGENS),
              (base + timedelta(seconds=i * 13)).strftime("%Y-%m-%dT%H:%M:%S-04:00")) for i in range(total)])
    print(f"{total:,} estimativas no banco:".replace(",", "."))
    medir("lista das salas (/ambientes)", lista_salas)
    medir("relatório por sessão (coordenação)", relatorio, vezes=5)
