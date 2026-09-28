import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # pasta do projeto
os.chdir(RAIZ)
sys.path.insert(0, RAIZ)
import database

database.ARQUIVO_BANCO = os.path.join(tempfile.mkdtemp(), "teste.db")
database.criar_banco(criar_voluntarios_exemplo=True)

with database.conectar() as conn:
    conn.execute(
        "INSERT INTO eventos (ambiente_codigo, tipo, quantidade, horario, voluntario_id) "
        "VALUES ('A1', 'entrada', 7, '2026-10-19T09:00:00-04:00', 1)"
    )
    print("antes: ", database.obter_ambiente(conn, "A1"))

# Simula a lista nova chegando da organização.
database.AMBIENTES_EXEMPLO[0] = ("A1", "Arena 1", "auditorio", 350)
database.criar_banco(criar_voluntarios_exemplo=True)

with database.conectar() as conn:
    a1 = database.obter_ambiente(conn, "A1")
    print("depois:", a1)
    total = conn.execute("SELECT COUNT(*) FROM ambientes").fetchone()[0]

assert a1["nome"] == "Arena 1" and a1["capacidade"] == 350, "não atualizou"
assert a1["ocupacao"] == 7, "perdeu a contagem"
assert total == 9, "duplicou salas"
print("Tudo certo.")
