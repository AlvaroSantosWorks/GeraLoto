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

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="GeraLoto - Premium", page_icon="🎲", layout="wide")

# --- CHAVES DO FIREBASE ---
FIREBASE_WEB_API_KEY = os.environ.get("FIREBASE_WEB_API_KEY")
PROJECT_ID = os.environ.get("PROJECT_ID")

# --- FUNÇÕES DE PAGAMENTO ---
def verificar_pagamento_aprovado():
    sdk = mercadopago.SDK(os.environ.get("MP_ACCESS_TOKEN"))
    search_result = sdk.payment().search({
        "filters": {"external_reference": st.session_state.get("user_uid", "")}
    })
    if search_result.get("status") == 200:
        pagamentos = search_result["response"].get("results", [])
        for p in pagamentos:
            if p["status"] == "approved":
                return True
    return False

def criar_preferencia_pagamento(uid, valor_fichas, preco):
    sdk = mercadopago.SDK(os.environ.get("MP_ACCESS_TOKEN"))
    preference_data = {
        "items": [{"title": f"Pacote de {valor_fichas} Fichas", "quantity": 1, "unit_price": float(preco)}],
        "payer": {"name": "Comprador", "surname": "Teste", "email": "teste@test.com"},
        "external_reference": uid,
        "back_urls": {
            "success": "https://geraloto.streamlit.app/",
            "failure": "https://geraloto.streamlit.app/",
            "pending": "https://geraloto.streamlit.app/"
        },
        "auto_return": "approved"
    }
    try:
        result = sdk.preference().create(preference_data)
        if result.get("status") in [200, 201]:
            return result["response"]["init_point"], result["response"]["id"]
        return None, None
    except: return None, None

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

def atualizar_saldo_nuvem(uid, id_token, novo_saldo):
    url = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents/usuarios/{uid}"
    headers = {"Authorization": f"Bearer {id_token}"}
    payload = {"fields": {"fichas": {"integerValue": str(novo_saldo)}}}
    requests.patch(url, headers=headers, json=payload)

def resetar_senha(email):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={FIREBASE_WEB_API_KEY}"
    return requests.post(url, json={"requestType": "PASSWORD_RESET", "email": email}).json()

def salvar_aposta_no_firestore(uid, id_token, jogos, concurso_alvo):
    url = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents/apostas_pendentes"
    headers = {"Authorization": f"Bearer {id_token}"}
    for jogo in jogos:
        payload = {"fields": {"uid": {"stringValue": uid}, "concurso_alvo": {"integerValue": str(concurso_alvo)}, "numeros": {"arrayValue": {"values": [{"integerValue": str(n)} for n in jogo]}}, "status": {"stringValue": "pendente"}}}
        requests.post(url, headers=headers, json=payload)

def buscar_apostas_pendentes(uid, id_token):
    url = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents:runQuery"
    headers = {"Authorization": f"Bearer {id_token}"}
    query = {"structuredQuery": {"from": [{"collectionId": "apostas_pendentes"}], "where": {"compositeFilter": {"op": "AND", "filters": [{"fieldFilter": {"field": {"fieldPath": "uid"}, "op": "EQUAL", "value": {"stringValue": uid}}}, {"fieldFilter": {"field": {"fieldPath": "status"}, "op": "EQUAL", "value": {"stringValue": "pendente"}}}]}}}}
    return requests.post(url, headers=headers, json=query).json()

def atualizar_status_aposta(document_name, id_token, acertos):
    url = f"https://firestore.googleapis.com/v1/{document_name}"
    headers = {"Authorization": f"Bearer {id_token}"}
    requests.patch(url, headers=headers, json={"fields": {"status": {"stringValue": "conferido"}, "acertos": {"integerValue": str(acertos)}}})

# --- AUTENTICAÇÃO ---
def registar_utilizador(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_WEB_API_KEY}"
    return requests.post(url, json={"email": email, "password": password, "returnSecureToken": True}).json()

def iniciar_sessao(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_WEB_API_KEY}"
    return requests.post(url, json={"email": email, "password": password, "returnSecureToken": True}).json()

# --- CLASSE GERADOR ---
class GeradorLoterias:
    def __init__(self, caminho_historico, total_bolas, faixa_numeros, caminho_gerados):
        self.caminho_historico = caminho_historico
        self.caminho_gerados = caminho_gerados
        self.total_bolas = total_bolas
        self.faixa_numeros = faixa_numeros
        self.historico_lista = []
        self.historico_oficial = self._carregar_historico()
        self.historico_gerados = self._carregar_gerados()
        self.jogos_proibidos = self.historico_oficial.union(self.historico_gerados)

    def conferir_acertos(self, jogo_gerado):
        if not self.historico_lista: return 0
        return len(set(jogo_gerado).intersection(set(self.historico_lista[-1])))

    def obter_ultimo_concurso(self):
        try:
            df = pd.read_csv(self.caminho_historico, encoding='latin1', sep=',', header=0)
            return str(df.iloc[:, 0].dropna().iloc[-1])
        except: return "N/A"

    def _carregar_historico(self):
        jogos = set()
        if not os.path.exists(self.caminho_historico): return jogos
        with open(self.caminho_historico, mode='r', encoding='latin1') as f:
            leitor = csv.DictReader(f)
            for linha in leitor:
                jogo = tuple(sorted([int(linha[f'Bola{i}']) for i in range(1, self.total_bolas + 1)]))
                jogos.add(jogo); self.historico_lista.append(list(jogo))
        return jogos

    def _carregar_gerados(self):
        jogos = set()
        if os.path.exists(self.caminho_gerados):
            with open(self.caminho_gerados, mode='r', encoding='utf-8') as f:
                for linha in csv.reader(f):
                    if 'Bola' not in str(linha[0]): jogos.add(tuple(sorted([int(x) for x in linha])))
        return jogos

    def _salvar_gerados(self, novos_jogos):
        with open(self.caminho_gerados, mode='a', newline='', encoding='utf-8') as f:
            escritor = csv.writer(f)
            for jogo in novos_jogos: escritor.writerow(jogo)

    def _gerar_base_com_ml(self, tamanho, modelo_escolhido):
        if len(self.historico_lista) < 10: return sorted(random.sample(range(1, self.faixa_numeros + 1), tamanho))
        X = self.historico_lista[:-1]; y = self.historico_lista[1:]; ultimo = [self.historico_lista[-1]]
        if modelo_escolhido == "Random Forest": modelo = RandomForestRegressor(n_estimators=50, random_state=42)
        elif modelo_escolhido == "KNN (Vizinhos Próximos)": modelo = KNeighborsRegressor(n_neighbors=5)
        else: modelo = MLPRegressor(hidden_layer_sizes=(50, 50), max_iter=500, random_state=42)
        modelo.fit(X, y); previsao = [int(round(p)) for p in modelo.predict(ultimo)[0]]
        base = set(previsao).union(random.sample(range(1, self.faixa_numeros + 1), tamanho))
        return sorted(list(base))[:tamanho]

    def _gerar_base_equilibrada(self, tamanho):
        pares = [n for n in range(2, self.faixa_numeros + 1, 2)]; impares = [n for n in range(1, self.faixa_numeros + 1, 2)]
        return sorted(random.sample(pares, tamanho//2) + random.sample(impares, tamanho - tamanho//2))

    def gerar_jogos(self, tamanho_base, tamanho_bilhete, tecnica, equilibrar, usar_ml, modelo_ml, qtd=1):
        jogos_validados = []
        while len(jogos_validados) < qtd:
            base = self._gerar_base_com_ml(tamanho_base, modelo_ml) if usar_ml else (self._gerar_base_equilibrada(tamanho_base) if equilibrar else sorted(random.sample(range(1, self.faixa_numeros + 1), tamanho_base)))
            jogo = tuple(sorted(random.sample(base, tamanho_bilhete)))
            if not any(combo in self.jogos_proibidos for combo in itertools.combinations(jogo, self.total_bolas)):
                jogos_validados.append(jogo)
                for c in itertools.combinations(jogo, self.total_bolas): self.jogos_proibidos.add(c)
        self._salvar_gerados(jogos_validados)
        return jogos_validados

# --- LOGIN ---
if "user_uid" not in st.session_state:
    st.title("🔒 GeraLoto - Acesso")
    e = st.text_input("E-mail"); s = st.text_input("Senha", type="password")
    if st.button("Executar"):
        res = iniciar_sessao(e, s)
        if "error" in res: st.error(res["error"]["message"])
        else:
            st.session_state.update({"user_uid": res["localId"], "user_email": res["email"], "id_token": res["idToken"]})
            st.rerun()
    st.stop()

# --- PAINEL ---
st.sidebar.title("👤 Perfil"); st.sidebar.info(f"🪙 Saldo: {st.session_state.get('fichas', 0)}")
if "fichas" not in st.session_state: st.session_state["fichas"] = obter_saldo_nuvem(st.session_state["user_uid"], st.session_state["id_token"])

# --- ÁREA DE COMPRA ---
st.sidebar.markdown("---"); st.sidebar.subheader("🛒 Comprar Fichas")
pacotes = {"Pacote Iniciante (1000 fichas)": (1000, 10.00), "Pacote Pro (2500 fichas)": (2500, 22.00), "Pacote VIP (5000 fichas)": (5000, 40.00)}
escolha = st.sidebar.selectbox("Escolha seu pacote:", list(pacotes.keys()))
qtd, valor = pacotes[escolha]

if st.sidebar.button(f"Gerar Link: R$ {valor:.2f}"):
    link, pref_id = criar_preferencia_pagamento(st.session_state["user_uid"], qtd, valor)
    st.session_state.update({"link_pagamento": link, "fichas_a_adicionar": qtd})

if st.session_state.get("link_pagamento"): st.sidebar.link_button("Pagar Agora", st.session_state["link_pagamento"])

if st.sidebar.button("Verificar Pagamento"):
    if verificar_pagamento_aprovado():
        adicionar = st.session_state.get("fichas_a_adicionar", 1000)
        novo_saldo = st.session_state["fichas"] + adicionar
        atualizar_saldo_nuvem(st.session_state["user_uid"], st.session_state["id_token"], novo_saldo)
        st.session_state["fichas"] = novo_saldo; st.success("Fichas creditadas!")
    else: st.error("Pagamento não localizado.")

if st.sidebar.button("🚪 Sair"): st.session_state.clear(); st.rerun()

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
