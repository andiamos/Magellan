import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

def load_data_to_neondb():
    # Load environment variables from .env file
    load_dotenv()
    
    # Get database connection URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("Error: DATABASE_URL environment variable is not set.")
        print("Please create a .env file with DATABASE_URL=postgres://user:password@endpoint/dbname")
        return

    print("Connecting to Neon DB...")
    # Create SQLAlchemy engine
    engine = create_engine(database_url)
    
    # Define files and target tables
    files_to_load = {
        "full_rezultat_final_all_01.12.2025_full.csv": "raw_legi",
        "procesat_comisii_01.12.2026_cd.csv": "raw_comisii_cd",
        "procesat_comisii_01.12.2026_senat.csv": "raw_comisii_senat"
    }

    try:
        with engine.connect() as conn:
            for file_name, table_name in files_to_load.items():
                if not os.path.exists(file_name):
                    print(f"Warning: File {file_name} not found. Skipping...")
                    continue
                
                print(f"Loading {file_name} into {table_name}...")
                
                # Load CSV into pandas DataFrame
                # using low_memory=False to avoid DtypeWarning for large mixed-type columns
                df = pd.read_csv(file_name, low_memory=False)
                
                # Write DataFrame to Neon DB table
                # if_exists='replace' will drop the table if it exists and recreate it
                df.to_sql(table_name, conn, if_exists='replace', index=False)
                
                print(f"Successfully loaded {df.shape[0]} rows into {table_name}.")
                
        print("All files processed successfully!")
        
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    load_data_to_neondb()
