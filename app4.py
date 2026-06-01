import streamlit as st
import pandas as pd
import random
import itertools
import os
import csv

# --- CLASSE DO GERADOR (AGORA UNIVERSAL) ---
class GeradorLoterias:
    def __init__(self, caminho_historico, total_bolas_sorteadas, faixa_numeros, caminho_gerados):
        self.caminho_historico = caminho_historico
        self.caminho_gerados = caminho_gerados
        self.total_bolas = total_bolas_sorteadas
        self.faixa_numeros = faixa_numeros
        self.historico_oficial = self._carregar_historico()
        self.historico_gerados = self._carregar_gerados()
        self.jogos_proibidos = self.historico_oficial.union(self.historico_gerados)

    def obter_ultimo_concurso(self):
        try:
            # Tenta ler especificando a vírgula (Lotofácil) ou ponto e vírgula (Mega)
            try:
                df = pd.read_csv(self.caminho_historico, encoding='latin1', sep=',', header=0)
            except:
                df = pd.read_csv(self.caminho_historico, encoding='latin1', sep=';', header=0)
            
            coluna_zero = df.iloc[:, 0].dropna().astype(str)
            limpo = coluna_zero[coluna_zero.str.strip() != '']
            return limpo.iloc[-1]
        except Exception as e:
            return f"Erro: {e}"

    def resetar_gerados(self):
        if os.path.exists(self.caminho_gerados):
            os.remove(self.caminho_gerados)
            self.historico_gerados = set()
            self.jogos_proibidos = self.historico_oficial 
            return True
        return False

    def _carregar_historico(self):
        jogos_oficiais = set()
        if not os.path.exists(self.caminho_historico): return jogos_oficiais
        with open(self.caminho_historico, mode='r', encoding='latin1') as ficheiro:
            # Lendo as colunas Bola1 até BolaN dinamicamente
            leitor = csv.DictReader(ficheiro, delimiter=',')
            if 'Bola1' not in leitor.fieldnames:
                # Retentativa caso seja separado por ;
                ficheiro.seek(0)
                leitor = csv.DictReader(ficheiro, delimiter=';')

            for linha in leitor:
                try:
                    jogo = []
                    for i in range(1, self.total_bolas + 1):
                        jogo.append(int(linha[f'Bola{i}']))
                    jogos_oficiais.add(tuple(sorted(jogo)))
                except: continue
        return jogos_oficiais

    def _carregar_gerados(self):
        jogos = set()
        if os.path.exists(self.caminho_gerados):
            with open(self.caminho_gerados, mode='r', encoding='utf-8') as f:
                for linha in csv.reader(f):
                    if not linha or 'Bola' in str(linha[0]): continue
                    try: jogos.add(tuple(sorted([int(x) for x in linha])))
                    except: continue
        return jogos

    def _salvar_gerados(self, novos_jogos):
        if not novos_jogos: return
        arquivo_existe = os.path.exists(self.caminho_gerados)
        with open(self.caminho_gerados, mode='a', newline='', encoding='utf-8') as f:
            escritor = csv.writer(f)
            if not arquivo_existe:
                escritor.writerow([f'Bola{i}' for i in range(1, len(novos_jogos[0]) + 1)])
            for jogo in novos_jogos: escritor.writerow(jogo)

    def _gerar_base_equilibrada(self, tamanho):
        pares = [n for n in range(2, self.faixa_numeros + 1, 2)]
        impares = [n for n in range(1, self.faixa_numeros + 1, 2)]
        
        # Balanceamento inteligente para não estourar o limite da lotofácil (ex: só tem 12 pares totais)
        qtd_pares = min(tamanho // 2, len(pares))
        qtd_impares = tamanho - qtd_pares
        
        # Ajuste se a quantidade de ímpares solicitada for maior do que existe
        if qtd_impares > len(impares):
            qtd_impares = len(impares)
            qtd_pares = tamanho - qtd_impares

        escolhidos = random.sample(pares, qtd_pares) + random.sample(impares, qtd_impares)
        return sorted(escolhidos)

    def gerar_jogos(self, tamanho_base, tamanho_bilhete, tecnica='simples', equilibrar=False, quantidade_pedida=1):
        jogos_validados = []
        if tecnica == 'desdobramento' and tamanho_base > self.total_bolas:
            tentativas = 0
            while len(jogos_validados) < quantidade_pedida and tentativas < 1000:
                tentativas += 1
                base = self._gerar_base_equilibrada(tamanho_base) if equilibrar else sorted(random.sample(range(1, self.faixa_numeros + 1), tamanho_base))
                possiveis = list(itertools.combinations(base, tamanho_bilhete))
                
                # Garante que nenhum jogo base existe no histórico oficial/gerado
                if not any(any(combo in self.jogos_proibidos for combo in itertools.combinations(b, self.total_bolas)) for b in possiveis):
                    jogos_validados.extend(possiveis)
                    for b in possiveis:
                        for c in itertools.combinations(b, self.total_bolas): self.jogos_proibidos.add(c)
        else:
            while len(jogos_validados) < quantidade_pedida:
                jogo = tuple(self._gerar_base_equilibrada(tamanho_base)) if equilibrar else tuple(sorted(random.sample(range(1, self.faixa_numeros + 1), tamanho_base)))
                if not any(combo in self.jogos_proibidos for combo in itertools.combinations(jogo, self.total_bolas)):
                    jogos_validados.append(jogo)
                    for c in itertools.combinations(jogo, self.total_bolas): self.jogos_proibidos.add(c)
        
        self._salvar_gerados(jogos_validados)
        return jogos_validados

# --- INTERFACE STREAMLIT ---
st.title("🎲 Gerador de Jogos - Loterias")

# Menu Lateral de Modalidades
modalidade = st.sidebar.selectbox("Escolha a Modalidade:", ["Mega-Sena", "Lotofácil"])

# Ajusta as configurações com base na loteria escolhida
if modalidade == "Mega-Sena":
    arquivo_selecionado = "Mega-Sena.csv"
    arquivo_gerados = "jogos_ja_gerados_mega.csv"
    total_bolas = 6
    faixa_maxima = 60
    min_permitido = 6
    max_permitido = 20
else:
    arquivo_selecionado = "Lotofacil.csv" 
    arquivo_gerados = "jogos_ja_gerados_lotofacil.csv"
    total_bolas = 15
    faixa_maxima = 25
    min_permitido = 15
    max_permitido = 20 # Limite da Lotofácil são apostas de até 20 números

@st.cache_resource
def carregar_gerador(caminho, bolas, faixa, arq_gerados):
    return GeradorLoterias(caminho, bolas, faixa, arq_gerados)

# Verifica se o arquivo existe antes de carregar
if not os.path.exists(arquivo_selecionado):
    st.error(f"Erro: O arquivo '{arquivo_selecionado}' não foi encontrado na pasta.")
    st.info("Coloque o arquivo csv correspondente na mesma pasta do código.")
else:
    gerador = carregar_gerador(arquivo_selecionado, total_bolas, faixa_maxima, arquivo_gerados)

    # 1. Mostrar o último concurso
    ultimo = gerador.obter_ultimo_concurso()
    st.info(f"Último concurso na base ({modalidade}): **{ultimo}**")

    if st.button("Apagar jogos anteriores e começar do zero"):
        if gerador.resetar_gerados(): st.success("Histórico apagado!")
        else: st.warning("Nenhum histórico para apagar.")

    tamanho_base = st.slider(f"Quantos números totais na base?", min_permitido, max_permitido, min_permitido)
    tecnica = st.radio("Escolha a técnica:", ["Jogo Único", "Desdobramento"])
    
    tamanho_bilhete = min_permitido
    if tecnica == "Desdobramento":
        tamanho_bilhete = st.number_input("Tamanho de cada bilhete?", min_permitido, tamanho_base - 1, min_permitido)

    equilibrar = st.checkbox("Forçar equilíbrio Pares/Ímpares?")

    if st.button("Gerar Jogos"):
        jogos = gerador.gerar_jogos(tamanho_base, tamanho_bilhete, tecnica.lower().replace(" ", "_"), equilibrar)
        if jogos:
            st.success(f"Sucesso! {len(jogos)} jogo(s) gerado(s):")
            st.table(pd.DataFrame(jogos, columns=[f"Bola {i}" for i in range(1, tamanho_bilhete + 1)]))
        else:
            st.error("Não foi possível gerar novos jogos inéditos com essa base.")
