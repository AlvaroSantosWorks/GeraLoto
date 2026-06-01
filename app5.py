import streamlit as st
import pandas as pd
import random
import itertools
import os
import csv
from sklearn.ensemble import RandomForestRegressor
from sklearn.neighbors import KNeighborsRegressor
from sklearn.neural_network import MLPRegressor

# --- CLASSE DO GERADOR UNIVERSAL COM IA ---
class GeradorLoterias:
    def __init__(self, caminho_historico, total_bolas_sorteadas, faixa_numeros, caminho_gerados):
        self.caminho_historico = caminho_historico
        self.caminho_gerados = caminho_gerados
        self.total_bolas = total_bolas_sorteadas
        self.faixa_numeros = faixa_numeros
        self.historico_lista = [] # Usado para treinar a IA (mantém a ordem temporal)
        self.historico_oficial = self._carregar_historico()
        self.historico_gerados = self._carregar_gerados()
        self.jogos_proibidos = self.historico_oficial.union(self.historico_gerados)

    def obter_ultimo_concurso(self):
        try:
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
        self.historico_lista = []
        if not os.path.exists(self.caminho_historico): return jogos_oficiais
        
        with open(self.caminho_historico, mode='r', encoding='latin1') as ficheiro:
            leitor = csv.DictReader(ficheiro, delimiter=',')
            if 'Bola1' not in leitor.fieldnames:
                ficheiro.seek(0)
                leitor = csv.DictReader(ficheiro, delimiter=';')

            for linha in leitor:
                try:
                    jogo = []
                    for i in range(1, self.total_bolas + 1):
                        jogo.append(int(linha[f'Bola{i}']))
                    
                    jogo_ordenado = tuple(sorted(jogo))
                    jogos_oficiais.add(jogo_ordenado)
                    self.historico_lista.append(list(jogo_ordenado))
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
        
        qtd_pares = min(tamanho // 2, len(pares))
        qtd_impares = tamanho - qtd_pares
        
        if qtd_impares > len(impares):
            qtd_impares = len(impares)
            qtd_pares = tamanho - qtd_impares

        escolhidos = random.sample(pares, qtd_pares) + random.sample(impares, qtd_impares)
        return sorted(escolhidos)

    def _gerar_base_com_ml(self, tamanho_base, modelo_escolhido):
        if len(self.historico_lista) < 10:
            st.warning("Histórico insuficiente para usar Inteligência Artificial. Usando método aleatório.")
            return sorted(random.sample(range(1, self.faixa_numeros + 1), tamanho_base))

        # Prepara os dados: Usa o sorteio atual para prever o próximo
        X = self.historico_lista[:-1]
        y = self.historico_lista[1:]
        ultimo_sorteio = [self.historico_lista[-1]]

        # Escolha do Modelo
        if modelo_escolhido == "Random Forest":
            modelo = RandomForestRegressor(n_estimators=50, random_state=42)
        elif modelo_escolhido == "KNN (Vizinhos Próximos)":
            modelo = KNeighborsRegressor(n_neighbors=5)
        elif modelo_escolhido == "Rede Neural (MLP)":
            modelo = MLPRegressor(hidden_layer_sizes=(50, 50), max_iter=500, random_state=42)
        else:
            modelo = RandomForestRegressor() # Default

        # Treinamento e Previsão
        modelo.fit(X, y)
        previsao = modelo.predict(ultimo_sorteio)[0]

        # Pós-processamento: Arredondar os números, garantir que estão dentro da faixa e não são repetidos
        numeros_preditos = set()
        for p in previsao:
            num = int(round(p))
            num = max(1, min(self.faixa_numeros, num)) # Garante que está entre 1 e o máximo
            numeros_preditos.add(num)

        # Se faltar números (por conta de números arredondados iguais), completamos com aleatórios
        while len(numeros_preditos) < tamanho_base:
            numeros_preditos.add(random.randint(1, self.faixa_numeros))
            
        # Se passar do tamanho da base (caso raro), cortamos
        return sorted(list(numeros_preditos))[:tamanho_base]

    def gerar_jogos(self, tamanho_base, tamanho_bilhete, tecnica='simples', equilibrar=False, usar_ml=False, modelo_ml=None, quantidade_pedida=1):
        jogos_validados = []
        
        if tecnica == 'desdobramento' and tamanho_base > self.total_bolas:
            tentativas = 0
            while len(jogos_validados) < quantidade_pedida and tentativas < 1000:
                tentativas += 1
                
                if usar_ml: base = self._gerar_base_com_ml(tamanho_base, modelo_ml)
                else: base = self._gerar_base_equilibrada(tamanho_base) if equilibrar else sorted(random.sample(range(1, self.faixa_numeros + 1), tamanho_base))
                
                possiveis = list(itertools.combinations(base, tamanho_bilhete))
                
                if not any(any(combo in self.jogos_proibidos for combo in itertools.combinations(b, self.total_bolas)) for b in possiveis):
                    jogos_validados.extend(possiveis)
                    for b in possiveis:
                        for c in itertools.combinations(b, self.total_bolas): self.jogos_proibidos.add(c)
        else:
            while len(jogos_validados) < quantidade_pedida:
                
                if usar_ml: jogo = tuple(self._gerar_base_com_ml(tamanho_base, modelo_ml))
                else: jogo = tuple(self._gerar_base_equilibrada(tamanho_base)) if equilibrar else tuple(sorted(random.sample(range(1, self.faixa_numeros + 1), tamanho_base)))
                
                if not any(combo in self.jogos_proibidos for combo in itertools.combinations(jogo, self.total_bolas)):
                    jogos_validados.append(jogo)
                    for c in itertools.combinations(jogo, self.total_bolas): self.jogos_proibidos.add(c)
        
        self._salvar_gerados(jogos_validados)
        return jogos_validados

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Gerador de Loterias com IA", page_icon="🎲")
st.title("🎲 Gerador de Jogos com IA")

# Menu Lateral
modalidade = st.sidebar.selectbox("Escolha a Modalidade:", ["Mega-Sena", "Lotofácil"])
modo_geracao = st.sidebar.radio("Motor de Geração:", ["Tradicional / Aleatório", "Inteligência Artificial 🧠"])

if modalidade == "Mega-Sena":
    arquivo_selecionado = "Mega-Sena.csv"
    arquivo_gerados = "jogos_ja_gerados_mega.csv"
    total_bolas = 6; faixa_maxima = 60; min_permitido = 6; max_permitido = 20
else:
    arquivo_selecionado = "Lotofacil.csv" 
    arquivo_gerados = "jogos_ja_gerados_lotofacil.csv"
    total_bolas = 15; faixa_maxima = 25; min_permitido = 15; max_permitido = 20

@st.cache_resource
def carregar_gerador(caminho, bolas, faixa, arq_gerados):
    return GeradorLoterias(caminho, bolas, faixa, arq_gerados)

if not os.path.exists(arquivo_selecionado):
    st.error(f"Erro: O arquivo '{arquivo_selecionado}' não foi encontrado.")
else:
    gerador = carregar_gerador(arquivo_selecionado, total_bolas, faixa_maxima, arquivo_gerados)

    ultimo = gerador.obter_ultimo_concurso()
    st.info(f"Último concurso analisado ({modalidade}): **{ultimo}**")

    # Configurações do Jogo
    st.subheader("Configurações do Jogo")
    tamanho_base = st.slider("Quantos números totais na base?", min_permitido, max_permitido, min_permitido)
    tecnica = st.radio("Escolha a técnica:", ["Jogo Único", "Desdobramento"])
    
    tamanho_bilhete = min_permitido
    if tecnica == "Desdobramento":
        tamanho_bilhete = st.number_input("Tamanho de cada bilhete?", min_permitido, tamanho_base - 1, min_permitido)

    # Controles condicionais do modo de geração
    equilibrar = False
    modelo_escolhido = None
    usar_ml = False

    if modo_geracao == "Tradicional / Aleatório":
        equilibrar = st.checkbox("Forçar equilíbrio Pares/Ímpares?")
    else:
        usar_ml = True
        st.markdown("---")
        st.markdown("### 🧠 Configurações da Inteligência Artificial")
        st.caption("A IA analisará todos os sorteios passados para tentar prever os próximos números.")
        modelo_escolhido = st.selectbox(
            "Escolha o Algoritmo Preditivo:", 
            ["Random Forest", "KNN (Vizinhos Próximos)", "Rede Neural (MLP)"]
        )
        if modelo_escolhido == "Rede Neural (MLP)":
            st.info("A Rede Neural pode levar alguns segundos a mais para treinar. Aguarde!")

    st.markdown("---")
    
    # Botões de Ação
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Gerar Jogos 🚀", use_container_width=True):
            with st.spinner('Analisando e gerando números...'):
                jogos = gerador.gerar_jogos(tamanho_base, tamanho_bilhete, tecnica.lower().replace(" ", "_"), equilibrar, usar_ml, modelo_escolhido)
                if jogos:
                    st.success(f"Sucesso! {len(jogos)} jogo(s) gerado(s):")
                    st.table(pd.DataFrame(jogos, columns=[f"Bola {i}" for i in range(1, tamanho_bilhete + 1)]))
                else:
                    st.error("Não foi possível gerar novos jogos inéditos com essa base.")
    with col2:
        if st.button("🗑️ Apagar histórico de jogos gerados", use_container_width=True):
            if gerador.resetar_gerados(): st.success("Histórico apagado!")
            else: st.warning("Nenhum histórico para apagar.")
