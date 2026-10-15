"""Testa o cadastro de voluntários por usuário (com senha escolhida ou sorteada)
e a conversão de um banco antigo, em que o login era pelo e-mail."""
import os
import sqlite3
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # pasta do projeto
os.chdir(RAIZ)
sys.path.insert(0, RAIZ)
import database

falhas = 0
def confere(nome, obtido, esperado):
    global falhas
    ok = obtido == esperado
    falhas += not ok
    print(f"{'OK  ' if ok else 'FALHOU'} {nome}: {obtido!r}" + ("" if ok else f" (esperado {esperado!r})"))


# ---------- Banco antigo (login pelo e-mail) vira banco com usuário ----------
antigo = os.path.join(tempfile.mkdtemp(), "antigo.db")
conn = sqlite3.connect(antigo)
conn.execute("""CREATE TABLE voluntarios (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE, pin_hash TEXT NOT NULL, ativo INTEGER NOT NULL DEFAULT 1)""")
conn.execute("INSERT INTO voluntarios (nome, email, pin_hash) VALUES ('Eduardo', 'eduardo@ufmt.br', ?)",
             (database.gerar_hash_pin("123456"),))
conn.commit()
conn.close()

database.ARQUIVO_BANCO = antigo
database.criar_banco(False)
with database.conectar() as conn:
    colunas = [c["name"] for c in conn.execute("PRAGMA table_info(voluntarios)")]
    eduardo = conn.execute("SELECT * FROM voluntarios WHERE usuario = 'eduardo@ufmt.br'").fetchone()
confere("coluna email virou usuario", ("usuario" in colunas, "email" in colunas), (True, False))
confere("quem já existia continua, com o e-mail como usuário", eduardo["nome"], "Eduardo")
confere("e a senha antiga continua valendo", database.verificar_pin("123456", eduardo["pin_hash"]), True)
database.criar_banco(False)  # ligar o site de novo não pode dar erro
confere("religar o site não quebra", True, True)


# ---------- Cadastro pelo painel ----------
database.ARQUIVO_BANCO = os.path.join(tempfile.mkdtemp(), "novo.db")
database.criar_banco(False)

from starlette.requests import Request
import main


def pedido():
    return Request({"type": "http", "session": {"coordenacao": True}, "client": ("1.1.1.1", 1), "headers": []})


criado = main.criar_voluntario(main.NovoVoluntario(nome="Contagem", usuario="Contagem", pin="2222"), pedido())
confere("senha escolhida é a que vale", criado["pin"], "2222")
confere("usuário fica em minúsculas", criado["usuario"], "contagem")
sorteado = main.criar_voluntario(main.NovoVoluntario(nome="Maria", usuario="maria"), pedido())
confere("sem senha: sorteia uma de 6 dígitos", (len(sorteado["pin"]), sorteado["pin"].isdigit()), (6, True))

from fastapi import HTTPException
for nome, usuario, pin, motivo in [
    ("Outra", "contagem", "", "usuário já cadastrado"),
    ("Com espaço", "joao silva", "", "usuário inválido"),
    ("Senha curta", "ana", "12", "pelo menos 4"),
]:
    try:
        main.criar_voluntario(main.NovoVoluntario(nome=nome, usuario=usuario, pin=pin), pedido())
        confere(f"recusa: {motivo}", "aceitou", "recusou")
    except HTTPException as erro:
        confere(f"recusa: {motivo}", motivo in erro.detail, True)

importados = main.importar_voluntarios(
    main.ImportarVoluntarios(texto="Nome, Usuário\nLuis, luis, 1604\nAna, ana\nSem usuário"), pedido())
confere("importa com e sem senha", [c["usuario"] for c in importados["criados"]], ["luis", "ana"])
confere("senha da lista importada", importados["criados"][0]["pin"], "1604")
confere("linha sem usuário vira erro", [e["linha"] for e in importados["erros"]], [4])

# O login funciona com a senha escolhida
main.login(main.DadosLogin(usuario="contagem", pin="2222"),
           Request({"type": "http", "session": {}, "client": ("1.1.1.1", 1), "headers": []}))
confere("entra com contagem / 2222", True, True)

print("\nTudo certo." if not falhas else f"\n{falhas} FALHA(S)")
sys.exit(1 if falhas else 0)
