# Migração da instalação antiga (Windows, Docker, SQLite) para a nova (Postgres + backend NestJS + visao)

Servidor: Windows, Docker Desktop, pasta do projeto em `C:\Users\supor\aplicacoes\gdel-vigia`. A instalação
antiga sobe hoje com `docker-compose.prod.yml` (versão anterior, imagem única `gdel-vigia:prod`, projeto
Compose `gdel-vigia-prod`), containers `vigia-backend-prod` (painel Python antigo), `vigia-roteador-prod`
(MediaMTX) e `vigia-roteador-config-prod` (gera a config do roteador, já encerrado).

Tudo neste guia roda só via terminal (`cmd.exe`), sem precisar abrir o Docker Desktop nem mudar nenhuma
configuração dele. O `docker-compose.prod.yml` novo não usa bind mount de pasta do Windows em nenhum
serviço — `vigia.yml`, `roteador.yml` e `roteador\.env` são copiados **para dentro da imagem** no build
(`docker compose build`), em vez de montados em runtime. Para mudar qualquer um desses arquivos depois,
edite o arquivo local e rode `docker compose build` de novo (reconstrói a imagem com o conteúdo
atualizado) — não precisa editar nada no Docker Desktop.

**Atenção de segurança:** como `roteador\.env` (senhas das câmeras) passa a fazer parte da imagem
`vigia-visao-prod-novo`, qualquer pessoa com acesso a essa imagem (via `docker save`, inspecionar camadas,
etc.) consegue ler essas senhas. Isso é uma troca deliberada para evitar bind mount neste servidor. Se
isso for um problema para vocês, me avise e revertemos para bind mount — mas aí a configuração do File
Sharing do Docker Desktop volta a ser necessária.

**Nenhum passo até a seção "Cortar para a nova versão" altera ou apaga nada da instalação antiga.** Os
comandos só *leem* o SQLite e copiam arquivos de evidência/gravação para fora. Em qualquer momento antes
do corte, a instalação antiga continua rodando exatamente como está.

Rode estes comandos no `cmd.exe`, dentro de `C:\Users\supor\aplicacoes\gdel-vigia`, a menos que indicado o
contrário. **Evite usar `^` para quebrar comando em várias linhas** — nos testes neste servidor isso
engoliu o comando sem erro. Cole cada comando como uma linha só.

## 0. Backup fresco, direto do volume em uso

O `vigia.db` do volume `gdel-vigia-prod_dados` tem arquivos `-shm`/`-wal` junto, ou seja, o painel antigo
está escrevendo nele agora. Tire um backup novo e consistente, com a aplicação **rodando** (não precisa
parar nada neste passo), usando o container que já está de pé (`vigia-backend-prod`):

```bat
docker exec vigia-backend-prod python -c "import sqlite3; origem=sqlite3.connect('/app/dados/vigia.db'); destino=sqlite3.connect('/tmp/vigia-backup.db'); origem.backup(destino); destino.close(); origem.close()"
```

Copie o arquivo gerado para fora do container, para a pasta do projeto:

```bat
docker cp vigia-backend-prod:/tmp/vigia-backup.db "%cd%\vigia-backup.db"
```

Confirme que o arquivo chegou e tem dados reais:

```bat
docker cp "%cd%\vigia-backup.db" vigia-backend-prod:/tmp/verificar.db
docker exec vigia-backend-prod python -c "import sqlite3; c=sqlite3.connect('/tmp/verificar.db'); print('usuarios', c.execute('select count(*) from usuarios').fetchone()); print('ocorrencias', c.execute('select count(*) from ocorrencias').fetchone()); print('visitas', c.execute('select count(*) from visitas').fetchone())"
```

Os números devem ser maiores que zero e fazer sentido com o que você sabe que existe hoje.

Agora empacote as evidências (fotos e clipes) direto de dentro do container, em um `.tar`, e copie para
fora:

```bat
docker exec vigia-backend-prod sh -c "tar czf /tmp/evidencias.tgz -C /app/dados evidencias"
docker cp vigia-backend-prod:/tmp/evidencias.tgz "%cd%\evidencias-backup.tgz"
```

E as gravações do roteador (container `vigia-roteador-prod`, outro volume):

```bat
docker exec vigia-roteador-prod sh -c "tar czf /tmp/gravacoes.tgz -C / gravacoes"
docker cp vigia-roteador-prod:/tmp/gravacoes.tgz "%cd%\gravacoes-backup.tgz"
```

Ao final deste passo, a pasta do projeto antigo tem: `vigia-backup.db`, `evidencias-backup.tgz`,
`gravacoes-backup.tgz`. Isso é independente do backup manual que você já tinha em
`C:\Users\supor\...\backup\vigia-2026-11-25.db` — pode manter os dois.

## 1. Levar o código novo para o servidor

Traga a pasta do projeto atualizada (a organizada: `backend\` NestJS + `visao\` + `frontend\`) para o
servidor, por exemplo copiando a pasta inteira por fora do Docker (rede, USB, etc.) para um diretório
novo, como `C:\Users\supor\aplicacoes\gdel-vigia-novo`, **sem apagar**
`C:\Users\supor\aplicacoes\gdel-vigia` (a instalação antiga continua ali). Isso não usa Docker, é só cópia
de arquivo no Windows.

Dentro da pasta nova, confirme que existem `backend\`, `visao\`, `frontend\`, `roteador\`,
`docker-compose.prod.yml`, `config-prod.env.exemplo`. A partir de agora, todos os comandos rodam dentro
dessa pasta nova.

Copie os três arquivos de backup do passo 0 para dentro dela também:

```bat
copy ..\gdel-vigia\vigia-backup.db .
copy ..\gdel-vigia\evidencias-backup.tgz .
copy ..\gdel-vigia\gravacoes-backup.tgz .
```

## 2. Preencher as variáveis e os arquivos de configuração

```bat
copy config-prod.env.exemplo config-prod.env
```

Edite `config-prod.env` (notepad ou editor de texto) e preencha `POSTGRES_PASSWORD` (gere uma senha
forte), `VIGIA_IP_PUBLICO`, `VIGIA_HOSTS_PUBLICOS` (mesmos valores que já estavam em `config\.env` da
instalação antiga) e `VIGIA_COOKIE_SEGURO=true`.

Copie o `.env` do `visao` com as credenciais que já existiam (TouchPay, `OPENAI_API_KEY`):

```bat
copy ..\gdel-vigia\config\.env visao\.env
```

Abra `visao\.env` e confirme que não ficou nenhuma linha `DATABASE_URL=` apontando para arquivo — se
houver, apague essa linha (o `docker-compose.prod.yml` novo já injeta a `DATABASE_URL` do Postgres
automaticamente nos serviços `backend` e `visao`).

Confirme que `roteador\roteador.yml` e `roteador\.env` existem e têm os dados reais das câmeras (mesmo
conteúdo que já estava na instalação antiga). Esses dois arquivos entram na imagem no próximo passo — se
precisar trocar a senha de alguma câmera depois, edite o arquivo aqui e rode `docker compose build` de
novo.

## 3. Subir só o Postgres novo

Isso não toca nos containers antigos — é um projeto Compose diferente (`gdel-vigia-prod` é o antigo; o
novo se chama `gdel-vigia-prod-novo`, definido no topo do `docker-compose.prod.yml`, sem colisão de nomes
de container nem de volume).

```bat
docker compose -f docker-compose.prod.yml --env-file config-prod.env up -d postgres
docker compose -f docker-compose.prod.yml --env-file config-prod.env logs postgres
```

Espere o log mostrar `database system is ready to accept connections`.

## 4. Aplicar o schema do Postgres (Prisma)

Cria as tabelas vazias; não copia nada ainda. Esse comando builda a imagem do `backend` na primeira vez
(leva alguns minutos):

```bat
docker compose -f docker-compose.prod.yml --env-file config-prod.env run --rm backend npx prisma migrate deploy
```

## 5. Migrar os dados do SQLite para o Postgres

Suba um container temporário baseado na imagem do `visao` (builda na primeira vez — leva alguns minutos
por causa do PyTorch), parado à espera de comandos, sem bind mount nenhum:

```bat
docker compose -f docker-compose.prod.yml --env-file config-prod.env run -d --name vigia-migracao-temp --entrypoint sleep visao 300
```

Copie o backup do SQLite para dentro desse container:

```bat
docker cp vigia-backup.db vigia-migracao-temp:/tmp/vigia-antigo.db
```

Simule a migração primeiro (não grava nada no Postgres):

```bat
docker exec vigia-migracao-temp python -m vigia migrar-dados /tmp/vigia-antigo.db --simular
```

Revise a saída: cada tabela deve aparecer com a mesma contagem dos dois lados (`origem -> destino (ok)`).
Se alguma tabela aparecer diferente, pare aqui e investigue antes de continuar.

Migre de verdade, só depois de revisar a simulação com calma:

```bat
docker exec vigia-migracao-temp python -m vigia migrar-dados /tmp/vigia-antigo.db
```

Recusa migrar se o Postgres já tiver dados em qualquer tabela (a menos que você passe `--substituir`, que
apaga e copia de novo — só use se tiver certeza).

Encerre o container temporário:

```bat
docker stop vigia-migracao-temp
docker rm vigia-migracao-temp
```

## 6. Conferir os dados migrados

```bat
docker compose -f docker-compose.prod.yml --env-file config-prod.env exec postgres psql -U vigia -d vigia -c "select count(*) from usuarios; select count(*) from ocorrencias; select count(*) from visitas;"
```

Compare com os números que você já confirmou no passo 0. Devem bater.

## 7. Copiar as evidências e gravações para os volumes novos

Os caminhos salvos no banco (`ocorrencias.evidencias`, `ocorrencias.clipes`) são relativos — por exemplo
`"itacolomi/itacolomi-....jpg"` e `"clipes/ocorrencia1_itacolomi.mp4"` — e continuam valendo desde que os
arquivos fiquem na mesma estrutura dentro de `dados/evidencias/` e `gravacoes/` do projeto novo.

Primeiro, crie os volumes vazios (nomes definidos no `docker-compose.prod.yml`, prefixados pelo nome do
projeto `gdel-vigia-prod-novo`):

```bat
docker volume create gdel-vigia-prod-novo_dados
docker volume create gdel-vigia-prod-novo_gravacoes
```

Suba um container temporário com esses volumes montados (sem bind mount de pasta do Windows — o volume
é do Docker, isso é diferente e não trava) e copie os `.tgz` do passo 0 para dentro:

Use a imagem `gdel-vigia:prod`, que já está em cache local neste servidor (evita o erro de credenciais do
Docker Hub que apareceu nos testes deste guia ao tentar baixar `python:3.12-slim`):

```bat
docker run -d --name vigia-copia-evidencias --entrypoint sleep -v gdel-vigia-prod-novo_dados:/destino gdel-vigia:prod 300
docker cp evidencias-backup.tgz vigia-copia-evidencias:/tmp/evidencias.tgz
docker exec vigia-copia-evidencias sh -c "mkdir -p /destino/evidencias && tar xzf /tmp/evidencias.tgz -C /destino/evidencias --strip-components=1"
docker stop vigia-copia-evidencias
docker rm vigia-copia-evidencias
```

```bat
docker run -d --name vigia-copia-gravacoes --entrypoint sleep -v gdel-vigia-prod-novo_gravacoes:/destino gdel-vigia:prod 300
docker cp gravacoes-backup.tgz vigia-copia-gravacoes:/tmp/gravacoes.tgz
docker exec vigia-copia-gravacoes sh -c "tar xzf /tmp/gravacoes.tgz -C /destino --strip-components=1"
docker stop vigia-copia-gravacoes
docker rm vigia-copia-gravacoes
```

Confirme o resultado:

```bat
docker run --rm -v gdel-vigia-prod-novo_dados:/d gdel-vigia:prod sh -c "ls /d/evidencias"
docker run --rm -v gdel-vigia-prod-novo_gravacoes:/d gdel-vigia:prod sh -c "ls /d"
```

Se você também tirou um backup manual mais antigo organizado por ocorrência (como
`vigia_ocorrencias_20261124\ocorrenciaN\evidencias\...`), ele tem uma camada extra de pasta por ocorrência
que precisa ser "desembrulhada" antes de copiar — mas como o passo 0 já pegou o estado mais recente do
volume em uso agora, isso só é necessário se o backup manual tiver evidências mais antigas que **não**
estão mais no volume atual (por exemplo, se algo já foi limpo por retenção).

## 8. Validar a nova versão antes do corte (ainda sem desligar a antiga)

Suba a visão e o backend novos, mas em portas e rede diferentes das reais, para não colidir com a
instalação antiga que ainda está rodando em 8790/1945/8289/8290 e na rede `172.30.57.0/24`. Edite
`config-prod.env` só para este teste, acrescentando:

```
VIGIA_PORTA_PAINEL=18790
VIGIA_PORTA_RTMP=11945
VIGIA_PORTA_WEBRTC_UDP=18289
VIGIA_PORTA_WEBRTC_TCP=18290
VIGIA_REDE=172.31.57.0/24
VIGIA_IP_VISAO=172.31.57.10
```

```bat
docker compose -f docker-compose.prod.yml --env-file config-prod.env up -d --build
docker compose -f docker-compose.prod.yml --env-file config-prod.env logs backend visao
```

Abra `http://IP_DO_SERVIDOR:18790` no navegador, faça login com um usuário migrado (mesma senha de antes:
o hash scrypt é compatível), confira ocorrências antigas abrindo com fotos e vídeo, confira câmeras ao
vivo. Resolvido, derrube de novo sem apagar volumes:

```bat
docker compose -f docker-compose.prod.yml --env-file config-prod.env down
```

## 9. Cortar para a nova versão

Primeiro, remova de `config-prod.env` as 6 linhas do passo 8 (`VIGIA_PORTA_PAINEL`, `VIGIA_PORTA_RTMP`,
`VIGIA_PORTA_WEBRTC_UDP`, `VIGIA_PORTA_WEBRTC_TCP`, `VIGIA_REDE`, `VIGIA_IP_VISAO`) — eram só para o teste
lado a lado. Sem elas, o compose volta a usar os padrões reais (8790, 1945, 8289, 8290, rede
`172.30.57.0/24`), que só ficam livres depois que a instalação antiga for parada no passo abaixo.

Pare a instalação antiga (ela continua existindo em disco, só os containers saem do ar; os volumes
`gdel-vigia-prod_*` não são tocados):

```bat
docker stop vigia-backend-prod vigia-roteador-prod
```

Confirme que as portas ficaram livres:

```bat
docker ps
```

Suba a nova, agora nas portas de produção reais:

```bat
docker compose -f docker-compose.prod.yml --env-file config-prod.env up -d --build
docker compose -f docker-compose.prod.yml --env-file config-prod.env logs backend visao
```

Abra `http://IP_DO_SERVIDOR:8790` (a mesma porta de sempre) e confirme que o painel novo responde, login
funciona, câmeras aparecem ao vivo.

## Rollback

Se algo der errado depois do corte:

```bat
docker compose -f docker-compose.prod.yml --env-file config-prod.env down
docker start vigia-roteador-prod vigia-backend-prod
```

Os volumes `gdel-vigia-prod_dados`, `gdel-vigia-prod_gravacoes`, `gdel-vigia-prod_roteador_config` nunca
foram apagados nem alterados por este guia — a instalação antiga volta a funcionar exatamente como estava,
nas mesmas portas 8790/1945/8289/8290. Os backups do passo 0 (`vigia-backup.db`, `evidencias-backup.tgz`,
`gravacoes-backup.tgz`) são a segunda camada de segurança, caso algo no volume original seja perdido por
qualquer outro motivo.

**Nunca rode `docker compose down -v`** nem em prod nem nos comandos deste guia — isso apagaria os
volumes. Todos os comandos acima usam `down` sem `-v` de propósito.
