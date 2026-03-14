import os
import sys
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')

def audit_database():
    print("=== Începere Audit Bază de Date NeonDB ===\n")
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("Eroare: DATABASE_URL nu este setat în .env")
        return
        
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        # 1. Numărarea recordurilor pe tabele
        print("1. Numărarea Înregistrărilor per Tabel:")
        tabele = ['legi', 'parlamentari', 'comisii', 'legi_initiatori', 'parcurs_comisii', 'pasi_lege']
        for tabel in tabele:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {tabel}")).scalar()
            print(f"  - {tabel.ljust(18)}: {count:,} rânduri")

        print("\n2. Verificarea Integrității Referențiale (Orphan Records):")
        # Există inițiatori care fac referire la o lege ștearsă/inexistentă?
        orfani_legi_init = conn.execute(text("""
            SELECT COUNT(*) FROM legi_initiatori li 
            LEFT JOIN legi l ON li.lege_id = l.id 
            WHERE l.id IS NULL
        """)).scalar()
        print(f"  - Legături Inițiatori Orfani: {orfani_legi_init} (Ar trebui să fie 0)")

        # Există pași care fac referire la o lege ștearsă/inexistentă?
        orfani_pasi = conn.execute(text("""
            SELECT COUNT(*) FROM pasi_lege pl 
            LEFT JOIN legi l ON pl.lege_id = l.id 
            WHERE l.id IS NULL
        """)).scalar()
        print(f"  - Pași Lege Orfani:           {orfani_pasi} (Ar trebui să fie 0)")

        print("\n3. Statistici și Distribuția Datelor:")
        # Top 5 Cei mai activi parlamentari
        top_parlamentari = pd.read_sql(text("""
            SELECT p.nume, COUNT(li.lege_id) as numar_legi
            FROM parlamentari p
            JOIN legi_initiatori li ON p.id = li.initiator_id
            GROUP BY p.nume
            ORDER BY numar_legi DESC
            LIMIT 5
        """), conn)
        print("  - Top 5 Inițiatori după numărul de legi:")
        for _, row in top_parlamentari.iterrows():
            print(f"      * {row['nume'][:40].ljust(40)}: {row['numar_legi']} legi")

        # Distribuția pe Camere
        camere = conn.execute(text("""
            SELECT prima_camera, COUNT(*) as nr 
            FROM legi 
            GROUP BY prima_camera
        """)).fetchall()
        print("\n  - Distribuția primei camere sesizate:")
        for row in camere:
             print(f"      * {str(row[0]).ljust(20)}: {row[1]} legi")
             
        # Distribuția pe tip_initiativa
        tipuri = conn.execute(text("""
            SELECT tip_initiativa, COUNT(*) as nr 
            FROM legi 
            GROUP BY tip_initiativa
        """)).fetchall()
        print("\n  - Distribuția pe tipul de inițiativă:")
        for row in tipuri:
             print(f"      * {str(row[0])[:30].ljust(30)}: {row[1]} legi")

        print("\n=== Audit Finalizat cu Succes ===")

if __name__ == "__main__":
    try:
        audit_database()
    except Exception as e:
         print(f"Eroare în timpul auditului: {e}")
