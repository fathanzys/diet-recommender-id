import sys
import os
import pandas as pd
import numpy as np
import joblib
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# --- 1. SETUP IMPORT MODUL ---
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from modules.io_utils import load_tkpi
except ImportError as e:
    print(f"Error Import: {e}")
    exit(1)

# --- FUNGSI CALCULATOR SKOR ---
def calculate_all_features(df, target_kcal=2000):
    df_calc = df.copy()
    eps = 1e-9

    cols = ["ENERGI", "PROTEIN", "LEMAK", "KARBO"]
    for c in cols:
        if c not in df_calc.columns: df_calc[c] = 0.0
        df_calc[c] = pd.to_numeric(df_calc[c], errors='coerce').fillna(0.0)

    t_K = (0.5 * target_kcal) / 4
    t_P = (0.2 * target_kcal) / 4
    t_L = (0.3 * target_kcal) / 9

    dev_E = (df_calc["ENERGI"] - target_kcal).abs() / (target_kcal + eps)
    dev_P = (df_calc["PROTEIN"] - t_P).abs() / (t_P + eps)
    dev_L = (df_calc["LEMAK"] - t_L).abs() / (t_L + eps)
    dev_K = (df_calc["KARBO"] - t_K).abs() / (t_K + eps)

    df_calc["S_ENERGY"] = 0.4 * dev_E
    df_calc["S_MACRO"] = (0.3 * dev_P) + (0.2 * dev_L) + (0.1 * dev_K)
    df_calc["S_RULE"] = df_calc["S_ENERGY"] + df_calc["S_MACRO"]

    return df_calc

# --- FUNGSI PREDIKSI PINTAR ---
def smart_predict(model, df_full):
    if hasattr(model, "feature_names_in_"):
        needed_feats = model.feature_names_in_
    else:
        needed_feats = ["ENERGI", "KARBO", "LEMAK", "PROTEIN", "S_RULE", "S_ENERGY", "S_MACRO"]

    X = df_full.copy()
    for f in needed_feats:
        if f not in X.columns: X[f] = 0.0
    
    return model.predict(X[needed_feats])

def main():
    print("="*60)
    print("   SKRIPSI: EVALUASI PERFORMA MODEL (MAE, RMSE, R2)")
    print("="*60)

    # --- KONFIGURASI PATH ---
    target_path = os.path.join("models", "ensemble_komposisi.pkl")
    if not os.path.exists(target_path):
        target_path = os.path.join("data", "models", "ensemble_komposisi.pkl")
        if not os.path.exists(target_path):
            print("ERROR: File model tidak ditemukan.")
            return

    # 1. LOAD DATASET
    print("[1/4] Memuat Dataset & Menghitung Fitur...")
    df, mapping, err = load_tkpi()
    if err:
        print(f"Gagal: {err}")
        return

    df_complete = calculate_all_features(df, target_kcal=2000)
    y_true = df_complete["S_RULE"]

    # 2. LOAD MODEL
    print(f"[2/4] Memuat Model dari {target_path}...")
    try:
        bundle = joblib.load(target_path)
        rf_model = bundle["rf"]
        xgb_model = bundle["xgb"]
    except Exception as e:
        print(f"Error loading pickle: {e}")
        return

    # 3. PREDIKSI
    print("[3/4] Melakukan Prediksi...")
    y_pred_rf = smart_predict(rf_model, df_complete)
    y_pred_xgb = smart_predict(xgb_model, df_complete)
    y_pred_ensemble = (0.5 * y_pred_rf) + (0.5 * y_pred_xgb)

    # 4. HITUNG METRIK
    print("[4/4] Menghitung MAE, RMSE, dan R2 Score...")
    
    # MAE
    mae_rf = mean_absolute_error(y_true, y_pred_rf)
    mae_xgb = mean_absolute_error(y_true, y_pred_xgb)
    mae_ens = mean_absolute_error(y_true, y_pred_ensemble)

    # RMSE (Root Mean Squared Error)
    rmse_rf = np.sqrt(mean_squared_error(y_true, y_pred_rf))
    rmse_xgb = np.sqrt(mean_squared_error(y_true, y_pred_xgb))
    rmse_ens = np.sqrt(mean_squared_error(y_true, y_pred_ensemble))

    # R2 Score
    r2_rf = r2_score(y_true, y_pred_rf)
    r2_xgb = r2_score(y_true, y_pred_xgb)
    r2_ens = r2_score(y_true, y_pred_ensemble)

    print("\n" + "="*85)
    print("   HASIL AKHIR (Salin Tabel ini ke Bab 4)")
    print("="*85)
    print(f"{'MODEL':<15} | {'MAE (Error)':<15} | {'RMSE (Error)':<15} | {'R2 Score (Akurasi)':<20}")
    print("-" * 85)
    print(f"{'Random Forest':<15} | {mae_rf:.5f}         | {rmse_rf:.5f}         | {r2_rf:.5f}")
    print(f"{'XGBoost':<15} | {mae_xgb:.5f}         | {rmse_xgb:.5f}         | {r2_xgb:.5f}")
    print(f"{'Ensemble':<15} | {mae_ens:.5f}         | {rmse_ens:.5f}         | {r2_ens:.5f}")
    print("-" * 85)

if __name__ == "__main__":
    main()