import streamlit as st
import pandas as pd
import random
import itertools
import os
import csv
import requests
import math
import mercadopago
from sklearn.ensemble import RandomForestRegressor
from sklearn.neighbors import KNeighborsRegressor
from sklearn.neural_network import MLPRegressor

# --- PAGAMENTO ---
def criar_preferencia_pagamento(uid, valor_fichas, preco):
    sdk = mercadopago.SDK(os.environ.get("MP_ACCESS_TOKEN"))
    
    preference_data = {
        "items": [
            {"title": f"Pacote de {valor_fichas} Fichas", "quantity": 1, "unit_price": float(preco)}
        ],
        "external_reference": uid,  # Isso é crucial: associa o pagamento ao usuário
        "back_urls": {
            "success": "https://geraloto.streamlit.app/",
            "failure": "https://geraloto.streamlit.app/",
            "pending": "https://geraloto.streamlit.app/"
        },
        "auto_return": "approved"
    }
    
    result = sdk.preference().create(preference_data)
    return result["response"]["init_point"] # Link para o usuário pagar

def verificar_pagamento_aprovado(uid):
    # Lembre-se: Use a variável de ambiente para o Access Token!
    sdk = mercadopago.SDK(os.environ.get("MP_ACCESS_TOKEN"))
    
    # Busca pagamentos realizados pelo usuário (usando o external_reference)
    filters = {"external_reference": uid, "status": "approved"}
    search_result = sdk.payment().search({"filters": filters})
    
    if search_result["status"] == 200:
        pagamentos = search_result["response"]["results"]
        if len(pagamentos) > 0:
            return True # Pagamento aprovado encontrado
    return False


# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="GeraLoto - Premium", page_icon="🎲", layout="wide")

# --- CHAVES DO FIREBASE ---
FIREBASE_WEB_API_KEY = os.environ.get("FIREBASE_WEB_API_KEY")
PROJECT_ID = os.environ.get("PROJECT_ID")

# --- FUNÇÕES DE COMUNICAÇÃO COM O FIRESTORE ---
def obter_saldo_nuvem(uid, id_token):
    url = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents/usuarios/{uid}"
    headers = {"Authorization": f"Bearer {id_token}"}
    resposta = requests.get(url, headers=headers)
    if resposta.status_code == 200:
        return int(resposta.json()['fields']['fichas']['integerValue'])
    elif resposta.status_code == 404:
        atualizar_saldo_nuvem(uid, id_token, 1000)
        return 1000
    return 0

def resetar_senha(email):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={FIREBASE_WEB_API_KEY}"
    payload = {
        "requestType": "PASSWORD_RESET",
        "email": email
    }
    return requests.post(url, json=payload).json()

def atualizar_saldo_nuvem(uid, id_token, novo_saldo):
    url = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents/usuarios/{uid}"
    headers = {"Authorization": f"Bearer {id_token}"}
    payload = {"fields": {"fichas": {"integerValue": str(novo_saldo)}}}
    requests.patch(url, headers=headers, json=payload)

def salvar_aposta_no_firestore(uid, id_token, jogos, concurso_alvo):
    url = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents/apostas_pendentes"
    headers = {"Authorization": f"Bearer {id_token}"}
    for jogo in jogos:
        payload = {
            "fields": {
                "uid": {"stringValue": uid},
                "concurso_alvo": {"integerValue": str(concurso_alvo)},
                "numeros": {"arrayValue": {"values": [{"integerValue": str(n)} for n in jogo]}},
                "status": {"stringValue": "pendente"}
            }
        }
        requests.post(url, headers=headers, json=payload)

def buscar_apostas_pendentes(uid, id_token):
    url = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents:runQuery"
    headers = {"Authorization": f"Bearer {id_token}"}
    query = {
        "structuredQuery": {
            "from": [{"collectionId": "apostas_pendentes"}],
            "where": {
                "compositeFilter": {
                    "op": "AND",
                    "filters": [
                        {"fieldFilter": {"field": {"fieldPath": "uid"}, "op": "EQUAL", "value": {"stringValue": uid}}},
                        {"fieldFilter": {"field": {"fieldPath": "status"}, "op": "EQUAL", "value": {"stringValue": "pendente"}}}
                    ]
                }
            }
        }
    }
    return requests.post(url, headers=headers, json=query).json()

def atualizar_status_aposta(document_name, id_token, acertos):
    url = f"https://firestore.googleapis.com/v1/{document_name}"
    headers = {"Authorization": f"Bearer {id_token}"}
    payload = {"fields": {"status": {"stringValue": "conferido"}, "acertos": {"integerValue": str(acertos)}}}
    requests.patch(url, headers=headers, json=payload)

# --- FUNÇÕES DE AUTENTICAÇÃO ---
def registar_utilizador(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_WEB_API_KEY}"
    payload = {"email": email, "password": password, "returnSecureToken": True}
    return requests.post(url, json=payload).json()

def iniciar_sessao(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_WEB_API_KEY}"
    payload = {"email": email, "password": password, "returnSecureToken": True}
    return requests.post(url, json=payload).json()

# --- CLASSE GERADOR ---
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

    def conferir_acertos(self, jogo_gerado):
        if not self.historico_lista: return 0
        ultimo_sorteio = set(self.historico_lista[-1])
        return len(set(jogo_gerado).intersection(ultimo_sorteio))

    def obter_ultimo_concurso(self):
        try:
            try: df = pd.read_csv(self.caminho_historico, encoding='latin1', sep=',', header=0)
            except: df = pd.read_csv(self.caminho_historico, encoding='latin1', sep=';', header=0)
            coluna_zero = df.iloc[:, 0].dropna().astype(str)
            return coluna_zero[coluna_zero.str.strip() != ''].iloc[-1]
        except: return "N/A"

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
                    jogo = [int(linha[f'Bola{i}']) for i in range(1, self.total_bolas + 1)]
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

    def _gerar_base_com_ml(self, tamanho_base, modelo_escolhido):
        if len(self.historico_lista) < 10: return sorted(random.sample(range(1, self.faixa_numeros + 1), tamanho_base))
        X = self.historico_lista[:-1]; y = self.historico_lista[1:]; ultimo_sorteio = [self.historico_lista[-1]]
        if modelo_escolhido == "Random Forest": modelo = RandomForestRegressor(n_estimators=50, random_state=42)
        elif modelo_escolhido == "KNN (Vizinhos Próximos)": modelo = KNeighborsRegressor(n_neighbors=5)
        else: modelo = MLPRegressor(hidden_layer_sizes=(50, 50), max_iter=500, random_state=42)
        modelo.fit(X, y); previsao = modelo.predict(ultimo_sorteio)[0]
        numeros_preditos = set()
        for p in previsao:
            num = int(round(p)); num = max(1, min(self.faixa_numeros, num)); numeros_preditos.add(num)
        while len(numeros_preditos) < tamanho_base: numeros_preditos.add(random.randint(1, self.faixa_numeros))
        return sorted(list(numeros_preditos))[:tamanho_base]

    def _gerar_base_equilibrada(self, tamanho):
        pares = [n for n in range(2, self.faixa_numeros + 1, 2)]; impares = [n for n in range(1, self.faixa_numeros + 1, 2)]
        qtd_pares = min(tamanho // 2, len(pares)); qtd_impares = tamanho - qtd_pares
        if qtd_impares > len(impares): qtd_impares = len(impares); qtd_pares = tamanho - qtd_impares
        return sorted(random.sample(pares, qtd_pares) + random.sample(impares, qtd_impares))

    def gerar_jogos(self, tamanho_base, tamanho_bilhete, tecnica, equilibrar, usar_ml, modelo_ml, quantidade_pedida=1):
        jogos_validados = []
        if tecnica == 'desdobramento' and tamanho_base > self.total_bolas:
            tentativas = 0
            while len(jogos_validados) < quantidade_pedida and tentativas < 2000:
                tentativas += 1
                base = self._gerar_base_com_ml(tamanho_base, modelo_ml) if usar_ml else (self._gerar_base_equilibrada(tamanho_base) if equilibrar else sorted(random.sample(range(1, self.faixa_numeros + 1), tamanho_base)))
                possiveis = list(itertools.combinations(base, tamanho_bilhete))
                if not any(any(combo in self.jogos_proibidos for combo in itertools.combinations(b, self.total_bolas)) for b in possiveis):
                    jogos_validados.extend(possiveis)
                    for b in possiveis:
                        for c in itertools.combinations(b, self.total_bolas): self.jogos_proibidos.add(c)
        else:
            while len(jogos_validados) < quantidade_pedida:
                jogo = tuple(self._gerar_base_com_ml(tamanho_base, modelo_ml)) if usar_ml else (tuple(self._gerar_base_equilibrada(tamanho_base)) if equilibrar else tuple(sorted(random.sample(range(1, self.faixa_numeros + 1), tamanho_base))))
                if not any(combo in self.jogos_proibidos for combo in itertools.combinations(jogo, self.total_bolas)):
                    jogos_validados.append(jogo)
                    for c in itertools.combinations(jogo, self.total_bolas): self.jogos_proibidos.add(c)
        self._salvar_gerados(jogos_validados)
        return jogos_validados

# --- LOGIN E AUTENTICAÇÃO ---
if "user_uid" not in st.session_state:
    st.title("🔒 GeraLoto - Acesso")
    escolha = st.radio("Selecione:", ["Iniciar Sessão", "Criar Conta"])
    e = st.text_input("E-mail")
    s = st.text_input("Senha", type="password")
    
    if st.button("Executar"):
        res = registar_utilizador(e, s) if escolha == "Criar Conta" else iniciar_sessao(e, s)
        if "error" in res: st.error(res["error"]["message"])
        else:
            st.session_state["user_uid"] = res["localId"]
            st.session_state["user_email"] = res["email"]
            st.session_state["id_token"] = res["idToken"]
            st.rerun()
            
    # Botão de recuperação de senha dentro do bloco de login
    if st.button("Esqueci minha senha"):
        if e:
            res = resetar_senha(e)
            if "error" in res: st.error(res["error"]["message"])
            else: st.success("E-mail de redefinição enviado!")
        else:
            st.warning("Digite seu e-mail acima primeiro.")
    st.stop() # Interrompe a execução aqui até o usuário logar

# --- APÓS LOGIN (PAINEL DO USUÁRIO) ---
st.sidebar.title("👤 Perfil")
st.sidebar.success(st.session_state['user_email'])

if "fichas" not in st.session_state: 
    st.session_state["fichas"] = obter_saldo_nuvem(st.session_state["user_uid"], st.session_state["id_token"])

st.sidebar.info(f"🪙 Saldo: {st.session_state['fichas']}")

# Botão de verificar pagamento agora está seguro aqui dentro
if st.sidebar.button("Verificar Pagamento de Fichas"):
    with st.spinner("Consultando Mercado Pago..."):
        if verificar_pagamento_aprovado(st.session_state["user_uid"]):
            novo_saldo = st.session_state["fichas"] + 1000
            atualizar_saldo_nuvem(st.session_state["user_uid"], st.session_state["id_token"], novo_saldo)
            st.session_state["fichas"] = novo_saldo
            st.success("Pagamento confirmado!")
        else:
            st.error("Nenhum pagamento aprovado encontrado.")

if st.sidebar.button("🚪 Sair"): 
    st.session_state.clear()
    st.rerun()


# --- GERADOR ---
st.title("🎲 Gerador Premium")
modalidade = st.sidebar.selectbox("Modalidade:", ["Mega-Sena", "Lotofácil"])
modo = st.sidebar.radio("Motor:", ["Tradicional", "IA 🧠"])
if modalidade == "Mega-Sena": arq, arq_ger, total, faixa, min_p, max_p = "Mega-Sena.csv", "jogos_ja_gerados_mega.csv", 6, 60, 6, 20
else: arq, arq_ger, total, faixa, min_p, max_p = "Lotofacil.csv", "jogos_ja_gerados_lotofacil.csv", 15, 25, 15, 20

@st.cache_resource
def carregar_gerador(a, b, c, d): return GeradorLoterias(a, b, c, d)
gerador = carregar_gerador(arq, total, faixa, arq_ger)

st.subheader("Configurações")
tecnica = st.radio("Técnica:", ["Jogo Único", "Desdobramento"])
if tecnica == "Desdobramento":
    tamanho_base = st.slider("Base:", min_p + 1, max_p, min_p + 1)
    tamanho_bilhete = st.number_input("Bilhete:", min_p, tamanho_base - 1, min_p)
    qtd_esp = math.comb(tamanho_base, tamanho_bilhete)
else:
    tamanho_base = min_p; tamanho_bilhete = min_p; qtd_esp = 1

equilibrar = st.checkbox("Equilibrar Pares/Ímpares?") if modo == "Tradicional" else False
modelo = st.selectbox("IA:", ["Random Forest", "KNN", "Rede Neural"]) if modo == "IA 🧠" else None

custo = qtd_esp * 10
if st.button(f"Gerar {qtd_esp} jogo(s) - Custo: {custo} Fichas"):
    if st.session_state["fichas"] >= custo:
        jogos = gerador.gerar_jogos(tamanho_base, tamanho_bilhete, tecnica.lower().replace(" ", "_"), equilibrar, modo=="IA 🧠", modelo, qtd_esp)
        st.session_state["fichas"] -= (len(jogos) * 10)
        atualizar_saldo_nuvem(st.session_state["user_uid"], st.session_state["id_token"], st.session_state["fichas"])
        concurso = int(gerador.obter_ultimo_concurso()) + 1
        salvar_aposta_no_firestore(st.session_state["user_uid"], st.session_state["id_token"], jogos, concurso)
        
        # Exibe resultado com acertos (backtesting)
        res_list = []
        for j in jogos:
            item = {f"Bola {i+1}": n for i, n in enumerate(sorted(j))}
            item["Acertos (Histórico)"] = gerador.conferir_acertos(j)
            res_list.append(item)
        st.dataframe(pd.DataFrame(res_list), use_container_width=True)
        st.success("Jogos salvos e gerados!")
    else: st.error("Saldo insuficiente!")

st.markdown("---")
st.subheader("🔍 Conferir Resultados")
input_num = st.text_input("Números sorteados (ex: 01,05,10...)")
if st.button("Conferir Minhas Apostas"):
    sorteio = set(int(n.strip()) for n in input_num.split(","))
    dados = buscar_apostas_pendentes(st.session_state["user_uid"], st.session_state["id_token"])
    for item in dados:
        if "document" in item:
            doc = item["document"]; doc_n = doc["name"]
            nums = [int(v["integerValue"]) for v in doc["fields"]["numeros"]["arrayValue"]["values"]]
            acertos = len(set(nums).intersection(sorteio))
            atualizar_status_aposta(doc_n, st.session_state["id_token"], acertos)
            st.write(f"Aposta {nums}: {acertos} acertos.")
