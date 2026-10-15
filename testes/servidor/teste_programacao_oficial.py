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
confere("'Room  4' (dois espaços) é a S4", por_titulo.get("SHORT COURSE: Multi-Agent Systems", ("",))[0] == "S4")
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

print("Tudo certo." if not falhas else f"{falhas} FALHARAM")
sys.exit(1 if falhas else 0)
