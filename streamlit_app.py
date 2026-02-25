import streamlit as st
import requests
import pandas as pd
import re
import io

# --- FUNÇÕES DE UTILIDADE ---
def clean_text(text):
    if isinstance(text, str):
        return re.sub(r'[^ -~]', '', text)
    return text

def gera_token_wms(client_id, client_secret):
    url = "https://supply.rac.totvs.app/totvs.rac/connect/token"
    data = {
        "client_id": client_id, 
        "client_secret": client_secret,
        "grant_type": "client_credentials", 
        "scope": "authorization_api"
    }
    try:
        res = requests.post(url, data=data, timeout=15)
        return res.json().get("access_token") if res.status_code == 200 else None
    except:
        return None

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="WMS Stock Query", layout="wide")
st.title("📊 Consulta de Estoque Atual WMS")

with st.sidebar:
    st.header("🔑 Credenciais WMS")
    c_id = st.text_input("Client ID", type="password", key="stock_cid")
    c_secret = st.text_input("Client Secret", type="password", key="stock_sec")
    
    st.divider()
    
    st.header("📍 Localização")
    u_id = st.text_input("Unidade ID (UUID)", placeholder="Ex: ac275b55-90f8-44b8-b8cb-bdcfca969526", key="stock_uid")
    
    st.caption("🔒 Dados protegidos por sessão. Nenhuma senha é salva no servidor.")

# --- BOTÃO DE EXECUÇÃO ---
if st.button("🚀 Consultar Estoque"):
    if not all([c_id, c_secret, u_id]):
        st.error("⚠️ Preencha o Client ID, Client Secret e o Unidade ID na barra lateral.")
    else:
        token = gera_token_wms(c_id, c_secret)
        
        if not token:
            st.error("❌ Falha na autenticação. Verifique suas credenciais.")
        else:
            all_data = []
            page = 1
            progress_text = st.empty()
            
            API_URL = "https://supply.logistica.totvs.app/wms/query/api/v1/estoques"

            with st.spinner("Coletando saldos de estoque..."):
                while True:
                    params = {
                        "page": page, 
                        "pageSize": 500, 
                        "unidadeId": u_id.strip()
                    }
                    
                    try:
                        headers = {"Authorization": f"Bearer {token}"}
                        res = requests.get(API_URL, params=params, headers=headers, timeout=60)
                        
                        if res.status_code == 200:
                            data = res.json()
                            items = data.get('items', [])
                            
                            if not items:
                                break
                            
                            for estoque in items:
                                # Extração segura de Lote e Validade percorrendo a lista de características
                                lote = "N/A"
                                validade = "N/A"
                                for carac in estoque.get('caracteristicas', []):
                                    desc = carac.get('descricao', '').upper()
                                    if "LOTE" in desc:
                                        lote = carac.get('valor')
                                    elif "VALIDADE" in desc:
                                        validade = carac.get('valor')

                                prod_info = estoque.get('produto', {})
                                endereco_info = estoque.get('endereco', {})
                                unitizador_info = estoque.get('unitizador', {}) or {}
                                tipo_est_info = estoque.get('tipoEstoque', {})

                                all_data.append({
                                    'Produto Código': clean_text(prod_info.get('codigo')),
                                    'Descrição': clean_text(prod_info.get('descricaoComercial')),
                                    'Saldo': estoque.get('saldo'),
                                    'Endereço': clean_text(endereco_info.get('descricao')),
                                    'Lote': clean_text(lote),
                                    'Validade': clean_text(validade),
                                    'Unitizador': clean_text(unitizador_info.get('codigoBarras')),
                                    'Tipo Estoque ID': clean_text(tipo_est_info.get('id')),
                                    'ID Registro': clean_text(estoque.get('id'))
                                })
                            
                            progress_text.info(f"⏳ Processando: {len(all_data)} registros de estoque (Página {page})...")
                            
                            if not data.get('hasNext'):
                                break
                            page += 1
                        else:
                            st.error(f"Erro na API (Página {page}): Status {res.status_code}")
                            break
                    except Exception as e:
                        st.error(f"Erro de conexão: {e}")
                        break

            if all_data:
                progress_text.empty()
                df = pd.DataFrame(all_data)
                
                st.success(f"✅ Sucesso! {len(all_data)} registros de estoque encontrados.")
                
                # Exibição da Tabela
                st.dataframe(df, use_container_width=True)
                
                # Preparação do Excel
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Estoque_WMS')
                
                st.download_button(
                    label="📥 Baixar Estoque em Excel",
                    data=buf.getvalue(),
                    file_name=f"estoque_wms_{u_id[:8]}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("⚠️ Nenhum saldo de estoque encontrado para esta Unidade ID.")
