import sys
import os
import pandas as pd
import numpy as np
import joblib
from sklearn.metrics import mean_absolute_error, mean_squared_error

# --- 1. SETUP IMPORT MODUL ---
# Memastikan kita bisa import dari folder modules/
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from modules.io_utils import load_tkpi
except ImportError as e:
    print(f"Error Import: {e}")
    print("Pastikan file ini berada sejajar dengan folder 'modules/'")
    exit(1)

# --- KONFIGURASI PATH MODEL ---
# Sesuaikan ini dengan lokasi file .pkl di laptop Anda
MODEL_PATH = os.path.join("data", "models", "ensemble_komposisi.pkl")
# Jika error file not found, coba ganti path di atas menjadi:
# MODEL_PATH = "models/ensemble_komposisi.pkl" 

def main():
    print("="*50)
    print("   SKRIPSI: EVALUASI PERFORMA MODEL ENSEMBLE")
    print("="*50)

    # 1. LOAD DATASET
    print("[1/5] Memuat Dataset TKPI...")
    df, mapping, err = load_tkpi()
    if err:
        print(f"Gagal memuat data: {err}")
        return

    # Pastikan data numerik aman
    cols_nutrisi = ["ENERGI", "PROTEIN", "LEMAK", "KARBO"]
    for c in cols_nutrisi:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
    
    # Ambil fitur input (X)
    # Sesuaikan urutan fitur dengan saat training model
    # Biasanya: [ENERGI, PROTEIN, LEMAK, KARBO]
    X = df[cols_nutrisi]

    # 2. BANGKITKAN GROUND TRUTH (PSEUDO-LABEL)
    # Karena tidak ada data rating user asli, kita gunakan Rule-Based Score
    # sebagai "Kunci Jawaban" (Target Ideal).
    print("[2/5] Membangkitkan Label Referensi (Rule-Based)...")
    
    # Skenario: Target 2000 kkal (Standar Umum)
    target_kcal = 2000
    target_p = 100  # gram
    target_l = 67   # gram
    target_k = 250  # gram
    
    # Rumus Rule-Based (Sama seperti di scoring.py)
    # Semakin mendekati 0, semakin sempurna.
    df["y_true"] = (
        0.4 * ((df["ENERGI"] - target_kcal).abs() / target_kcal) +
        0.3 * ((df["PROTEIN"] - target_p).abs() / target_p) +
        0.2 * ((df["LEMAK"] - target_l).abs() / target_l) +
        0.1 * ((df["KARBO"] - target_k).abs() / target_k)
    )

    # 3. LOAD MODEL ML
    print(f"[3/5] Memuat Model dari {MODEL_PATH}...")
    if not os.path.exists(MODEL_PATH):
        print(f"ERROR: File model tidak ditemukan di {MODEL_PATH}")
        print("Solusi: Pastikan folder 'data/models' ada dan berisi file .pkl")
        return

    try:
        bundle = joblib.load(MODEL_PATH)
        rf_model = bundle["rf"]
        xgb_model = bundle["xgb"]
    except Exception as e:
        print(f"Error loading pickle: {e}")
        return

    # 4. LAKUKAN PREDIKSI (TESTING)
    print("[4/5] Melakukan Prediksi...")
    
    # Handle feature names mismatch (Robustness)
    # Kadang model dilatih pakai nama kolom "Energi (Kal)" tapi di sini "ENERGI"
    # Kita paksa rename kolom X agar sesuai dengan feature_names_in_ model jika ada
    try:
        if hasattr(rf_model, "feature_names_in_"):
            model_feats = rf_model.feature_names_in_
            # Mapping manual sederhana jika nama beda
            # (Asumsi model dilatih dengan urutan ENERGI, PROTEIN, LEMAK, KARBO)
            X.columns = model_feats 
    except:
        pass # Lanjut saja

    y_pred_rf = rf_model.predict(X)
    y_pred_xgb = xgb_model.predict(X)
    
    # Ensemble Average (Bobot 50:50)
    y_pred_ensemble = (0.5 * y_pred_rf) + (0.5 * y_pred_xgb)

    # 5. HITUNG EVALUASI (METRIK SKRIPSI)
    print("[5/5] Menghitung Metrik Evaluasi...")
    
    mae_rf = mean_absolute_error(df["y_true"], y_pred_rf)
    mae_xgb = mean_absolute_error(df["y_true"], y_pred_xgb)
    mae_ens = mean_absolute_error(df["y_true"], y_pred_ensemble)

    print("\n" + "="*40)
    print("HASIL AKHIR (Salin ke Bab 4 Skripsi)")
    print("="*40)
    print(f"1. MAE Random Forest (Single) : {mae_rf:.5f}")
    print(f"2. MAE XGBoost (Single)       : {mae_xgb:.5f}")
    print(f"3. MAE Ensemble (Hybrid)      : {mae_ens:.5f}")
    print("-" * 40)
    
    improvement = ((mae_rf - mae_ens) / mae_rf) * 100
    print(f"Peningkatan Akurasi vs RF     : {improvement:.2f}%")
    print("="*40)
    print("\n[Interpretasi]:")
    print("Nilai MAE (Mean Absolute Error) yang lebih KECIL berarti model lebih akurat.")
    print("Jika MAE Ensemble paling kecil, hipotesis skripsi Anda TERBUKTI.")

if __name__ == "__main__":
    main()