PY := $(CURDIR)/.venv/bin/python
VISAO := cd visao &&
BACKEND := cd backend &&
EMAIL ?=
NOME ?=
PAPEL ?= admin
VIDEO ?=
SQLITE ?=
IP ?= IP_DO_SERVIDOR

.PHONY: instalar instalar-visao instalar-backend instalar-frontend frontend \
        servir servir-sem-deteccao servir-video servir-remoto dev \
        backend-build backend-dev backend-start \
        migrar migrar-simular usuario seed testes testes-visao testes-backend \
        tunel-prod roteador-config roteador roteador-logs

instalar: instalar-visao instalar-backend instalar-frontend frontend

instalar-visao:
	python3 -m venv .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
	$(PY) -m pip install -r visao/requirements.txt

instalar-backend:
	$(BACKEND) npm ci
	$(BACKEND) npx prisma generate

instalar-frontend:
	cd frontend && npm ci

frontend:
	cd frontend && npm run build

servir:
	$(VISAO) $(PY) -m vigia servir

servir-remoto:
	VIGIA_AMBIENTE=remoto $(VISAO) $(PY) -m vigia servir

servir-sem-deteccao:
	$(VISAO) $(PY) -m vigia servir --sem-deteccao

servir-video:
	$(VISAO) $(PY) -m vigia servir $(foreach v,$(VIDEO),--video $(v))

dev:
	$(BACKEND) npm run dev & $(VISAO) $(PY) -m vigia servir & cd frontend && npm run dev

backend-build:
	$(BACKEND) npm run build

backend-dev:
	$(BACKEND) npm run dev

backend-start:
	$(BACKEND) npm run start

migrar:
	$(BACKEND) npx prisma migrate deploy
	$(VISAO) $(PY) -m vigia migrar-dados $(SQLITE)

migrar-simular:
	$(VISAO) $(PY) -m vigia migrar-dados $(SQLITE) --simular

usuario:
	$(BACKEND) npm run usuario -- $(EMAIL) $(if $(NOME),--nome "$(NOME)") --papel $(PAPEL)

seed:
	$(BACKEND) npm run prisma:seed

testes: testes-visao testes-backend

testes-visao:
	$(VISAO) $(PY) -m unittest discover -s testes

testes-backend:
	$(BACKEND) npm test

tunel-prod:
	ssh -N -L 1945:127.0.0.1:1945 gdel

roteador-config:
	$(PY) roteador/gerar.py --ip $(IP)

roteador: roteador-config
	cd roteador && docker compose up -d

roteador-logs:
	cd roteador && docker compose logs -f --tail 100
