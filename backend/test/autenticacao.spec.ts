import { INestApplication } from "@nestjs/common";
import request from "supertest";
import { cookieDaResposta, criarAppDeTeste, limparBanco } from "./apoio";

const SENHA_ADMIN = "admin-forte-123";
const SENHA_OPERADOR = "operador-forte-123";

describe("autenticação e usuários", () => {
  let app: INestApplication;

  beforeEach(async () => {
    app = await criarAppDeTeste();
    await limparBanco(app);
  });

  afterEach(async () => {
    await app.close();
  });

  async function criarAdminLogado() {
    const prisma = app.get((await import("../src/prisma/prisma.service")).PrismaService);
    const seguranca = app.get((await import("../src/seguranca/seguranca.service")).SegurancaService);
    const usuario = await prisma.usuario.create({
      data: { nome: "Admin", email: "admin@vigia.local", senha: seguranca.gerarHash(SENHA_ADMIN), papel: "admin" },
    });
    const login = await request(app.getHttpServer())
      .post("/api/auth/login")
      .send({ email: "admin@vigia.local", senha: SENHA_ADMIN });
    return { usuario, cookie: cookieDaResposta(login) };
  }

  async function criarOperador() {
    const prisma = app.get((await import("../src/prisma/prisma.service")).PrismaService);
    const seguranca = app.get((await import("../src/seguranca/seguranca.service")).SegurancaService);
    return prisma.usuario.create({
      data: { nome: "Operador", email: "operador@vigia.local", senha: seguranca.gerarHash(SENHA_OPERADOR), papel: "operador" },
    });
  }

  describe("login", () => {
    it("recusa senha errada com 401", async () => {
      await criarAdminLogado();
      const resposta = await request(app.getHttpServer())
        .post("/api/auth/login")
        .send({ email: "admin@vigia.local", senha: "errada-123456" });
      expect(resposta.status).toBe(401);
    });

    it("recusa email inexistente com 401", async () => {
      const resposta = await request(app.getHttpServer())
        .post("/api/auth/login")
        .send({ email: "ninguem@vigia.local", senha: "qualquer-coisa" });
      expect(resposta.status).toBe(401);
    });

    it("aceita login correto, devolve 200 com cookie httpOnly e dados públicos", async () => {
      await criarAdminLogado();
      const resposta = await request(app.getHttpServer())
        .post("/api/auth/login")
        .send({ email: "ADMIN@vigia.local", senha: SENHA_ADMIN });
      expect(resposta.status).toBe(200);
      expect(resposta.body).toMatchObject({ nome: "Admin", email: "admin@vigia.local", papel: "admin" });
      expect(resposta.body.senha).toBeUndefined();
      const cookie = resposta.headers["set-cookie"][0];
      expect(cookie.toLowerCase()).toContain("httponly");
    });

    it("bloqueia depois de várias tentativas e libera outro usuário", async () => {
      const { usuario: admin } = await criarAdminLogado();
      await criarOperador();
      for (let tentativa = 0; tentativa < 5; tentativa += 1) {
        await request(app.getHttpServer()).post("/api/auth/login").send({ email: admin.email, senha: "errada-123456" });
      }
      const bloqueado = await request(app.getHttpServer())
        .post("/api/auth/login")
        .send({ email: admin.email, senha: SENHA_ADMIN });
      expect(bloqueado.status).toBe(429);
      const outroUsuario = await request(app.getHttpServer())
        .post("/api/auth/login")
        .send({ email: "operador@vigia.local", senha: SENHA_OPERADOR });
      expect(outroUsuario.status).toBe(200);
    });

    it("usuário desativado não consegue entrar", async () => {
      const prisma = app.get((await import("../src/prisma/prisma.service")).PrismaService);
      const operador = await criarOperador();
      await prisma.usuario.update({ where: { id: operador.id }, data: { ativo: false } });
      const resposta = await request(app.getHttpServer())
        .post("/api/auth/login")
        .send({ email: "operador@vigia.local", senha: SENHA_OPERADOR });
      expect(resposta.status).toBe(401);
    });
  });

  describe("sessão", () => {
    it("/api/auth/eu sem cookie é 401", async () => {
      const resposta = await request(app.getHttpServer()).get("/api/auth/eu");
      expect(resposta.status).toBe(401);
    });

    it("/api/auth/eu com cookie válido devolve o usuário", async () => {
      const { cookie } = await criarAdminLogado();
      const resposta = await request(app.getHttpServer()).get("/api/auth/eu").set("Cookie", cookie);
      expect(resposta.status).toBe(200);
      expect(resposta.body.papel).toBe("admin");
    });

    it("logout invalida a sessão", async () => {
      const { cookie } = await criarAdminLogado();
      const logout = await request(app.getHttpServer()).post("/api/auth/logout").set("Cookie", cookie);
      expect(logout.status).toBe(200);
      const depois = await request(app.getHttpServer()).get("/api/auth/eu").set("Cookie", cookie);
      expect(depois.status).toBe(401);
    });
  });

  describe("permissões", () => {
    it("operador não acessa rotas de admin", async () => {
      await criarAdminLogado();
      await criarOperador();
      const login = await request(app.getHttpServer())
        .post("/api/auth/login")
        .send({ email: "operador@vigia.local", senha: SENHA_OPERADOR });
      const cookie = cookieDaResposta(login);
      expect((await request(app.getHttpServer()).get("/api/usuarios").set("Cookie", cookie)).status).toBe(403);
      expect(
        (
          await request(app.getHttpServer())
            .post("/api/usuarios")
            .set("Cookie", cookie)
            .send({ nome: "Intruso", email: "intruso@vigia.local", senha: "senha-forte-1", papel: "admin" })
        ).status,
      ).toBe(403);
    });
  });

  describe("gestão de usuários", () => {
    it("admin cria usuário que consegue entrar, sem expor a senha na listagem", async () => {
      const { cookie } = await criarAdminLogado();
      const criar = await request(app.getHttpServer())
        .post("/api/usuarios")
        .set("Cookie", cookie)
        .send({ nome: "Maria", email: "maria@vigia.local", senha: "senha-forte-1", papel: "operador" });
      expect(criar.status).toBe(201);
      const listagem = await request(app.getHttpServer()).get("/api/usuarios").set("Cookie", cookie);
      expect(listagem.body.map((u: { email: string }) => u.email)).toContain("maria@vigia.local");
      expect(JSON.stringify(listagem.body)).not.toContain("senha-forte-1");
      const login = await request(app.getHttpServer())
        .post("/api/auth/login")
        .send({ email: "maria@vigia.local", senha: "senha-forte-1" });
      expect(login.body.papel).toBe("operador");
    });

    it("email duplicado é 409", async () => {
      const { cookie } = await criarAdminLogado();
      const dados = { nome: "Maria", email: "maria@vigia.local", senha: "senha-forte-1", papel: "operador" };
      await request(app.getHttpServer()).post("/api/usuarios").set("Cookie", cookie).send(dados);
      const duplicado = await request(app.getHttpServer())
        .post("/api/usuarios")
        .set("Cookie", cookie)
        .send({ ...dados, email: "MARIA@vigia.local" });
      expect(duplicado.status).toBe(409);
    });

    it("senha fraca é 422 ao criar e ao alterar", async () => {
      const { cookie } = await criarAdminLogado();
      const operador = await criarOperador();
      const criar = await request(app.getHttpServer())
        .post("/api/usuarios")
        .set("Cookie", cookie)
        .send({ nome: "Maria", email: "maria@vigia.local", senha: "curta", papel: "operador" });
      expect(criar.status).toBe(422);
      const alterar = await request(app.getHttpServer())
        .patch(`/api/usuarios/${operador.id}`)
        .set("Cookie", cookie)
        .send({ senha: "curta" });
      expect(alterar.status).toBe(422);
    });

    it("email inválido e papel inválido são 422", async () => {
      const { cookie } = await criarAdminLogado();
      const semArroba = await request(app.getHttpServer())
        .post("/api/usuarios")
        .set("Cookie", cookie)
        .send({ nome: "Maria", email: "sem-arroba", senha: "senha-forte-1", papel: "operador" });
      expect(semArroba.status).toBe(422);
      const papelInvalido = await request(app.getHttpServer())
        .post("/api/usuarios")
        .set("Cookie", cookie)
        .send({ nome: "Maria", email: "maria@vigia.local", senha: "senha-forte-1", papel: "dono" });
      expect(papelInvalido.status).toBe(422);
    });

    it("admin não pode desativar nem rebaixar a própria conta", async () => {
      const { usuario: admin, cookie } = await criarAdminLogado();
      const desativar = await request(app.getHttpServer())
        .patch(`/api/usuarios/${admin.id}`)
        .set("Cookie", cookie)
        .send({ ativo: false });
      expect(desativar.status).toBe(400);
      const rebaixar = await request(app.getHttpServer())
        .patch(`/api/usuarios/${admin.id}`)
        .set("Cookie", cookie)
        .send({ papel: "operador" });
      expect(rebaixar.status).toBe(400);
      const eu = await request(app.getHttpServer()).get("/api/auth/eu").set("Cookie", cookie);
      expect(eu.status).toBe(200);
    });

    it("desativar outro usuário derruba a sessão dele", async () => {
      const { cookie } = await criarAdminLogado();
      const operador = await criarOperador();
      const loginOperador = await request(app.getHttpServer())
        .post("/api/auth/login")
        .send({ email: "operador@vigia.local", senha: SENHA_OPERADOR });
      const cookieOperador = cookieDaResposta(loginOperador);
      expect((await request(app.getHttpServer()).get("/api/auth/eu").set("Cookie", cookieOperador)).status).toBe(200);
      const desativar = await request(app.getHttpServer())
        .patch(`/api/usuarios/${operador.id}`)
        .set("Cookie", cookie)
        .send({ ativo: false });
      expect(desativar.status).toBe(200);
      expect((await request(app.getHttpServer()).get("/api/auth/eu").set("Cookie", cookieOperador)).status).toBe(401);
    });

    it("alterar usuário inexistente é 404", async () => {
      const { cookie } = await criarAdminLogado();
      const resposta = await request(app.getHttpServer())
        .patch("/api/usuarios/9999")
        .set("Cookie", cookie)
        .send({ nome: "Fulano" });
      expect(resposta.status).toBe(404);
    });
  });
});
