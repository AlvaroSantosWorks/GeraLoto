import streamlit as st
import pandas as pd
import random
import itertools
import os
import csv
import requests
from sklearn.ensemble import RandomForestRegressor
from sklearn.neighbors import KNeighborsRegressor
from sklearn.neural_network import MLPRegressor

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="GeraLoto - Premium", page_icon="🎲")

# --- CHAVE DE API DO FIREBASE ---
FIREBASE_WEB_API_KEY = "AIzaSyARvB207Vwg3ghFq5MDi-YVKjBKpXM7evg"

# --- FUNÇÕES DE AUTENTICAÇÃO (REST API DO FIREBASE) ---
def registar_utilizador(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_WEB_API_KEY}"
    payload = {"email": email, "password": password, "returnSecureToken": True}
    resposta = requests.post(url, json=payload)
    return resposta.json()

def iniciar_sessao(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_WEB_API_KEY}"
    payload = {"email": email, "password": password, "returnSecureToken": True}
    resposta = requests.post(url, json=payload)
    return resposta.json()

# ==========================================
# ECRÃ DE LOGIN / REGISTO
# ==========================================
if "user_uid" not in st.session_state:
    st.title("🔒 Bem-vindo ao GeraLoto")
    st.write("Inicie sessão ou crie uma conta para aceder ao sistema de previsões.")
    
    escolha = st.radio("Selecione uma opção:", ["Iniciar Sessão", "Criar Conta Nova"])
    
    email_input = st.text_input("E-mail")
    senha_input = st.text_input("Palavra-passe (Mínimo 6 caracteres)", type="password")
    
    if escolha == "Criar Conta Nova":
        if st.button("Registar Conta"):
            if len(senha_input) < 6:
                st.error("A palavra-passe deve ter pelo menos 6 caracteres.")
            else:
                with st.spinner("A criar conta..."):
                    resultado = registar_utilizador(email_input, senha_input)
                    if "error" in resultado:
                        erro = resultado["error"]["message"]
                        if erro == "EMAIL_EXISTS": st.error("Este e-mail já está registado!")
                        elif erro == "INVALID_EMAIL": st.error("Formato de e-mail inválido!")
                        else: st.error(f"Erro: {erro}")
                    else:
                        st.success("Conta criada com sucesso! Pode iniciar sessão agora.")
                        
    elif escolha == "Iniciar Sessão":
        if st.button("Entrar no Sistema"):
            with st.spinner("A autenticar..."):
                resultado = iniciar_sessao(email_input, senha_input)
                if "error" in resultado:
                    erro = resultado["error"]["message"]
                    if erro == "INVALID_LOGIN_CREDENTIALS": st.error("E-mail ou palavra-passe incorretos!")
                    elif erro == "INVALID_EMAIL": st.error("Formato de e-mail inválido!")
                    else: st.error("Credenciais inválidas ou conta inexistente.")
                else:
                    # Sucesso no login - guarda os dados na sessão
                    st.session_state["user_uid"] = resultado["localId"]
                    st.session_state["user_email"] = resultado["email"]
                    st.rerun()
                    
    st.stop() # Bloqueia o resto da aplicação até o utilizador fazer login


# ==========================================
# PAINEL DO UTILIZADOR LOGADO (BARRA LATERAL)
# ==========================================
st.sidebar.title("👤 O seu Perfil")
st.sidebar.success(f"**Utilizador:**\n{st.session_state['user_email']}")

# SISTEMA DE FICHAS PROVISÓRIO (Ainda na memória)
if "fichas" not in st.session_state:
    st.session_state["fichas"] = 1000

st.sidebar.info(f"🪙 **Saldo:** {st.session_state['fichas']} fichas")

if st.sidebar.button("🚪 Terminar Sessão (Logout)"):
    st.session_state.clear()
    st.rerun()

st.sidebar.markdown("---")


# ==========================================
# MOTOR DO GERADOR DE LOTARIAS
# ==========================================
class GeradorLoterias:
    def __init__(self, caminho_historico, total_bolas_sorteadas, faixa_numeros, caminho_gerados):
        self.caminho_historico = caminho_historico
        self.caminho_gerados = caminho_gerados
        self.total_bolas = total_bolas_sorteadas
        self.faixa_numeros = faixa_numeros
        self.historico_lista = [] 
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
        except Exception as e: return f"Erro: {e}"

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
                    for i in range(1, self.total_bolas + 1): jogo.append(int(linha[f'Bola{i}']))
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
        if len(self.historico_lista) < 10: return sorted(random.sample(range(1, self.faixa_numeros + 1), tamanho_base))
        X = self.historico_lista[:-1]
        y = self.historico_lista[1:]
        ultimo_sorteio = [self.historico_lista[-1]]

        if modelo_escolhido == "Random Forest": modelo = RandomForestRegressor(n_estimators=50, random_state=42)
        elif modelo_escolhido == "KNN (Vizinhos Próximos)": modelo = KNeighborsRegressor(n_neighbors=5)
        elif modelo_escolhido == "Rede Neural (MLP)": modelo = MLPRegressor(hidden_layer_sizes=(50, 50), max_iter=500, random_state=42)
        else: modelo = RandomForestRegressor()

        modelo.fit(X, y)
        previsao = modelo.predict(ultimo_sorteio)[0]

        numeros_preditos = set()
        for p in previsao:
            num = int(round(p))
            num = max(1, min(self.faixa_numeros, num))
            numeros_preditos.add(num)

        while len(numeros_preditos) < tamanho_base: numeros_preditos.add(random.randint(1, self.faixa_numeros))
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

# --- INTERFACE PRINCIPAL DO GERADOR ---
st.title("🎲 Gerador de Jogos com IA")

modalidade = st.sidebar.selectbox("Escolha a Modalidade:", ["Mega-Sena", "Lotofácil"])
modo_geracao = st.sidebar.radio("Motor de Geração:", ["Tradicional / Aleatório", "Inteligência Artificial 🧠"])

if modalidade == "Mega-Sena":
    arquivo_selecionado = "Mega-Sena.csv"; arquivo_gerados = "jogos_ja_gerados_mega.csv"
    total_bolas = 6; faixa_maxima = 60; min_permitido = 6; max_permitido = 20
else:
    arquivo_selecionado = "Lotofacil.csv"; arquivo_gerados = "jogos_ja_gerados_lotofacil.csv"
    total_bolas = 15; faixa_maxima = 25; min_permitido = 15; max_permitido = 20

@st.cache_resource
def carregar_gerador(caminho, bolas, faixa, arq_gerados): return GeradorLoterias(caminho, bolas, faixa, arq_gerados)

if not os.path.exists(arquivo_selecionado):
    st.error(f"Erro: O ficheiro '{arquivo_selecionado}' não foi encontrado.")
else:
    gerador = carregar_gerador(arquivo_selecionado, total_bolas, faixa_maxima, arquivo_gerados)
    ultimo = gerador.obter_ultimo_concurso()
    st.info(f"Último concurso analisado ({modalidade}): **{ultimo}**")

    st.subheader("Configurações do Jogo")
    tamanho_base = st.slider("Quantos números totais na base?", min_permitido, max_permitido, min_permitido)
    tecnica = st.radio("Escolha a técnica:", ["Jogo Único", "Desdobramento"])
    
    tamanho_bilhete = min_permitido
    if tecnica == "Desdobramento":
        tamanho_bilhete = st.number_input("Tamanho de cada bilhete?", min_permitido, tamanho_base - 1, min_permitido)

    equilibrar = False
    modelo_escolhido = None
    usar_ml = False

    if modo_geracao == "Tradicional / Aleatório":
        equilibrar = st.checkbox("Forçar equilíbrio Pares/Ímpares?")
    else:
        usar_ml = True
        st.markdown("### 🧠 Configurações da IA")
        modelo_escolhido = st.selectbox("Escolha o Algoritmo Preditivo:", ["Random Forest", "KNN (Vizinhos Próximos)", "Rede Neural (MLP)"])

    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Gerar Jogos 🚀 (Custa 1 Ficha)", use_container_width=True):
            if st.session_state["fichas"] > 0:
                with st.spinner('A analisar e gerar números...'):
                    jogos = gerador.gerar_jogos(tamanho_base, tamanho_bilhete, tecnica.lower().replace(" ", "_"), equilibrar, usar_ml, modelo_escolhido)
                    if jogos:
                        # DESCONTA UMA FICHA
                        st.session_state["fichas"] -= 1 
                        st.success(f"Sucesso! {len(jogos)} jogo(s) gerado(s):")
                        st.table(pd.DataFrame(jogos, columns=[f"Bola {i}" for i in range(1, tamanho_bilhete + 1)]))
                        st.warning(f"Saldo atualizado: {st.session_state['fichas']} fichas.")
                    else:
                        st.error("Não foi possível gerar novos jogos inéditos com essa base.")
            else:
                st.error("❌ Não tem fichas suficientes! Compre mais para continuar.")
    with col2:
        if st.button("🗑️ Apagar histórico", use_container_width=True):
            if gerador.resetar_gerados(): st.success("Histórico apagado!")
            else: st.warning("Nenhum histórico para apagar.")
