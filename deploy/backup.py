"""Copia o banco para a pasta backups/ e apaga as cópias mais antigas.

Roda a cada hora pelo cron (ver INSTALACAO.md). Para rodar na mão:
    cd /opt/bracis && .venv/bin/python deploy/backup.py
"""

import sqlite3
from datetime import datetime
from pathlib import Path

PASTA_PROJETO = Path(__file__).resolve().parent.parent
BANCO = PASTA_PROJETO / "bracis.db"
PASTA_BACKUPS = PASTA_PROJETO / "backups"
MANTER = 72  # uma por hora: 3 dias de cópias

PASTA_BACKUPS.mkdir(exist_ok=True)
destino = PASTA_BACKUPS / f"bracis-{datetime.now():%Y-%m-%d_%H-%M}.db"

# backup() copia o banco com segurança mesmo com o site gravando nele ao mesmo tempo
# (copiar o arquivo com cp poderia pegar uma gravação pela metade).
origem = sqlite3.connect(BANCO)
copia = sqlite3.connect(destino)
origem.backup(copia)
copia.close()
origem.close()

# Os nomes têm data e hora, então em ordem alfabética as mais antigas vêm primeiro.
copias = sorted(PASTA_BACKUPS.glob("bracis-*.db"))
for antiga in copias[:-MANTER]:
    antiga.unlink()

print(f"Backup salvo em {destino}")
