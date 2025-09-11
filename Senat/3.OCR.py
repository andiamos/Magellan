import os
import pytesseract
from pdf2image import convert_from_path

# Folders
pdf_folder = "temp_pdfs"
txt_folder = "extracted_texts"
os.makedirs(txt_folder, exist_ok=True)

# Log file
log_path = "processing_summary.log"
with open(log_path, 'w', encoding='utf-8') as log_file:
    log_file.write("OCR processing log:\n")

# Process all PDF files in the folder, skipping already processed ones
for filename in os.listdir(pdf_folder):
    if not filename.endswith(".pdf"):
        continue

    pdf_path = os.path.join(pdf_folder, filename)
    txt_filename = filename.replace(".pdf", ".txt")
    txt_path = os.path.join(txt_folder, txt_filename)

    if os.path.exists(txt_path):
        print(f"Skipped (already processed): {filename}")
        with open(log_path, 'a', encoding='utf-8') as log_file:
            log_file.write(f"Skipped (already exists): {filename}\n")
        continue

    try:
        images = convert_from_path(pdf_path)
        extracted_text = ""
        for image in images:
            extracted_text += pytesseract.image_to_string(image, lang='ron')

        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(extracted_text.strip())

        with open(log_path, 'a', encoding='utf-8') as log_file:
            log_file.write(f"Processed (OCR): {filename}\n")

    except Exception as e:
        print(f"Error processing {filename}: {e}")
        with open(log_path, 'a', encoding='utf-8') as log_file:
            log_file.write(f"Error processing {filename}: {e}\n")

print("OCR text extraction complete.")
