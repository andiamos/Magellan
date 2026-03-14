import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))

print("=== Anomalii curente din parlamentari ===")
df_anom = pd.read_sql("SELECT nume, titlu, partid FROM parlamentari WHERE nume LIKE '%%:%%' OR nume LIKE 'senatori%%' OR nume = 'Guvernul României' LIMIT 10", engine)
print(df_anom)

print("\n=== Date Brute care genereaza aceste anomalii ===")
df_raw = pd.read_sql("SELECT \"Initiator\" FROM raw_legi WHERE \"Initiator\" LIKE '%%Guvernul României%%' OR \"Initiator\" LIKE '%%senatori%%' LIMIT 10", engine)
for row in df_raw['Initiator'].tolist():
    print(f"RAW: {row}\n")
