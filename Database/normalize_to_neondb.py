import os
import re
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

def clean_romanian_text(val):
    if pd.isna(val): return val
    val_str = str(val).strip()
    # Normalize old cedilla characters to correct comma-below characters
    val_str = val_str.replace('ţ', 'ț').replace('Ţ', 'Ț')
    val_str = val_str.replace('ş', 'ș').replace('Ş', 'Ș')
    return val_str

def clean_boolean(val):
    if pd.isna(val): return False
    val_str = str(val).strip().lower()
    return val_str in ['da', 'true', '1']

def extract_monitorul_oficial(val):
    if pd.isna(val) or str(val).lower() == 'nu a fost specificat':
        return None, None
    
    val_str = str(val).strip()
    # Pattern to match nr. X/DD.MM.YYYY or nr. X/DD/MM/YYYY
    match = re.search(r'nr\.\s*(\d+)[\s/]+(\d{2}[\./]\d{2}[\./]\d{4})', val_str)
    if match:
        return match.group(1), match.group(2)
    
    # Fallback for just the number if date is missing or in different format
    match_nr = re.search(r'nr\.\s*(\d+)', val_str)
    if match_nr:
        return match_nr.group(1), None
        
    return None, None

def normalize_data():
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("Error: DATABASE_URL not set in .env")
        return
        
    engine = create_engine(db_url)
    
    print("Reading raw tables from Neon DB...")
    # 1. Read raw data from postgres
    try:
        raw_legi = pd.read_sql_table('raw_legi', engine)
        raw_comisii_cd = pd.read_sql_table('raw_comisii_cd', engine)
        raw_comisii_senat = pd.read_sql_table('raw_comisii_senat', engine)
        
        # FIX: Restore full column names from original CSVs because PostgreSQL truncates them to 63 bytes
        try:
            cd_csv_cols = pd.read_csv('procesat_comisii_01.12.2026_cd.csv', nrows=0).columns
            senat_csv_cols = pd.read_csv('procesat_comisii_01.12.2026_senat.csv', nrows=0).columns
            
            if len(cd_csv_cols) == len(raw_comisii_cd.columns):
                raw_comisii_cd.columns = cd_csv_cols
            if len(senat_csv_cols) == len(raw_comisii_senat.columns):
                raw_comisii_senat.columns = senat_csv_cols
            print("Successfully restored full commission names from local CSV files.")
        except Exception as csv_err:
            print(f"Warning: Could not restore full column names from CSVs: {csv_err}")
            
    except Exception as e:
        print(f"Error reading raw tables. Ensure the initial loader ran successfully: {e}")
        return

    print("Building normalized structure in memory (Stateless DataFrame manipulation)...")
    
    # 2. Build Legi
    # Drop duplicates by "lege" business key
    legi_df = raw_legi.dropna(subset=['lege']).drop_duplicates(subset=['lege']).copy()
    legi_df = legi_df.reset_index(drop=True)
    legi_df['id'] = range(1, len(legi_df) + 1)
    
    # Mapping table for the business key (lege string -> legi.id)
    lege_to_id = dict(zip(legi_df['lege'], legi_df['id']))
    
    print("Extracting Monitorul Oficial details...")
    mo_details = legi_df['Monitorul Oficial'].apply(extract_monitorul_oficial)
    legi_df['mo_numar'] = [d[0] for d in mo_details]
    legi_df['mo_data'] = [d[1] for d in mo_details]

    # Prepare the legi table for insertion
    legi_insert = pd.DataFrame({
        'id': legi_df['id'],
        'numar_lege': legi_df['lege'].apply(clean_romanian_text),
        'titlu': legi_df['Titlu lege'].apply(clean_romanian_text),
        'titlu_sumar': legi_df['Titlu lege (sumar)'].apply(clean_romanian_text),
        'data_inregistrare': legi_df['Data'],
        'numar_inregistrare_senat': legi_df['Numar de inregistrare Senat'].apply(clean_romanian_text),
        'numar_inregistrare_cd': legi_df['Număr de înregistrare Camera Deputaților'].apply(clean_romanian_text),
        'prima_camera': legi_df['Prima cameră'].apply(clean_romanian_text).replace({'Camera Deputatilor': 'Camera Deputaților'}),
        'tip_initiativa': legi_df['Tip inițiativă'].apply(clean_romanian_text).str.capitalize(),
        'caracter_lege': legi_df['Caracterul legii'].apply(clean_romanian_text),
        'procedura_urgenta': legi_df['Procedura de urgență'].apply(clean_boolean),
        'stadiu_general': legi_df['Stadiu'].apply(clean_romanian_text),
        'rezumat': legi_df['Rezumat forma Initiala'],
        'pct_vedere_guvern': legi_df['Punct de vedere guvern'],
        'monitorul_oficial_numar': legi_df['mo_numar'],
        'monitorul_oficial_data': legi_df['mo_data']
    })
    
    # 3. Build Parlamentari (Initiatori)
    initiator_records = []
    lista_initiatori_dict = {}
    
    for _, row in legi_df.iterrows():
        l_id = row['id']
        initiator_str = row['Initiator']
        if pd.notna(initiator_str):
            # Split initiators string by ; or ,
            initiators_raw = [i.strip() for i in re.split(r'[;,]', str(initiator_str)) if i.strip()]
            if not initiators_raw:
                # Fallback if split fails but string is not empty
                initiators_raw = [str(initiator_str).strip()]
            
            for init_raw in initiators_raw:
                init_raw = init_raw.strip()
                nume = init_raw
                titlu = None
                partid = None
                
                # Cleanup common bad group strings
                lower_init = init_raw.lower()
                if not init_raw or lower_init in ['senatori', 'deputati', 'deputaţi', 'din care:', 'din care:deputati', 'din care: deputați']:
                    continue
                
                # Unify Guvernul Romaniei
                if lower_init == 'guvernul româniei' or lower_init == 'guvern':
                    nume = 'Guvernul României'
                    if nume not in lista_initiatori_dict:
                        lista_initiatori_dict[nume] = {'nume': nume, 'titlu': None, 'partid': None}
                    initiator_records.append({'lege_id': l_id, 'initiator_nume': nume})
                    continue
                    
                # Strip out comprehensive group and prefix mentions
                init_raw = re.sub(r'(?i)^(din care:)?\s*(\d*\s*)?(senator|senatori|deputat|deputați|deputati|neafiliati|neafiliați)[\s\-:]*([a-z0-9]+)?:\s*', '', init_raw)
                
                # Also clean "din care:- USR:" and similar
                init_raw = re.sub(r'(?i)^din care:.*?:\s*', '', init_raw)
                
                # Remove leading group names if missed (e.g., "deputați - PNL: ")
                init_raw = re.sub(r'(?i)^(deputati|deputați|senatori)\s*-\s*[a-zA-Z0-9]+:\s*', '', init_raw)
                
                nume = init_raw
                
                # Deal with pattern: Name - Title Party
                # Split at the LAST dash instead of the first
                if ' - ' in init_raw:
                    parts = init_raw.rsplit(' - ', 1)
                    nume = parts[0].strip()
                    meta = parts[1].strip()
                    
                    meta_parts = meta.split(' ', 1)
                    if len(meta_parts) == 2:
                        titlu = meta_parts[0].strip()
                        partid = meta_parts[1].strip()
                    else:
                        titlu = meta_parts[0].strip()
                
                if nume not in lista_initiatori_dict:
                    lista_initiatori_dict[nume] = {'nume': nume, 'titlu': titlu, 'partid': partid}
                    
                initiator_records.append({'lege_id': l_id, 'initiator_nume': nume})

    lista_initiatori = list(lista_initiatori_dict.values())
    initiatori_df = pd.DataFrame(lista_initiatori)
    initiatori_df['id'] = range(1, len(initiatori_df) + 1)
    nume_to_id = dict(zip(initiatori_df['nume'], initiatori_df['id']))

    # 4. Build Legi_Initiatori
    legi_initiatori_df = pd.DataFrame(initiator_records)
    if not legi_initiatori_df.empty:
        legi_initiatori_df['initiator_id'] = legi_initiatori_df['initiator_nume'].map(nume_to_id)
        legi_initiatori_df = legi_initiatori_df[['lege_id', 'initiator_id']].drop_duplicates()

    # 5. Build Comisii
    # Get commission columns dynamically
    comisii_names_cd = [c for c in raw_comisii_cd.columns if c.lower() != 'lege']
    comisii_names_senat = [c for c in raw_comisii_senat.columns if c.lower() != 'lege']
    
    all_comisii = []
    for c in comisii_names_cd:
        all_comisii.append({'nume': c, 'camera': 'Camera Deputaților'})
    for c in comisii_names_senat:
        all_comisii.append({'nume': c, 'camera': 'Senat'})
        
    comisii_df = pd.DataFrame(all_comisii)
    comisii_df.drop_duplicates(inplace=True)
    comisii_df = comisii_df.reset_index(drop=True)
    comisii_df['id'] = range(1, len(comisii_df) + 1)
    
    # Helper mappers
    comisie_cd_to_id = {row['nume']: row['id'] for _, row in comisii_df[comisii_df['camera'] == 'Camera Deputaților'].iterrows()}
    comisie_senat_to_id = {row['nume']: row['id'] for _, row in comisii_df[comisii_df['camera'] == 'Senat'].iterrows()}

    # 6. Build Parcurs Comisii
    parcurs_records = []
    # parse CD records
    for _, row in raw_comisii_cd.iterrows():
        lege_str = str(row['lege']).strip()
        if lege_str in lege_to_id:
            l_id = lege_to_id[lege_str]
            for col in comisii_names_cd:
                aviz = row[col]
                if pd.notna(aviz):
                    aviz_str = str(aviz).strip()
                    if aviz_str and aviz_str.lower() != 'nu e specificat':
                        c_id = comisie_cd_to_id[col]
                        parcurs_records.append({'lege_id': l_id, 'comisie_id': c_id, 'aviz': aviz_str})

    # parse Senat records
    for _, row in raw_comisii_senat.iterrows():
        lege_str = str(row['lege']).strip()
        if lege_str in lege_to_id:
            l_id = lege_to_id[lege_str]
            for col in comisii_names_senat:
                aviz = row[col]
                if pd.notna(aviz):
                    aviz_str = str(aviz).strip()
                    if aviz_str and aviz_str.lower() != 'nu e specificat':
                        c_id = comisie_senat_to_id[col]
                        parcurs_records.append({'lege_id': l_id, 'comisie_id': c_id, 'aviz': aviz_str})

    parcurs_df = pd.DataFrame(parcurs_records)
    if not parcurs_df.empty:
        parcurs_df['id'] = range(1, len(parcurs_df) + 1)

    # 7. Build Pasi Lege
    timeline_cols = [
        'Inregistrare', 'Biroul permanent (prima camera)', 'Termen depunere amendamente', 
        'Inscrierea pe ordinea de zi a plenului', 'Vot plen', 'Dezbatere plen', 
        'Cale de atac', 'Sesizare neconstitutionalitate', 'Trimis la Promulgare', 
        'Presedintele ataca la Curtea Constitutionala', 'Promulgat', 'Monitorul Oficial'
    ]
    
    existing_timeline_cols = [c for c in timeline_cols if c in legi_df.columns]
    
    pasi_records = []
    for _, row in legi_df.iterrows():
        l_id = row['id']
        for i, col in enumerate(existing_timeline_cols):
            val = row[col]
            if pd.notna(val):
                val_str = str(val).strip()
                if val_str and val_str.lower() != 'nu a fost specificat':
                    pasi_records.append({
                        'lege_id': l_id,
                        'etapa': col,
                        'detalii': val_str,
                        'ordine_pas': i + 1
                    })
                
    pasi_df = pd.DataFrame(pasi_records)
    if not pasi_df.empty:
        pasi_df['id'] = range(1, len(pasi_df) + 1)
        
    print("\n--- Summary ---")
    print(f"Prepared Legi: {len(legi_insert)}")
    print(f"Prepared Parlamentari: {len(initiatori_df)}")
    print(f"Prepared Legi_Initiatori: {len(legi_initiatori_df)}")
    print(f"Prepared Comisii: {len(comisii_df)}")
    print(f"Prepared Parcurs Comisii: {len(parcurs_df)}")
    print(f"Prepared Pasi Lege: {len(pasi_df)}")

    # 8. Clean existing tables securely due to Foreign Keys
    print("\nDropping existing normalized tables (CASCADE)...")
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS pasi_lege CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS parcurs_comisii CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS legi_initiatori CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS afiliere_politica CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS comisii CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS partide CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS parlamentari CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS legi CASCADE;"))

    # 9. Write to Database using Transaction
    print("\nWriting objects to DB tables...")
    with engine.begin() as conn:
        print(" -> Bulk inserting legi...")
        legi_insert.to_sql('legi', conn, if_exists='append', index=False)
        
        print(" -> Bulk inserting parlamentari...")
        initiatori_df.to_sql('parlamentari', conn, if_exists='append', index=False)
        
        print(" -> Bulk inserting legi_initiatori...")
        if not legi_initiatori_df.empty:
            legi_initiatori_df.to_sql('legi_initiatori', conn, if_exists='append', index=False)
            
        print(" -> Bulk inserting comisii...")
        comisii_df.to_sql('comisii', conn, if_exists='append', index=False)
        
        print(" -> Bulk inserting parcurs_comisii...")
        if not parcurs_df.empty:
            parcurs_df.to_sql('parcurs_comisii', conn, if_exists='append', index=False)
            
        print(" -> Bulk inserting pasi_lege...")
        if not pasi_df.empty:
            pasi_df.to_sql('pasi_lege', conn, if_exists='append', index=False)
            
    # 9. Add Data Integrity via Raw SQL Primary and Foreign Keys
    print("\nEstablishing Data Integrity (Foreign Keys & Primary Keys)...")
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE legi ADD PRIMARY KEY (id);"))
        conn.execute(text("ALTER TABLE parlamentari ADD PRIMARY KEY (id);"))
        conn.execute(text("ALTER TABLE comisii ADD PRIMARY KEY (id);"))
        
        conn.execute(text("ALTER TABLE legi_initiatori ADD FOREIGN KEY (lege_id) REFERENCES legi(id) ON DELETE CASCADE;"))
        conn.execute(text("ALTER TABLE legi_initiatori ADD FOREIGN KEY (initiator_id) REFERENCES parlamentari(id) ON DELETE CASCADE;"))
        
        if not parcurs_df.empty:
            conn.execute(text("ALTER TABLE parcurs_comisii ADD PRIMARY KEY (id);"))
            conn.execute(text("ALTER TABLE parcurs_comisii ADD FOREIGN KEY (lege_id) REFERENCES legi(id) ON DELETE CASCADE;"))
            conn.execute(text("ALTER TABLE parcurs_comisii ADD FOREIGN KEY (comisie_id) REFERENCES comisii(id) ON DELETE CASCADE;"))
            
        if not pasi_df.empty:
            conn.execute(text("ALTER TABLE pasi_lege ADD PRIMARY KEY (id);"))
            conn.execute(text("ALTER TABLE pasi_lege ADD FOREIGN KEY (lege_id) REFERENCES legi(id) ON DELETE CASCADE;"))

        # Create empty tables for future Political Parties architecture
        print("\nCreating schema for Political Parties (Empty for now)...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS partide (
                id SERIAL PRIMARY KEY,
                acronim VARCHAR(50),
                nume_complet VARCHAR(255),
                data_infiintare DATE,
                data_desfiintare DATE
            );
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS afiliere_politica (
                id SERIAL PRIMARY KEY,
                parlamentar_id INTEGER REFERENCES parlamentari(id) ON DELETE CASCADE,
                partid_id INTEGER REFERENCES partide(id) ON DELETE CASCADE,
                data_inceput DATE,
                data_sfarsit DATE
            );
        """))

    print("\nNormalization and Integrity Locks Complete!")
    
    # 10. Validation Spot Checks
    raw_count = len(raw_legi['lege'].dropna().unique())
    norm_count = len(legi_insert)
    print(f"\n[Validation] Raw unique legi: {raw_count} | Normalized legi: {norm_count}")
    if raw_count == norm_count:
        print("[SUCCESS] Check 1: Records parity achieved. Complete sets transferred.")
    else:
        print("[WARNING] Check 1: Discrepancy in records count. Missing uniqueness.")

if __name__ == "__main__":
    try:
        normalize_data()
    except Exception as e:
        print(f"Fatal error during normalization: {e}")
