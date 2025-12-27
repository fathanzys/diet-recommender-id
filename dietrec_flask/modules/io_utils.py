from __future__ import annotations
from pathlib import Path
from typing import Tuple, List, Dict, Any
import pandas as pd
import re

# Path basis direktori data
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

def load_tkpi() -> Tuple[pd.DataFrame | None, Dict[str, str], List[str]]:
    """
    Memuat dataset TKPI (Prioritas: Total.csv) dan menstandarisasi kolom.
    """
    # Prioritas membaca file gabungan (Total)
    csv_path = DATA_DIR / "TKPI-2020.xlsx - Total.csv"
    xlsx_path = DATA_DIR / "TKPI-2020.xlsx"
    
    # Cek keberadaan file
    path = None
    if csv_path.exists():
        path = csv_path
    elif xlsx_path.exists():
        path = xlsx_path
    
    if not path:
        return None, {}, [f"File Dataset (Total.csv/xlsx) tidak ditemukan di {DATA_DIR}"]

    try:
        # Load Data
        if str(path).endswith(".csv"):
            df = pd.read_csv(path)
        else:
            df = pd.read_excel(path)
    except Exception as e:
        return None, {}, [f"Gagal membaca data: {e}"]

    # --- STANDARISASI NAMA KOLOM ---
    # Agar sistem bisa membaca kolom 'Penyakit' dan 'Alergi' dengan benar
    new_columns = {}
    for col in df.columns:
        c_up = str(col).upper().strip()
        
        # Nutrisi Utama (Wajib untuk ML)
        if "ENERGI" in c_up or "ENERGY" in c_up: new_columns[col] = "ENERGI"
        elif "PROTEIN" in c_up: new_columns[col] = "PROTEIN"
        elif "LEMAK" in c_up or "FAT" in c_up: new_columns[col] = "LEMAK"
        elif "KARBO" in c_up or "KH" in c_up: new_columns[col] = "KARBO"
        elif "NAMA" in c_up: new_columns[col] = "NAMA"
        
        # Filter Tambahan
        elif "NATRIUM" in c_up: new_columns[col] = "NATRIUM"
        elif "GULA" in c_up: new_columns[col] = "GULA"
        elif "HALAL" in c_up: new_columns[col] = "HALAL"
        
        # Target Dropdown
        elif "ALERGI" in c_up or "ALLERGI" in c_up: new_columns[col] = "ALERGI"
        elif "PENYAKIT" in c_up: new_columns[col] = "PENYAKIT"

    df = df.rename(columns=new_columns)
    
    # Bersihkan Data Numerik (Isi NaN dengan 0)
    required_ml = ["ENERGI", "PROTEIN", "LEMAK", "KARBO"]
    for c in required_ml:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    
    # Mapping untuk digunakan modul lain
    mapping = {
        "energy": "ENERGI", "protein": "PROTEIN", "fat": "LEMAK", "carb": "KARBO",
        "sodium": "NATRIUM" if "NATRIUM" in df.columns else None,
        "sugar": "GULA" if "GULA" in df.columns else None,
        "halal_flag": "HALAL" if "HALAL" in df.columns else None,
        "allergy": "ALERGI" if "ALERGI" in df.columns else None,
        "disease": "PENYAKIT" if "PENYAKIT" in df.columns else None
    }
    return df, mapping, []

def extract_dropdown_options(df: pd.DataFrame, mapping: Dict[str, str]) -> Tuple[List[str], List[str]]:
    """
    Ekstraksi opsi dropdown menggunakan SCIENTIFIC MAPPING.
    Mengubah data raw Excel yang berantakan menjadi kategori medis standar.
    """
    
    # --- 1. KAMUS PEMETAAN PENYAKIT (Scientific Standard) ---
    # Sumber: PERKENI, JNC 8, PERKI, WHO
    DISEASE_MAP = {
        # Diabetes
        "diabetes": "Diabetes Melitus",
        "dm ": "Diabetes Melitus", # Spasi agar tidak kena 'admin'
        "gula darah": "Diabetes Melitus",
        "hiperglikemia": "Diabetes Melitus",
        
        # Hipertensi
        "hipertensi": "Hipertensi",
        "darah tinggi": "Hipertensi",
        "natrium": "Hipertensi",
        
        # Kolesterol / Jantung
        "kolesterol": "Dislipidemia (Kolesterol Tinggi)",
        "lemak": "Dislipidemia (Kolesterol Tinggi)",
        "dislipidemia": "Dislipidemia (Kolesterol Tinggi)",
        "jantung": "Penyakit Jantung",
        
        # Asam Urat
        "asam urat": "Asam Urat (Gout)",
        "gout": "Asam Urat (Gout)",
        "purin": "Asam Urat (Gout)",
        
        # Ginjal
        "ginjal": "Penyakit Ginjal Kronis",
        "renal": "Penyakit Ginjal Kronis",
        
        # Obesitas
        "obesitas": "Obesitas",
        "gemuk": "Obesitas",
        "berat badan": "Obesitas",
        
        # Lambung
        "maag": "Gangguan Lambung (Maag/GERD)",
        "lambung": "Gangguan Lambung (Maag/GERD)",
        "gerd": "Gangguan Lambung (Maag/GERD)"
    }

    # --- 2. KAMUS PEMETAAN ALERGI (FDA/BPOM Standard) ---
    ALLERGY_MAP = {
        # Seafood
        "udang": "Seafood (Udang/Kepiting/Kerang)",
        "kepiting": "Seafood (Udang/Kepiting/Kerang)",
        "cumi": "Seafood (Udang/Kepiting/Kerang)",
        "kerang": "Seafood (Udang/Kepiting/Kerang)",
        "crustacea": "Seafood (Udang/Kepiting/Kerang)",
        "seafood": "Seafood (Udang/Kepiting/Kerang)",
        
        # Ikan
        "ikan": "Ikan",
        "tongkol": "Ikan",
        "tuna": "Ikan",
        "lele": "Ikan",
        
        # Telur
        "telur": "Telur & Olahannya",
        "egg": "Telur & Olahannya",
        
        # Susu
        "susu": "Susu Sapi & Laktosa",
        "laktosa": "Susu Sapi & Laktosa",
        "dairy": "Susu Sapi & Laktosa",
        "keju": "Susu Sapi & Laktosa",
        
        # Kacang
        "kacang": "Kacang-kacangan",
        "kedelai": "Kacang-kacangan",
        "tanah": "Kacang-kacangan",
        "almond": "Kacang-kacangan",
        
        # Gandum
        "gandum": "Gandum & Gluten",
        "gluten": "Gandum & Gluten",
        "tepung": "Gandum & Gluten",
        "roti": "Gandum & Gluten"
    }

    final_diseases = set()
    final_allergies = set()

    # --- PROSES MAPPING PENYAKIT ---
    col_d = mapping.get("disease")
    if col_d and col_d in df.columns:
        for val in df[col_d].dropna().astype(str):
            val_lower = val.lower()
            
            # Filter: Jangan masukkan kalimat rekomendasi positif
            if re.search(r'(baik|aman|sumber|rendah|pilihan|mencegah)', val_lower):
                continue

            # Cek mapping dictionary
            for keyword, label in DISEASE_MAP.items():
                if keyword in val_lower:
                    final_diseases.add(label)

    # --- PROSES MAPPING ALERGI ---
    col_a = mapping.get("allergy")
    if col_a and col_a in df.columns:
        for val in df[col_a].dropna().astype(str):
            val_lower = val.lower()
            
            for keyword, label in ALLERGY_MAP.items():
                if keyword in val_lower:
                    final_allergies.add(label)

    return sorted(list(final_allergies)), sorted(list(final_diseases))

# --- DEBUGGING (Cek Hasil di Terminal) ---
if __name__ == "__main__":
    df, mapping, err = load_tkpi()
    if not err:
        a, d = extract_dropdown_options(df, mapping)
        print("\n=== [HASIL LABELING ALERGI (BPOM STANDARD)] ===")
        for x in a: print(f"- {x}")
        
        print("\n=== [HASIL LABELING PENYAKIT (KEMENKES STANDARD)] ===")
        for x in d: print(f"- {x}")