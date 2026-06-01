import streamlit as st
import pandas as pd
import random
import itertools
import os
import csv

# --- CLASSE DO GERADOR ---
class GeradorMegaSenaAvancado:
    def __init__(self, caminho_historico, caminho_gerados='jogos_gerados.csv'):
        self.caminho_historico = caminho_historico
        self.caminho_gerados = caminho_gerados
        self.historico_oficial = self._carregar_historico()
        self.jogos_proibidos = self.historico_oficial.union(self._carregar_gerados())

    def obter_ultimo_sorteio(self):
        """Lê o número do último sorteio (primeira coluna do CSV)."""
        try:
            df = pd.read_csv(self.caminho_historico, encoding='latin1')
            return df.iloc[-1, 0] # Pega o valor da última linha, primeira coluna
        except:
            return "Indisponível"

    def resetar_gerados(self):
        if os.path.exists(self.caminho_gerados):
            os.remove(self.caminho_gerados)
            return True
        return False

    def _carregar_historico(self):
        jogos_oficiais = set()
        if not os.path.exists(self.caminho_historico): return jogos_oficiais
        # Ajuste: lendo as colunas de 'Bola1' a 'Bola6'
        df = pd.read_csv(self.caminho_historico, encoding='latin1')
        cols = ['Bola1', 'Bola2', 'Bola3', 'Bola4', 'Bola5', 'Bola6']
        for _, row in df.iterrows():
            try: jogos_oficiais.add(tuple(sorted([int(row[c]) for c in cols])))
            except: continue
        return jogos_oficiais

    def _carregar_gerados(self):
        if os.path.exists(self.caminho_gerados):
            df = pd.read_csv(self.caminho_gerados)
            return set(tuple(sorted(x)) for x in df.values)
        return set()

    def gerar_jogos(self, tamanho_base, tamanho_bilhete, equilibrar, qtd=1):
        # Lógica simplificada para exemplo
        jogos = []
        tentativas = 0
        while len(jogos) < qtd and tentativas < 500:
            tentativas += 1
            base = sorted(random.sample(range(1, 61), tamanho_base))
            bilhete = tuple(sorted(random.sample(base, tamanho_bilhete)))
            if bilhete not in self.jogos_proibidos:
                jogos.append(bilhete)
                self.jogos_proibidos.add(bilhete)
        return jogos

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Gerador de Loteria")
st.title("🎲 Gerador de Jogos")

st.write("---")
st.write("Diagnóstico de erro:")
st.write(f"Pasta atual onde o script está rodando: {os.getcwd()}")
arquivos_na_pasta = os.listdir()
st.write(f"Arquivos que o Python consegue ver nesta pasta: {arquivos_na_pasta}")
st.write("---")

# 1. Menu Lateral para escolha da modalidade
#modalidade = st.sidebar.selectbox("Escolha a Loteria:", ["Mega-Sena", "Lotofácil"])
# Deixe apenas o que você sabe que existe na pasta por enquanto:
modalidade = st.sidebar.selectbox(
    "Escolha a Modalidade:", 
    ["Mega-Sena"] 
)

# Mapeamento de arquivos (Certifique-se de ter esses arquivos na pasta!)
arquivos = {
    "Mega-Sena": r"C:\MegaSena\Mega-Sena.csv",
    "Lotofácil": r"C:\MegaSena\Lotofacil.csv",
    "Quina": r"C:\MegaSena\Quina.csv"
}
arquivo_csv = arquivos[modalidade]

@st.cache_resource
def carregar_gerador(arq):
    return GeradorMegaSenaAvancado(arq)

try:
    gerador = carregar_gerador(arquivo_csv)
    
    # 2. Informar último sorteio
    ultimo = gerador.obter_ultimo_sorteio()
    st.info(f"📊 Base atual: **{modalidade}** | Último sorteio registrado: **{ultimo}**")

    if st.sidebar.button("Resetar Histórico de Jogos"):
        gerador.resetar_gerados()
        st.success("Histórico limpo!")

    # Controles
    tamanho_base = st.slider("Números na base:", 6, 15, 6)
    equilibrar = st.checkbox("Forçar equilíbrio Pares/Ímpares?")

    if st.button("Gerar Jogos"):
        jogos = gerador.gerar_jogos(tamanho_base, 6, equilibrar)
        if jogos:
            st.table(pd.DataFrame(jogos, columns=[f"B{i}" for i in range(1, 7)]))
        else:
            st.error("Não foi possível gerar.")

except Exception as e:
    st.error(f"Erro ao carregar o arquivo da {modalidade}. Verifique se o arquivo '{arquivo_csv}' existe.")
