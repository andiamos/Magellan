import streamlit as st
import streamlit.components.v1 as components
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
        def load_dashboard_data_v3(url):
            eng = create_engine(url)
            l_df = pd.read_sql("SELECT id, numar_lege, titlu, prima_camera, tip_initiativa, data_inregistrare, monitorul_oficial_numar, monitorul_oficial_data FROM legi", eng)
            l_df['an'] = l_df['data_inregistrare'].str.extract(r'(\d{4})')[0]
            
            i_df = pd.read_sql("""
                SELECT li.lege_id, p.id as parlamentar_id, p.nume, p.titlu, p.partid 
                FROM legi_initiatori li
                JOIN parlamentari p ON li.initiator_id = p.id
            """, eng)
            
            c_df = pd.read_sql("SELECT lege_id, comisie_id FROM parcurs_comisii", eng)
            p_df = pd.read_sql("SELECT lege_id, etapa, detalii, ordine_pas FROM pasi_lege", eng)
            
            try:
                p_reex_df = pd.read_sql("SELECT lege_id, etapa, detalii, ordine_pas FROM pasi_reexaminare", eng)
            except Exception:
                p_reex_df = pd.DataFrame(columns=['lege_id', 'etapa', 'detalii', 'ordine_pas'])
                
            return l_df, i_df, c_df, p_df, p_reex_df
            
        legi_df, initiatori_df, parcurs_df, pasi_df, pasi_reex_df = load_dashboard_data_v3(db_url)
        
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
            
        st.divider()
        
        st.subheader("Previzualizare Publicări (Monitorul Oficial)")
        # Show only laws that have a Monitorul Oficial number
        mo_df = filtered_legi[filtered_legi['monitorul_oficial_numar'].notna()].copy()
        if not mo_df.empty:
            mo_display = mo_df[['numar_lege', 'titlu', 'monitorul_oficial_numar', 'monitorul_oficial_data']].head(10)
            mo_display.columns = ['Număr Lege', 'Titlu', 'Nr. M.Of.', 'Data M.Of.']
            st.dataframe(mo_display, use_container_width=True)
        else:
            st.info("Nu există date de publicare pentru selecția curentă.")
            
        st.divider()
        st.header("🔍 Urmărire Progres Lege (Tracker Vertical)")
        st.write("Alege o lege pentru a vizualiza în timp real stadiul ei de parcurs, conform procedurilor (22 pași canonici).")

        # Selectbox limitat la primele 500 de legi pt performanța UI
        lista_legi_tracker = filtered_legi.head(500)
        
        # Creem o formatare curată pentru Dropdown
        options = [""] + lista_legi_tracker.apply(
            lambda r: f"{r['numar_lege']} - {str(r['titlu'])[:80]}...", axis=1
        ).tolist()
        
        lege_selectata = st.selectbox("Caută sau selectează legea:", options)
        
        if lege_selectata and lege_selectata != "":
            # Extragem ID-ul numărului public (gen L120/2025)
            numar_extras = lege_selectata.split(" - ")[0]
            row_lege = filtered_legi[filtered_legi['numar_lege'] == numar_extras]
            
            if not row_lege.empty:
                id_lege = row_lege.iloc[0]['id']
                prima_cam = row_lege.iloc[0]['prima_camera']
                
                # Fetch pasi pentru aceasta lege
                pasi_lege_curenta = pasi_df[pasi_df['lege_id'] == id_lege]
                pasi_rezolvati = pasi_lege_curenta['ordine_pas'].tolist()
                pasi_rezolvati.sort()
                
                st.markdown(f"#### Parcurs Live: {numar_extras}")
                st.markdown(f"*Prima Cameră sesizată: **{prima_cam}***", unsafe_allow_html=True)
                
                # Definim lista canonică (State Machine 22 Pași)
                pasii_canonici = [
                    (1, "Dep. proiect (I-a Cam.)"),
                    (2, "BP (I-a Cam.)"),
                    (3, "Avize Cons. (I-a Cam.)"),
                    (4, "Trim. comisii (I-a Cam.)"),
                    (5, "Avize Comisii (I-a Cam.)"),
                    (6, "Raport Comisii (I-a Cam.)"),
                    (7, "Ord. de zi (I-a Cam.)"),
                    (8, "Vot Plen (I-a Cam.)"),
                    (9, "Dep. proiect (II-a Cam.)"),
                    (10, "BP (II-a Cam.)"),
                    (11, "Avize Cons. (II-a Cam.)"),
                    (12, "Trim. comisii (II-a Cam.)"),
                    (13, "Avize Comisii (II-a Cam.)"),
                    (14, "Raport Comisii (II-a Cam.)"),
                    (15, "Ord. de zi (II-a Cam.)"),
                    (16, "Vot Plen (II-a Cam.)"),
                    (17, "Sesizare CCR"),
                    (18, "CC Admite Neconst."),
                    (19, "Trimis Promulgare"),
                    (20, "Intoarsa Parlament"),
                    (21, "Promulgat Presedinte"),
                    (22, "Publicat M.Of")
                ]
                
                # Căutăm reexaminarea
                reex_curenta = pasi_reex_df[pasi_reex_df['lege_id'] == id_lege]
                are_reexaminare = False
                
                if not reex_curenta.empty:
                    for _, r in reex_curenta.iterrows():
                        v = r['detalii']
                        if pd.notna(v) and str(v).strip() != "" and str(v).lower() != "none":
                            are_reexaminare = True
                            break
                            
                pasii_reex_canonici = [
                    (1, "Cerere Reex. (I-a Cam.)"),
                    (2, "BP (I-a Cam.)"),
                    (3, "Trim. comisii (I-a Cam.)"),
                    (4, "Raport Comisii (I-a Cam.)"),
                    (5, "Ord. de zi (I-a Cam.)"),
                    (6, "Vot Plen (I-a Cam.)"),
                    (7, "Cerere Reex. (II-a Cam.)"),
                    (8, "BP (II-a Cam.)"),
                    (9, "Trim. comisii (II-a Cam.)"),
                    (10, "Raport Comisii (II-a Cam.)"),
                    (11, "Ord. de zi (II-a Cam.)"),
                    (12, "Vot Plen (II-a Cam.)"),
                    (13, "Trimis Promulgare"),
                    (14, "Promulgat Presedinte"),
                    (15, "Publicat M.Of")
                ]
                
                with st.container(border=True):
                    # Generează codul sursă pentru diagrama Mermaid (Rețea Metrou)
                    mermaid_code = ["graph TD"]
                    mermaid_code.append("classDef done fill:#d4edda,stroke:#28a745,stroke-width:2px,color:#155724")
                    mermaid_code.append("classDef todo fill:#f8f9fa,stroke:#ced4da,stroke-width:2px,color:#6c757d")
                    mermaid_code.append("classDef reex fill:#ffe8a1,stroke:#ffc107,stroke-width:3px,color:#856404")
                    
                    # Rădăcinile de traseu standard
                    for pas_nr, nume_pas in pasii_canonici:
                        detaliu_row = pasi_lege_curenta[pasi_lege_curenta['ordine_pas'] == pas_nr]
                        este_atins = False
                        
                        if not detaliu_row.empty:
                            valoare = detaliu_row.iloc[0]['detalii']
                            if pd.notna(valoare) and str(valoare).strip() != "" and str(valoare).lower() != "none":
                                este_atins = True
                        
                        clean_name = nume_pas.replace("(", "").replace(")", "").replace('"', '')
                        mermaid_code.append(f"  P{pas_nr}[\"{pas_nr}. {clean_name}\"]")
                        
                        if este_atins:
                            mermaid_code.append(f"  class P{pas_nr} done")
                        else:
                            mermaid_code.append(f"  class P{pas_nr} todo")
                            
                        # Desenează sinele (traseul M1)
                        if pas_nr > 1:
                            if pas_nr == 21 and are_reexaminare:
                                # Macaz: Daca intra in reexaminare, tronsonul vechi cade (ramane gri in aer)
                                pass
                            else:
                                mermaid_code.append(f"  P{pas_nr-1} --> P{pas_nr}")
                    
                    if are_reexaminare:
                        # Deschidem o linie nouă din statia 20!
                        mermaid_code.append(f"  P20 -.->|Deviere: Cerere de Reexaminare| R1")
                        
                        for pas_nr, nume_pas in pasii_reex_canonici:
                            detaliu_row = reex_curenta[reex_curenta['ordine_pas'] == pas_nr]
                            este_atins = False
                            
                            if not detaliu_row.empty:
                                valoare = detaliu_row.iloc[0]['detalii']
                                if pd.notna(valoare) and str(valoare).strip() != "" and str(valoare).lower() != "none":
                                    este_atins = True
                                    
                            clean_name = nume_pas.replace("(", "").replace(")", "").replace('"', '')
                            # Prefixăm statiile cu R- pentru a indica distinctia Liniei Secundare
                            mermaid_code.append(f"  R{pas_nr}([\"R-{pas_nr}. {clean_name}\"])")
                            
                            if este_atins:
                                mermaid_code.append(f"  class R{pas_nr} reex")
                            else:
                                mermaid_code.append(f"  class R{pas_nr} todo")
                                
                            # Șinele tronsonului galben/portocaliu
                            if pas_nr > 1:
                                mermaid_code.append(f"  R{pas_nr-1} ==> R{pas_nr}")
                    
                    final_mermaid = "\\n".join(mermaid_code)
                    
                    html_code = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <script type="module">
                            import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
                            mermaid.initialize({{ startOnLoad: true, theme: 'base' }});
                        </script>
                    </head>
                    <body style="margin:0; padding:10px; font-family: sans-serif; text-align: center;">
                        <pre class="mermaid">
{final_mermaid}
                        </pre>
                    </body>
                    </html>
                    """
                    
                    components.html(html_code, height=650, scrolling=True)

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
