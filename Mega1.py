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
                # O bloco 'with' garante que o ficheiro é fechado da memória corretamente
                with open(self.caminho_historico, mode='r', encoding='latin1') as ficheiro:
                    leitor = csv.DictReader(ficheiro, delimiter=',')
                    
                    for linha in leitor:
                        try:
                            # Extrai e converte unicamente as colunas das bolas
                            jogo = tuple(sorted([
                                int(linha['Bola1']), int(linha['Bola2']), int(linha['Bola3']),
                                int(linha['Bola4']), int(linha['Bola5']), int(linha['Bola6'])
                            ]))
                            jogos_oficiais.add(jogo)
                        except (ValueError, KeyError, TypeError):
                            # Se uma linha estiver corrompida, vazia ou tiver texto em vez de número,
                            # o código salta essa linha silenciosamente e avança para o próximo jogo.
                            continue
                            
                return jogos_oficiais
            except Exception as e:
                print(f"Aviso: Não foi possível carregar o histórico oficial. ({e})")
                return set()

    def _carregar_gerados(self):
            jogos = set()
            if os.path.exists(self.caminho_gerados):
                # Usando a biblioteca nativa csv para ler linhas de qualquer tamanho sem erros
                with open(self.caminho_gerados, mode='r', encoding='utf-8') as f:
                    leitor = csv.reader(f)
                    for linha in leitor:
                        if not linha: 
                            continue
                        # Ignora a linha de cabeçalho
                        if 'Bola' in str(linha[0]): 
                            continue
                        try:
                            # Converte a linha de tamanho variável (6, 8, 10...) para inteiros e salva no set
                            jogo = tuple(sorted([int(x) for x in linha]))
                            jogos.add(jogo)
                        except ValueError:
                            continue
            return jogos

    def _salvar_gerados(self, novos_jogos):
        if not novos_jogos: 
            return
            
        arquivo_existe = os.path.exists(self.caminho_gerados)
        
        # Abre o arquivo em modo append ('a') para adicionar linhas ao final
        with open(self.caminho_gerados, mode='a', newline='', encoding='utf-8') as f:
            escritor = csv.writer(f)
            
            if not arquivo_existe:
                # Pega o tamanho do primeiro jogo gerado para criar as colunas do cabeçalho dinamicamente
                qtd_bolas = len(novos_jogos[0])
                cabecalho = [f'Bola{i}' for i in range(1, qtd_bolas + 1)]
                escritor.writerow(cabecalho)
                
            for jogo in novos_jogos:
                escritor.writerow(jogo)

    def _gerar_base_equilibrada(self, tamanho):
        """Gera um conjunto de dezenas equilibrando pares e ímpares."""
        pares_disponiveis = [n for n in range(2, 61, 2)]
        impares_disponiveis = [n for n in range(1, 61, 2)]
        
        # Define a quantidade de pares e ímpares (metade para cada, ajustando se o tamanho for ímpar)
        qtd_pares = tamanho // 2
        qtd_impares = tamanho - qtd_pares

        escolhidos = random.sample(pares_disponiveis, qtd_pares) + random.sample(impares_disponiveis, qtd_impares)
        return sorted(escolhidos)

    def gerar_jogos(self, tamanho_fechamento=6, tecnica='simples', equilibrar=False, quantidade_pedida=1):
            """
            Gera jogos baseados nas escolhas do usuário.
            tecnica: 'simples' (apenas gera 1 bilhete do tamanho escolhido) ou 'desdobramento' (combinações de 6).
            """
            jogos_validados = []

            if tecnica == 'desdobramento' and tamanho_fechamento > 6:
                while len(jogos_validados) < quantidade_pedida: 
                    if equilibrar:
                        base = self._gerar_base_equilibrada(tamanho_fechamento)
                    else:
                        base = sorted(random.sample(range(1, 61), tamanho_fechamento))
                    
                    combinacoes = list(itertools.combinations(base, 6))
                    
                    desdobramento_valido = True
                    for combo in combinacoes:
                        if combo in self.jogos_proibidos:
                            desdobramento_valido = False
                            break
                    
                    if desdobramento_valido:
                        jogos_validados.extend(combinacoes)
                        for combo in combinacoes:
                            self.jogos_proibidos.add(combo)
                        break 

            else:
                # Jogo simples (Um bilhete único que pode ter de 6 a 15 números)
                while len(jogos_validados) < quantidade_pedida:
                    # Correção: Agora usa tamanho_fechamento em vez do número 6 fixo
                    if equilibrar:
                        jogo = tuple(self._gerar_base_equilibrada(tamanho_fechamento))
                    else:
                        jogo = tuple(sorted(random.sample(range(1, 61), tamanho_fechamento)))
                    
                    # Checagem de ineditismo: garante que nenhuma combinação de 6 dentro desse bilhete já saiu
                    combinacoes_internas = list(itertools.combinations(jogo, 6))
                    jogo_valido = True
                    
                    for combo in combinacoes_internas:
                        if combo in self.jogos_proibidos:
                            jogo_valido = False
                            break
                    
                    if jogo_valido:
                        jogos_validados.append(jogo)
                        # Bloqueia todas as sub-combinações de 6 desse jogo gerado
                        for combo in combinacoes_internas:
                            self.jogos_proibidos.add(combo)

            self._salvar_gerados(jogos_validados)
            return jogos_validados

def menu_interativo():
    print("="*40)
    print("GERADOR DE JOGOS INÉDITOS - MEGA-SENA")
    print("="*40)
    
    # 1. Tamanho do Fechamento
    tamanho = int(input("Quantos números você quer no seu fechamento/base? (6 a 10): "))
    if tamanho < 6 or tamanho > 10:
        print("Tamanho inválido. Usando o padrão de 6 números.")
        tamanho = 6

    # 2. Técnica
    tecnica = 'simples'
    if tamanho > 6:
        print("\nVocê escolheu mais de 6 números.")
        print("1. Jogo Único (Um bilhete caro com múltiplos números)")
        print("2. Desdobramento (Gerar bilhetes de 6 números combinando sua base)")
        resp_tecnica = input("Escolha a técnica (1 ou 2): ")
        if resp_tecnica == '2':
            tecnica = 'desdobramento'

    # 3. Equilíbrio
    resp_equilibrio = input("\nDeseja forçar equilíbrio entre dezenas Pares e Ímpares? (S/N): ").upper()
    equilibrar = True if resp_equilibrio == 'S' else False

    # Executa o Gerador
    print("\nProcessando cruzamento de dados com a base oficial...")
    gerador = GeradorMegaSenaAvancado('Mega-Sena.csv')
    
    print("\nGerando seus jogos inéditos...")
    jogos = gerador.gerar_jogos(tamanho_fechamento=tamanho, tecnica=tecnica, equilibrar=equilibrar)
        
    if jogos:
        # Pega a quantidade de números do primeiro jogo da lista para a mensagem
        qtd_dezenas = len(jogos[0]) 
        print(f"\nSucesso! {len(jogos)} jogo(s) de {qtd_dezenas} dezenas gerado(s):")
        for i, jogo in enumerate(jogos, 1):
            print(f"Jogo {i:02d}: {jogo}")
    else:
        print("\nNenhum jogo pôde ser gerado com esses parâmetros.")

if __name__ == "__main__":
    menu_interativo()
