from __future__ import annotations
from pathlib import Path
from typing import Tuple, List, Dict
import pandas as pd
import numpy as np
import re

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# Kamus Pemetaan Penyakit (Scientific Standard)
DISEASE_MAP = {
    "diabetes": "Diabetes Melitus",
    "kencing manis": "Diabetes Melitus",
    "gula darah": "Diabetes Melitus",
    "hiperglikemia": "Diabetes Melitus",
    "hipertensi": "Hipertensi",
    "darah tinggi": "Hipertensi",
    "tensi": "Hipertensi",
    "jantung": "Penyakit Jantung",
    "kolesterol": "Dislipidemia (Kolesterol Tinggi)",
    "lemak darah": "Dislipidemia (Kolesterol Tinggi)",
    "ginjal": "Penyakit Ginjal Kronis",
    "asam urat": "Asam Urat (Gout)",
    "gout": "Asam Urat (Gout)",
    "maag": "Dyspepsia (Maag/GERD)",
    "gerd": "Dyspepsia (Maag/GERD)",
    "lambung": "Dyspepsia (Maag/GERD)"
}

ALLERGY_MAP = {
    "udang": "Seafood", "kepiting": "Seafood", "cumi": "Seafood", "kerang": "Seafood",
    "ikan": "Seafood", "seafood": "Seafood",
    "telur": "Telur", "susu": "Susu Sapi", "laktosa": "Susu Sapi",
    "kacang": "Kacang", "gluten": "Gluten", "tepung": "Gluten"
}

def load_tkpi() -> Tuple[pd.DataFrame | None, Dict[str, str], List[str]]:
    csv_path = DATA_DIR / "TKPI-2020.xlsx - Total.csv"
    xlsx_path = DATA_DIR / "TKPI-2020.xlsx"
    
    path = None
    if csv_path.exists(): path = csv_path
    elif xlsx_path.exists(): path = xlsx_path
    
    if not path:
        return None, {}, [f"Dataset tidak ditemukan di {DATA_DIR}"]

    try:
        if str(path).endswith(".csv"):
            df = pd.read_csv(path, sep=None, engine='python')
        else:
            df = pd.read_excel(path)
            
        # Standarisasi Kolom (Logika Anti-Duplikat & Robust)
        new_columns = {}
        found_targets = set()

        for col in df.columns:
            c_up = str(col).strip().upper()
            target = None
            
            # Identifikasi Nutrisi Utama
            if any(x in c_up for x in ["ENERGI", "ENERGY", "KALORI"]):
                target = "ENERGI"
            elif "PROTEIN" in c_up:
                target = "PROTEIN"
            elif any(x in c_up for x in ["LEMAK", "FAT"]):
                target = "LEMAK"
            elif any(x in c_up for x in ["KH", "KARBO", "CARB", "ARANG"]):
                target = "KARBO"
            
            # Identifikasi Metadata
            elif any(x in c_up for x in ["NAMA", "BAHAN", "FOOD"]):
                target = "NAMA"
            elif any(x in c_up for x in ["GOLONGAN", "KELOMPOK"]):
                target = "GOLONGAN"
            elif any(x in c_up for x in ["HALAL", "STATUS"]):
                target = "HALAL"
            elif any(x in c_up for x in ["PENYAKIT", "PANTANGAN"]):
                target = "PENYAKIT"
            elif any(x in c_up for x in ["ALERGI", "ALLERGY"]):
                target = "ALERGI"

            if target and target not in found_targets:
                new_columns[col] = target
                found_targets.add(target)

        df = df.rename(columns=new_columns)
        
        keep_cols = list(new_columns.values())
        df = df[[c for c in keep_cols if c in df.columns]].copy()

        # Pembersihan Nama Bahan
        if "NAMA" in df.columns:
            patterns = [
                r',\s*mentah', r'\s*mentah', 
                r',\s*segar', r'\s*segar', 
                r',\s*kering', r'\s*kering',
                r'Daging,\s*', r'Ikan,\s*', r'Ayam,\s*'
            ]
            for pat in patterns:
                df["NAMA"] = df["NAMA"].astype(str).str.replace(pat, "", regex=True, flags=re.IGNORECASE)
            df["NAMA"] = df["NAMA"].str.strip()

        # Konversi Data Numerik
        for c in ["ENERGI", "PROTEIN", "LEMAK", "KARBO"]:
            if c in df.columns:
                if df[c].dtype == object:
                     df[c] = df[c].astype(str).str.replace(',', '.', regex=False)
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
            else:
                df[c] = 0.0

        # Auto-Tagging Kategori
        if "CLASS_45" not in df.columns:
            df["CLASS_45"] = df.apply(_classify_food, axis=1)

        mapping = {
            "halal": "HALAL" if "HALAL" in df.columns else None,
            "allergy": "ALERGI" if "ALERGI" in df.columns else None,
            "penyakit": "PENYAKIT" if "PENYAKIT" in df.columns else None
        }

        return df, mapping, []

    except Exception as e:
        return None, {}, [f"Error load data: {str(e)}"]

def _classify_food(row):
    nama = str(row.get("NAMA", "")).lower()
    gol = str(row.get("GOLONGAN", "")).lower()
    txt = f"{nama} {gol}"

    blacklist_staple = ["gula", "minyak", "tepung bumbu", "kerupuk", "sambal", "kecap", "bumbu"]
    if any(b in txt for b in blacklist_staple):
        return "other"

    if any(k in txt for k in ["beras", "nasi", "jagung", "ubi", "singkong", "kentang", "roti", "mie", "bihun", "havermut", "oat", "biskuit", "talas", "sagu", "ketan"]):
        return "staple"
    
    if any(k in txt for k in ["bayam", "kangkung", "sawi", "wortel", "buncis", "kacang panjang", "daun", "tomat", "timun", "labu", "terong", "kol", "brokoli", "sayur", "pare", "selada", "jamur", "petai", "oyong", "tauge", "kecambah", "rebung"]):
        return "vegetable"
    
    if any(k in txt for k in ["apel", "jeruk", "pisang", "mangga", "pepaya", "semangka", "melon", "nanas", "anggur", "salak", "rambutan", "lengkeng", "durian", "buah", "jambu", "alpukat", "belimbing", "strawberry", "pir", "kurma"]):
        return "fruit"
    
    if any(k in txt for k in ["ayam", "daging", "sapi", "kambing", "ikan", "telur", "bebek", "udang", "cumi", "kerang", "kepiting", "tahu", "tempe", "kedelai", "kacang", "oncom", "susu", "keju", "yogurt", "sarden", "kornet", "bakso", "sosis", "abon", "hati", "ampela", "tongkol", "mujair", "lele"]):
        return "protein"
    
    return "other"

def extract_dropdown_options(df: pd.DataFrame, mapping: Dict[str, str]) -> Tuple[List[str], List[str]]:
    final_allergies = set()
    final_diseases = set()

    col_p = mapping.get("penyakit")
    if col_p and col_p in df.columns:
        for val in df[col_p].dropna().astype(str):
            val_lower = val.lower()
            
            # Filter Regex (Menghapus kalimat rekomendasi positif)
            if re.search(r'(baik|aman|sumber|rendah|pilihan|mencegah|anjuran)', val_lower):
                continue

            # Mapping ke Standar Scientific
            for keyword, label in DISEASE_MAP.items():
                if keyword in val_lower: final_diseases.add(label)

    col_a = mapping.get("allergy")
    if col_a and col_a in df.columns:
        for val in df[col_a].dropna().astype(str):
            val_lower = val.lower()
            for keyword, label in ALLERGY_MAP.items():
                if keyword in val_lower: final_allergies.add(label)
    
    if not final_allergies: 
        final_allergies = {"Seafood", "Kacang", "Telur", "Susu Sapi", "Gluten"}
    if not final_diseases: 
        final_diseases = {"Diabetes Melitus", "Hipertensi", "Dislipidemia (Kolesterol Tinggi)", "Asam Urat (Gout)", "Penyakit Ginjal Kronis", "Dyspepsia (Maag/GERD)"}

    return sorted(list(final_allergies)), sorted(list(final_diseases))