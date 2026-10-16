"""Testa a leitura da planilha oficial (uma linha por artigo), sem internet.

As linhas abaixo imitam casos reais da planilha do BRACIS 2026.
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # pasta do projeto
sys.path.insert(0, RAIZ)
import programacao

AMBIENTES = [
    {"codigo": "S1", "nome": "Room Nobres"},
    {"codigo": "S4", "nome": "Room Vila Bela"},
    {"codigo": "S5", "nome": "Room Chapada"},
    {"codigo": "A1", "nome": "Pantanal Auditorium"},
]

CSV = """Date,Event,Location,Start,End,Order,ID,Session,Chair,Title,Authors
19/10/2026,BRACIS,Room 1,08:30,10:30,1,#1,Graph Learning,,Paper A,X
19/10/2026,BRACIS,Room 1,08:30,10:30,2,#2,Graph Learning,,Paper B,Y
19/10/2026,WESAAC,Room 5,08:30,08:45,1,30,Agents,,Paper C,Z
19/10/2026,WESAAC,Room 5,08:45,09:00,2,31,Agents,,Paper D,Z
19/10/2026,WESAAC,Room 5,08:31,09:15,3,32,Agents,,Paper E,Z
19/10/2026,WESAAC,Room 5,09:45,09:30,4,33,Agents,,Paper F,Z
19/10/2026,WESAAC,Room 5,08:32,09:45,5,34,Agents,,Paper G,Z
19/10/2026,WESAAC,Room 5,10:45,10:00,6,35,Agents,,Paper H,Z
19/10/2026,WESAAC,Room 5,08:33,10:15,7,36,Agents,,Paper I,Z
19/10/2026,WESAAC,Room 5,11:45,10:30,8,37,Agents,,Paper J,Z
19/10/2026,BRACIS,Arena 1,18:00,19:00,,,Keynote,,The Design of Physical Intelligence,Marcelo Coelho
19/10/2026,WESAAC,Room 4,13:30,15:30,,,SHORT COURSE,,Multi-Agent Systems,Prof. A
19/10/2026,Wesaac,Room  4,13:30,15:30,,,Tutorials,,Multi-Agent Systems,Prof. A
21/10/2026,CTDIAC,Room 1,08:30,09:10,1,#5,MSc Track,,Thesis 1,W
21/10/2026,CTDIAC,Room 1,13:30,14:10,2,#6,MSc Track,,Thesis 2,W
22/10/2026,WESAAC,Room 5,09:30,10:30,1,,,,NATIONAL KEYNOTE SPEAKER - Prof. B,
22/10/2026,WESAAC,Room 5,09:30,10:30,,,,,Beyond the Model,
22/10/2026,BRACIS,Sala que não existe,09:30,10:30,,,X,,Y,
"""

sessoes, erros = programacao.interpretar(CSV, AMBIENTES)
por_titulo = {s[1]: s for s in sessoes}
for s in sessoes:
    print(s)
for e in erros:
    print("erro:", e)

falhas = 0
def confere(nome, ok):
    global falhas
    falhas += not ok
    print(f"{'OK  ' if ok else 'FALHOU'} {nome}")

confere("artigos da mesma sessão viram uma sessão", por_titulo.get("Graph Learning") == ("S1", "Graph Learning", None, "2026-10-19T08:30", "2026-10-19T10:30"))
confere("início trocado: usa o fim e vai até 10:30", por_titulo.get("Agents", ())[3:] == ("2026-10-19T08:30", "2026-10-19T10:30"))
confere("início trocado aparece como aviso", sum("usamos só o fim" in e["motivo"] for e in erros) == 3)
confere("palestra: sessão + título", "Keynote: The Design of Physical Intelligence" in por_titulo)
confere("palestra: palestrante", por_titulo.get("Keynote: The Design of Physical Intelligence", (0, 0, 0))[2] == "Marcelo Coelho")
confere("'Room  4' (dois espaços) é a S5 (Chapada)", por_titulo.get("SHORT COURSE: Multi-Agent Systems", ("",))[0] == "S5")
confere("mesma sala e horário: fica a primeira", "Tutorials: Multi-Agent Systems" not in por_titulo)
confere("mesma sala e horário: avisa", any("ficou só a primeira" in e["motivo"] for e in erros))
confere("intervalo do almoço separa a sessão em duas", sum(s[1] == "MSc Track" for s in sessoes) == 2)
confere("sessão de artigos não pega o título do artigo", not any(s[1].startswith("MSc Track:") for s in sessoes))
confere("sem nome de sessão: junta os títulos", any(s[1] == "Beyond the Model · NATIONAL KEYNOTE SPEAKER - Prof. B" for s in sessoes))
confere("sala desconhecida é ignorada com erro", any("não existe" in e["motivo"] for e in erros))
confere("total de sessões", len(sessoes) == 7)

# O formato simples (uma linha por sessão) continua funcionando
simples = "sala,data,inicio,fim,titulo\nS1,20/10/2026,09:00,10:00,Abertura\n"
confere("formato simples", programacao.interpretar(simples, AMBIENTES)[0] == [("S1", "Abertura", None, "2026-10-20T09:00", "2026-10-20T10:00")])

# Linha com colunas faltando (ex.: planilha salva pelo Excel) não derruba a leitura
curta = "Date,Event,Location,Start,End,Order,ID,Session,Chair,Title,Authors\n19/10/2026,BRACIS,Room 1,08:30,10:30\n"
try:
    resultado = programacao.interpretar(curta, AMBIENTES)[0]
    confere("linha curta: vira sessão sem nome", resultado == [("S1", "Session", None, "2026-10-19T08:30", "2026-10-19T10:30")])
except Exception as erro:
    confere(f"linha curta não pode dar erro ({erro!r})", False)

# Várias abas: se uma não tem nada válido, a programação antiga fica (não apaga um dia inteiro)
import sqlite3
conn = sqlite3.connect(":memory:")
conn.row_factory = sqlite3.Row
conn.execute("CREATE TABLE ambientes (codigo TEXT, nome TEXT)")
conn.execute("CREATE TABLE sessoes (ambiente_codigo TEXT, titulo TEXT, palestrante TEXT, inicio TEXT, fim TEXT)")
conn.executemany("INSERT INTO ambientes VALUES (?, ?)", [(a["codigo"], a["nome"]) for a in AMBIENTES])
conn.execute("INSERT INTO sessoes VALUES ('S1', 'Antiga', NULL, '2026-10-19T08:30', '2026-10-19T10:30')")
original = programacao.baixar_planilha
programacao.baixar_planilha = lambda: ([CSV, "Data,Coluna errada\n"], "teste")
leitura = programacao.atualizar(conn)
programacao.baixar_planilha = original
confere("aba sem nada válido: mantém a programação antiga", [r[0] for r in conn.execute("SELECT titulo FROM sessoes")] == ["Antiga"])
confere("aba sem nada válido: avisa qual aba", "aba 2" in (leitura["falha"] or ""))

# Linha estragada numa sala (hora apagada): essa sala fica com a programação anterior; as outras mudam
conn.execute("DELETE FROM sessoes")
conn.execute("INSERT INTO sessoes VALUES ('S1', 'Antiga S1', NULL, '2026-10-19T08:30', '2026-10-19T10:30')")
conn.execute("INSERT INTO sessoes VALUES ('S5', 'Antiga S5', NULL, '2026-10-19T08:30', '2026-10-19T10:30')")
estragada = """Date,Event,Location,Start,End,Order,ID,Session,Chair,Title,Authors
19/10/2026,BRACIS,Room 1,,10:30,1,#1,Graph Learning,,Paper A,X
19/10/2026,BRACIS,Room 1,08:30,10:30,2,#2,Graph Learning,,Paper B,X
19/10/2026,BRACIS,Room 4,08:30,10:30,1,#3,Nova S5,,Paper C,Y
19/10/2026,BRACIS,Sala Nova,08:30,10:30,1,#4,Outra,,Paper D,Y
"""
programacao.baixar_planilha = lambda: ([estragada], "teste")
leitura = programacao.atualizar(conn)
programacao.baixar_planilha = original
titulos = sorted(r[0] for r in conn.execute("SELECT titulo FROM sessoes"))
confere("sala com linha estragada: fica a programação anterior", "Antiga S1" in titulos and "Graph Learning" not in titulos)
confere("as outras salas recebem a mudança", "Nova S5" in titulos and "Antiga S5" not in titulos)
confere("sala com linha estragada: avisa no painel", "Room Nobres" in (leitura["falha"] or ""))
confere("sala que não existe não trava nenhuma sala", "Room Chapada" not in (leitura["falha"] or ""))

# Arquivo Excel da coordenação: outros nomes de coluna, salas com o nome real, datas e horas do Excel
import io as _io
from datetime import datetime as _dt, time as _time
import openpyxl
arquivo = openpyxl.Workbook()
aba = arquivo.active
aba.append(["Date", "Event", "Room / Arena", "Start", "End", "Order", "ID", "Session Title", "Chair", "Title", "Authors"])
aba.append([_dt(2026, 10, 19), "BRACIS", "Nobres Room ", _time(8, 30), "10:30:00", 1.0, "#1", "Best Paper\nCandidates", None, "Paper A", "X"])
aba.append([_dt(2026, 10, 19), "BRACIS", "Chapada Room ", "08:30", _dt(1899, 12, 30, 10, 30), 1.0, "", "-", None, "Can you build it?", "Y"])
segunda = arquivo.create_sheet("2010")
segunda.append(["Date", "Event", "Room / Arena", "Start", "End", "Order", "ID", "Session Title", "Chair", "Title", "Authors"])
segunda.append([_dt(2026, 10, 20), "BRACIS", "Pantanal Auditorium", _time(9, 0), _time(10, 0), None, None, "Keynote", None, "Opening", "Z"])
memoria = _io.BytesIO()
arquivo.save(memoria)
abas = programacao.abas_do_excel(memoria.getvalue())
confere("Excel: uma aba vira um texto", len(abas) == 2)
lidas = sorted(programacao.interpretar(abas[0], AMBIENTES)[0] + programacao.interpretar(abas[1], AMBIENTES)[0])
confere("Excel: sala pelo nome real, datas e horas do Excel, quebra de linha e '-' como sessão", lidas == [
    ("A1", "Keynote: Opening", "Z", "2026-10-20T09:00", "2026-10-20T10:00"),
    ("S1", "Best Paper Candidates", None, "2026-10-19T08:30", "2026-10-19T10:30"),
    ("S5", "Can you build it?", "Y", "2026-10-19T08:30", "2026-10-19T10:30"),
])

print("Tudo certo." if not falhas else f"{falhas} FALHARAM")
sys.exit(1 if falhas else 0)
