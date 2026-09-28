#!/bin/bash
# Coloca no ar a versão mais nova do GitHub. Uso, no servidor:
#   bash /opt/bracis/deploy/atualizar.sh
set -e  # se algum comando der erro, para aqui (não reinicia um site quebrado)

cd /opt/bracis
git pull
.venv/bin/pip install -r requirements.txt --quiet
sudo systemctl restart bracis
sleep 2
systemctl status bracis --no-pager --lines 5
