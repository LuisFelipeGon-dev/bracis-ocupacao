"""Testa a troca de capacidade pela coordenação (e que reiniciar o site não desfaz a troca)."""
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # pasta do projeto
os.chdir(RAIZ)
sys.path.insert(0, RAIZ)

import database
database.ARQUIVO_BANCO = os.path.join(tempfile.mkdtemp(), "teste.db")

from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request
import main

falhas = 0
def confere(nome, obtido, esperado):
    global falhas
    ok = obtido == esperado
    falhas += not ok
    print(f"{'OK  ' if ok else 'FALHOU'} {nome}: {obtido!r}" + ("" if ok else f" (esperado {esperado!r})"))


def pedido(coordenacao):
    return Request({"type": "http", "client": ("10.4.0.74", 1), "headers": [],
                    "session": {"coordenacao": True} if coordenacao else {}})


def status(funcao):
    try:
        funcao()
        return 200
    except HTTPException as erro:
        return erro.status_code


def capacidade(codigo):
    with database.conectar() as conn:
        return database.obter_ambiente(conn, codigo)["capacidade"]


nova = main.MudarCapacidade(capacidade=120)
confere("sem login da coordenação: recusa", status(lambda: main.mudar_capacidade("A1", nova, pedido(False))), 401)
confere("sala que não existe: 404", status(lambda: main.mudar_capacidade("Z9", nova, pedido(True))), 404)
confere("coordenação muda", status(lambda: main.mudar_capacidade("A1", nova, pedido(True))), 200)
confere("capacidade nova no banco", capacidade("A1"), 120)

database.criar_banco(False)  # o site reiniciou
confere("reiniciar não volta a capacidade antiga", capacidade("A1"), 120)

for invalida in (0, -5, 99999):
    try:
        main.MudarCapacidade(capacidade=invalida)
        confere(f"capacidade {invalida} recusada", False, True)
    except ValidationError:
        confere(f"capacidade {invalida} recusada", True, True)

print("\nTudo certo." if not falhas else f"\n{falhas} FALHA(S)")
sys.exit(1 if falhas else 0)
