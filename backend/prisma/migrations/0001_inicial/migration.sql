CREATE SCHEMA IF NOT EXISTS "public";

CREATE TABLE "usuarios" (
    "id" SERIAL NOT NULL,
    "nome" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "senha" TEXT NOT NULL,
    "papel" TEXT NOT NULL,
    "ativo" BOOLEAN NOT NULL DEFAULT true,
    "criado_em" DOUBLE PRECISION,
    "ultimo_acesso" DOUBLE PRECISION,

    CONSTRAINT "usuarios_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "sessoes" (
    "token" TEXT NOT NULL,
    "usuario_id" INTEGER NOT NULL,
    "criada_em" DOUBLE PRECISION,
    "expira_em" DOUBLE PRECISION,

    CONSTRAINT "sessoes_pkey" PRIMARY KEY ("token")
);

CREATE TABLE "pagamentos" (
    "id" TEXT NOT NULL,
    "horario" DOUBLE PRECISION,
    "valor" DOUBLE PRECISION,
    "situacao" TEXT,
    "qtd_itens" INTEGER,
    "pdv" TEXT,
    "loja" TEXT,
    "metodo" TEXT,
    "itens" JSONB,
    "recebido_em" DOUBLE PRECISION,
    "visita_id" TEXT,

    CONSTRAINT "pagamentos_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "movimentacoes" (
    "id" BIGINT NOT NULL,
    "data" DOUBLE PRECISION,
    "tipo" TEXT,
    "produto_id" BIGINT,
    "quantidade" INTEGER,
    "final" INTEGER,
    "usuario" TEXT,
    "humana" BOOLEAN,
    "contagem" INTEGER,
    "pdv" TEXT,

    CONSTRAINT "movimentacoes_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "visitas" (
    "id" TEXT NOT NULL,
    "loja" TEXT,
    "inicio" DOUBLE PRECISION,
    "fim" DOUBLE PRECISION,
    "cameras" JSONB,
    "pegadas" INTEGER,
    "foi_totem" BOOLEAN,
    "score" INTEGER,
    "nivel" TEXT,
    "pagamento_id" TEXT,
    "dados" JSONB,
    "decidida_em" DOUBLE PRECISION,

    CONSTRAINT "visitas_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "ocorrencias" (
    "id" SERIAL NOT NULL,
    "visita_id" TEXT,
    "loja" TEXT,
    "cameras" JSONB,
    "criada_em" DOUBLE PRECISION,
    "inicio" DOUBLE PRECISION,
    "fim" DOUBLE PRECISION,
    "score" INTEGER,
    "nivel" TEXT,
    "situacao" TEXT DEFAULT 'aberta',
    "motivos" JSONB,
    "evidencias" JSONB,
    "clipes" JSONB DEFAULT '[]',
    "resolucao" TEXT,
    "resolvida_em" DOUBLE PRECISION,
    "veredito" TEXT,
    "observacao" TEXT,
    "revisada_por" TEXT,
    "revisada_em" DOUBLE PRECISION,
    "ia" JSONB,
    "tipo" TEXT NOT NULL DEFAULT 'suspeita',

    CONSTRAINT "ocorrencias_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "lojas_cadastradas" (
    "chave" TEXT NOT NULL,
    "nome" TEXT NOT NULL,
    "pdv" TEXT,
    "criada_em" DOUBLE PRECISION,

    CONSTRAINT "lojas_cadastradas_pkey" PRIMARY KEY ("chave")
);

CREATE TABLE "cameras_cadastradas" (
    "nome" TEXT NOT NULL,
    "descricao" TEXT,
    "loja" TEXT NOT NULL,
    "caminho" TEXT NOT NULL,
    "usuario" TEXT NOT NULL,
    "senha" TEXT NOT NULL,
    "criada_em" DOUBLE PRECISION,

    CONSTRAINT "cameras_cadastradas_pkey" PRIMARY KEY ("nome")
);

CREATE TABLE "maquininhas_marcadas" (
    "camera" TEXT NOT NULL,
    "caixas" JSONB NOT NULL,
    "origem" TEXT NOT NULL DEFAULT 'manual',
    "marcada_por" TEXT,
    "marcada_em" DOUBLE PRECISION,

    CONSTRAINT "maquininhas_marcadas_pkey" PRIMARY KEY ("camera")
);

CREATE TABLE "recorte_sem_compra" (
    "loja" TEXT NOT NULL,
    "ativo" BOOLEAN NOT NULL DEFAULT false,
    "espera_s" INTEGER NOT NULL,
    "alterado_por" TEXT,
    "alterado_em" DOUBLE PRECISION,

    CONSTRAINT "recorte_sem_compra_pkey" PRIMARY KEY ("loja")
);

CREATE UNIQUE INDEX "usuarios_email_key" ON "usuarios"("email");

CREATE INDEX "sessoes_usuario_id_idx" ON "sessoes"("usuario_id");

CREATE INDEX "sessoes_expira_em_idx" ON "sessoes"("expira_em");

CREATE INDEX "pagamentos_horario" ON "pagamentos"("horario");

CREATE INDEX "movimentacoes_data" ON "movimentacoes"("data");

CREATE INDEX "visitas_inicio" ON "visitas"("inicio");

CREATE UNIQUE INDEX "ocorrencias_visita_id_key" ON "ocorrencias"("visita_id");

CREATE INDEX "ocorrencias_criada" ON "ocorrencias"("criada_em");

CREATE INDEX "ocorrencias_fim_idx" ON "ocorrencias"("fim");

ALTER TABLE "sessoes" ADD CONSTRAINT "sessoes_usuario_id_fkey" FOREIGN KEY ("usuario_id") REFERENCES "usuarios"("id") ON DELETE CASCADE ON UPDATE CASCADE;

