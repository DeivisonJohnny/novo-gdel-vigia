# GDEL Vigia

Monitoramento de lojas autônomas. É a versão de servidor da POC `poc-get-burglar`. A IA acompanha cada pessoa na câmera, vê quando ela pega um produto e se passa no totem. O pagamento é conferido na TouchPay. Se alguém sai com produto sem pagamento aprovado, abre uma ocorrência com fotos e vídeo. Uma IA generativa (Claude) olha as fotos e o vídeo antes e só depois a ocorrência chega ao operador no painel.

## O que tem no painel

| Página | Para quê |
|---|---|
| Visão geral | Indicadores do dia, movimento por hora, câmeras e ocorrências recentes |
| Ao vivo | Vídeo das câmeras por WebRTC (MJPEG como reserva) com as detecções desenhadas por cima e o feed de eventos |
| Ocorrências | Fila de revisão (abertas, na triagem da IA, descartadas pela IA, revisadas, resolvidas), filtros por nível e período |
| Detalhe da ocorrência | Fotos e clipe, parecer da IA, motivos com o peso de cada um, linha do tempo, vendas próximas e a revisão (furto, falso positivo, inconclusivo) |
| Visitas | Todas as visitas decididas, com produto na mão, totem e pagamento |
| Vendas | Pagamentos lidos da TouchPay e a visita ligada a cada um |
| Sistema (admin) | Estado da detecção, do modelo, da triagem por IA, da TouchPay, do disco e de cada câmera |
| Câmeras (admin) | Cadastro de câmera nova: digita o código e a loja e recebe a URL RTMP completa para o app |
| Usuários (admin) | Cadastro, perfil (admin ou operador), desativar e redefinir senha |

Os avisos chegam em tempo real (SSE) em qualquer página: toast, som opcional, notificação da área de trabalho e contador no menu. Tema claro, escuro ou do sistema.

## Arquitetura

```
câmeras (RTMP) ──▶ roteador MediaMTX ──RTSP──▶ visao: detecção (YOLO + rastreador)
                      │  grava 48 h                  │
                      │                              ├─▶ fusão: visita × pagamento TouchPay ─▶ Postgres
                      └──WebRTC (WHEP via visao)─────┤
                                                     └─▶ API FastAPI + SSE ─▶ painel React
backend (NestJS) ──▶ login, sessão (cookie) e usuários ──▶ Postgres (mesmas tabelas usuarios/sessoes)
```

São dois serviços de backend, compartilhando o mesmo Postgres:

- **`backend`** (NestJS + Prisma): dono do login, das sessões e do CRUD de usuários. Grava a sessão (hash SHA-256 do token) e o `visao` só lê essa mesma tabela para autorizar as próprias rotas — nenhum dos dois conhece segredo do outro, a confiança é só "a sessão existe e não expirou no banco".
- **`visao`** (FastAPI/Python): detecção, fusão, TouchPay, triagem por IA, cadastro de câmeras/lojas e o painel (API de domínio + o build do frontend). Não sabe mais criar usuário nem logar ninguém — só lê a sessão.

Dentro de `visao/vigia`:
- `deteccao`: leitura do vídeo (ffmpeg), modelo, análise por câmera (pessoa, produto na mão, totem) e coleta de imagens para treino.
- `fusao.py`: junta as câmeras de uma mesma loja numa visita, procura o pagamento e decide o nível (ok, atenção, alerta).
- `touchpay.py`: consulta vendas e movimentações de estoque por polling.
- `evidencias.py`: recorta o clipe da ocorrência no playback do roteador.
- `triagem.py`: fila da triagem por IA generativa (Claude) antes da revisão humana.
- `web`: API de domínio (sem login), leitura de sessão do cookie e arquivos do painel.

Dentro de `backend/src`:
- `autenticacao`: login, logout, `/api/auth/eu`.
- `usuarios`: CRUD de usuários (admin).
- `seguranca`: hash de senha (scrypt) e de token de sessão (SHA-256) — mesmo formato que o `visao` espera.
- `prisma`: schema e migrations das tabelas de usuários/sessão (e das demais tabelas de domínio, espelhando o que o `visao` usa).

Outras pastas:
- `frontend`: React + Vite + Tailwind. O build vai para `frontend/dist` e o `visao` serve.
- `roteador`: MediaMTX em Docker. Recebe as câmeras, grava e entrega para a detecção e o painel.

## Instalação

Requisitos: Python 3.12+, Node 20+, ffmpeg, Docker (para o roteador e o Postgres).

```bash
make instalar
docker run -d --name vigia-postgres -e POSTGRES_PASSWORD=vigia -e POSTGRES_USER=vigia -e POSTGRES_DB=vigia -p 5432:5432 postgres:16-alpine
cp backend/.env.exemplo backend/.env && chmod 600 backend/.env
cp visao/.env.exemplo visao/.env && chmod 600 visao/.env
cp roteador/.env.exemplo roteador/.env && chmod 600 roteador/.env
cd backend && npx prisma migrate deploy && cd ..
make seed
make usuario EMAIL=voce@empresa.com.br
```

Em `backend/.env` vão `DATABASE_URL` (a conexão com o Postgres) e a porta do backend. Os usuários iniciais ficam fixos em `backend/prisma/seed.ts`; `make seed` (ou `npm run prisma:seed` dentro de `backend/`) cria como admin quem ainda não existe, sem precisar de variáveis de ambiente. Para criar usuários adicionais avulsos, use `make usuario EMAIL=...`. Em `visao/.env` vão as credenciais da TouchPay, o PDV de cada loja, a chave da OpenAI (`OPENAI_API_KEY`) para a triagem por IA e a mesma `DATABASE_URL`. Em `roteador/.env` vão as senhas das câmeras e do leitor (gere com `openssl rand -hex 12`). Os três arquivos ficam fora do git.

## Rodar

```bash
make roteador IP=<ip público>
make backend-dev
make servir
make servir-sem-deteccao
make servir-video VIDEO="vguard=/caminho/video.mp4"
make dev
make testes
```

- `make roteador` gera o `mediamtx.yml`, sobe o roteador e imprime a URL RTMP de cada câmera. Nas câmeras Mibo iMX, use o IP, não o domínio.
- `make backend-dev` sobe o backend NestJS com recarga automática em http://127.0.0.1:8001 (ou a porta de `VIGIA_PORTA_BACKEND`).
- `make servir` sobe o painel do `visao` em http://127.0.0.1:8000.
- `make servir-sem-deteccao` sobe só o painel e os registros, sem IA.
- `make servir-video` roda a detecção num vídeo, no lugar do stream.
- `make dev` sobe o backend NestJS, o `visao` e o Vite com recarga automática (http://127.0.0.1:5173).
- `make testes` roda a suíte Python (`visao/testes`, exige um Postgres acessível em `VIGIA_DATABASE_URL_TESTE` ou `DATABASE_URL`) e a suíte Jest (`backend/test`, mesma exigência de Postgres).

O roteador usa as mesmas portas do roteador da POC. Na mesma máquina, rode um ou outro.

### Com Docker Compose

Alternativa aos comandos `make` acima: o `docker-compose.yml` da raiz sobe Postgres, roteador MediaMTX, backend NestJS, `visao` e o Vite do frontend numa rede só, sem precisar instalar Python/Node/ffmpeg na máquina.

```bash
docker compose up --build
docker compose exec backend npm run usuario -- voce@empresa.com.br
```

- Painel (Vite, com hot-reload): http://localhost:5173
- `visao` direto: http://localhost:8000
- `backend` direto: http://localhost:3000
- Roteador: publique um stream de teste em `rtmp://localhost:1935/live/<camera>` (câmeras disponíveis em `visao/vigia.yml` → `cameras`); API do MediaMTX em http://localhost:9997

O `visao` sobe com `VIGIA_AMBIENTE=docker`, que usa o ambiente `docker` em `visao/vigia.yml` — só troca os endpoints do roteador de `127.0.0.1` para o nome do serviço (`roteador`) e o host do servidor para `0.0.0.0`. O `roteador/mediamtx.dev.yml` usado aqui é uma config simplificada só para dev (sem autenticação, paths livres); não serve para produção, que continua usando `roteador/roteador.yml` + `make roteador`.

Código de `backend/`, `visao/` e `frontend/` é montado por volume, então editar os arquivos localmente recarrega o serviço (tsc-watch no backend, reinício manual no `visao`, Vite no frontend) sem precisar reconstruir a imagem.

## Triagem por IA generativa

Toda ocorrência (alerta ou atenção) entra primeiro na fila "Na triagem da IA", sem avisar o operador. O backend espera o clipe da visita ficar pronto (até `espera_clipe_s`). Depois manda ao Claude as fotos do detector, alguns quadros do vídeo e os dados da visita: motivos, linha do tempo e vendas próximas. O Claude devolve um parecer com veredito (`furto_provavel`, `falso_positivo` ou `inconclusivo`), confiança de 0 a 100, um resumo e os sinais que viu.

- Falso positivo com confiança a partir de `confianca_descarte` (80) vai para "Descartadas pela IA". Ela não avisa ninguém e continua no painel para conferência.
- Todo o resto vai para "Abertas" e avisa o operador com o resumo da IA.
- Se a API falhar `tentativas` vezes, se não houver imagem ou se a chave não estiver configurada, a ocorrência segue para o operador sem parecer. A triagem nunca segura uma ocorrência.
- Pagamento tardio ou reposição resolvem a ocorrência mesmo durante a triagem.

A triagem usa a OpenAI por padrão. Para ligar, coloque `OPENAI_API_KEY` em `visao/.env` e reinicie. Os parâmetros ficam em `triagem_ia` no `visao/vigia.yml`: provedor (`openai` ou `anthropic`, ou `TRIAGEM_PROVEDOR` no `.env`), modelo (`gpt-5.5`, ou `TRIAGEM_MODELO` no `.env`), esforço, quantas fotos e quadros mandar e se descarta ou não. Para usar o Claude, troque o provedor para `anthropic`, o modelo para `claude-opus-5-5` e preencha `ANTHROPIC_API_KEY`. As imagens dos clientes vão para a API do provedor escolhido, e só as fotos e quadros da ocorrência são enviados. Dados de pagamento pessoais nunca saem do sistema.

## Configuração

Tudo fica em `visao/vigia.yml`. O ambiente `prod` (variável `VIGIA_AMBIENTE=prod`) sobrepõe o que estiver em `ambientes.prod`.

- `lojas`: nome e PDV TouchPay de cada loja.
- `cameras`: caminho no roteador, loja e `cobre_totem`. Use `auto` para a IA aprender onde está a maquininha, `true` ou `false` para fixar.
- `visao`: modelo, nomes das classes e parâmetros da detecção de produto na mão.
- `fusao`: janelas de tempo, pesos dos sinais e limites de atenção e alerta.
- `coleta`: imagens salvas em `visao/dados/treino` para anotar e retreinar.
- `triagem_ia`: a triagem por IA generativa (veja acima).

## Testar o roteador

Com o roteador no ar (`make roteador`):

```bash
curl -s http://127.0.0.1:9997/v3/paths/list | python3 -m json.tool
ffplay -rtsp_transport tcp rtsp://127.0.0.1:8554/live/vguard
curl -s "http://127.0.0.1:9996/list?path=gravacao/vguard"
make roteador-logs
```

1. A API lista cada caminho e se ele está `ready`, ou seja, com a câmera publicando.
2. O `ffplay` abre o vídeo ao vivo, que é o mesmo que a detecção lê.
3. O playback lista os trechos gravados. É de lá que saem os clipes das ocorrências.

Sem câmera, dá para publicar um vídeo no lugar dela:

```bash
ffmpeg -re -stream_loop -1 -i video.mp4 -c:v libx264 -preset veryfast -tune zerolatency -an -f flv \
  "rtmp://127.0.0.1:1935/live/vguard?user=vguard&pass=$(grep CAM_VGUARD_SENHA roteador/.env | cut -d= -f2)"
```

## Produção em Docker

O `docker-compose.prod.yml` sobe tudo em containers: Postgres, o gerador da config do roteador, o roteador (MediaMTX, com gravação), o `backend` (NestJS, login/usuários) e o `visao` (detecção + painel já compilado). O banco é Postgres, guardado no volume `postgres`. Evidências e clipes ficam no volume `dados`; as gravações, no volume `gravacoes`. O `docker-compose.yml` de desenvolvimento continua igual e não divide nada com o de produção: os nomes (`*-prod`), a rede e os volumes são outros.

| Porta no servidor | Para quê |
|---|---|
| 8790/tcp | painel e API do `visao` (pôr atrás do proxy com HTTPS) |
| 1945/tcp | RTMP: as câmeras publicam aqui |
| 8289/udp e 8290/tcp | mídia do vídeo ao vivo (WebRTC) |

RTSP, API e playback do roteador, o Postgres e o `backend` não saem da rede interna do compose. Só o `visao`, com IP fixo (`VIGIA_IP_VISAO`), lê o roteador sem senha; quem vem de fora precisa do usuário da câmera ou do `leitor`.

Antes de subir, no servidor:

1. `config-prod.env` (copie de `config-prod.env.exemplo`): a senha do Postgres, as portas, `VIGIA_IP_PUBLICO`/`VIGIA_HOSTS_PUBLICOS` com o IP público do servidor e `VIGIA_COOKIE_SEGURO=true`. Os usuários iniciais (admin) são criados automaticamente pelo `prisma:seed` (roda no start do container `backend`, veja `backend/prisma/seed.ts`).
2. `visao/.env`: TouchPay, PDVs e `OPENAI_API_KEY`.
3. `roteador/.env`: senha de cada câmera (`CAM_*_SENHA`) e `LEITOR_SENHA`.

Subir, atualizar e acompanhar:

```bash
docker compose -f docker-compose.prod.yml --env-file config-prod.env up -d --build
docker compose -f docker-compose.prod.yml --env-file config-prod.env logs roteador-config
docker compose -f docker-compose.prod.yml --env-file config-prod.env logs -f backend visao
docker compose -f docker-compose.prod.yml --env-file config-prod.env down
```

O log do `roteador-config` imprime a URL RTMP de cada câmera. Mudou câmera em `visao/vigia.yml` ou `roteador/roteador.yml`? Rode o `up -d` de novo: a config do roteador é gerada outra vez a cada subida. O `down` não apaga os volumes; `down -v` apaga banco, evidências e gravações — **nunca rode `down -v` sem ter um backup** (veja `MIGRACAO.md`).

Atrás do Nginx Proxy Manager: crie um Proxy Host para `http://host.docker.internal:8790`, ligue *Websockets Support* e SSL, e em *Advanced* ponha `proxy_buffering off; proxy_read_timeout 1h;` para os eventos ao vivo. As rotas `/api/auth` e `/api/usuarios` também precisam de um Proxy Host apontando para a porta do `backend` (3000) — veja `nginx-vigia.conf` para o roteamento completo caso use nginx direto em vez do NPM.

### Migrando uma instalação antiga (SQLite, backend único)

Se já existe um `gdel-vigia` em produção na versão anterior (um só backend Python, SQLite), siga `MIGRACAO.md` à risca: ele faz backup do SQLite, sobe o Postgres, aplica o schema, simula a cópia dos dados antes de aplicar de verdade, e só então orienta a desligar a instalação antiga. Em nenhum passo o SQLite original é apagado ou alterado — o rollback é sempre possível.

## Servidor

1. Copie a pasta para `/opt/gdel-vigia`. Crie o usuário de sistema `vigia`, dono de `visao/dados/` e `roteador/gravacoes/`.
2. Suba um Postgres (gerenciado ou `docker run`, veja a seção de Instalação) e rode `cd backend && npx prisma migrate deploy`.
3. Rode `make instalar`, `make usuario EMAIL=...` e `make roteador IP=<ip público>`.
4. `backend/vigia-backend.service` e `visao/vigia-visao.service` vão em `/etc/systemd/system/`. Depois: `systemctl enable --now vigia-backend vigia-visao` (o `visao` depende do `backend` estar no ar).
5. `nginx-vigia.conf` (na raiz do projeto) é o modelo do proxy com TLS: roteia `/api/auth` e `/api/usuarios` para o `backend` (porta 3000) e o resto para o `visao` (porta 8000). Troque o domínio e gere o certificado. O nginx já desliga o buffer nas rotas de tempo real (eventos, detecções e MJPEG).
6. Com HTTPS, `cookie_seguro: true` já vem no ambiente `prod`.

Portas abertas no firewall:

| Porta | Para quê |
|---|---|
| 443/tcp | Painel |
| 1935/tcp | Câmeras publicando |
| 8189/udp e 8190/tcp | Mídia WebRTC, só se for usar o vídeo fluido de fora do servidor |

RTSP, playback, a API do MediaMTX e o Postgres não saem da rede interna do compose. O `visao` fica em 127.0.0.1 (porta 8790 por fora). O `backend` publica a porta 3000 só em 127.0.0.1 — é por onde o nginx (no host) alcança `/api/auth` e `/api/usuarios`; dentro da rede Docker, o `visao` fala com ele pelo nome do serviço.

### Ler o roteador de produção da sua máquina

Use um túnel SSH. Ele não abre porta nova no servidor:

```bash
ssh -N -L 18554:127.0.0.1:8554 -L 19996:127.0.0.1:9996 usuario@servidor
ffplay -rtsp_transport tcp rtsp://127.0.0.1:18554/live/vguard
curl -o trecho.mp4 "http://127.0.0.1:19996/get?path=gravacao/vguard&start=2026-11-13T10:00:00-03:00&duration=60&format=mp4"
rsync -avz usuario@servidor:/opt/gdel-vigia/visao/dados/treino/ ./treino-prod/
```

Para rodar a detecção local em cima das câmeras de produção, aponte `roteador.rtsp` para `rtsp://127.0.0.1:18554` e `roteador.playback` para `http://127.0.0.1:19996`.

### Vídeo ao vivo fora do servidor

O navegador negocia o WebRTC pelo backend (`/api/cameras/{nome}/whep`), então a sinalização já passa pelo HTTPS. A mídia, porém, vai direto do roteador para o navegador. Para isso:

1. Em `roteador/roteador.yml`, preencha `webrtc.hosts_publicos` com o IP público (ou o domínio) do servidor.
2. Rode `make roteador` de novo.
3. Abra 8189/udp. A 8190/tcp serve de reserva para redes que bloqueiam UDP.

Sem isso, o painel usa MJPEG automaticamente: funciona em qualquer rede, só que com menos quadros por segundo.

## Trocar o modelo depois do treino

1. Copie o `best.pt` treinado para `modelos/`.
2. Aponte `visao.modelo` para ele.
3. Confira `visao.classes`: cada papel (cliente, produto, totem, celular) aponta para o nome da classe no modelo. `celular` é opcional.
4. Reinicie o serviço. A página Sistema mostra o modelo carregado, as classes e o tempo de inferência.

Com o modelo novo validado, vale subir o peso de `pegada_fraca` em `fusao.pesos` (hoje 0) para -20. Assim, uma pegada vista de relance deixa de pesar a favor da ocorrência.

## Dados e privacidade

- O banco (usuários, sessões, visitas, ocorrências, pagamentos, cadastros) fica no Postgres. As evidências e as imagens de treino ficam em `visao/dados/`.
- Da TouchPay, o sistema guarda só valor, itens, forma de pagamento e PDV. CPF, e-mail e telefone do comprador são descartados na leitura.
- As gravações do roteador são apagadas em 48 h. O clipe de cada ocorrência é copiado antes disso.

## Cadastrar câmera pelo painel

Em **Câmeras** (admin), clique em **Nova câmera**, informe o código (ex.: `XTPRZS54`) e a loja (ou crie uma nova, com o PDV TouchPay se já souber). O painel gera usuário e senha da câmera, libera o caminho `live/<código>` no roteador e devolve a URL para colar no app (RTMP personalizado). A detecção começa a analisar a câmera sem reiniciar nada.

- As câmeras e lojas cadastradas ficam no banco (`cameras_cadastradas` e `lojas_cadastradas`); as do `vigia.yml`/`roteador.yml` continuam valendo e aparecem como "arquivo de config".
- O `visao` aplica as câmeras no MediaMTX pela API (`roteador.api`) e confere a cada minuto. Se o roteador reiniciar, elas voltam sozinhas em até um minuto.
- A lista de usuários do roteador é montada a partir do `mediamtx.yml` gerado (`roteador.config_gerada`), porque a API devolve as senhas mascaradas.
- A URL usa `VIGIA_RTMP_PUBLICO`; no compose de produção ela vem de `VIGIA_IP_PUBLICO` e `VIGIA_PORTA_RTMP`.
