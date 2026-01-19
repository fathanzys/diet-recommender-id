import pandas as pd
import numpy as np
import joblib
import os
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split

# ==============================================================================
# KONFIGURASI MODEL
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(BASE_DIR, "models")

if not os.path.exists(MODEL_DIR):
    os.makedirs(MODEL_DIR)

# ==============================================================================
# 1. SAFETY LAYER (FILTERING)
# ==============================================================================
def apply_filters(df, mapping, halal_pref, allergies, diseases):
    """
    LAPISAN 1: SAFETY LAYER (Rule-Based Filtering)
    Menyaring menu berdasarkan batasan absolut: Halal, Alergi, dan Penyakit.
    Sifat: Hard Constraint (Menu yang tidak lolos langsung dibuang).
    """
    out = df.copy()
    
    # helper cek label
    def _row_has_label(cell_val, keywords):
        val_lower = str(cell_val).lower()
        for k in keywords:
            if k.lower() in val_lower:
                return True
        return False

    # 1. Filter Halal (Wajib)
    if halal_pref and mapping.get("halal"):
        # Hanya ambil yang memiliki label 'halal' pada kolom terkait
        out = out[out[mapping["halal"]].astype(str).str.contains("halal", case=False, na=False)]

    # 2. Filter Alergi (Wajib)
    if allergies and mapping.get("allergy"):
        col_a = mapping["allergy"]
        for allergy in allergies:
            # Buang baris jika mengandung kata kunci alergi
            mask = out[col_a].astype(str).apply(lambda x: _row_has_label(x, [allergy]))
            out = out[~mask]

    # 3. Filter Penyakit (Wajib - Safety First)
    if diseases and mapping.get("penyakit"):
        col_p = mapping["penyakit"]
        for d in diseases:
            # Buang menu yang ditandai sebagai pantangan untuk penyakit tersebut
            mask = out[col_p].astype(str).apply(lambda x: _row_has_label(x, [d]))
            out = out[~mask]

    return out

# ==============================================================================
# 2. INTELLIGENCE LAYER (SCORING & MODELING)
# ==============================================================================
def _calculate_pseudo_label(row, target_calories=2000):
    """
    Menghitung skor manual (Pseudo-Label) sebagai target latihan model.
    """
    e = float(row.get("ENERGI", 0))
    p = float(row.get("PROTEIN", 0))
    l = float(row.get("LEMAK", 0))
    
    # Logika Sederhana: Semakin dekat ke target kalori per porsi, semakin bagus
    meal_target = target_calories * 0.33 
    diff_e = abs(e - meal_target)
    
    # Skor dasar (0-100)
    score = 100 * np.exp(-0.005 * diff_e)
    
    # Bonus Keseimbangan Makro
    if p > 10: score += 5
    if l < 20: score += 5
    
    return max(0, min(100, score))

def train_models(df):
    """
    Melatih model Random Forest dan XGBoost.
    Fitur input DIBATASI hanya 4 Makronutrien Utama.
    """
    df = df.copy()
    # Siapkan Pseudo-Label
    df["pseudo_score"] = df.apply(lambda r: _calculate_pseudo_label(r, 2000), axis=1)

    # HANYA GUNAKAN 4 MACRO UTAMA
    feature_cols = ["ENERGI", "PROTEIN", "LEMAK", "KARBO"]
    
    # Pastikan kolom ada
    for col in feature_cols:
        if col not in df.columns:
            df[col] = 0

    X = df[feature_cols].fillna(0)
    y = df["pseudo_score"]

    # Split & Train
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    rf = RandomForestRegressor(n_estimators=100, random_state=42)
    rf.fit(X_train, y_train)

    xgb = XGBRegressor(n_estimators=100, learning_rate=0.1, random_state=42)
    xgb.fit(X_train, y_train)

    # Simpan Model
    joblib.dump(rf, os.path.join(MODEL_DIR, "rf_model.pkl"))
    joblib.dump(xgb, os.path.join(MODEL_DIR, "xgb_model.pkl"))
    
    print("Model berhasil dilatih ulang dengan fitur:", feature_cols)
    return rf, xgb

def load_models():
    """Memuat model dari disk."""
    rf_path = os.path.join(MODEL_DIR, "rf_model.pkl")
    xgb_path = os.path.join(MODEL_DIR, "xgb_model.pkl")

    if os.path.exists(rf_path) and os.path.exists(xgb_path):
        rf = joblib.load(rf_path)
        xgb = joblib.load(xgb_path)
        return {"rf": rf, "xgb": xgb}
    else:
        return None

def calculate_scores(df_filtered, bundle):
    """
    Menghitung skor akhir menggunakan Ensemble Learning (RF + XGB).
    """
    if df_filtered.empty:
        return df_filtered

    # Pastikan urutan fitur sama persis dengan saat training
    feature_cols = ["ENERGI", "PROTEIN", "LEMAK", "KARBO"]
    
    df_ml = df_filtered.copy()
    
    # Handle missing values & ensure columns exist
    for col in feature_cols:
        if col not in df_ml.columns:
            df_ml[col] = 0
            
    X_input = df_ml[feature_cols].fillna(0)

    # Prediksi RF
    pred_rf = bundle["rf"].predict(X_input)
    
    # Prediksi XGBoost
    pred_xgb = bundle["xgb"].predict(X_input)

    # Ensemble: Weighted Average (50:50)
    final_score = (0.5 * pred_rf) + (0.5 * pred_xgb)
    
    df_ml["S_FINAL"] = final_score
    
    # Urutkan dari skor TERTINGGI (Descending) -> Kualitas Terbaik
    return df_ml.sort_values("S_FINAL", ascending=False)