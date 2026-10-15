"""Testa as estimativas de lotação: validade ("zera a cada sessão"), registro pelo voluntário e relatório."""
import os
import sys
import tempfile
from datetime import datetime

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # pasta do projeto
os.chdir(RAIZ)
sys.path.insert(0, RAIZ)
import database
database.ARQUIVO_BANCO = os.path.join(tempfile.mkdtemp(), "teste.db")
database.criar_banco(True)

from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request
import estimativas
import main

falhas = 0
def confere(nome, obtido, esperado):
    global falhas
    ok = obtido == esperado
    falhas += not ok
    print(f"{'OK  ' if ok else 'FALHOU'} {nome}: {obtido!r}" + ("" if ok else f" (esperado {esperado!r})"))


# Programação do teste: na S1, sessão das 08:30 às 10:30 e outra das 11:00 às 12:00.
with database.conectar() as conn:
    conn.execute("INSERT INTO sessoes (ambiente_codigo, titulo, inicio, fim) VALUES "
                 "('S1', 'Manhã', '2026-10-20T08:30', '2026-10-20T10:30'), "
                 "('S1', 'Fim da manhã', '2026-10-20T11:00', '2026-10-20T12:00')")


def estima(sala, porcentagem, horario):
    with database.conectar() as conn:
        conn.execute("INSERT INTO estimativas (ambiente_codigo, porcentagem, horario, voluntario_id) "
                     "VALUES (?, ?, ?, 1)", (sala, porcentagem, horario + ":00-04:00"))


def vale_agora(sala, hora):
    with database.conectar() as conn:
        atual = estimativas.estimativas_atuais(conn, datetime.fromisoformat(f"2026-10-20T{hora}"))
    return atual.get(sala, {}).get("porcentagem")


# ---------- Validade ----------
confere("sem estimativa: nada", vale_agora("S1", "09:00"), None)

estima("S1", 60, "2026-10-20T08:20")  # 10 min antes da sessão das 08:30
confere("15 min antes do início já vale para a sessão", vale_agora("S1", "09:00"), 60)
estima("S1", 80, "2026-10-20T09:40")
confere("vale a última", vale_agora("S1", "10:00"), 80)
confere("a sessão terminou (10:30): zera", vale_agora("S1", "10:35"), None)

estima("S1", 30, "2026-10-20T10:40")  # no intervalo
confere("estimativa no intervalo vale no intervalo", vale_agora("S1", "10:42"), 30)
confere("começa a próxima (10:45 = 11:00 − 15 min): zera", vale_agora("S1", "10:50"), None)

estima("S2", 50, "2026-10-20T09:00")  # S2 não tem sessão hoje
confere("sala sem sessão no dia: vale até o fim do dia", vale_agora("S2", "18:00"), 50)
with database.conectar() as conn:
    no_dia_seguinte = estimativas.estimativas_atuais(conn, datetime(2026, 10, 21, 8, 0)).get("S2")
confere("no dia seguinte a estimativa de ontem não vale", no_dia_seguinte, None)


# ---------- Registro pelo voluntário (rota POST /estimativas) ----------
def pedido(voluntario_id):
    sessao = {} if voluntario_id is None else {"voluntario_id": voluntario_id}
    return Request({"type": "http", "session": sessao, "client": ("1.1.1.1", 1), "headers": []})


def status(funcao):
    try:
        funcao()
        return 200
    except HTTPException as erro:
        return erro.status_code


nova = main.NovaEstimativa(ambiente_codigo="A1", porcentagem=70)
confere("sem login: recusa", status(lambda: main.registrar_estimativa(nova, pedido(None))), 401)
confere("sala que não existe: 404",
        status(lambda: main.registrar_estimativa(main.NovaEstimativa(ambiente_codigo="Z9", porcentagem=10), pedido(1))), 404)
resposta = main.registrar_estimativa(nova, pedido(1))
confere("devolve a sala com a estimativa nova", resposta["estimativa"]["porcentagem"], 70)
confere("com o nome de quem informou", resposta["estimativa"]["voluntario"], "Voluntário Exemplo 1")
confere("o totem vê na hora (a memória de 2 s é limpa)",
        next(a for a in main.listar_ambientes() if a["codigo"] == "A1")["estimativa"]["porcentagem"], 70)
main.registrar_estimativa(main.NovaEstimativa(ambiente_codigo="A1", porcentagem=110), pedido(1))
confere("gente em pé (110) é aceito", main.obter_ambiente("A1")["estimativa"]["porcentagem"], 110)

for invalida in [-10, 5, 55, 120]:
    try:
        main.NovaEstimativa(ambiente_codigo="A1", porcentagem=invalida)
        confere(f"{invalida}% recusado", False, True)
    except ValidationError:
        confere(f"{invalida}% recusado", True, True)


# ---------- Relatório por sessão ----------
with database.conectar() as conn:
    linhas = {linha["titulo"]: linha for linha in estimativas.relatorio(conn)}
manha = linhas["Manhã"]
confere("manhã: estimativas de 08:20 (15 min antes) e 09:40", manha["estimativas"], 2)
confere("manhã: maior", manha["maior"], 80)
confere("manhã: média", manha["media"], 70)
fim = linhas["Fim da manhã"]
confere("fim da manhã: a do intervalo (10:40) é antes de 10:45, não conta", fim["estimativas"], 0)
confere("sessão sem estimativa: maior vazio", fim["maior"], None)

print("\nTudo certo." if not falhas else f"\n{falhas} FALHA(S)")
sys.exit(1 if falhas else 0)
