import hashlib
import hmac
import secrets
import sqlite3
from contextlib import contextmanager

ARQUIVO_BANCO = "bracis.db"

# Os 7 ambientes do evento: 5 salas e 2 auditórios (nomes reais, em inglês como no totem).
# O código não muda (as estimativas ficam ligadas a ele); só o nome.
AMBIENTES_EXEMPLO = [
    ("S1", "Room Nobres", "sala"),
    ("S2", "Room Araguaia", "sala"),
    ("S3", "Room Xingu", "sala"),
    ("S4", "Room Vila Bela", "sala"),
    ("S5", "Room Chapada", "sala"),
    ("A1", "Pantanal Auditorium", "auditorio"),
    ("A2", "Cerrado Auditorium", "auditorio"),
]

# Como cada ambiente aparece na coluna "Location" da planilha oficial da programação.
# (Na planilha a sala também pode vir pelo código ou pelo nome de cima.)
NOMES_NA_PLANILHA = {
    "S1": "Room 1",
    "S2": "Room 2",
    "S3": "Room 3",
    "S4": "Room 4",
    "S5": "Room 5",
    "A1": "Arena 1",
    "A2": "Arena 2",
}

VOLUNTARIOS_EXEMPLO = [
    ("Voluntário Exemplo 1", "voluntario1@exemplo.com", "1111"),
    ("Voluntário Exemplo 2", "voluntario2@exemplo.com", "2222"),
    ("Voluntário Exemplo 3", "voluntario3@exemplo.com", "3333"),
]


@contextmanager
def conectar():
    """Abre o banco, salva as alterações no final e sempre fecha a conexão."""
    conn = sqlite3.connect(ARQUIVO_BANCO)
    conn.row_factory = sqlite3.Row  # permite acessar colunas pelo nome: linha["nome"]
    conn.execute("PRAGMA foreign_keys = ON")  # faz o SQLite checar as ligações entre tabelas
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def gerar_hash_pin(pin: str) -> str:
    """Embaralha o PIN para guardar no banco. O PIN original não pode ser recuperado."""
    sal = secrets.token_hex(16)  # valor aleatório para dois PINs iguais não gerarem o mesmo hash
    hash_pin = hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(sal), 200_000)
    return f"{sal}${hash_pin.hex()}"


def verificar_pin(pin: str, pin_hash: str) -> bool:
    """Confere se o PIN digitado gera o mesmo hash que está guardado."""
    sal, hash_guardado = pin_hash.split("$")
    hash_pin = hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(sal), 200_000)
    return hmac.compare_digest(hash_pin.hex(), hash_guardado)


def gerar_pin() -> str:
    """Sorteia um PIN de 6 dígitos (pode começar com zero, ex.: 048213)."""
    return f"{secrets.randbelow(1_000_000):06d}"


def listar_ambientes(conn):
    # Salas primeiro, depois auditórios ("tipo = 'auditorio'" vale 0 para salas e 1 para auditórios).
    linhas = conn.execute(
        "SELECT codigo, nome, tipo FROM ambientes ORDER BY tipo = 'auditorio', codigo"
    ).fetchall()
    return [dict(linha) for linha in linhas]


def obter_ambiente(conn, codigo):
    """Devolve o ambiente, ou None se o código não existir."""
    linha = conn.execute("SELECT codigo, nome, tipo FROM ambientes WHERE codigo = ?", (codigo,)).fetchone()
    return dict(linha) if linha else None


def criar_banco(criar_voluntarios_exemplo: bool):
    """Cria as tabelas (se ainda não existirem) e coloca os dados de exemplo.

    Os voluntários de exemplo têm PINs conhecidos (1111...), então só são
    criados quando pedido: no computador de desenvolvimento, nunca no servidor.
    """
    with conectar() as conn:
        # WAL deixa o site ler o banco enquanto um voluntário está gravando.
        conn.execute("PRAGMA journal_mode = WAL")

        conn.executescript("""
            -- "capacidade" não é mais usada (desde 15/10 o voluntário informa a lotação em %),
            -- mas continua na tabela para não precisar refazer o banco que já está no servidor.
            CREATE TABLE IF NOT EXISTS ambientes (
                codigo     TEXT PRIMARY KEY,
                nome       TEXT NOT NULL,
                tipo       TEXT NOT NULL CHECK (tipo IN ('sala', 'auditorio', 'laboratorio')),
                capacidade INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS voluntarios (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                nome     TEXT NOT NULL,
                email    TEXT NOT NULL UNIQUE,
                pin_hash TEXT NOT NULL,
                ativo    INTEGER NOT NULL DEFAULT 1
            );

            -- Contagem exata de entradas e saídas, usada até 15/10. Não é mais usada,
            -- mas fica no banco com o histórico dos testes.
            CREATE TABLE IF NOT EXISTS eventos (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                ambiente_codigo TEXT NOT NULL REFERENCES ambientes (codigo),
                tipo            TEXT NOT NULL CHECK (tipo IN ('entrada', 'saida')),
                quantidade      INTEGER NOT NULL DEFAULT 1 CHECK (quantidade > 0),
                horario        TEXT NOT NULL,
                voluntario_id   INTEGER NOT NULL REFERENCES voluntarios (id),
                desfeito        INTEGER NOT NULL DEFAULT 0
            );

            -- Cada estimativa que um voluntário informa: "a sala está uns 60% cheia".
            -- porcentagem: 0, 10, 20 ... 100, ou 110 = lotada, com gente em pé.
            -- Guardamos todas (não só a última) para o relatório de cada sessão.
            CREATE TABLE IF NOT EXISTS estimativas (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                ambiente_codigo TEXT NOT NULL REFERENCES ambientes (codigo),
                porcentagem     INTEGER NOT NULL CHECK (porcentagem BETWEEN 0 AND 110),
                horario         TEXT NOT NULL,
                voluntario_id   INTEGER NOT NULL REFERENCES voluntarios (id)
            );

            -- Índice: deixa rápido achar a última estimativa de uma sala.
            CREATE INDEX IF NOT EXISTS idx_estimativas_ambiente
                ON estimativas (ambiente_codigo, id);

            CREATE TABLE IF NOT EXISTS sessoes (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                ambiente_codigo TEXT NOT NULL REFERENCES ambientes (codigo),
                titulo          TEXT NOT NULL,
                palestrante     TEXT,
                inicio          TEXT NOT NULL,
                fim             TEXT NOT NULL
            );
        """)

        # Bancos criados antes da coluna "ativo" existir: acrescenta a coluna.
        # (CREATE TABLE IF NOT EXISTS não mexe numa tabela que já existe.)
        colunas = [c["name"] for c in conn.execute("PRAGMA table_info(voluntarios)")]
        if "ativo" not in colunas:
            conn.execute("ALTER TABLE voluntarios ADD COLUMN ativo INTEGER NOT NULL DEFAULT 1")

        # Se o código já existe, atualiza nome e tipo (assim, trocar a lista acima e reiniciar
        # o site já corrige os dados). "excluded" = a linha que tentamos inserir.
        # As estimativas ficam ligadas ao código, que não muda, então nada se perde.
        conn.executemany(
            """INSERT INTO ambientes (codigo, nome, tipo, capacidade) VALUES (?, ?, ?, 0)
               ON CONFLICT (codigo) DO UPDATE SET
                   nome = excluded.nome,
                   tipo = excluded.tipo""",
            AMBIENTES_EXEMPLO,
        )

        # Salas que saíram da lista: apaga, desde que não tenham nenhum registro
        # (essas ficam, para não perder o histórico; o aviso aparece no log).
        codigos = [a[0] for a in AMBIENTES_EXEMPLO]
        marcadores = ", ".join("?" * len(codigos))
        sobrando = conn.execute(
            f"SELECT codigo FROM ambientes WHERE codigo NOT IN ({marcadores})", codigos
        ).fetchall()
        for (codigo,) in sobrando:
            tem_registros = conn.execute(
                """SELECT 1 FROM eventos WHERE ambiente_codigo = ?
                   UNION ALL SELECT 1 FROM estimativas WHERE ambiente_codigo = ?""",
                (codigo, codigo),
            ).fetchone()
            if tem_registros:
                print(f"Aviso: a sala {codigo} saiu da lista, mas tem registros; ela foi mantida.")
                continue
            conn.execute("DELETE FROM sessoes WHERE ambiente_codigo = ?", (codigo,))
            conn.execute("DELETE FROM ambientes WHERE codigo = ?", (codigo,))
        if not criar_voluntarios_exemplo:
            return
        for nome, email, pin in VOLUNTARIOS_EXEMPLO:
            conn.execute(
                "INSERT OR IGNORE INTO voluntarios (nome, email, pin_hash) VALUES (?, ?, ?)",
                (nome, email, gerar_hash_pin(pin)),
            )
