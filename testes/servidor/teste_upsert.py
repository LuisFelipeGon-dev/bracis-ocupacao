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
    # Duas salas que não estão mais na lista (como o A3 e o laboratório de antes):
    # uma sem registros e outra com registros.
    conn.execute("INSERT INTO ambientes VALUES ('L1', 'Laboratório 1', 'laboratorio', 30)")
    conn.execute("INSERT INTO ambientes VALUES ('A3', 'Auditório 3', 'auditorio', 120)")
    conn.execute("INSERT INTO sessoes (ambiente_codigo, titulo, inicio, fim) "
                 "VALUES ('L1', 'Minicurso', '2026-10-20T14:00', '2026-10-20T17:00')")
    conn.execute(
        "INSERT INTO eventos (ambiente_codigo, tipo, quantidade, horario, voluntario_id) "
        "VALUES ('A3', 'entrada', 2, '2026-10-19T09:00:00-04:00', 1)"
    )
    print("antes: ", database.obter_ambiente(conn, "A1"))

# Simula a lista nova chegando da organização.
database.AMBIENTES_EXEMPLO[0] = ("A1", "Arena 1", "auditorio", 350)
database.criar_banco(criar_voluntarios_exemplo=True)

with database.conectar() as conn:
    a1 = database.obter_ambiente(conn, "A1")
    print("depois:", a1)
    codigos = {linha[0] for linha in conn.execute("SELECT codigo FROM ambientes")}

assert a1["nome"] == "Arena 1", "não atualizou o nome"
assert a1["capacidade"] == 200, "a capacidade é da coordenação: a lista não pode sobrescrever"
assert a1["ocupacao"] == 7, "perdeu a contagem"
assert "L1" not in codigos, "sala fora da lista e sem registros deveria sair"
assert "A3" in codigos, "sala fora da lista com registros deveria ficar"
assert len(codigos) == 8, "duplicou salas"
print("Tudo certo.")
