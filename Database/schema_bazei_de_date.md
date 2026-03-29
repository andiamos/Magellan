# Schema Bazei de Date (ER Diagram) cu Date Brute (RAW) și Partide Politice

Acesta este modelul entitate-relație (ERD) vizual care ilustrează felul în care **datele brute (RAW)** curg în structura **normalizată**, dar și noul modul propus pentru **Partide Politice**.

```mermaid
erDiagram
    %% Sursele RAW (Extrase din CSV / DB Staging)
    raw_legi ||--o{ legi : "Migrat & Curatat in"
    raw_legi ||--o{ parlamentari : "Nume extrase din coloana Initiator"
    raw_legi ||--o{ pasi_lege : "Logica Regex: Extrage 22 Pasi Canonici"
    
    raw_comisii_cd ||--o{ comisii : "Creaza intrari pt CD"
    raw_comisii_senat ||--o{ comisii : "Creaza intrari pt Senat"
    
    raw_comisii_cd ||--o{ parcurs_comisii : "Mapa avize CD"
    raw_comisii_senat ||--o{ parcurs_comisii : "Mapa avize Senat"

    %% Structura Normalizata
    legi ||--o{ legi_initiatori : "este_initiata_de"
    legi ||--o{ parcurs_comisii : "trece_prin"
    legi ||--o{ pasi_lege : "are_ca_etape"
    
    parlamentari ||--o{ legi_initiatori : "initiaza"
    comisii ||--o{ parcurs_comisii : "analizeaza_si_avizeaza"
    
    %% Modulul Nou: Partide Politice
    partide ||--o{ afiliere_politica : "are_membri"
    parlamentari ||--o{ afiliere_politica : "este_membru_in"

    %% Definitia structurii normalizate
    legi {
        int id PK
        string numar_lege 
        string titlu
        string data_inregistrare
        string stadiu_general
        string monitorul_oficial_numar
        string monitorul_oficial_data
    }

    parlamentari {
        int id PK
        string nume 
        string titlu "Ex: senator, deputat"
        string partid "Ex: PNL, PSD, USR"
    }

    legi_initiatori {
        int lege_id FK
        int initiator_id FK
    }

    comisii {
        int id PK
        string nume 
        string camera "Senat sau CD"
    }

    parcurs_comisii {
        int id PK
        int lege_id FK
        int comisie_id FK
        string aviz
    }

    pasi_lege {
        int id PK
        int lege_id FK
        string etapa "Numele standard al pasului (ex: pas_4, pas_16, pas_22)"
        string detalii "Textul brut original din scrapper folosit pentru Audit"
        int ordine_pas "Ordinea cronologica (ex: 4 pt pas_4)"
    }
    
    %% Structura pentru Partide
    partide {
        int id PK
        string acronim "Ex: PSD, PNL, USR"
        string nume_complet "Ex: Partidul Social Democrat"
        string data_infiintare "Pentru a capta partidele noi (ex: AUR, REPER)"
        string data_desfiintare "Pentru cele care au disparut (ex: PDL, ALDE)"
    }
    
    afiliere_politica {
        int id PK
        int parlamentar_id FK
        int partid_id FK
        string data_inceput "Mandatul de la care se afiliaza"
        string data_sfarsit "Cand paraseste partidul (poate fi NULL pt curent)"
    }
```

### Funcționarea "pasi_lege" (State Machine cu 22 de Etape)
Noua arhitectură a renunțat la copierea directă a textelor de pe site-uri ca "Stadii". În schimb, un algoritm de parsare (Regex) traversează cronologia fiecărei legi și o mapează pe un parcurs standard (canon) cu **22 de pași prestabiliți** (și 15 pași de reexaminare). 

Pașii inteligenți țin cont automat dacă o lege a plecat din Senat sau de la CD, și folosesc un `offset (+8)` pentru Camera 2. Exemple:
- `pas_1`: *Depunere proiect de lege (I-a Camera)*
- `pas_8`: *Vot Plen (I-a Camera)*
- `pas_9`: *Depunere proiect de lege (II-a Camera)*
- `pas_22`: *Publicata in Monitorul Oficial*

Aceasta înseamnă că interfața vizuală (Dashboard UI) folosește aceste ID-uri de pași pentru a aprinde sau stinge bulinele dintr-un Tracker modern, știind 100% sigur la ce pas a ajuns un dosar.

### De ce o tabelă intermediară (`afiliere_politica`)?
În politica din România (și din 2010 până în prezent), "traseismul politic" este foarte frecvent (parlamentarii trec de la un partid la altul pe parcursul mandatelor). Dacă am pune doar un câmp `partid_id` direct pe tabelul `parlamentari`, am ști doar partidul lor de *acum*. Prin tabela intermediară `afiliere_politica` (care stochează perioadele `data_inceput` - `data_sfarsit`), vom putea analiza exact din ce partid făcea parte un parlamentar **în momentul în care a inițiat o anumită lege**.
