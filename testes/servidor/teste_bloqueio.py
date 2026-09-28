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

main.SENHA_COORDENACAO = "senha-certa"


def pedido(ip):
    return Request({"type": "http", "client": (ip, 5000), "session": {}, "headers": []})


def status(funcao, dados, ip):
    try:
        funcao(dados, pedido(ip))
        return 200
    except HTTPException as erro:
        return erro.status_code


falhas = 0
def confere(nome, obtido, esperado):
    global falhas
    ok = obtido == esperado
    falhas += not ok
    print(f"{'OK  ' if ok else 'FALHOU'} {nome}: {obtido} (esperado {esperado})")


# (A coordenação não tem mais bloqueio desde 27/09 à tarde: ver teste_coordenacao.py)

login = main.login
Dados = main.DadosLogin
email = "voluntario1@exemplo.com"
for _ in range(5):
    status(login, Dados(email=email, pin="0000"), "200.1.1.1")
confere("atacante bloqueado no e-mail do voluntário", status(login, Dados(email=email, pin="1111"), "200.1.1.1"), 429)
confere("voluntário entra do celular dele", status(login, Dados(email=email, pin="1111"), "189.3.3.3"), 200)

main.liberar_todos_os_ips(email)  # o que o "Novo PIN" faz
confere("depois do novo PIN, libera", status(login, Dados(email=email, pin="1111"), "200.1.1.1"), 200)

print("\nTudo certo." if not falhas else f"\n{falhas} FALHA(S)")
