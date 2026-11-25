import json
import logging
import threading
import time

import psycopg
from psycopg.rows import dict_row
from psycopg.types.string import TextLoader

log = logging.getLogger(__name__)

VEREDITOS = ("furto", "falso_positivo", "duvida")
SITUACOES = ("aberta", "triagem", "descartada", "resolvida", "revisada")
SITUACOES_SEM_REVISAO = ("aberta", "triagem")
CAMPOS_JSON_OCORRENCIA = ("cameras", "motivos", "evidencias", "clipes", "ia")
TIPOS_DE_OCORRENCIA = ("suspeita", "sem_compra")
FILTROS_VISITA = {
    "pagas": "v.pagamento_id IS NOT NULL",
    "sem_pagamento": "v.pegadas > 0 AND v.pagamento_id IS NULL",
    "sem_produto": "v.pegadas = 0",
    "suspeitas": "v.nivel IN ('alerta', 'atencao')",
}
HORA_DO_DIA = "((FLOOR({campo})::bigint + %s) %% 86400) / 3600"


def _decodificar(linha, campos):
    for campo in campos:
        if campo in linha:
            linha[campo] = json.loads(linha[campo] or "null")
    return linha


def _filtro(condicoes):
    usadas = [(sql, valores) for sql, valores, ativa in condicoes if ativa]
    if not usadas:
        return "", []
    return " WHERE " + " AND ".join(sql for sql, _ in usadas), [v for _, valores in usadas for v in valores]


def _como_json(valor):
    return json.dumps(valor, ensure_ascii=False, default=str)


def conectar(url):
    conexao = psycopg.connect(url, autocommit=True, row_factory=dict_row)
    for tipo in ("json", "jsonb"):
        conexao.adapters.register_loader(tipo, TextLoader)
    return conexao


class Banco:
    def __init__(self, url):
        self.url = url
        self.lock = threading.RLock()
        self.con = conectar(url)

    def fechar(self):
        self.con.close()

    def _executar(self, sql, parametros, buscar):
        for tentativa in range(2):
            try:
                with self.lock:
                    cursor = self.con.execute(sql, parametros)
                    return cursor.fetchall() if buscar and cursor.description else []
            except psycopg.OperationalError:
                if tentativa:
                    raise
                log.warning("conexão com o banco caiu: reconectando")
                with self.lock:
                    self.con = conectar(self.url)

    def _exec(self, sql, parametros=()):
        return self._executar(sql, parametros, buscar=True)

    def _todos(self, sql, parametros=()):
        return self._executar(sql, parametros, buscar=True)

    def _um(self, sql, parametros=()):
        linhas = self._todos(sql, parametros)
        return linhas[0] if linhas else None

    def salvar_pagamento(self, p):
        self._exec(
            """INSERT INTO pagamentos (id, horario, valor, situacao, qtd_itens, pdv, loja, metodo, itens, recebido_em)
               VALUES (%(id)s, %(horario)s, %(valor)s, %(situacao)s, %(qtd_itens)s, %(pdv)s, %(loja)s, %(metodo)s, %(itens)s, %(recebido_em)s)
               ON CONFLICT (id) DO UPDATE SET situacao=excluded.situacao, valor=excluded.valor,
                   qtd_itens=excluded.qtd_itens, itens=excluded.itens, horario=excluded.horario""",
            {**p, "itens": _como_json(p.get("itens") or []), "recebido_em": time.time()})

    def pagamentos_entre(self, inicio, fim):
        linhas = self._todos("SELECT * FROM pagamentos WHERE horario BETWEEN %s AND %s ORDER BY horario", (inicio, fim))
        return [_decodificar(linha, ("itens",)) for linha in linhas]

    def associar_pagamento(self, pagamento_id, visita_id):
        self._exec("UPDATE pagamentos SET visita_id=%s WHERE id=%s", (visita_id, pagamento_id))

    def liberar_pagamento(self, visita_id):
        with self.lock:
            self._exec("UPDATE visitas SET pagamento_id=NULL WHERE id=%s", (visita_id,))
            self._exec("UPDATE pagamentos SET visita_id=NULL WHERE visita_id=%s", (visita_id,))

    def ultimo_horario_pagamento(self):
        linha = self._um("SELECT MAX(horario) AS h FROM pagamentos")
        return linha["h"] if linha else None

    def listar_pagamentos(self, loja=None, desde=None, ate=None, limite=100, deslocamento=0):
        where, valores = _filtro([
            ("loja = %s", [loja], loja),
            ("horario >= %s", [desde], desde),
            ("horario < %s", [ate], ate),
        ])
        total = self._um(f"SELECT COUNT(*) AS n, COALESCE(SUM(valor), 0) AS soma FROM pagamentos{where}", valores)
        itens = self._todos(f"SELECT * FROM pagamentos{where} ORDER BY horario DESC LIMIT %s OFFSET %s",
                            [*valores, limite, deslocamento])
        return {"total": total["n"], "valor_total": total["soma"], "itens": [_decodificar(i, ("itens",)) for i in itens]}

    def salvar_movimentacoes(self, movimentacoes):
        if not movimentacoes:
            return
        with self.lock, self.con.transaction(), self.con.cursor() as cursor:
            cursor.executemany(
                """INSERT INTO movimentacoes (id, data, tipo, produto_id, quantidade, final, usuario, humana, contagem, pdv)
                   VALUES (%(id)s, %(data)s, %(tipo)s, %(produto_id)s, %(quantidade)s, %(final)s, %(usuario)s, %(humana)s, %(contagem)s, %(pdv)s)
                   ON CONFLICT (id) DO UPDATE SET data=excluded.data, tipo=excluded.tipo, produto_id=excluded.produto_id,
                       quantidade=excluded.quantidade, final=excluded.final, usuario=excluded.usuario, humana=excluded.humana,
                       contagem=excluded.contagem, pdv=excluded.pdv""",
                [{**m, "humana": bool(m["humana"]), "contagem": int(bool(m["contagem"]))} for m in movimentacoes])

    def ultima_movimentacao(self):
        linha = self._um("SELECT MAX(data) AS d FROM movimentacoes")
        return linha["d"] if linha else None

    def operador_entre(self, inicio, fim, pdvs=None):
        sql = "SELECT * FROM movimentacoes WHERE humana AND data BETWEEN %s AND %s"
        valores = [inicio, fim]
        if pdvs:
            sql += " AND (pdv = ANY(%s) OR pdv IS NULL)"
            valores.append([str(pdv) for pdv in pdvs])
        return self._todos(sql, valores)

    def salvar_visita(self, v):
        self._exec(
            """INSERT INTO visitas (id, loja, inicio, fim, cameras, pegadas, foi_totem, score, nivel, pagamento_id, dados, decidida_em)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (id) DO UPDATE SET loja=excluded.loja, inicio=excluded.inicio, fim=excluded.fim, cameras=excluded.cameras,
                   pegadas=excluded.pegadas, foi_totem=excluded.foi_totem, score=excluded.score, nivel=excluded.nivel,
                   pagamento_id=excluded.pagamento_id, dados=excluded.dados, decidida_em=excluded.decidida_em""",
            (v["id"], v.get("loja"), v["inicio"], v["fim"], json.dumps(v["cameras"]), v["pegadas"], bool(v["foi_totem"]),
             v["score"], v["nivel"], v.get("pagamento_id"), _como_json(v), time.time()))

    def pegadas_da_visita(self, visita_id):
        linha = self._um("SELECT pegadas FROM visitas WHERE id=%s", (visita_id,))
        return linha["pegadas"] if linha else None

    def pagamento_da_visita(self, visita_id):
        linha = self._um("SELECT pagamento_id FROM visitas WHERE id=%s", (visita_id,))
        return linha["pagamento_id"] if linha else None

    def listar_visitas(self, loja=None, resultado=None, desde=None, ate=None, limite=100, deslocamento=0):
        where, valores = _filtro([
            ("v.loja = %s", [loja], loja),
            (FILTROS_VISITA.get(resultado, "TRUE"), [], resultado in FILTROS_VISITA),
            ("v.inicio >= %s", [desde], desde),
            ("v.inicio < %s", [ate], ate),
        ])
        total = self._um(f"SELECT COUNT(*) AS n FROM visitas v{where}", valores)["n"]
        linhas = self._todos(
            f"""SELECT v.id, v.loja, v.inicio, v.fim, v.cameras, v.pegadas, v.foi_totem, v.score, v.nivel, v.pagamento_id,
                       v.dados, p.valor, p.metodo, p.qtd_itens, p.horario AS pago_em, o.id AS ocorrencia_id
                FROM visitas v
                LEFT JOIN pagamentos p ON p.id = v.pagamento_id
                LEFT JOIN ocorrencias o ON o.visita_id = v.id{where}
                ORDER BY v.inicio DESC LIMIT %s OFFSET %s""", [*valores, limite, deslocamento])
        for linha in linhas:
            dados = json.loads(linha.pop("dados") or "{}")
            linha["cameras"] = json.loads(linha["cameras"] or "[]")
            linha["foi_totem"] = int(bool(linha["foi_totem"]))
            linha["motivos"] = dados.get("motivos", [])
        return {"total": total, "itens": linhas}

    def visita(self, visita_id):
        linha = self._um("SELECT dados FROM visitas WHERE id=%s", (visita_id,))
        return json.loads(linha["dados"]) if linha else None

    def criar_ocorrencia(self, visita, evidencias, situacao="aberta", tipo="suspeita"):
        criada = self._um(
            """INSERT INTO ocorrencias (visita_id, loja, cameras, criada_em, inicio, fim, score, nivel, motivos, evidencias, clipes, situacao, tipo)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, '[]', %s, %s)
               ON CONFLICT (visita_id) DO NOTHING RETURNING id""",
            (visita["id"], visita.get("loja"), json.dumps(visita["cameras"]), time.time(), visita["inicio"], visita["fim"],
             visita["score"], visita["nivel"], _como_json(visita["motivos"]), json.dumps(evidencias), situacao, tipo))
        return criada["id"] if criada else None

    def ocorrencias_sem_clipe(self, desde):
        linhas = self._todos("SELECT * FROM ocorrencias WHERE criada_em >= %s AND (clipes IS NULL OR clipes = '[]'::jsonb) "
                             "ORDER BY criada_em", (desde,))
        return [_decodificar(linha, CAMPOS_JSON_OCORRENCIA) for linha in linhas]

    def periodos_das_ocorrencias(self, desde):
        return [(linha["inicio"], linha["fim"])
                for linha in self._todos("SELECT inicio, fim FROM ocorrencias WHERE fim >= %s", (desde,))]

    def ocorrencias_em_triagem(self):
        linhas = self._todos("SELECT * FROM ocorrencias WHERE situacao = 'triagem' ORDER BY criada_em")
        return [_decodificar(linha, CAMPOS_JSON_OCORRENCIA) for linha in linhas]

    def concluir_triagem(self, ocorrencia_id, parecer, situacao):
        with self.lock:
            self._exec(
                """UPDATE ocorrencias SET ia=%s, situacao=CASE WHEN situacao='triagem' THEN %s ELSE situacao END
                   WHERE id=%s""", (_como_json(parecer), situacao, ocorrencia_id))
            return self.ocorrencia(ocorrencia_id)

    def adicionar_clipe(self, ocorrencia_id, caminho):
        self._exec("UPDATE ocorrencias SET clipes = COALESCE(clipes, '[]'::jsonb) || jsonb_build_array(%s::text) WHERE id=%s",
                   (caminho, ocorrencia_id))

    def resolver_ocorrencia(self, visita_id, pagamento_id, motivo, nivel_visita):
        with self.lock:
            self._exec(
                f"UPDATE ocorrencias SET situacao='resolvida', resolucao=%s, resolvida_em=%s WHERE visita_id=%s AND situacao IN {SITUACOES_SEM_REVISAO}",
                (motivo, time.time(), visita_id))
            self._exec("UPDATE visitas SET nivel=%s, pagamento_id=%s WHERE id=%s", (nivel_visita, pagamento_id, visita_id))
            if pagamento_id:
                self.associar_pagamento(pagamento_id, visita_id)
        return self._um("SELECT id FROM ocorrencias WHERE visita_id=%s", (visita_id,))

    def ocorrencias_abertas_desde(self, desde):
        linhas = self._todos(
            f"""SELECT o.id, o.visita_id, o.loja, o.inicio, o.fim, v.dados -> 'grupo' AS grupo
               FROM ocorrencias o JOIN visitas v ON v.id = o.visita_id
               WHERE o.fim >= %s AND o.situacao IN {SITUACOES_SEM_REVISAO} AND v.pagamento_id IS NULL""", (desde,))
        for linha in linhas:
            linha["grupo"] = json.loads(linha["grupo"] or "[]")
        return linhas

    def listar_ocorrencias(self, situacao=None, nivel=None, loja=None, desde=None, ate=None, limite=50, deslocamento=0, tipo=None):
        where, valores = _filtro([
            ("situacao = %s", [situacao], situacao in SITUACOES),
            ("tipo = %s", [tipo], tipo in TIPOS_DE_OCORRENCIA),
            ("nivel = %s", [nivel], nivel),
            ("loja = %s", [loja], loja),
            ("criada_em >= %s", [desde], desde),
            ("criada_em < %s", [ate], ate),
        ])
        total = self._um(f"SELECT COUNT(*) AS n FROM ocorrencias{where}", valores)["n"]
        itens = self._todos(f"SELECT * FROM ocorrencias{where} ORDER BY criada_em DESC LIMIT %s OFFSET %s",
                            [*valores, limite, deslocamento])
        return {"total": total, "itens": [_decodificar(i, CAMPOS_JSON_OCORRENCIA) for i in itens]}

    def ocorrencia(self, ocorrencia_id):
        linha = self._um("SELECT * FROM ocorrencias WHERE id=%s", (ocorrencia_id,))
        return _decodificar(linha, CAMPOS_JSON_OCORRENCIA) if linha else None

    def contar_ocorrencias_abertas(self):
        return self._um("SELECT COUNT(*) AS n FROM ocorrencias WHERE situacao = 'aberta'")["n"]

    def revisar_ocorrencia(self, ocorrencia_id, veredito, observacao, usuario):
        if veredito not in VEREDITOS:
            raise ValueError(f"veredito deve ser um de {VEREDITOS}")
        self._exec(
            """UPDATE ocorrencias SET veredito=%s, observacao=%s, revisada_por=%s, revisada_em=%s, situacao='revisada'
               WHERE id=%s""", (veredito, observacao, usuario, time.time(), ocorrencia_id))

    def resumo(self, desde, loja=None):
        filtro_loja = " AND loja = %s" if loja else ""
        extra = [loja] if loja else []

        def contar(sql, campo="inicio"):
            return self._um(f"SELECT COUNT(*) AS n FROM visitas WHERE {campo} >= %s{filtro_loja}{sql}", [desde, *extra])["n"]

        vendas = self._um(f"SELECT COUNT(*) AS n, COALESCE(SUM(valor), 0) AS soma FROM pagamentos WHERE horario >= %s{filtro_loja}",
                          [desde, *extra])
        ocorrencias = self._todos(
            f"""SELECT situacao, nivel, veredito, COUNT(*) AS n FROM ocorrencias WHERE criada_em >= %s{filtro_loja}
                GROUP BY situacao, nivel, veredito""", [desde, *extra])
        return {
            "visitas": contar(""),
            "visitas_com_produto": contar(" AND pegadas > 0"),
            "visitas_pagas": contar(" AND pegadas > 0 AND pagamento_id IS NOT NULL"),
            "vendas": vendas["n"],
            "faturamento": vendas["soma"],
            "ocorrencias": sum(o["n"] for o in ocorrencias),
            "ocorrencias_abertas": sum(o["n"] for o in ocorrencias if o["situacao"] == "aberta"),
            "alertas_abertos": sum(o["n"] for o in ocorrencias if o["situacao"] == "aberta" and o["nivel"] == "alerta"),
            "furtos_confirmados": sum(o["n"] for o in ocorrencias if o["veredito"] == "furto"),
            "falsos_positivos": sum(o["n"] for o in ocorrencias if o["veredito"] == "falso_positivo"),
        }

    def movimento_por_hora(self, desde, fuso_offset_s, loja=None):
        filtro_loja = " AND loja = %s" if loja else ""
        extra = [loja] if loja else []
        visitas = self._todos(
            f"SELECT {HORA_DO_DIA.format(campo='inicio')} AS h, COUNT(*) AS n FROM visitas WHERE inicio >= %s{filtro_loja} GROUP BY h",
            [fuso_offset_s, desde, *extra])
        ocorrencias = self._todos(
            f"SELECT {HORA_DO_DIA.format(campo='criada_em')} AS h, COUNT(*) AS n FROM ocorrencias WHERE criada_em >= %s{filtro_loja} GROUP BY h",
            [fuso_offset_s, desde, *extra])
        por_hora = {h: {"hora": h, "visitas": 0, "ocorrencias": 0} for h in range(24)}
        for linha in visitas:
            por_hora[int(linha["h"])]["visitas"] = linha["n"]
        for linha in ocorrencias:
            por_hora[int(linha["h"])]["ocorrencias"] = linha["n"]
        return list(por_hora.values())

    def usuario_da_sessao(self, token_hash):
        return self._um(
            """SELECT u.id, u.nome, u.email, u.papel FROM sessoes s JOIN usuarios u ON u.id = s.usuario_id
               WHERE s.token = %s AND s.expira_em > %s AND u.ativo""", (token_hash, time.time()))

    def listar_lojas_cadastradas(self):
        return self._todos("SELECT chave, nome, pdv FROM lojas_cadastradas ORDER BY nome")

    def salvar_loja_cadastrada(self, chave, nome, pdv):
        self._exec(
            """INSERT INTO lojas_cadastradas (chave, nome, pdv, criada_em) VALUES (%s, %s, %s, %s)
               ON CONFLICT (chave) DO UPDATE SET nome=excluded.nome, pdv=excluded.pdv, criada_em=excluded.criada_em""",
            (chave, nome, pdv, time.time()))

    def listar_cameras_cadastradas(self):
        return self._todos("SELECT nome, descricao, loja, caminho, usuario, senha, criada_em FROM cameras_cadastradas ORDER BY nome")

    def salvar_camera_cadastrada(self, camera):
        self._exec(
            """INSERT INTO cameras_cadastradas (nome, descricao, loja, caminho, usuario, senha, criada_em)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (camera["nome"], camera["descricao"], camera["loja"], camera["caminho"], camera["usuario"], camera["senha"], time.time()))

    def remover_camera_cadastrada(self, nome):
        self._exec("DELETE FROM cameras_cadastradas WHERE nome=%s", (nome,))

    def maquininhas_marcadas(self):
        return {linha["camera"]: json.loads(linha["caixas"])
                for linha in self._todos("SELECT camera, caixas FROM maquininhas_marcadas")}

    def salvar_maquininhas(self, camera, caixas, usuario):
        origem = "manual" if caixas else "sem_maquininha"
        self._exec(
            """INSERT INTO maquininhas_marcadas (camera, caixas, origem, marcada_por, marcada_em) VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (camera) DO UPDATE SET caixas=excluded.caixas, origem=excluded.origem,
                   marcada_por=excluded.marcada_por, marcada_em=excluded.marcada_em""",
            (camera, json.dumps(caixas), origem, usuario, time.time()))

    def remover_maquininhas(self, camera):
        self._exec("DELETE FROM maquininhas_marcadas WHERE camera=%s", (camera,))

    def recortes_sem_compra(self):
        return {linha["loja"]: {"ativo": bool(linha["ativo"]), "espera_s": linha["espera_s"]}
                for linha in self._todos("SELECT loja, ativo, espera_s FROM recorte_sem_compra")}

    def configurar_recorte_sem_compra(self, loja, ativo, espera_s, usuario):
        self._exec(
            """INSERT INTO recorte_sem_compra (loja, ativo, espera_s, alterado_por, alterado_em) VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (loja) DO UPDATE SET ativo=excluded.ativo, espera_s=excluded.espera_s,
                   alterado_por=excluded.alterado_por, alterado_em=excluded.alterado_em""",
            (loja, bool(ativo), espera_s, usuario, time.time()))
