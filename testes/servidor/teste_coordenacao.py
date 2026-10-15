import asyncio
import os
import sys
import tempfile
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # pasta do projeto
os.chdir(RAIZ)
sys.path.insert(0, RAIZ)

import database
database.ARQUIVO_BANCO = os.path.join(tempfile.mkdtemp(), "teste.db")

from fastapi import HTTPException
from starlette.requests import Request
import main

main.USUARIO_COORDENACAO = "luis"
main.SENHA_COORDENACAO = "ipe-rio-cerrado-pantanal"


def pedido():
    return Request({"type": "http", "client": ("10.4.0.74", 1), "session": {}, "headers": []})


async def tenta(senha, usuario="luis"):
    try:
        await main.login_coordenacao(main.LoginCoordenacao(usuario=usuario, senha=senha), pedido())
        return 200
    except HTTPException as erro:
        return erro.status_code


def confere(nome, obtido, esperado):
    print(f"{'OK  ' if obtido == esperado else 'FALHOU'} {nome}: {obtido!r}" + ("" if obtido == esperado else f" (esperado {esperado!r})"))


async def teste():
    inicio = time.monotonic()
    erros = [await tenta("errada") for _ in range(6)]
    demorou = time.monotonic() - inicio
    print("6 senhas erradas:", erros, f"em {demorou:.1f} s (esperado ~6 s, nenhum 429)")
    confere("nenhuma senha errada bloqueia (só 401)", erros, [401] * 6)
    confere("senha certa logo depois", await tenta("ipe-rio-cerrado-pantanal"), 200)
    confere("usuário errado com a senha certa", await tenta("ipe-rio-cerrado-pantanal", "maria"), 401)
    confere("usuário com maiúscula", await tenta("ipe-rio-cerrado-pantanal", "Luis"), 200)

    # Enquanto uma senha errada espera 1 s, outro pedido é atendido na hora?
    inicio = time.monotonic()
    espera = asyncio.create_task(tenta("errada"))
    await asyncio.sleep(0.05)
    certo = await tenta("ipe-rio-cerrado-pantanal")
    print(f"senha certa durante a espera de outra: {certo} em {time.monotonic() - inicio:.2f} s (esperado 200, < 0,2 s)")
    confere("senha certa durante a espera de outra", certo, 200)
    await espera

asyncio.run(teste())
