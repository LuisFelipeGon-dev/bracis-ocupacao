import asyncio
import csv
import hmac
import io
import os
import secrets
import sqlite3
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Literal

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

import database
import programacao
import relatorio

load_dotenv()  # lê as configurações do arquivo .env, se existir

# Cuiabá fica em UTC−4 o ano todo (não tem horário de verão).
FUSO_CUIABA = timezone(timedelta(hours=-4))

# Senha do painel da coordenação. Sem ela no .env, o painel fica desligado.
SENHA_COORDENACAO = os.getenv("SENHA_COORDENACAO")

# De quanto em quanto tempo o site relê a planilha da programação.
INTERVALO_PROGRAMACAO = timedelta(minutes=10)


def atualizar_programacao() -> dict:
    with database.conectar() as conn:
        return programacao.atualizar(conn)


async def reler_programacao_sempre():
    while True:
        # to_thread: baixar a planilha pode demorar alguns segundos; rodando à parte,
        # o site continua respondendo aos outros pedidos enquanto isso.
        await asyncio.to_thread(atualizar_programacao)
        await asyncio.sleep(INTERVALO_PROGRAMACAO.total_seconds())


@asynccontextmanager
async def ciclo_de_vida(app):
    """O que roda quando o site liga (antes do yield) e quando desliga (depois)."""
    tarefa = asyncio.create_task(reler_programacao_sempre())
    yield
    tarefa.cancel()


app = FastAPI(title="BRACIS 2026 - Salas", lifespan=ciclo_de_vida)

# Guarda quem está logado num cookie assinado com uma chave secreta:
# se alguém alterar o cookie, a assinatura não bate e o site recusa.
# Sem CHAVE_SESSAO no .env, uma chave aleatória é criada a cada vez que o site liga
# (aí todos precisam logar de novo quando o site reinicia).
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("CHAVE_SESSAO") or secrets.token_hex(32),
    max_age=12 * 60 * 60,  # o login vale 12 horas
    # Com HTTPS no ar, o cookie só viaja criptografado (ninguém no Wi-Fi consegue copiá-lo).
    https_only=os.getenv("COOKIE_SO_HTTPS") == "sim",
)

# O site inteiro fica debaixo deste prefixo: bracis.ic.ufmt.br/live (combinado com o IC).
# Se mudar, troque aqui, no <base href> dos HTML e no nginx-bracis.conf.
PREFIXO = "/live"

# Todas as rotas abaixo são registradas neste roteador; no fim do arquivo ele é
# encaixado no site com o PREFIXO na frente (ex.: "/ambientes" vira "/live/ambientes").
rotas = APIRouter()

# Arquivos da pasta static/ (HTML, CSS, JS) ficam disponíveis em /live/static/...
app.mount(PREFIXO + "/static", StaticFiles(directory="static"), name="static")

# Cria as tabelas e os dados de exemplo na primeira vez que o site liga.
database.criar_banco(os.getenv("CRIAR_VOLUNTARIOS_EXEMPLO") == "sim")


# Formatos esperados nos pedidos. O FastAPI recusa sozinho o que vier fora disso.
class DadosLogin(BaseModel):
    email: str
    pin: str


class NovoEvento(BaseModel):
    ambiente_codigo: str
    tipo: Literal["entrada", "saida"]
    quantidade: int = Field(default=1, ge=1, le=500)


class PedidoDesfazer(BaseModel):
    ambiente_codigo: str
    evento_id: int  # o registro que o voluntário viu na confirmação e aceitou desfazer


class LoginCoordenacao(BaseModel):
    senha: str


class NovoVoluntario(BaseModel):
    nome: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=200)


class ImportarVoluntarios(BaseModel):
    texto: str = Field(max_length=100_000)


class MudarAtivo(BaseModel):
    ativo: bool


def pessoas(n: int) -> str:
    """ "1 pessoa" / "3 pessoas" """
    return "1 pessoa" if n == 1 else f"{n} pessoas"


# ---------- Bloqueio depois de muitas tentativas erradas (login dos voluntários) ----------
# Guardado na memória do servidor (some quando ele reinicia, e tudo bem).
# Funciona porque o site roda com 1 processo só; com vários, cada um teria sua lista.
#
# O bloqueio vale para o par (e-mail, IP): a ideia é bloquear só quem errou.
# Hoje o proxy do IC não informa o IP do visitante (todos chegam como 10.4.0.74), então,
# na prática, vale para o e-mail. Se alguém travar um voluntário de propósito,
# a coordenação gera um "Novo PIN", que destrava na hora.
# (A coordenação não usa este bloqueio: veja login_coordenacao.)

TENTATIVAS_MAXIMAS = 5
TEMPO_BLOQUEIO = timedelta(minutes=5)
falhas_login = {}  # (e-mail, IP) -> (quantidade de erros, bloqueado até)


def ip_de(request: Request) -> str:
    """IP de quem fez o pedido. Atrás do Nginx e do proxy do IC, o uvicorn só enxerga
    o IP real se confiar neles (--forwarded-allow-ips no deploy/bracis.service)."""
    return request.client.host if request.client else "desconhecido"


def conferir_bloqueio(chave: tuple):
    _, bloqueado_ate = falhas_login.get(chave, (0, None))
    if bloqueado_ate and datetime.now() < bloqueado_ate:
        raise HTTPException(
            status_code=429,
            detail="Muitas tentativas erradas. Espere 5 minutos e tente de novo.",
        )


def registrar_falha(chave: tuple):
    quantidade, bloqueado_ate = falhas_login.get(chave, (0, None))
    if bloqueado_ate:  # o bloqueio anterior já acabou: recomeça a contar
        quantidade = 0
    quantidade += 1
    bloqueio = datetime.now() + TEMPO_BLOQUEIO if quantidade >= TENTATIVAS_MAXIMAS else None
    falhas_login[chave] = (quantidade, bloqueio)


def limpar_falhas(chave: tuple):
    falhas_login.pop(chave, None)


def liberar_todos_os_ips(quem: str):
    """Tira o bloqueio de um e-mail em qualquer IP (usado quando a coordenação gera um PIN novo)."""
    for chave in [c for c in falhas_login if c[0] == quem]:
        del falhas_login[chave]


# ---------- Quem está logado ----------

def exigir_login(request: Request) -> int:
    """Devolve o id do voluntário logado, ou recusa o pedido se ninguém estiver logado."""
    voluntario_id = request.session.get("voluntario_id")
    if voluntario_id is None:
        raise HTTPException(status_code=401, detail="Faça login para continuar.")
    # Confere se a coordenação não desativou a conta depois do login.
    with database.conectar() as conn:
        voluntario = conn.execute(
            "SELECT ativo FROM voluntarios WHERE id = ?", (voluntario_id,)
        ).fetchone()
    if voluntario is None or not voluntario["ativo"]:
        request.session.pop("voluntario_id", None)
        raise HTTPException(status_code=401, detail="Sua conta foi desativada.")
    return voluntario_id


def exigir_coordenacao(request: Request):
    if not request.session.get("coordenacao"):
        raise HTTPException(status_code=401, detail="Faça login para continuar.")


# ---------- Páginas ----------
# include_in_schema=False: páginas não aparecem no /docs, que é só para a API.

@rotas.get("/", include_in_schema=False)
def pagina_participante():
    return FileResponse("static/index.html")


@rotas.get("/voluntario", include_in_schema=False)
def pagina_voluntario():
    return FileResponse("static/voluntario.html")


@rotas.get("/sala/{codigo}", include_in_schema=False)
def pagina_sala(codigo: str):
    # A página é a mesma para todas as salas; o sala.js lê o código no endereço.
    return FileResponse("static/sala.html")


@rotas.get("/programacao", include_in_schema=False)
def pagina_programacao():
    return FileResponse("static/programacao.html")


@rotas.get("/coordenacao", include_in_schema=False)
def pagina_coordenacao():
    return FileResponse("static/coordenacao.html")


# ---------- Login dos voluntários ----------

@rotas.post("/login")
def login(dados: DadosLogin, request: Request):
    email = dados.email.strip().lower()
    chave = (email, ip_de(request))
    conferir_bloqueio(chave)
    with database.conectar() as conn:
        voluntario = conn.execute(
            "SELECT * FROM voluntarios WHERE email = ?", (email,)
        ).fetchone()
    # Mesma mensagem para e-mail ou PIN errado, para não revelar quais e-mails existem.
    if voluntario is None or not database.verificar_pin(dados.pin, voluntario["pin_hash"]):
        registrar_falha(chave)
        raise HTTPException(status_code=401, detail="E-mail ou PIN incorreto.")
    limpar_falhas(chave)
    if not voluntario["ativo"]:
        raise HTTPException(status_code=403, detail="Sua conta foi desativada.")
    request.session["voluntario_id"] = voluntario["id"]
    return {"id": voluntario["id"], "nome": voluntario["nome"]}


@rotas.post("/logout")
def logout(request: Request):
    request.session.pop("voluntario_id", None)
    return {"mensagem": "Até logo!"}


@rotas.get("/eu")
def voluntario_atual(request: Request):
    voluntario_id = exigir_login(request)
    with database.conectar() as conn:
        voluntario = conn.execute(
            "SELECT id, nome, email FROM voluntarios WHERE id = ?", (voluntario_id,)
        ).fetchone()
    return dict(voluntario)


# ---------- Ambientes e ocupação (público) ----------

# Memória curta das respostas públicas. A lista das salas soma todas as entradas e saídas do banco;
# no fim do evento (dezenas de milhares de registros) isso leva dezenas de milissegundos, e com
# centenas de celulares pedindo a cada 10 s o servidor não daria conta (medido em 27/09).
# Então cada resposta é calculada no máximo uma vez a cada 2 segundos e entregue igual para todos.
# A tela do voluntário (/ambientes/{codigo}) NÃO usa a memória: ele vê o número exato na hora.
MEMORIA_SEGUNDOS = 2
_memoria = {}  # chave -> (quando foi calculada, resposta)


def da_memoria(chave, calcular):
    """Devolve a resposta guardada se ela tiver menos de 2 s; senão calcula de novo e guarda."""
    agora = time.monotonic()
    guardada = _memoria.get(chave)
    if guardada and agora - guardada[0] < MEMORIA_SEGUNDOS:
        return guardada[1]
    resposta = calcular()
    _memoria[chave] = (agora, resposta)
    return resposta


@rotas.get("/ambientes")
def listar_ambientes():
    return da_memoria("ambientes", calcular_ambientes)


def calcular_ambientes():
    with database.conectar() as conn:
        ambientes = database.listar_ambientes(conn)
        sessoes = programacao.agora_e_depois(conn, datetime.now(FUSO_CUIABA))
    for ambiente in ambientes:
        da_sala = sessoes.get(ambiente["codigo"], {})
        ambiente["agora"] = da_sala.get("agora")
        ambiente["depois"] = da_sala.get("depois")
    return ambientes


@rotas.get("/programacao-dados")
def programacao_publica():
    """Tudo o que a tela "Programação" mostra: as sessões de todas as salas e a ocupação atual
    (para o selo de nível das sessões que estão acontecendo). Só leitura, sem login."""
    return da_memoria("programacao", calcular_programacao)


def calcular_programacao():
    agora = datetime.now(FUSO_CUIABA)
    with database.conectar() as conn:
        return {
            "horario_servidor": agora.strftime("%Y-%m-%dT%H:%M"),
            "ambientes": database.listar_ambientes(conn),
            "sessoes": programacao.todas_as_sessoes(conn),
        }


@rotas.get("/ambientes/{codigo}")
def obter_ambiente(codigo: str):
    with database.conectar() as conn:
        ambiente = database.obter_ambiente(conn, codigo)
    if ambiente is None:
        raise HTTPException(status_code=404, detail="Sala não encontrada.")
    return ambiente


@rotas.get("/ambientes/{codigo}/detalhes")
def detalhes_ambiente(codigo: str):
    """Tudo o que a página de uma sala mostra. Separado de /ambientes/{codigo}
    porque aquela rota é consultada o tempo todo pelo celular do voluntário e deve ser leve."""
    # Sala que não existe dá erro 404 antes de guardar: a memória só tem salas de verdade.
    return da_memoria(("detalhes", codigo), lambda: calcular_detalhes(codigo))


def calcular_detalhes(codigo: str):
    agora = datetime.now(FUSO_CUIABA)
    with database.conectar() as conn:
        ambiente = database.obter_ambiente(conn, codigo)
        if ambiente is None:
            raise HTTPException(status_code=404, detail="Sala não encontrada.")
        sessoes = programacao.agora_e_depois(conn, agora).get(codigo, {})
        return {
            **ambiente,
            "agora": sessoes.get("agora"),
            "depois": sessoes.get("depois"),
            "programacao": programacao.sessoes_do_ambiente(conn, codigo),
            "hoje": database.movimento_do_dia(conn, codigo, agora.strftime("%Y-%m-%d")),
            "horario_servidor": agora.strftime("%Y-%m-%dT%H:%M"),
        }


# ---------- Contagem (voluntários) ----------

@rotas.post("/eventos")
def registrar_evento(evento: NovoEvento, request: Request):
    voluntario_id = exigir_login(request)
    with database.conectar() as conn:
        # Trava o banco para escrita até o fim deste bloco: assim dois registros
        # ao mesmo tempo não conferem a ocupação antiga e passam os dois.
        conn.execute("BEGIN IMMEDIATE")
        ambiente = database.obter_ambiente(conn, evento.ambiente_codigo)
        if ambiente is None:
            raise HTTPException(status_code=404, detail="Sala não encontrada.")
        if evento.tipo == "saida" and evento.quantidade > ambiente["ocupacao"]:
            raise HTTPException(
                status_code=400,
                detail=f"Só há {pessoas(ambiente['ocupacao'])} na sala.",
            )
        conn.execute(
            """INSERT INTO eventos (ambiente_codigo, tipo, quantidade, horario, voluntario_id)
               VALUES (?, ?, ?, ?, ?)""",
            (
                evento.ambiente_codigo,
                evento.tipo,
                evento.quantidade,
                datetime.now(FUSO_CUIABA).isoformat(timespec="seconds"),
                voluntario_id,
            ),
        )
        return database.obter_ambiente(conn, evento.ambiente_codigo)


# Cada voluntário só desfaz os próprios registros: se uma sala tiver duas portas,
# quem está numa não desfaz sem querer o toque de quem está na outra.
SQL_ULTIMO_DO_VOLUNTARIO = """
    SELECT id, tipo, quantidade, horario FROM eventos
    WHERE ambiente_codigo = ? AND voluntario_id = ? AND desfeito = 0
    ORDER BY id DESC LIMIT 1
"""


@rotas.get("/eventos/ultimo")
def ultimo_registro(ambiente_codigo: str, request: Request):
    """O último registro deste voluntário nesta sala (para a pergunta do "Desfazer")."""
    voluntario_id = exigir_login(request)
    with database.conectar() as conn:
        ultimo = conn.execute(SQL_ULTIMO_DO_VOLUNTARIO, (ambiente_codigo, voluntario_id)).fetchone()
    if ultimo is None:
        raise HTTPException(status_code=404, detail="Você ainda não tem registro para desfazer nesta sala.")
    return dict(ultimo)


@rotas.post("/eventos/desfazer")
def desfazer_ultimo(pedido: PedidoDesfazer, request: Request):
    voluntario_id = exigir_login(request)
    with database.conectar() as conn:
        conn.execute("BEGIN IMMEDIATE")
        ultimo = conn.execute(SQL_ULTIMO_DO_VOLUNTARIO, (pedido.ambiente_codigo, voluntario_id)).fetchone()
        # Confere se ainda é o mesmo registro que apareceu na pergunta.
        if ultimo is None or ultimo["id"] != pedido.evento_id:
            raise HTTPException(
                status_code=409,
                detail="Esse registro já foi desfeito ou mudou. Toque em Desfazer de novo.",
            )
        # Desfazer uma entrada tira gente da sala: não pode ficar negativo.
        ambiente = database.obter_ambiente(conn, pedido.ambiente_codigo)
        if ultimo["tipo"] == "entrada" and ultimo["quantidade"] > ambiente["ocupacao"]:
            raise HTTPException(
                status_code=400,
                detail=f"Não dá para desfazer: só há {pessoas(ambiente['ocupacao'])} na sala agora.",
            )
        conn.execute("UPDATE eventos SET desfeito = 1 WHERE id = ?", (ultimo["id"],))
        return {
            "desfeito": dict(ultimo),
            "ambiente": database.obter_ambiente(conn, pedido.ambiente_codigo),
        }


# ---------- Painel da coordenação ----------

# Sem bloqueio depois de erros: o proxy do IC não informa o IP de quem acessa, então um
# bloqueio valeria para todo mundo, e qualquer pessoa poderia travar o painel errando de propósito.
# Em vez disso, cada senha errada espera 1 segundo, e a senha do .env deve ser longa
# (ex.: 4 palavras aleatórias): assim adivinhar levaria milhares de anos.
ESPERA_SENHA_ERRADA = 1  # segundos

@rotas.post("/coordenacao/login")
async def login_coordenacao(dados: LoginCoordenacao, request: Request):
    if not SENHA_COORDENACAO:
        raise HTTPException(
            status_code=503,
            detail="Painel desligado: defina SENHA_COORDENACAO no arquivo .env.",
        )
    # compare_digest compara sem "vazar" pelo tempo de resposta quantas letras acertou.
    if not hmac.compare_digest(dados.senha.encode(), SENHA_COORDENACAO.encode()):
        # asyncio.sleep espera sem travar o site: os outros pedidos continuam sendo atendidos.
        await asyncio.sleep(ESPERA_SENHA_ERRADA)
        raise HTTPException(status_code=401, detail="Senha incorreta.")
    request.session["coordenacao"] = True
    return {"mensagem": "Bem-vindo(a) ao painel."}


@rotas.post("/coordenacao/logout")
def logout_coordenacao(request: Request):
    request.session.pop("coordenacao", None)
    return {"mensagem": "Até logo!"}


@rotas.get("/coordenacao/eu")
def coordenacao_logada(request: Request):
    exigir_coordenacao(request)
    return {"coordenacao": True}


@rotas.get("/coordenacao/situacao")
def situacao(request: Request):
    exigir_coordenacao(request)
    with database.conectar() as conn:
        return database.situacao_ambientes(conn)


@rotas.get("/coordenacao/voluntarios")
def listar_voluntarios(request: Request):
    exigir_coordenacao(request)
    with database.conectar() as conn:
        linhas = conn.execute(
            "SELECT id, nome, email, ativo FROM voluntarios ORDER BY nome"
        ).fetchall()
    return [dict(linha) for linha in linhas]


def cadastrar_voluntario(conn, nome: str, email: str) -> dict:
    """Cria o voluntário com um PIN sorteado. O PIN só é devolvido aqui, uma única vez."""
    nome = nome.strip()
    email = email.strip().lower()
    if not nome or "@" not in email:
        raise ValueError("nome ou e-mail inválido")
    pin = database.gerar_pin()
    try:
        conn.execute(
            "INSERT INTO voluntarios (nome, email, pin_hash) VALUES (?, ?, ?)",
            (nome, email, database.gerar_hash_pin(pin)),
        )
    except sqlite3.IntegrityError:  # o e-mail é UNIQUE no banco
        raise ValueError("e-mail já cadastrado")
    return {"nome": nome, "email": email, "pin": pin}


@rotas.post("/coordenacao/voluntarios")
def criar_voluntario(dados: NovoVoluntario, request: Request):
    exigir_coordenacao(request)
    with database.conectar() as conn:
        try:
            return cadastrar_voluntario(conn, dados.nome, dados.email)
        except ValueError as erro:
            raise HTTPException(status_code=400, detail=f"Não foi possível: {erro}.")


@rotas.post("/coordenacao/voluntarios/importar")
def importar_voluntarios(dados: ImportarVoluntarios, request: Request):
    """Recebe várias linhas "nome, e-mail" (também aceita ; ou tab) e cadastra todas."""
    exigir_coordenacao(request)
    criados, erros = [], []
    with database.conectar() as conn:
        for numero, linha in enumerate(dados.texto.splitlines(), start=1):
            if not linha.strip():
                continue
            partes = linha.replace(";", ",").replace("\t", ",").split(",")
            if len(partes) < 2:
                erros.append({"linha": numero, "texto": linha, "motivo": "faltou o e-mail"})
                continue
            nome, email = partes[0], partes[1]
            if email.strip().lower() in ("email", "e-mail"):
                continue  # linha de cabeçalho copiada da planilha
            try:
                criados.append(cadastrar_voluntario(conn, nome, email))
            except ValueError as erro:
                erros.append({"linha": numero, "texto": linha, "motivo": str(erro)})
    return {"criados": criados, "erros": erros}


@rotas.post("/coordenacao/voluntarios/{voluntario_id}/novo-pin")
def trocar_pin(voluntario_id: int, request: Request):
    exigir_coordenacao(request)
    pin = database.gerar_pin()
    with database.conectar() as conn:
        cursor = conn.execute(
            "UPDATE voluntarios SET pin_hash = ? WHERE id = ?",
            (database.gerar_hash_pin(pin), voluntario_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Voluntário não encontrado.")
        voluntario = conn.execute(
            "SELECT nome, email FROM voluntarios WHERE id = ?", (voluntario_id,)
        ).fetchone()
    liberar_todos_os_ips(voluntario["email"])  # PIN novo: libera se estava bloqueado
    return {**dict(voluntario), "pin": pin}


@rotas.post("/coordenacao/voluntarios/{voluntario_id}/ativo")
def mudar_ativo(voluntario_id: int, dados: MudarAtivo, request: Request):
    exigir_coordenacao(request)
    with database.conectar() as conn:
        cursor = conn.execute(
            "UPDATE voluntarios SET ativo = ? WHERE id = ?", (int(dados.ativo), voluntario_id)
        )
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Voluntário não encontrado.")
    return {"id": voluntario_id, "ativo": dados.ativo}


@rotas.get("/coordenacao/programacao")
def ver_programacao(request: Request):
    """Situação da última leitura da planilha e todas as sessões guardadas."""
    exigir_coordenacao(request)
    with database.conectar() as conn:
        sessoes = conn.execute("""
            SELECT a.nome AS ambiente, s.titulo, s.palestrante, s.inicio, s.fim
            FROM sessoes s JOIN ambientes a ON a.codigo = s.ambiente_codigo
            ORDER BY s.inicio, a.codigo
        """).fetchall()
    return {**programacao.ultima_leitura, "sessoes": [dict(s) for s in sessoes]}


@rotas.post("/coordenacao/programacao/atualizar")
def atualizar_programacao_agora(request: Request):
    exigir_coordenacao(request)
    atualizar_programacao()
    return ver_programacao(request)


def resposta_csv(nome_arquivo: str, cabecalho: list, linhas: list) -> Response:
    """Monta um arquivo CSV para baixar e abrir no Excel."""
    saida = io.StringIO()
    # O Excel em português espera ";" como separador.
    escritor = csv.writer(saida, delimiter=";")
    escritor.writerow(cabecalho)
    escritor.writerows(linhas)
    # "﻿" no começo avisa o Excel que o arquivo é UTF-8 (senão os acentos quebram).
    return Response(
        content="﻿" + saida.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )


@rotas.get("/coordenacao/eventos.csv")
def exportar_eventos(request: Request):
    """Todo o histórico de entradas e saídas, para abrir no Excel."""
    exigir_coordenacao(request)
    with database.conectar() as conn:
        linhas = conn.execute("""
            SELECT e.id, a.nome AS ambiente, e.tipo, e.quantidade, e.horario,
                   v.nome AS voluntario, e.desfeito
            FROM eventos e
            JOIN ambientes a ON a.codigo = e.ambiente_codigo
            JOIN voluntarios v ON v.id = e.voluntario_id
            ORDER BY e.id
        """).fetchall()
    return resposta_csv(
        "eventos-bracis.csv",
        ["id", "ambiente", "tipo", "quantidade", "horario", "voluntario", "desfeito"],
        [[*linha[:6], "sim" if linha["desfeito"] else "não"] for linha in linhas],
    )


# ---------- Relatório por sessão ----------

@rotas.get("/coordenacao/relatorio")
def ver_relatorio(request: Request):
    exigir_coordenacao(request)
    with database.conectar() as conn:
        return relatorio.gerar(conn, datetime.now(FUSO_CUIABA))


@rotas.get("/coordenacao/relatorio.csv")
def exportar_relatorio(request: Request):
    exigir_coordenacao(request)
    with database.conectar() as conn:
        dados = relatorio.gerar(conn, datetime.now(FUSO_CUIABA))
    linhas = [
        [s["inicio"][:10], s["inicio"][11:16], s["fim"][11:16], s["ambiente"], s["titulo"],
         s["palestrante"] or "", s["entradas"], s["saidas"], "" if s["pico"] is None else s["pico"],
         s["capacidade"]]
        for s in dados["sessoes"]
    ]
    for fora in dados["fora_da_programacao"]:
        linhas.append(["", "", "", fora["ambiente"], "(fora da programação)", "",
                       fora["entradas"], fora["saidas"], "", ""])
    return resposta_csv(
        "relatorio-sessoes-bracis.csv",
        ["dia", "inicio", "fim", "ambiente", "sessao", "palestrante",
         "entradas", "saidas", "pico_de_publico", "capacidade"],
        linhas,
    )


# ---------- Encaixe no endereço /live ----------

app.include_router(rotas, prefix=PREFIXO)


# Quem digitar o endereço sem o /live (ou sem a barra final) cai na página inicial.
@app.get("/", include_in_schema=False)
@app.get(PREFIXO, include_in_schema=False)
def ir_para_inicio():
    return RedirectResponse(PREFIXO + "/")
