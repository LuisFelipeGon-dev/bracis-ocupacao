import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # pasta do projeto
os.chdir(RAIZ)
sys.path.insert(0, RAIZ)
os.environ["CRIAR_VOLUNTARIOS_EXEMPLO"] = "sim"

import database
database.ARQUIVO_BANCO = os.path.join(tempfile.mkdtemp(), "teste.db")

from fastapi import HTTPException
from starlette.requests import Request
import main


def como(voluntario_id):
    return Request({"type": "http", "client": ("1.1.1.1", 1), "session": {"voluntario_id": voluntario_id}, "headers": []})


def tenta(f, *args):
    try:
        return f(*args)
    except HTTPException as erro:
        return erro.status_code


falhas = 0
def confere(nome, obtido, esperado):
    global falhas
    ok = obtido == esperado
    falhas += not ok
    print(f"{'OK  ' if ok else 'FALHOU'} {nome}: {obtido} (esperado {esperado})")


E = main.NovoEvento
D = main.PedidoDesfazer
main.registrar_evento(E(ambiente_codigo="S1", tipo="entrada", quantidade=5), como(1))  # porta 1
main.registrar_evento(E(ambiente_codigo="S1", tipo="entrada", quantidade=3), como(2))  # porta 2

u1 = main.ultimo_registro("S1", como(1))
u2 = main.ultimo_registro("S1", como(2))
confere("último do voluntário 1 é a entrada de 5", u1["quantidade"], 5)
confere("último do voluntário 2 é a entrada de 3", u2["quantidade"], 3)
confere("voluntário 3 não tem registro", tenta(main.ultimo_registro, "S1", como(3)), 404)

confere("voluntário 1 não desfaz o registro do 2", tenta(main.desfazer_ultimo, D(ambiente_codigo="S1", evento_id=u2["id"]), como(1)), 409)
r = main.desfazer_ultimo(D(ambiente_codigo="S1", evento_id=u1["id"]), como(1))
confere("voluntário 1 desfaz a própria entrada de 5", r["ambiente"]["ocupacao"], 3)
confere("desfazer de novo o mesmo registro", tenta(main.desfazer_ultimo, D(ambiente_codigo="S1", evento_id=u1["id"]), como(1)), 409)

# Voluntário 2 registrou 3 entradas; o voluntário 1 registra saída de 3; desfazer a entrada deixaria -3.
main.registrar_evento(E(ambiente_codigo="S1", tipo="saida", quantidade=3), como(1))
confere("desfazer entrada com a sala vazia é recusado", tenta(main.desfazer_ultimo, D(ambiente_codigo="S1", evento_id=u2["id"]), como(2)), 400)

print("\nTudo certo." if not falhas else f"\n{falhas} FALHA(S)")
