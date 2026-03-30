import re
import pandas as pd

# ==========================================
# MOTORUL DE REGULI (DICTIONARE REGEX)
# ==========================================
# Cheia este numărul pasului logic (1-8 pt camera curenta). Vor fi ajustate dinamic.
STANDARD_STEPS = {
    "depunere_proiect": {
        "SE": r"înregistrat[ăa]? la senat",
        "CD": r"înregistrat[ăa]? la camera deputa[țţ]ilor"
    },
    "prezentare_bp": {
        "SE": r"prezentare în biroul permanent",
        "CD": r"prezentare în biroul permanent"
    },
    "avize_consultative": {
        # Optional, un aviz oarecare de la CES/CSM/Consiliul Legislativ
        "SE": r"primire aviz de la consiliul",
        "CD": r"primire aviz de la consiliul"
    },
    "trimitere_comisii": {
        "SE": r"trimis pentru aviz la|trimis pentru raport la",
        "CD": r"trimis pentru raport la|trimis pentru aviz la"
    },
    "avize_comisii": {
        "SE": r"transmite avizul",
        "CD": r"primire aviz de la"
    },
    "raport_comisii": {
        "SE": r"depune raportul",
        "CD": r"primire raport"
    },
    "ordine_de_zi": {
        "SE": r"înscris pe ordinea de zi a plenului",
        "CD": r"înscris pe ordinea de zi a plenului"
    },
    "vot_plen": {
        "SE": r"adoptat de senat|respins de senat",
        "CD": r"adoptat de camera deputaţilor|adoptat de camera deputaților|respins de camera"
    }
}

FINAL_STEPS = {
    "pas_17_sesizare_ccr": {
        "SE": r"sesizare de neconstituționalitate|sesizare de neconstituţionalitate",
        "CD": r"sesizare de neconstituţionalitate|sesizare de neconstituționalitate"
    },
    "pas_18_lege_neconstitutionala": {
        "SE": r"curtea constituțională admite|curtea constituţională admite",
        "CD": r"curtea constitutionala decide.*admite|curtea constituțională decide.*admite"
    },
    "pas_19_trimis_promulgare": {
        "SE": r"trimis la promulgare",
        "CD": r"trimitere la pre.edinte"
    },
    "pas_20_intoarsa_parlament": {
        "SE": r"cere reexaminarea legii|solicită reexaminarea",
        "CD": r"solicită reexaminarea"
    },
    "pas_21_promulgat_presedinte": {
        "SE": r"promulgat prin decret",
        "CD": r"promulgata prin decret|promulgată prin decret"
    },
    "pas_22_publicat_mo": {
        "SE": r"publicată în monitorul oficial",
        "CD": r"devine legea"
    }
}


def get_all_tip_pasi():
    """Returnează dicționarul static cu toți pașii posibili pentru popularea tabelei tip_pasi."""
    found_steps = []
    
    step_mapping = [
        ("depunere_proiect", "Depunere proiect de lege"),
        ("prezentare_bp", "Prezentare in Biroul Permanent"),
        ("avize_consultative", "Avize Consultative"),
        ("trimitere_comisii", "Trimitere catre comisii"),
        ("avize_comisii", "Avize Comisii"),
        ("raport_comisii", "Raport Comisii"),
        ("ordine_de_zi", "Ordinea de zi a Plenului"),
        ("vot_plen", "Vot Plen")
    ]

    # Pre-populăm matricea Standard (1-22)
    for idx, (step_key, step_name) in enumerate(step_mapping, start=1):
        found_steps.append({"id": idx, "cod": f"pas_{idx}", "nume": f"{step_name} (I-a Camera)", "ordine_pas": idx, "tip_flux": "standard"})
        found_steps.append({"id": idx + 8, "cod": f"pas_{idx+8}", "nume": f"{step_name} (II-a Camera)", "ordine_pas": idx + 8, "tip_flux": "standard"})
        
    for num_key in FINAL_STEPS.keys():
        pas_id = num_key.split('_')[0] + "_" + num_key.split('_')[1] # pas_17
        pas_nr = int(pas_id.split('_')[1])
        nume_pas = num_key.replace(pas_id + "_", "").title().replace("_", " ")
        found_steps.append({"id": pas_nr, "cod": pas_id, "nume": nume_pas, "ordine_pas": pas_nr, "tip_flux": "standard"})

    # Adăugăm Reexaminarea (15 pași) cu ID-uri începând de pe la 30
    for idx in range(1, 16):
        nume_pas = f"Reexaminare Etapa {idx}"
        # A simple mapping for reexaminare will just be added to the db
        found_steps.append({"id": 30 + idx, "cod": f"pas_reex_{idx}", "nume": nume_pas, "ordine_pas": idx, "tip_flux": "reexaminare"})

    # Sort and return unique steps by ID
    found_steps.sort(key=lambda x: x['id'])
    return found_steps

def extract_standard_steps(row, prima_cam_text):
    """
    Parcurge rândul de tabel asociat unei legi și extrage dicționarul de pași atinși prin MAPARE DIRECTĂ pe coloane.
    Nu necesită ca userul să spună ce cameră a emis acțiunea, deduce automat din Regex (SE/CD).
    Acum returnează MEREU 22 de pași (matrice completă).
    """
    if pd.isna(prima_cam_text) or str(prima_cam_text).lower() == 'nan':
        prima_cam_code = 'SE' # Default
    else:
        prima_cam_code = 'SE' if 'senat' in str(prima_cam_text).lower() else 'CD'
        
    found_steps = {}
    
    step_mapping = [
        ("depunere_proiect", "Depunere proiect de lege"),
        ("prezentare_bp", "Prezentare in Biroul Permanent"),
        ("avize_consultative", "Avize Consultative"),
        ("trimitere_comisii", "Trimitere catre comisii"),
        ("avize_comisii", "Avize Comisii"),
        ("raport_comisii", "Raport Comisii"),
        ("ordine_de_zi", "Ordinea de zi a Plenului"),
        ("vot_plen", "Vot Plen")
    ]

    # Pre-populăm matricea cu toți cei 22 de Pași și detalii = None (Ne-atins)
    for idx, (step_key, step_name) in enumerate(step_mapping, start=1):
        # Pt I-a Camera
        found_steps[idx] = {"id": f"pas_{idx}", "nume": f"{step_name} (I-a Camera)", "detalii": None, "ordine_pas": idx}
        # Pt II-a Camera
        found_steps[idx + 8] = {"id": f"pas_{idx+8}", "nume": f"{step_name} (II-a Camera)", "detalii": None, "ordine_pas": idx + 8}
        
    for num_key in FINAL_STEPS.keys():
        pas_id = num_key.split('_')[0] + "_" + num_key.split('_')[1] # pas_17
        pas_nr = int(pas_id.split('_')[1])
        nume_pas = num_key.replace(pas_id + "_", "").title().replace("_", " ")
        found_steps[pas_nr] = {"id": pas_id, "nume": nume_pas, "detalii": None, "ordine_pas": pas_nr}

    # ==========================================
    # IMPLEMENTARE NOUA LOGICA (1-LA-1) PT PAȘII 1-3
    # ==========================================

    # Pas 1: Depunere proiect (Din coloana Inregistrare)
    inreg = str(row.get('Inregistrare', '')).strip()
    if inreg and inreg.lower() not in ['nan', 'nu a fost specificat']:
        if prima_cam_code == 'SE':
            if re.search(STANDARD_STEPS["depunere_proiect"]["SE"], inreg.lower()):
                found_steps[1]["detalii"] = inreg
        elif prima_cam_code == 'CD':
            if re.search(STANDARD_STEPS["depunere_proiect"]["CD"], inreg.lower()):
                found_steps[1]["detalii"] = inreg

    # Pas 2: Prezentare în Biroul Permanent (Din coloana Biroul permanent)
    bp = str(row.get('Biroul permanent (prima camera)', '')).strip()
    if bp and bp.lower() not in ['nan', 'nu a fost specificat']:
        if prima_cam_code == 'SE':
            if re.search(STANDARD_STEPS["prezentare_bp"]["SE"], bp.lower()):
                found_steps[2]["detalii"] = bp
        elif prima_cam_code == 'CD':
            if re.search(STANDARD_STEPS["prezentare_bp"]["CD"], bp.lower()):
                found_steps[2]["detalii"] = bp

    # Pas 3: Stadiu (Noua cerință: Doar pentru Senat populează Pas 3)
    stadiu = str(row.get('Stadiu', '')).strip()
    if stadiu and stadiu.lower() not in ['nan', 'nu a fost specificat']:
        if prima_cam_code == 'SE':
            found_steps[3]["detalii"] = stadiu
        elif prima_cam_code == 'CD':
            # Conform cerinței, lăsăm gol deocamdată
            pass

    # TODO: Logica pentru pașii 4-16 va fi mapată ulterior.

    # Verificăm pașii finali (17-22) concatenând tot timeline-ul (temporar pentru a nu-i pierde)
    timeline_cols = [
        'Inregistrare', 'Biroul permanent (prima camera)', 'Termen depunere amendamente', 
        'Inscrierea pe ordinea de zi a plenului', 'Vot plen', 'Dezbatere plen', 
        'Cale de atac', 'Sesizare neconstitutionalitate', 'Trimis la Promulgare', 
        'Presedintele ataca la Curtea Constitutionala', 'Promulgat', 'Monitorul Oficial'
    ]
    texts_final = [str(row.get(col, '')).lower() for col in timeline_cols if pd.notna(row.get(col))]
    
    for text in texts_final:
        if text.strip() in ['nan', 'nu a fost specificat', '']: continue
        for num_key, val in FINAL_STEPS.items():
            if re.search(val["SE"], text) or re.search(val["CD"], text):
                pas_id = num_key.split('_')[0] + "_" + num_key.split('_')[1] # ex: pas_17
                pas_nr = int(pas_id.split('_')[1])
                found_steps[pas_nr]["detalii"] = text
                
    # Returnăm lista completă (Mereu 22 de rânduri) sortată
    return [v for k, v in sorted(found_steps.items())]


def extract_reexaminare_steps(texts, prima_cam_text):
    """
    Parcurge textele pentru a vedea dacă legea se află în procedura de reexaminare.
    Dacă DA, generează o matrice de 15 pași (1-6 pt prima cameră, 7-12 pt a 2a, 13-15 finale).
    Dacă NU, returnează o listă goală.
    """
    text_concat = " ".join([str(t).lower() for t in texts if pd.notna(t)])
    
    # Condiția esențială: a existat o cerere de reexaminare?
    is_reexaminare = "reexaminar" in text_concat or "reexaminări" in text_concat
    
    if not is_reexaminare:
        return []
        
    if pd.isna(prima_cam_text) or str(prima_cam_text).lower() == 'nan':
        prima_cam_code = 'SE'
    else:
        prima_cam_code = 'SE' if 'senat' in str(prima_cam_text).lower() else 'CD'
        
    found_steps = {}
    
    # Doar 6 pași per cameră la reexaminare!
    step_mapping = [
        ("depunere_proiect", "Depunere cerere reexaminare"),
        ("prezentare_bp", "Prezentare in BP"),
        ("trimitere_comisii", "Trimitere catre comisii"),
        ("raport_comisii", "Raport Comisii"),
        ("ordine_de_zi", "Ordinea de zi a Plenului"),
        ("vot_plen", "Vot Plen")
    ]
    
    # Pre-populare Matrice 1-15
    for idx, (step_key, step_name) in enumerate(step_mapping, start=1):
        found_steps[idx] = {"id": f"pas_reex_{idx}", "nume": f"{step_name} (I-a Camera)", "detalii": None, "ordine_pas": idx}
        found_steps[idx + 6] = {"id": f"pas_reex_{idx+6}", "nume": f"{step_name} (II-a Camera)", "detalii": None, "ordine_pas": idx + 6}
        
    found_steps[13] = {"id": "pas_reex_13", "nume": "Trimis la Promulgare", "detalii": None, "ordine_pas": 13}
    found_steps[14] = {"id": "pas_reex_14", "nume": "Promulgat de Presedinte", "detalii": None, "ordine_pas": 14}
    found_steps[15] = {"id": "pas_reex_15", "nume": "Publicat in MO", "detalii": None, "ordine_pas": 15}

    vot_plen_cam_1_atins = False

    for text in texts:
        if pd.isna(text): continue
        t_lower = str(text).lower()
        if t_lower == 'nan' or not t_lower.strip() or t_lower == 'nu a fost specificat':
            continue
            
        # Alocam detaliile gasite cu logica 'Waterfall'
        for idx, (step_key, _) in enumerate(step_mapping, start=1):
            match_se = re.search(STANDARD_STEPS[step_key]["SE"], t_lower)
            match_cd = re.search(STANDARD_STEPS[step_key]["CD"], t_lower)
            
            if match_se or match_cd:
                if not vot_plen_cam_1_atins:
                    pas_nr = idx
                    found_steps[pas_nr]["detalii"] = text
                    if idx == 6: # Vot Plen Reexaminare I-a Camera
                        vot_plen_cam_1_atins = True
                else:
                    pas_nr = idx + 6
                    found_steps[pas_nr]["detalii"] = text

        # Finalii specifici
        if re.search(FINAL_STEPS["pas_19_trimis_promulgare"]["SE"], t_lower) or re.search(FINAL_STEPS["pas_19_trimis_promulgare"]["CD"], t_lower):
            found_steps[13]["detalii"] = text
        if re.search(FINAL_STEPS["pas_21_promulgat_presedinte"]["SE"], t_lower) or re.search(FINAL_STEPS["pas_21_promulgat_presedinte"]["CD"], t_lower):
            found_steps[14]["detalii"] = text
        if re.search(FINAL_STEPS["pas_22_publicat_mo"]["SE"], t_lower) or re.search(FINAL_STEPS["pas_22_publicat_mo"]["CD"], t_lower):
            found_steps[15]["detalii"] = text

    return [v for k, v in sorted(found_steps.items())]


# ==========================================
# TESTARE NOUA LOGICA DE BATCH (din Tabelul curent / Varianta 2)
# ==========================================
if __name__ == "__main__":
    # Simulam cum arată o lege citită din tabelul nostru actual (CSV vechi plat), unde avem X coloane de timeline
    mock_lege_bruta_1 = {
        "Prima_camera": "Senat",
        "row_data": {
            "Inregistrare": "Înregistrat la Senat pentru dezbatere cu nr.b125",
            "Biroul permanent (prima camera)": "prezentare în biroul permanent",
            "Stadiu": "trimis pentru raport la Comisia de Munca",
            "Vot plen": "adoptat de Senat adoptare cu respectarea prevederilor art.76; înregistrat la CD",
            "Trimis la Promulgare": "trimis la promulgare",
            "Monitorul Oficial": "devine Legea 241/2025"
        }
    }
    
    print("Testare Sistem de Extragere Automat (Varianta Mapare coloane 1-la-1):\\n" + "-"*80)
    pasi_gasiti = extract_standard_steps(mock_lege_bruta_1["row_data"], mock_lege_bruta_1["Prima_camera"])
    
    print(f"Legea Simulata (Prima Camera: {mock_lege_bruta_1['Prima_camera']}) - Au fost identificate {len(pasi_gasiti)} etape:")
    for pas in pasi_gasiti:
        det = str(pas['detalii'])[:30] + "..." if pas['detalii'] else "Neatins"
        print(f"  [>] {pas['id']:<8} | {pas['nume']:<40} | Matches text: '{det}'")
