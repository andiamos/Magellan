import re
import pandas as pd

# ==========================================
# MOTORUL DE REGULI (DICTIONARE REGEX)
# ==========================================
# Cheia este numărul pasului logic (1-8 pt camera curenta). Vor fi ajustate dinamic.
STANDARD_STEPS = {
    "depunere_proiect": {
        "SE": r"înregistrat la senat pentru dezbatere cu nr",
        "CD": r"înregistrat la camera deputaţilor pentru dezbatere|înregistrat la camera deputaților pentru dezbatere"
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


def extract_standard_steps(texts, prima_cam_text):
    """
    Parcurge o listă de texte brute asociată unei legi și extrage dicționarul de pași atinși.
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

    for text in texts:
        if pd.isna(text): continue
        text = str(text).lower()
        if text == 'nan' or text == 'nu a fost specificat' or not text.strip():
            continue
            
        # Verificăm pașii 1-16 (Standard, I-a și a II-a Cameră)
        for idx, (step_key, step_name) in enumerate(step_mapping, start=1):
            if re.search(STANDARD_STEPS[step_key]["SE"], text):
                offset = 0 if prima_cam_code == "SE" else 8
                pas_nr = idx + offset
                found_steps[pas_nr]["detalii"] = text
            
            if re.search(STANDARD_STEPS[step_key]["CD"], text):
                offset = 0 if prima_cam_code == "CD" else 8
                pas_nr = idx + offset
                found_steps[pas_nr]["detalii"] = text

        # Verificăm pașii finali (17-22)
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

    for text in texts:
        if pd.isna(text): continue
        t_lower = str(text).lower()
        if t_lower == 'nan' or not t_lower.strip() or t_lower == 'nu a fost specificat':
            continue
            
        # Alocam detaliile gasite conform dictionarului STANDARD (extins intern)
        for idx, (step_key, _) in enumerate(step_mapping, start=1):
            if re.search(STANDARD_STEPS[step_key]["SE"], t_lower):
                offset = 0 if prima_cam_code == "SE" else 6
                found_steps[idx + offset]["detalii"] = text
                
            if re.search(STANDARD_STEPS[step_key]["CD"], t_lower):
                offset = 0 if prima_cam_code == "CD" else 6
                found_steps[idx + offset]["detalii"] = text

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
        "Timeline": [
            "Înregistrat la Senat pentru dezbatere cu nr.b125",
            "trimis pentru raport la Comisia de Munca",
            "adoptat de Senat adoptare cu respectarea prevederilor art.76",
            "înregistrat la Camera Deputaților pentru dezbatere",
            "devine Legea 241/2025"
        ]
    }
    
    print("Testare Sistem de Extragere Automat (Varianta fără a mai primi explicit camera actiunii):\\n" + "-"*80)
    pasi_gasiti = extract_standard_steps(mock_lege_bruta_1["Timeline"], mock_lege_bruta_1["Prima_camera"])
    
    print(f"Legea Simulata (Prima Camera: {mock_lege_bruta_1['Prima_camera']}) - Au fost identificate {len(pasi_gasiti)} etape:")
    for pas in pasi_gasiti:
        print(f"  [>] {pas['id']:<8} | {pas['nume']:<40} | Matches text: '{pas['detalii'][:30]}...'")
