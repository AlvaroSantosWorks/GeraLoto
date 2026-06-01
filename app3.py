import streamlit as st
import pandas as pd
import random
import itertools
import os
import csv

# --- CLASSE DO GERADOR ---
class GeradorMegaSenaAvancado:
    def __init__(self, caminho_historico, caminho_gerados='jogos_ja_gerados.csv'):
        self.caminho_historico = caminho_historico
        self.caminho_gerados = caminho_gerados
        self.historico_oficial = self._carregar_historico()
        self.historico_gerados = self._carregar_gerados()
        self.jogos_proibidos = self.historico_oficial.union(self.historico_gerados)

    def obter_ultimo_concurso(self):
        try:
            # Tentamos ler especificando que o separador é o ponto e vírgula
            # Se ainda der erro, podemos tentar sep='\t' (tabulação)
            df = pd.read_csv(self.caminho_historico, encoding='latin1', sep=';', header=0)
            
            # Pega a primeira coluna
            coluna_zero = df.iloc[:, 0].dropna().astype(str)
            
            # Remove linhas que sejam apenas espaços em branco
            limpo = coluna_zero[coluna_zero.str.strip() != '']
            
            return limpo.iloc[-1]
        except Exception as e:
            # Caso o ponto e vírgula também falhe, vamos ver o erro
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
            leitor = csv.DictReader(ficheiro, delimiter=',')
            for linha in leitor:
                try:
                    jogo = tuple(sorted([int(linha['Bola1']), int(linha['Bola2']), int(linha['Bola3']),
                                         int(linha['Bola4']), int(linha['Bola5']), int(linha['Bola6'])]))
                    jogos_oficiais.add(jogo)
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
        pares = [n for n in range(2, 61, 2)]
        impares = [n for n in range(1, 61, 2)]
        escolhidos = random.sample(pares, tamanho // 2) + random.sample(impares, tamanho - (tamanho // 2))
        return sorted(escolhidos)

    def gerar_jogos(self, tamanho_base=6, tamanho_bilhete=6, tecnica='simples', equilibrar=False, quantidade_pedida=1):
        jogos_validados = []
        if tecnica == 'desdobramento' and tamanho_base > 6:
            tentativas = 0
            while len(jogos_validados) < quantidade_pedida and tentativas < 1000:
                tentativas += 1
                base = self._gerar_base_equilibrada(tamanho_base) if equilibrar else sorted(random.sample(range(1, 61), tamanho_base))
                possiveis = list(itertools.combinations(base, tamanho_bilhete))
                if not any(any(combo in self.jogos_proibidos for combo in itertools.combinations(b, 6)) for b in possiveis):
                    jogos_validados.extend(possiveis)
                    for b in possiveis:
                        for c in itertools.combinations(b, 6): self.jogos_proibidos.add(c)
        else:
            while len(jogos_validados) < quantidade_pedida:
                jogo = tuple(self._gerar_base_equilibrada(tamanho_base)) if equilibrar else tuple(sorted(random.sample(range(1, 61), tamanho_base)))
                if not any(combo in self.jogos_proibidos for combo in itertools.combinations(jogo, 6)):
                    jogos_validados.append(jogo)
                    for c in itertools.combinations(jogo, 6): self.jogos_proibidos.add(c)
        self._salvar_gerados(jogos_validados)
        return jogos_validados

# --- INTERFACE STREAMLIT ---
st.title("🎲 Gerador de Jogos")

# Menu Lateral de Modalidades
modalidade = st.sidebar.selectbox("Escolha a Modalidade:", ["Mega-Sena"])
arquivo_selecionado = "Mega-Sena.csv"

@st.cache_resource
def carregar_gerador(caminho):
    return GeradorMegaSenaAvancado(caminho)

# Verifica se o arquivo existe antes de carregar
if not os.path.exists(arquivo_selecionado):
    st.error(f"Erro: O arquivo '{arquivo_selecionado}' não foi encontrado na pasta.")
else:
    gerador = carregar_gerador(arquivo_selecionado)

    # 1. Mostrar o último concurso
    ultimo = gerador.obter_ultimo_concurso()
    st.info(f"Último concurso na base: **{ultimo}**")

    if st.button("Apagar jogos anteriores e começar do zero"):
        if gerador.resetar_gerados(): st.success("Histórico apagado!")
        else: st.warning("Nenhum histórico para apagar.")

    tamanho_base = st.slider("Quantos números totais na base?", 6, 15, 6)
    tecnica = st.radio("Escolha a técnica:", ["Jogo Único", "Desdobramento"])
    tamanho_bilhete = 6
    if tecnica == "Desdobramento":
        tamanho_bilhete = st.number_input("Tamanho de cada bilhete?", 6, tamanho_base - 1, 6)

    equilibrar = st.checkbox("Forçar equilíbrio Pares/Ímpares?")

    if st.button("Gerar Jogos"):
        jogos = gerador.gerar_jogos(tamanho_base, tamanho_bilhete, tecnica.lower().replace(" ", "_"), equilibrar)
        if jogos:
            st.success(f"Sucesso! {len(jogos)} jogo(s) gerado(s):")
            st.table(pd.DataFrame(jogos))
        else:
            st.error("Não foi possível gerar novos jogos inéditos com essa base.")
