"""Testa a rota pública /programacao-dados (chamando a função direto, num banco temporário)."""
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # pasta do projeto
os.chdir(RAIZ)
sys.path.insert(0, RAIZ)
os.environ["URL_PROGRAMACAO"] = ""  # usa o programacao_exemplo.csv

import database
database.ARQUIVO_BANCO = os.path.join(tempfile.mkdtemp(), "teste.db")

import main
import programacao

falhas = 0
def confere(nome, obtido, esperado):
    global falhas
    ok = obtido == esperado
    falhas += not ok
    print(f"{'OK  ' if ok else 'FALHOU'} {nome}: {obtido!r}" + ("" if ok else f" (esperado {esperado!r})"))

with database.conectar() as conn:
    conn.execute("DELETE FROM sessoes")
    conn.executemany(
        "INSERT INTO sessoes (ambiente_codigo, titulo, palestrante, inicio, fim) VALUES (?, ?, ?, ?, ?)",
        [("S1", "Tarde", None, "2026-10-20T14:00", "2026-10-20T15:00"),
         ("A1", "Manhã", "Ana", "2026-10-20T09:00", "2026-10-20T10:00"),
         ("A2", "Manhã 2", None, "2026-10-20T09:00", "2026-10-20T10:00")])
    conn.execute("INSERT INTO voluntarios (nome, email, pin_hash) VALUES ('T', 't@t', 'x$y')")
    conn.execute("INSERT INTO eventos (ambiente_codigo, tipo, quantidade, horario, voluntario_id) "
                 "VALUES ('A1', 'entrada', 7, '2026-10-20T09:05:00-04:00', 1)")

dados = main.programacao_publica()
confere("tem horário do servidor", len(dados["horario_servidor"]), 16)
confere("sessões em ordem de início e sala", [s["titulo"] for s in dados["sessoes"]], ["Manhã", "Manhã 2", "Tarde"])
confere("sessão traz nome e tipo da sala", (dados["sessoes"][0]["ambiente_nome"], dados["sessoes"][0]["tipo"]), ("Auditório 1", "auditorio"))
confere("sessão traz palestrante", dados["sessoes"][0]["palestrante"], "Ana")
confere("ambientes com ocupação", next(a for a in dados["ambientes"] if a["codigo"] == "A1")["ocupacao"], 7)
confere("página existe", main.pagina_programacao().path, "static/programacao.html")

print("\nTudo certo." if not falhas else f"\n{falhas} FALHA(S)")
sys.exit(1 if falhas else 0)
