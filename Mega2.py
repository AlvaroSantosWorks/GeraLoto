import pandas as pd
import random
import itertools
import os
import csv

class GeradorMegaSenaAvancado:
    def __init__(self, caminho_historico, caminho_gerados='jogos_ja_gerados.csv'):
        self.caminho_historico = caminho_historico
        self.caminho_gerados = caminho_gerados
        self.historico_oficial = self._carregar_historico()
        self.historico_gerados = self._carregar_gerados()
        self.jogos_proibidos = self.historico_oficial.union(self.historico_gerados)

    def _carregar_historico(self):
        jogos_oficiais = set()
        try:
            with open(self.caminho_historico, mode='r', encoding='latin1') as ficheiro:
                leitor = csv.DictReader(ficheiro, delimiter=',')
                for linha in leitor:
                    try:
                        jogo = tuple(sorted([
                            int(linha['Bola1']), int(linha['Bola2']), int(linha['Bola3']),
                            int(linha['Bola4']), int(linha['Bola5']), int(linha['Bola6'])
                        ]))
                        jogos_oficiais.add(jogo)
                    except (ValueError, KeyError, TypeError):
                        continue
            return jogos_oficiais
        except Exception as e:
            print(f"Aviso: Não foi possível carregar o histórico oficial. ({e})")
            return set()

    def _carregar_gerados(self):
        jogos = set()
        if os.path.exists(self.caminho_gerados):
            with open(self.caminho_gerados, mode='r', encoding='utf-8') as f:
                leitor = csv.reader(f)
                for linha in leitor:
                    if not linha or 'Bola' in str(linha[0]): 
                        continue
                    try:
                        jogo = tuple(sorted([int(x) for x in linha]))
                        jogos.add(jogo)
                    except ValueError:
                        continue
        return jogos

    def _salvar_gerados(self, novos_jogos):
        if not novos_jogos: return
        arquivo_existe = os.path.exists(self.caminho_gerados)
        with open(self.caminho_gerados, mode='a', newline='', encoding='utf-8') as f:
            escritor = csv.writer(f)
            if not arquivo_existe:
                qtd_bolas = len(novos_jogos[0])
                cabecalho = [f'Bola{i}' for i in range(1, qtd_bolas + 1)]
                escritor.writerow(cabecalho)
            for jogo in novos_jogos:
                escritor.writerow(jogo)

    def _gerar_base_equilibrada(self, tamanho):
        pares_disponiveis = [n for n in range(2, 61, 2)]
        impares_disponiveis = [n for n in range(1, 61, 2)]
        qtd_pares = tamanho // 2
        qtd_impares = tamanho - qtd_pares
        escolhidos = random.sample(pares_disponiveis, qtd_pares) + random.sample(impares_disponiveis, qtd_impares)
        return sorted(escolhidos)

    def gerar_jogos(self, tamanho_base=6, tamanho_bilhete=6, tecnica='simples', equilibrar=False, quantidade_pedida=1):
        jogos_validados = []

        if tecnica == 'desdobramento' and tamanho_base > 6:
            while len(jogos_validados) < quantidade_pedida: 
                # 1. Gera o universo de dezenas (a base)
                if equilibrar:
                    base = self._gerar_base_equilibrada(tamanho_base)
                else:
                    base = sorted(random.sample(range(1, 61), tamanho_base))
                
                # 2. Faz o desdobramento no tamanho de bilhete que o usuário escolheu (ex: bilhetes de 8)
                bilhetes_gerados = list(itertools.combinations(base, tamanho_bilhete))
                
                # 3. Validação rigorosa: Garante que NENHUMA sub-combinação de 6 dentro desses bilhetes já saiu
                desdobramento_valido = True
                for bilhete in bilhetes_gerados:
                    combinacoes_internas_de_6 = list(itertools.combinations(bilhete, 6))
                    for combo_6 in combinacoes_internas_de_6:
                        if combo_6 in self.jogos_proibidos:
                            desdobramento_valido = False
                            break
                    if not desdobramento_valido:
                        break
                
                # 4. Se a base gerou um desdobramento 100% inédito, salva e bloqueia no histórico
                if desdobramento_valido:
                    jogos_validados.extend(bilhetes_gerados)
                    for bilhete in bilhetes_gerados:
                        combinacoes_internas_de_6 = list(itertools.combinations(bilhete, 6))
                        for combo_6 in combinacoes_internas_de_6:
                            self.jogos_proibidos.add(combo_6)
                    break 

        else:
            # Jogo simples (Um único bilhete)
            while len(jogos_validados) < quantidade_pedida:
                if equilibrar:
                    jogo = tuple(self._gerar_base_equilibrada(tamanho_base))
                else:
                    jogo = tuple(sorted(random.sample(range(1, 61), tamanho_base)))
                
                combinacoes_internas = list(itertools.combinations(jogo, 6))
                jogo_valido = True
                
                for combo in combinacoes_internas:
                    if combo in self.jogos_proibidos:
                        jogo_valido = False
                        break
                
                if jogo_valido:
                    jogos_validados.append(jogo)
                    for combo in combinacoes_internas:
                        self.jogos_proibidos.add(combo)

        self._salvar_gerados(jogos_validados)
        return jogos_validados


def menu_interativo():
    print("="*50)
    print("  GERADOR DE JOGOS INÉDITOS - MEGA-SENA")
    print("="*50)
    
    # 1. Tamanho da Base
    tamanho_base = int(input("Quantos números totais você quer no seu fechamento/base? (6 a 15): "))
    if tamanho_base < 6:
        print("Tamanho inválido. Usando o padrão de 6 números.")
        tamanho_base = 6

    tecnica = 'simples'
    tamanho_bilhete = tamanho_base # Por padrão, o bilhete gerado tem o tamanho da base
    
    # 2. Técnica e Tamanho do Bilhete Desdobrado
    if tamanho_base > 6:
        print(f"\nVocê escolheu uma base de {tamanho_base} números.")
        print(f"1. Jogo Único (Gerar 1 único bilhete de {tamanho_base} números)")
        print(f"2. Desdobramento (Gerar vários bilhetes menores combinando esses {tamanho_base} números)")
        resp_tecnica = input("Escolha a técnica (1 ou 2): ")
        
        if resp_tecnica == '2':
            tecnica = 'desdobramento'
            print(f"\nOs bilhetes gerados devem ter no mínimo 6 e no máximo {tamanho_base - 1} números.")
            tamanho_bilhete = int(input("Qual será o tamanho de CADA bilhete gerado?: "))
            
            # Validação do tamanho escolhido
            if tamanho_bilhete < 6 or tamanho_bilhete >= tamanho_base:
                print("Tamanho inválido. Ajustando o desdobramento para bilhetes de 6 números.")
                tamanho_bilhete = 6

    # 3. Equilíbrio
    resp_equilibrio = input("\nDeseja forçar equilíbrio entre dezenas Pares e Ímpares na base? (S/N): ").upper()
    equilibrar = True if resp_equilibrio == 'S' else False

    # Executa o Gerador
    print("\nProcessando cruzamento de dados com a base oficial...")
    gerador = GeradorMegaSenaAvancado('Mega-Sena.csv')
    
    print("\nGerando seus jogos inéditos...")
    jogos = gerador.gerar_jogos(tamanho_base=tamanho_base, tamanho_bilhete=tamanho_bilhete, tecnica=tecnica, equilibrar=equilibrar)
    
    if jogos:
        qtd_dezenas = len(jogos[0])
        print(f"\nSucesso! {len(jogos)} jogo(s) de {qtd_dezenas} dezenas gerado(s):")
        for i, jogo in enumerate(jogos, 1):
            print(f"Jogo {i:02d}: {jogo}")
    else:
        print("\nNenhum jogo pôde ser gerado com esses parâmetros.")

if __name__ == "__main__":
    menu_interativo()
