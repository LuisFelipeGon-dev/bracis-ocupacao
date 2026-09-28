# Instalação no servidor

Passo a passo para colocar o site no ar num servidor Ubuntu 24.04.
Os comandos rodam **no servidor**, depois de entrar por SSH. Rode um bloco de cada vez
e confira o resultado antes de seguir.

Nos comandos abaixo, troque `USUARIO`, `IP_DO_SERVIDOR` e `PORTA_SSH` pelos dados do seu servidor.

Como o servidor da UFMT funciona:
- O SSH é por uma porta encaminhada para a 22 do servidor (`PORTA_SSH`).
- **Só a porta 443 (HTTPS)** fica aberta para a internet; a porta 80 não é usada.
- O certificado HTTPS vem da equipe de TI do IC (sem a porta 80, o Let's Encrypt
  do jeito comum não funciona). Ver o passo 6.

## 1. Entrar no servidor e trocar a senha

No PowerShell do seu computador:

```bash
ssh -p PORTA_SSH USUARIO@IP_DO_SERVIDOR
```

Já dentro do servidor, troque a senha inicial:

```bash
passwd
```

## 2. Instalar os programas

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-venv git nginx
```

- `python3-venv`: para criar o ambiente virtual, como no seu computador.
- `nginx`: recebe os acessos da internet (HTTPS) e repassa para o site.

## 3. Baixar o código e instalar as bibliotecas

O repositório é público, então o servidor baixa o código sem precisar de senha nem chave:

```bash
sudo mkdir -p /opt/bracis && sudo chown $USER:$USER /opt/bracis
git clone https://github.com/LuisFelipeGon-dev/bracis-ocupacao.git /opt/bracis
cd /opt/bracis
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Troque `USUARIO` na linha `User=` de `deploy/bracis.service` pelo seu usuário no servidor
antes do passo 5.

## 4. Criar o .env do servidor

Gere uma chave aleatória para o login:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Crie o arquivo com o editor `nano`:

```bash
nano /opt/bracis/.env
```

Escreva o conteúdo abaixo, trocando os valores. Para salvar: Ctrl+O, Enter; para sair: Ctrl+X.

```
CHAVE_SESSAO=cole-aqui-a-chave-gerada-acima
SENHA_COORDENACAO=uma-senha-forte-e-diferente-da-de-teste
URL_PROGRAMACAO=cole-aqui-o-link-do-csv-da-planilha
```

**Não** coloque `CRIAR_VOLUNTARIOS_EXEMPLO` no servidor: os voluntários de verdade são
cadastrados pelo painel da coordenação. Deixe `COOKIE_SO_HTTPS` para o final do passo 7
(ligado antes, o login não funciona no teste pelo túnel SSH, que é HTTP).

Proteja o arquivo para só o seu usuário ler:

```bash
chmod 600 /opt/bracis/.env
```

## 5. Ligar o site como serviço

```bash
sudo cp /opt/bracis/deploy/bracis.service /etc/systemd/system/bracis.service
sudo systemctl daemon-reload
sudo systemctl enable --now bracis
systemctl status bracis --no-pager
```

Tem que aparecer `active (running)` em verde. Se aparecer erro, veja o motivo com:

```bash
journalctl -u bracis -n 50 --no-pager
```

### Testar antes do HTTPS existir (túnel SSH)

Enquanto a porta 443 não funciona, dá para ver o site do servidor no seu computador por
dentro da conexão SSH. Saia do servidor (`exit`) e, no PowerShell do seu computador, rode:

```bash
ssh -p PORTA_SSH -L 8000:127.0.0.1:8000 USUARIO@IP_DO_SERVIDOR
```

Deixe essa janela aberta e abra **http://127.0.0.1:8000/live/** no navegador: é o site rodando
no servidor. (Pare o servidor de teste do seu computador antes, senão a porta 8000 já está ocupada.)
Fechando a janela do SSH, o túnel acaba.

## 6. Certificado HTTPS

O `bracis.ic.ufmt.br` aponta para um proxy do IC, que já tem o certificado e repassa os
acessos em HTTPS para a porta 443 deste servidor. A equipe de TI do IC deixa uma cópia do
certificado e da chave no servidor. Copie para o lugar que o Nginx usa (troque os caminhos
de origem pelos arquivos recebidos):

```bash
sudo mkdir -p /etc/ssl/bracis
sudo cp CAMINHO_DO_CERTIFICADO /etc/ssl/bracis/certificado.pem
sudo cp CAMINHO_DA_CHAVE /etc/ssl/bracis/chave.key
sudo chmod 600 /etc/ssl/bracis/chave.key
```

Quando o IC renovar o certificado, copie de novo e rode `sudo systemctl reload nginx`.

A chave privada é secreta: não mande por e-mail aberto nem coloque no GitHub.

## 7. Configurar o Nginx

```bash
sudo cp /opt/bracis/deploy/nginx-bracis.conf /etc/nginx/sites-available/bracis
sudo ln -s /etc/nginx/sites-available/bracis /etc/nginx/sites-enabled/bracis
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

`nginx -t` confere a configuração antes de aplicar: tem que dizer `syntax is ok` e
`test is successful` (se reclamar do certificado, confira os caminhos do passo 6).
O `rm` tira a página padrão do Nginx.

Se o firewall do Ubuntu estiver ligado, libere o HTTPS:

```bash
sudo ufw status
# Só se aparecer "Status: active":
sudo ufw allow 443/tcp
```

Não rode `ufw enable` se ele estiver desligado: sem a regra do SSH, você perderia o acesso.

Quando o IC liberar a 443 e o domínio apontar para o servidor, teste:
**https://bracis.ic.ufmt.br/live/** deve abrir com o cadeado.

Com o cadeado funcionando, ligue o cookie seguro:

```bash
echo "COOKIE_SO_HTTPS=sim" >> /opt/bracis/.env
sudo systemctl restart bracis
```

## 8. Backup automático do banco

Abra a lista de tarefas agendadas do seu usuário:

```bash
crontab -e
```

(Na primeira vez ele pergunta qual editor: escolha `1`, o nano.) Adicione no final:

```
0 * * * * cd /opt/bracis && .venv/bin/python deploy/backup.py >> backups/backup.log 2>&1
```

Isso roda o backup no minuto 0 de toda hora. As cópias ficam em `/opt/bracis/backups/`
(as 72 mais recentes). Para testar na hora: `cd /opt/bracis && .venv/bin/python deploy/backup.py`.

Os backups ficam no mesmo servidor. De vez em quando (e sempre no fim de cada dia do evento),
baixe uma cópia para o seu computador, no PowerShell:

```powershell
scp -P PORTA_SSH "USUARIO@IP_DO_SERVIDOR:/opt/bracis/backups/*.db" .
```

## Depois: atualizar o site

Depois de enviar mudanças para a branch `main` no GitHub:

```bash
bash /opt/bracis/deploy/atualizar.sh
```

## Comandos úteis

| Para quê | Comando |
|---|---|
| Ver se o site está rodando | `systemctl status bracis --no-pager` |
| Ver os últimos erros do site | `journalctl -u bracis -n 50 --no-pager` |
| Acompanhar o log ao vivo (Ctrl+C sai) | `journalctl -u bracis -f` |
| Reiniciar o site | `sudo systemctl restart bracis` |
| Ver erros do Nginx | `sudo tail -n 30 /var/log/nginx/error.log` |
