"""Programação do evento: lê a planilha (CSV) e guarda na tabela sessoes.

Aceita dois formatos (o site descobre qual é pelo cabeçalho):

1. Planilha oficial do BRACIS: uma aba por dia e uma linha por ARTIGO, com as colunas
       Date, Event, Location, Start, End, Order, ID, Session, Chair, Title, Authors
   (no arquivo Excel da coordenação, "Location" se chama "Room / Arena" e "Session", "Session Title")
   As linhas da mesma sessão (mesmo dia, sala, evento e "Session") viram uma sessão só,
   do primeiro início ao último fim.

2. Formato simples: uma linha por sessão, com as colunas
       sala, data, inicio, fim, titulo, palestrante
   Exemplo:  A1, 20/10/2026, 09:00, 10:30, Abertura, Fulano de Tal

O link pode ser de um CSV (Google Sheets) ou de um arquivo Excel (.xlsx) no Google Drive;
no Excel, cada aba do arquivo vira um CSV e segue o mesmo caminho.
"""

import csv
import io
import os
import unicodedata
import urllib.request
from datetime import datetime, time, timedelta

import openpyxl

import database

ARQUIVO_EXEMPLO = "programacao_exemplo.csv"
COLUNAS = ["sala", "data", "inicio", "fim", "titulo", "palestrante"]
COLUNAS_OFICIAIS = ["date", "location", "start", "end", "session"]
# Outros nomes para as mesmas colunas (como estão no arquivo Excel da coordenação)
SINONIMOS = {"room / arena": "location", "session title": "session"}

# Na planilha oficial, artigos da mesma sessão separados por mais que isto viram duas sessões
# (ex.: uma trilha com uma parte de manhã e outra à tarde: no almoço a sala não está "em sessão").
INTERVALO_MAXIMO = timedelta(minutes=20)

# Resultado da última leitura, mostrado no painel da coordenação.
# Fica na memória: quando o site reinicia, a planilha é lida de novo logo no começo.
ultima_leitura = {"horario": None, "origem": None, "erros": [], "falha": None}


def simplificar(texto: str) -> str:
    """"  Auditório  1 " vira "auditorio 1": sem acento, minúsculo e sem espaços sobrando."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())


def baixar_planilha() -> tuple[list[str], str]:
    """Devolve (textos dos CSVs, de onde vieram). Sem URL_PROGRAMACAO no .env, usa o arquivo de exemplo.

    URL_PROGRAMACAO pode ter vários links separados por espaço: um para cada aba da planilha.
    Se o link for de um arquivo Excel, cada aba dele vira um texto.
    """
    urls = os.getenv("URL_PROGRAMACAO", "").split()
    if not urls:
        with open(ARQUIVO_EXEMPLO, encoding="utf-8-sig") as arquivo:
            return [arquivo.read()], "arquivo de exemplo"
    textos = []
    excel = False
    for url in urls:
        with urllib.request.urlopen(url, timeout=20) as resposta:
            conteudo = resposta.read()
        # Todo arquivo .xlsx começa com "PK" (por dentro ele é um .zip).
        if conteudo.startswith(b"PK"):
            textos += abas_do_excel(conteudo)
            excel = True
            continue
        texto = conteudo.decode("utf-8-sig")
        # Se o link for o da planilha "normal" (e não o do CSV), o Google devolve uma página HTML.
        if texto.lstrip().startswith("<"):
            raise ValueError(f"o link {url} não é de um CSV (veja o README, parte da programação)")
        textos.append(texto)
    origem = "arquivo Excel do Google Drive" if excel else "planilha do Google"
    if len(textos) > 1:
        origem += f" ({len(textos)} abas)"
    return textos, origem


def abas_do_excel(conteudo: bytes) -> list[str]:
    """Arquivo .xlsx -> um texto CSV por aba, no mesmo formato que o Google Sheets exporta."""
    arquivo = openpyxl.load_workbook(io.BytesIO(conteudo), read_only=True, data_only=True)
    textos = []
    for aba in arquivo.worksheets:
        saida = io.StringIO()
        escritor = csv.writer(saida)
        for linha in aba.iter_rows(values_only=True):
            escritor.writerow([celula_como_texto(valor) for valor in linha])
        textos.append(saida.getvalue())
    arquivo.close()
    return textos


def celula_como_texto(valor) -> str:
    """No Excel, datas e horas vêm como datas do Python: viram "19/10/2026" e "08:30"."""
    if valor is None:
        return ""
    if isinstance(valor, time):
        return valor.strftime("%H:%M")
    if isinstance(valor, datetime):
        if valor.year < 1900:  # hora guardada como data (o Excel usa o dia 30/12/1899)
            return valor.strftime("%H:%M")
        return valor.strftime("%d/%m/%Y")
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))  # 1.0 vira "1"
    return str(valor)


def ler_horario(data: str, hora: str) -> str:
    """"20/10/2026" + "9:00" vira "2026-10-20T09:00" (horário de Cuiabá).

    Nesse formato, comparar os textos já compara as datas: "…T09:00" < "…T10:30".
    """
    dia = datetime.strptime(data.strip(), "%d/%m/%Y")
    hora = hora.strip()
    # O Google às vezes exporta a hora com segundos (09:00:00).
    formato = "%H:%M:%S" if hora.count(":") == 2 else "%H:%M"
    horario = datetime.strptime(hora, formato)
    return dia.replace(hour=horario.hour, minute=horario.minute).strftime("%Y-%m-%dT%H:%M")


def interpretar(texto: str, ambientes: list[dict]) -> tuple[list[tuple], list[dict]]:
    """Confere cada linha da planilha. Devolve (sessões válidas, erros encontrados)."""
    # A sala pode vir pelo código (A1), pelo nome (Pantanal Auditorium) ou pelo nome da planilha (Arena 1, Nobres Room).
    codigo_por_nome = {}
    for ambiente in ambientes:
        codigo = ambiente["codigo"]
        for nome in (codigo, ambiente["nome"], *database.NOMES_NA_PLANILHA.get(codigo, ())):
            codigo_por_nome[simplificar(nome)] = codigo

    # Planilhas salvas pelo Excel em português costumam separar com ";".
    primeira_linha = texto.split("\n", 1)[0]
    separador = ";" if primeira_linha.count(";") > primeira_linha.count(",") else ","
    leitor = csv.reader(io.StringIO(texto), delimiter=separador)

    cabecalho = [simplificar(coluna) for coluna in next(leitor, [])]
    cabecalho = [SINONIMOS.get(coluna, coluna) for coluna in cabecalho]
    if all(coluna in cabecalho for coluna in COLUNAS_OFICIAIS):
        return interpretar_oficial(leitor, cabecalho, codigo_por_nome)
    faltando = [coluna for coluna in COLUNAS[:5] if coluna not in cabecalho]
    if faltando:
        return [], [{"linha": 1, "motivo": f"faltam as colunas: {', '.join(faltando)} (aba ignorada)"}]

    sessoes, erros = [], []
    # start=2: a linha 1 é o cabeçalho, então os números batem com os da planilha.
    for numero, valores in enumerate(leitor, start=2):
        if not any(valor.strip() for valor in valores):
            continue  # linha em branco
        linha = dict(zip(cabecalho, valores))
        try:
            codigo = codigo_por_nome.get(simplificar(linha.get("sala", "")))
            if codigo is None:
                raise ValueError(f'sala "{linha.get("sala", "")}" não existe')
            titulo = " ".join(linha.get("titulo", "").split())
            if not titulo:
                raise ValueError("falta o título")
            try:
                inicio = ler_horario(linha.get("data", ""), linha.get("inicio", ""))
                fim = ler_horario(linha.get("data", ""), linha.get("fim", ""))
            except ValueError:
                raise ValueError("data ou hora em formato errado (use 20/10/2026 e 09:00)")
            if fim <= inicio:
                raise ValueError("o fim está antes do início")
            palestrante = linha.get("palestrante", "").strip() or None
            sessoes.append((codigo, titulo, palestrante, inicio, fim))
        except ValueError as erro:
            erros.append({"linha": numero, "motivo": f"{erro} (linha ignorada)", "sala": codigo})
    return sessoes, erros


def interpretar_oficial(leitor, cabecalho: list[str], codigo_por_nome: dict) -> tuple[list[tuple], list[dict]]:
    """Planilha oficial (uma linha por artigo): junta os artigos de cada sessão numa sessão só."""
    # (dia, sala, evento, nome da sessão) -> artigos dessa sessão: (início, fim, título, autores, chair)
    grupos = {}
    erros = []
    for numero, valores in enumerate(leitor, start=2):
        if not any(valor.strip() for valor in valores):
            continue  # linha em branco
        # " ".join(split()): tira espaços sobrando e as quebras de linha dentro da célula (comuns no Excel)
        linha = {coluna: " ".join(valor.split()) for coluna, valor in zip(cabecalho, valores)}
        try:
            codigo = codigo_por_nome.get(simplificar(linha.get("location", "")))
            if codigo is None:
                raise ValueError(f'sala "{linha.get("location", "")}" não existe')
            try:
                inicio = ler_horario(linha.get("date", ""), linha.get("start", ""))
                fim = ler_horario(linha.get("date", ""), linha.get("end", ""))
            except ValueError:
                raise ValueError("data ou hora em formato errado (use 20/10/2026 e 09:00)")
        except ValueError as erro:
            erros.append({"linha": numero, "motivo": f"{erro} (linha ignorada)", "sala": codigo})
            continue
        if fim <= inicio:
            # Visto na planilha: o início de alguns artigos saiu errado, mas o fim está certo.
            # Usamos só o fim, que já basta para saber até quando vai a sessão.
            erros.append({"linha": numero, "motivo": f"o início ({inicio[11:]}) está depois do fim ({fim[11:]}); usamos só o fim"})
            inicio = fim
        sessao = linha.get("session", "")
        if sessao in ("-", "–"):
            sessao = ""  # "-" na planilha = sessão sem nome
        chave = (linha.get("date", ""), codigo, simplificar(linha.get("event", "")), sessao)
        artigo = (inicio, fim, linha.get("title", ""), linha.get("authors", ""), linha.get("chair", ""),
                  linha.get("id", ""), numero)
        grupos.setdefault(chave, []).append(artigo)

    sessoes = []
    ja_vistas = {}  # (sala, início, fim) -> título: a planilha às vezes repete a mesma palestra
    for (_, codigo, _, nome_sessao), artigos in grupos.items():
        for bloco in separar_blocos(sorted(artigos)):
            inicio = bloco[0][0]
            fim = max(artigo[1] for artigo in bloco)
            if fim <= inicio:
                continue
            titulo, palestrante = titulo_e_palestrante(nome_sessao, bloco)
            repetida = ja_vistas.get((codigo, inicio, fim))
            if repetida:
                erros.append({"linha": bloco[0][6], "motivo": f'"{titulo}" está no mesmo horário e sala '
                              f'que "{repetida}"; ficou só a primeira'})
                continue
            ja_vistas[(codigo, inicio, fim)] = titulo
            sessoes.append((codigo, titulo, palestrante, inicio, fim))
    return sessoes, erros


def separar_blocos(artigos: list[tuple]) -> list[list[tuple]]:
    """Artigos em ordem de início -> blocos de artigos seguidos (corta onde há um intervalo grande)."""
    blocos = []
    fim_do_bloco = None
    for artigo in artigos:
        inicio, fim = artigo[0], artigo[1]
        if fim_do_bloco is None or datetime.fromisoformat(inicio) > datetime.fromisoformat(fim_do_bloco) + INTERVALO_MAXIMO:
            blocos.append([])
            fim_do_bloco = fim
        blocos[-1].append(artigo)
        fim_do_bloco = max(fim_do_bloco, fim)
    return blocos


def titulo_e_palestrante(nome_sessao: str, artigos: list[tuple]) -> tuple[str, str | None]:
    """O que aparece no totem.

    Sessão de artigos (têm ID): o nome da sessão, ex.: "Speech and Audio Processing".
    Palestra, minicurso, keynote (sem ID): junta o título, ex.: "Keynote: The Design of Physical Intelligence".
    """
    titulos = list(dict.fromkeys(artigo[2] for artigo in artigos if artigo[2]))  # sem repetir
    palestra = titulos and not any(artigo[5] for artigo in artigos)
    if palestra and nome_sessao and len(titulos) == 1:
        artigo = next(a for a in artigos if a[2] == titulos[0])
        return f"{nome_sessao}: {titulos[0]}", artigo[3] or artigo[4] or None
    if not nome_sessao and titulos:
        # Sem nome de sessão: os títulos (às vezes a mesma palestra vem em duas linhas,
        # uma com o nome de quem fala e outra com o tema)
        palestrante = next((a[3] for a in artigos if a[3]), None)
        return " · ".join(titulos), palestrante
    chair = next((a[4] for a in artigos if a[4]), None)  # quem coordena a sessão
    return nome_sessao or "Session", chair


def atualizar(conn) -> dict:
    """Baixa a planilha e troca a programação guardada no banco pela nova."""
    # astimezone(): inclui o fuso no texto, para o navegador converter a hora certa.
    ultima_leitura["horario"] = datetime.now().astimezone().isoformat(timespec="seconds")
    try:
        textos, origem = baixar_planilha()
    except Exception as erro:  # sem internet, link errado, arquivo sumiu...
        ultima_leitura["falha"] = f"Não foi possível ler a planilha: {erro}"
        return ultima_leitura

    ambientes = [dict(a) for a in conn.execute("SELECT codigo, nome FROM ambientes")]
    sessoes, erros = [], []
    abas_vazias = []
    for numero_aba, texto in enumerate(textos, start=1):
        sessoes_aba, erros_aba = interpretar(texto, ambientes)
        sessoes += sessoes_aba
        if not sessoes_aba:
            abas_vazias.append(numero_aba)
        for erro in erros_aba:
            if len(textos) > 1:
                erro["aba"] = numero_aba  # na ordem dos links do URL_PROGRAMACAO
            erros.append(erro)
    ultima_leitura.update(origem=origem, erros=erros, falha=None)

    # Planilha vazia ou toda errada: melhor manter a programação antiga do que apagar tudo.
    if not sessoes:
        ultima_leitura["falha"] = "Nenhuma linha válida na planilha. A programação anterior foi mantida."
        return ultima_leitura
    # Uma aba sem nada válido (cabeçalho mexido, aba apagada enquanto alguém edita...) apagaria
    # aquele dia inteiro do totem. Melhor esperar a próxima leitura com a programação antiga.
    if abas_vazias and len(textos) > 1:
        lista = ", ".join(str(numero) for numero in abas_vazias)
        ultima_leitura["falha"] = (f"A aba {lista} não tem nenhuma linha válida. "
                                   "A programação anterior foi mantida.")
        return ultima_leitura

    # Linha estragada numa sala que existe (hora apagada, data errada...): a sessão sumiria e o
    # totem diria "No session now" com a sala cheia. Nessa sala fica a programação anterior até
    # corrigirem a planilha; as outras salas recebem as mudanças normalmente.
    # (Sala com nome que não existe não entra aqui: não dá para saber de qual sala era a linha.)
    nomes = {ambiente["codigo"]: ambiente["nome"] for ambiente in ambientes}
    mantidas = []
    for codigo in sorted({erro["sala"] for erro in erros if erro.get("sala")}):
        anteriores = conn.execute(
            "SELECT ambiente_codigo, titulo, palestrante, inicio, fim FROM sessoes WHERE ambiente_codigo = ?",
            (codigo,),
        ).fetchall()
        if anteriores:  # sem programação anterior (ex.: primeira leitura), fica o que deu para ler
            sessoes = [sessao for sessao in sessoes if sessao[0] != codigo] + [tuple(s) for s in anteriores]
            mantidas.append(nomes.get(codigo, codigo))
    if mantidas:
        ultima_leitura["falha"] = (f"Há linhas com erro em: {', '.join(mantidas)} (veja abaixo). Nessas salas o "
                                   "totem continua com a programação anterior até a planilha ser corrigida.")

    # Apaga e grava na mesma transação: quem consulta o site vê a programação
    # antiga ou a nova, nunca uma mistura das duas.
    conn.execute("DELETE FROM sessoes")
    conn.executemany(
        "INSERT INTO sessoes (ambiente_codigo, titulo, palestrante, inicio, fim) VALUES (?, ?, ?, ?, ?)",
        sessoes,
    )
    return ultima_leitura


def agora_e_depois(conn, agora: datetime) -> dict:
    """Para cada ambiente: a sessão que está acontecendo e a próxima.

    Devolve {"A1": {"agora": {...} ou None, "depois": {...} ou None}, ...}
    """
    agora_texto = agora.strftime("%Y-%m-%dT%H:%M")
    resultado = {}

    acontecendo = conn.execute(
        """SELECT ambiente_codigo, titulo, palestrante, inicio, fim FROM sessoes
           WHERE inicio <= ? AND fim > ? ORDER BY inicio""",
        (agora_texto, agora_texto),
    ).fetchall()
    for sessao in acontecendo:  # se duas se sobrepõem, fica a que começou por último
        resultado.setdefault(sessao["ambiente_codigo"], {})["agora"] = dict(sessao)

    # No SQLite, junto com MIN(inicio) as outras colunas vêm da mesma linha do mínimo:
    # ou seja, a próxima sessão de cada ambiente.
    proximas = conn.execute(
        """SELECT ambiente_codigo, titulo, palestrante, MIN(inicio) AS inicio, fim FROM sessoes
           WHERE inicio > ? GROUP BY ambiente_codigo""",
        (agora_texto,),
    ).fetchall()
    for sessao in proximas:
        proxima = dict(sessao)
        proxima["hoje"] = proxima["inicio"][:10] == agora_texto[:10]
        resultado.setdefault(sessao["ambiente_codigo"], {})["depois"] = proxima

    return resultado
