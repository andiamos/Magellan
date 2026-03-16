import streamlit as st
import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

# Configurare Pagină
st.set_page_config(page_title="Analiză Legislativă AI", layout="wide", page_icon="🏛️")

# Incarcare mediu
load_dotenv()
db_url = os.getenv("DATABASE_URL")
app_password = os.getenv("APP_PASSWORD", "magellan2024") # Fallback daca nu e setat

# --- Sistem de Autentificare Simpatic ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

def check_password():
    if st.session_state["authenticated"]:
        return True
    
    st.markdown("""
        <style>
        .login-box {
            padding: 2rem;
            border-radius: 10px;
            background-color: #f0f2f6;
            text-align: center;
        }
        </style>
    """, unsafe_allow_html=True)
    
    col_l, col_m, col_r = st.columns([1, 2, 1])
    with col_m:
        st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=100)
        st.title("Acces Magellan")
        pwd = st.text_input("Introdu parola de acces pentru echipă:", type="password")
        if st.button("Deblochează 🚀"):
            if pwd == app_password:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Parolă incorectă. Te rugăm să verifici cu adminul.")
    return False

if not check_password():
    st.stop()
# ---------------------------------------

@st.cache_resource
def get_engine():
    return create_engine(db_url)

if not db_url:
    st.error("DATABASE_URL lipsește din mediu (fișierul .env). Nu ne putem conecta la baza de date.")
    st.stop()

engine = get_engine()

st.title("🏛️ Platformă de Analiză Legislativă (Testare Echipă)")
st.caption("Conectat live la structura normalizată NeonDB. Modul Dashboard & Modul Asistent AI Active.")

# Creare secțiuni (Tabs)
tab1, tab2 = st.tabs(["📊 Dashboard Echipă", "🤖 Asistent AI Data Agent"])

with tab1:
    st.header("Vizualizare Rapidă (Date NeonDB)")
    
    col1, col2, col3 = st.columns(3)
    
    try:
        # ---------------- Incarcare și Caching Date ----------------
        @st.cache_data(ttl=300)
        def load_dashboard_data(url):
            eng = create_engine(url)
            l_df = pd.read_sql("SELECT id, prima_camera, tip_initiativa, data_inregistrare FROM legi", eng)
            l_df['an'] = l_df['data_inregistrare'].str.extract(r'(\d{4})')[0]
            
            i_df = pd.read_sql("""
                SELECT li.lege_id, p.id as parlamentar_id, p.nume, p.titlu, p.partid 
                FROM legi_initiatori li
                JOIN parlamentari p ON li.initiator_id = p.id
            """, eng)
            
            c_df = pd.read_sql("SELECT lege_id, comisie_id FROM parcurs_comisii", eng)
            return l_df, i_df, c_df
            
        legi_df, initiatori_df, parcurs_df = load_dashboard_data(db_url)
        
        # Extragem listele pentru filtre
        ani_list = sorted(legi_df['an'].dropna().unique().tolist(), reverse=True)
        partide_list = sorted(initiatori_df['partid'].dropna().unique().tolist())
        
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            selected_ani = st.multiselect("📅 Filtrează după Anul Înregistrării:", ani_list)
        with col_f2:
            selected_partide = st.multiselect("🏛️ Filtrează după Partidul Inițiatorului:", partide_list)
            
        # ---------------- Aplicare Filtre ----------------
        filtered_legi = legi_df.copy()
        filtered_init = initiatori_df.copy()
        
        if selected_partide:
            filtered_init = filtered_init[filtered_init['partid'].isin(selected_partide)]
            filtered_legi = filtered_legi[filtered_legi['id'].isin(filtered_init['lege_id'])]
            
        if selected_ani:
            filtered_legi = filtered_legi[filtered_legi['an'].isin(selected_ani)]
            
        # Re-sincronizare
        filtered_init = initiatori_df[initiatori_df['lege_id'].isin(filtered_legi['id'])]
        if selected_partide: 
            filtered_init = filtered_init[filtered_init['partid'].isin(selected_partide)]
            
        filtered_parcurs = parcurs_df[parcurs_df['lege_id'].isin(filtered_legi['id'])]
        
        # Metrici de top
        total_legi = len(filtered_legi)
        total_initiatori = filtered_init['parlamentar_id'].nunique()
        total_comisii = filtered_parcurs['comisie_id'].nunique()
        
        col1.metric("Număr Legi", f"{total_legi:,}")
        col2.metric("Inițiatori Implicați", f"{total_initiatori:,}")
        col3.metric("Comisii Implicate", f"{total_comisii:,}")
        
        st.divider()
        
        # Grafice
        st.subheader("Distribuția Inițiativelor")
        col_grafic, col_tabel = st.columns([1, 1])
        
        with col_grafic:
            if not filtered_legi.empty:
                dist_df = filtered_legi.groupby('prima_camera').size().reset_index(name='Numar_Legi')
                dist_df.rename(columns={'prima_camera': 'Camera'}, inplace=True)
                st.bar_chart(dist_df.set_index('Camera'), color="#1A5276")
            else:
                st.info("Nu există date pentru filtrele selectate.")
                
        with col_tabel:
            if not filtered_legi.empty:
                tip_df = filtered_legi.groupby('tip_initiativa').size().reset_index(name='num').sort_values('num', ascending=False).head(5)
                st.write("Top 5 Tipuri de Inițiative")
                st.dataframe(tip_df, use_container_width=True)
                
        st.divider()
        
        st.subheader("Top Cei Mai Activi Parlamentari (Inițiatori)")
        if not filtered_init.empty:
            top_df = filtered_init.groupby(['nume', 'titlu', 'partid']).size().reset_index(name='Legi Inițiate')
            top_df.rename(columns={'nume': 'Nume Inițiator', 'titlu': 'Titlu', 'partid': 'Partid'}, inplace=True)
            top_df = top_df.sort_values('Legi Inițiate', ascending=False).head(15)
            st.dataframe(top_df, use_container_width=True)
        else:
            st.info("Nu există date despre parlamentari pentru filtrele selectate.")
            
    except Exception as e:
        st.error(f"Eroare la redarea tabloului de bord: {e}")

with tab2:
    st.header("Interoghează Baza de Date cu Inteligenta Artificiala")
    st.write("Acest agent are acces *doar in citire* la schema noastra de Legi, Parlamentari, si Comisii. Îi poți pune întrebări direct în Română.")
    
    # Secure API Key Entry for Team Testing
    gemini_key = st.text_input("Cheia API Google Gemini:", type="password", key="gemini", help="Pune cheia ta Gemini API aici pentru a alimenta 'creierul' Agentului.")
    
    # Chat History
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat Input Box
    if prompt := st.chat_input("Ex: 'Arată-mi o listă cu toate legile inițiate de parlamentari de la PSD în 2024'"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            if not gemini_key:
                st.warning("Te rog introdu o cheie API Gemini pentru a putea genera scripturi SQL pe loc.")
                st.session_state.messages.append({"role": "assistant", "content": "Nu a fost setată cheia Gemini API."})
            else:
                with st.spinner("Agentul accesează schema Neon DB și scrie codul SQL..."):
                    try:
                        from langchain_community.utilities import SQLDatabase
                        from langchain_google_genai import ChatGoogleGenerativeAI
                        from langchain_community.agent_toolkits import create_sql_agent
                        
                        # Conn to LangChain SQL Agent Mechanism
                        db = SQLDatabase.from_uri(db_url)
                        llm = ChatGoogleGenerativeAI(google_api_key=gemini_key, model="gemini-2.5-flash", temperature=0)
                        
                        agent_executor = create_sql_agent(
                            llm=llm,
                            db=db,
                            agent_type="openai-tools",
                            verbose=True
                        )
                        
                        # Command the agent
                        system_prompt = "Ești un analist de date pentru o echipă publică. Răspunde întotdeauna politicos și exact, folosind detalii, pe limba Română. Întrebarea este: "
                        response = agent_executor.invoke({"input": system_prompt + prompt})
                        
                        answer = response['output']
                        
                        # Handle Gemini Flash complex list-of-dicts response format
                        if isinstance(answer, list):
                            clean_text = ""
                            for item in answer:
                                if isinstance(item, dict) and 'text' in item:
                                    clean_text += item['text']
                                elif isinstance(item, str):
                                    clean_text += item
                            answer = clean_text
                            
                        st.markdown(answer)
                        st.session_state.messages.append({"role": "assistant", "content": answer})
                        
                    except Exception as e:
                        error_msg = f"A apărut o problemă la interogarea AI: {e}"
                        st.error(error_msg)
                        st.session_state.messages.append({"role": "assistant", "content": error_msg})
