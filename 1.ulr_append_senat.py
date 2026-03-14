import pandas as pd
import ast
import hashlib

#default df
df = pd.read_excel("PDF_Mag.xlsx")

#base URL
base_url = "https://www.senat.ro"

#parse URL
def construct_full_links(link_str):
    if pd.isna(link_str):
        return []
    try:
        link_list = ast.literal_eval(link_str)
        return [base_url + link if not link.startswith('http') else link for link in link_list]
    except Exception:
        return []

#create 'full_links'
df['full_links'] = df['links'].apply(construct_full_links)

#explode 'full_links' on its own row
df = df.explode('full_links', ignore_index=True)
df['data']= pd.to_datetime(df['data'], errors='coerce').dt.strftime('%d/%m/%Y')

# tag 'extract' column -start and end
#start
df['extract_y_n'] = df['actiunea'].apply(lambda x: 'yes' if isinstance(x, str) and 'la Senat pentru dezbatere cu' in x else 'no')
#end

#tag file name
df['hash_name'] = df['full_links'].apply(lambda x: hashlib.sha256(x.encode('utf-8')).hexdigest() if pd.notna(x) else '')


print(df.head())

#export
df.to_excel('clean_senat_pars.xlsx', index= False)