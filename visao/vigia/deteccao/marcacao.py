def origem_da_marcacao(caixas, sem_marcacao):
    if caixas is None:
        return sem_marcacao
    return "manual" if caixas else "sem_maquininha"
