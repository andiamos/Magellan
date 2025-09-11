import pandas as pd
import requests
import os
import time
import random
import hashlib
from datetime import datetime

# Load DataFrame
input_file = "clean_senat_pars_2025.xlsx"
df = pd.read_excel(input_file)

# Load existing output if available
output_file = "senat_with_text.xlsx"
if os.path.exists(output_file):
    existing_df = pd.read_excel(output_file)
    for col in ['Text', 'Text_img']:
        if col in existing_df.columns:
            if col not in df.columns:
                df[col] = ''
            df[col] = existing_df[col].combine_first(df[col])

#create folder to store temporary PDFs
os.makedirs("temp_pdfs", exist_ok=True)

#load or initialize log file
audit_log_path = "processing_log.csv"
if os.path.exists(audit_log_path):
    log_df = pd.read_csv(audit_log_path)
    processed_hashes = set(log_df['url_hash'])
else:
    log_df = pd.DataFrame(columns=['row_index', 'index_column', 'saved_file', 'url', 'result', 'url_hash', 'timestamp', 'error_message'])
    processed_hashes = set()

headers = {
    'User-Agent': 'Mozilla/5.0 (compatible; PDF-Scraper/1.0; +https://www.example.com/bot)'
}

df['extract_y_n']= 'yes'

for idx, row in df.iterrows():

    #check y/n in 'extract_y_n'
    if row.get('extract_y_n', '').strip().lower() != 'yes':
        continue

    url = row['full_links']
    if pd.isna(url):
        continue

    #generate hash from URL
    url_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()

    if url_hash in processed_hashes:
        print(f"Skipping already downloaded: {url}")
        continue

    result = ""
    error_message = ""
    try:
        # Randomized delay to avoid rate limiting
        time.sleep(random.uniform(0.5,1))

        # Download file with custom headers
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"failed to download: {url}")
            result = "download failed"
            error_message = f"Status code: {response.status_code}"
            continue

        content_type = response.headers.get('Content-Type', '')
        if 'application/pdf' not in content_type:
            result = "no PDF"
            error_message = "content is not a PDF"
        else:
            # Save PDF with hash as filename
            pdf_filename = f"{url_hash}.pdf"
            pdf_path = os.path.join("temp_pdfs", pdf_filename)

            with open(pdf_path, 'wb') as f:
                f.write(response.content)

            result = "downloaded"

    except Exception as e:
        print(f"Error processing {url}: {e}")
        result = "error"
        error_message = str(e)

    #log the processing result
    log_df = pd.concat([
        log_df,
        pd.DataFrame([{
            'row_index': idx,
            'index_column': row['index'] if 'index' in row else idx,
            'saved_file': f"{url_hash}.pdf",
            'url': url,
            'result': result,
            'url_hash': url_hash,
            'timestamp': datetime.now().isoformat(),
            'error_message': error_message
        }])
    ], ignore_index=True)
    log_df.to_csv(audit_log_path, index=False)

print("done downloading PDFs to 'temp_pdfs'")
