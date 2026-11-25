def linha_do_tempo(visita):
    eventos = []
    for parte in visita.get("partes", []):
        camera = parte["camera"]
        eventos.append({"t": parte["inicio"], "tipo": "entrou", "camera": camera, "texto": "apareceu na câmera"})
        eventos += [{"t": t, "tipo": "pegou", "camera": camera, "texto": f"produto na mão ({n}º item)"}
                    for n, t in enumerate(parte["pegadas"], 1)]
        eventos += [{"t": inicio, "tipo": "totem", "camera": camera, "texto": f"no totem por {fim - inicio:.0f}s"}
                    for inicio, fim in parte["totem"]]
        eventos.append({"t": parte["fim"], "tipo": "saiu",
                        "texto": "saiu com o produto na mão" if parte.get("saiu_com_produto") else "saiu da imagem",
                        "camera": camera})
    return sorted(eventos, key=lambda e: e["t"])
