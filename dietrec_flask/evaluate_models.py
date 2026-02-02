import sys
import os
import pandas as pd
import numpy as np
import joblib

from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# >>> TAMBAHAN UNTUK CROSS VALIDATION <<<
from sklearn.model_selection import KFold


# --- 1. SETUP IMPORT MODUL ---
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from modules.io_utils import load_tkpi
except ImportError as e:
    print(f"Error Import: {e}")
    exit(1)


# --- FUNGSI CALCULATOR SKOR (RULE-BASED) ---
def calculate_all_features(df, target_kcal=2000):
    """
    Menghitung skor deviasi nutrisi berbasis aturan (pseudo-label).
    Skor ini digunakan sebagai target evaluasi surrogate model.
    """
    df_calc = df.copy()
    eps = 1e-9

    cols = ["ENERGI", "PROTEIN", "LEMAK", "KARBO"]
    for c in cols:
        if c not in df_calc.columns:
            df_calc[c] = 0.0
        df_calc[c] = pd.to_numeric(df_calc[c], errors='coerce').fillna(0.0)

    # Target distribusi makro (heuristic)
    t_K = (0.5 * target_kcal) / 4
    t_P = (0.2 * target_kcal) / 4
    t_L = (0.3 * target_kcal) / 9

    # Deviasi relatif
    dev_E = (df_calc["ENERGI"] - target_kcal).abs() / (target_kcal + eps)
    dev_P = (df_calc["PROTEIN"] - t_P).abs() / (t_P + eps)
    dev_L = (df_calc["LEMAK"] - t_L).abs() / (t_L + eps)
    dev_K = (df_calc["KARBO"] - t_K).abs() / (t_K + eps)

    # Skor rule-based
    df_calc["S_ENERGY"] = 0.4 * dev_E
    df_calc["S_MACRO"] = (0.3 * dev_P) + (0.2 * dev_L) + (0.1 * dev_K)
    df_calc["S_RULE"] = df_calc["S_ENERGY"] + df_calc["S_MACRO"]

    return df_calc


# --- FUNGSI PREDIKSI PINTAR ---
def smart_predict(model, df_full):
    """
    Menyesuaikan fitur input sesuai model yang disimpan.
    """
    if hasattr(model, "feature_names_in_"):
        needed_feats = model.feature_names_in_
    else:
        needed_feats = ["ENERGI", "KARBO", "LEMAK", "PROTEIN",
                        "S_RULE", "S_ENERGY", "S_MACRO"]

    X = df_full.copy()
    for f in needed_feats:
        if f not in X.columns:
            X[f] = 0.0

    return model.predict(X[needed_feats])


# ============================================================
# MAIN PROGRAM
# ============================================================
def main():
    print("=" * 60)
    print("   SKRIPSI: EVALUASI PERFORMA MODEL (MAE, RMSE, R2 + CV)")
    print("=" * 60)

    # --- KONFIGURASI PATH MODEL ---
    target_path = os.path.join("models", "ensemble_komposisi.pkl")
    if not os.path.exists(target_path):
        print("ERROR: File model tidak ditemukan.")
        return

    # ============================================================
    # 1. LOAD DATASET
    # ============================================================
    print("[1/5] Memuat Dataset & Menghitung Fitur Rule-Based...")

    df, mapping, err = load_tkpi()
    if err:
        print(f"Gagal: {err}")
        return

    df_complete = calculate_all_features(df, target_kcal=2000)
    y_true = df_complete["S_RULE"]

    # ============================================================
    # 2. LOAD MODEL
    # ============================================================
    print(f"[2/5] Memuat Model dari {target_path}...")

    try:
        bundle = joblib.load(target_path)
        rf_model = bundle["rf"]
        xgb_model = bundle["xgb"]
    except Exception as e:
        print(f"Error loading pickle: {e}")
        return

    # ============================================================
    # 3. PREDIKSI MODEL
    # ============================================================
    print("[3/5] Melakukan Prediksi...")

    y_pred_rf = smart_predict(rf_model, df_complete)
    y_pred_xgb = smart_predict(xgb_model, df_complete)
    y_pred_ensemble = (0.5 * y_pred_rf) + (0.5 * y_pred_xgb)

    # ============================================================
    # 4. HITUNG METRIK UTAMA
    # ============================================================
    print("[4/5] Menghitung MAE, RMSE, dan R2 Score...")

    mae_rf = mean_absolute_error(y_true, y_pred_rf)
    mae_xgb = mean_absolute_error(y_true, y_pred_xgb)
    mae_ens = mean_absolute_error(y_true, y_pred_ensemble)

    rmse_rf = np.sqrt(mean_squared_error(y_true, y_pred_rf))
    rmse_xgb = np.sqrt(mean_squared_error(y_true, y_pred_xgb))
    rmse_ens = np.sqrt(mean_squared_error(y_true, y_pred_ensemble))

    r2_rf = r2_score(y_true, y_pred_rf)
    r2_xgb = r2_score(y_true, y_pred_xgb)
    r2_ens = r2_score(y_true, y_pred_ensemble)

    print("\n" + "=" * 85)
    print("   HASIL AKHIR (Salin Tabel ini ke Bab IV)")
    print("=" * 85)
    print(f"{'MODEL':<15} | {'MAE':<12} | {'RMSE':<12} | {'R2 Score':<12}")
    print("-" * 85)
    print(f"{'Random Forest':<15} | {mae_rf:.5f}     | {rmse_rf:.5f}     | {r2_rf:.5f}")
    print(f"{'XGBoost':<15} | {mae_xgb:.5f}     | {rmse_xgb:.5f}     | {r2_xgb:.5f}")
    print(f"{'Ensemble':<15} | {mae_ens:.5f}     | {rmse_ens:.5f}     | {r2_ens:.5f}")
    print("-" * 85)

    # ============================================================
    # 5. 5-FOLD CROSS VALIDATION
    # ============================================================
    print("\n[5/5] Menjalankan 5-Fold Cross Validation (Ensemble)...")

    kf = KFold(n_splits=5, shuffle=True, random_state=42)

    cv_r2_scores = []
    cv_rmse_scores = []

    # Gunakan fitur lengkap sesuai rule-based scoring
    X_full = df_complete[[
        "ENERGI", "PROTEIN", "LEMAK", "KARBO",
        "S_RULE", "S_ENERGY", "S_MACRO"
    ]].fillna(0)

    y_full = y_true.reset_index(drop=True)

    fold = 1
    for train_idx, test_idx in kf.split(X_full):
        X_train, X_test = X_full.iloc[train_idx], X_full.iloc[test_idx]
        y_train, y_test = y_full.iloc[train_idx], y_full.iloc[test_idx]

        # Train ulang model tiap fold
        rf_fold = rf_model.__class__(**rf_model.get_params())
        xgb_fold = xgb_model.__class__(**xgb_model.get_params())

        rf_fold.fit(X_train, y_train)
        xgb_fold.fit(X_train, y_train)

        # Ensemble prediction fold
        pred_rf_fold = rf_fold.predict(X_test)
        pred_xgb_fold = xgb_fold.predict(X_test)

        pred_ens_fold = 0.5 * pred_rf_fold + 0.5 * pred_xgb_fold

        # Hitung metrik fold
        r2_fold = r2_score(y_test, pred_ens_fold)
        rmse_fold = np.sqrt(mean_squared_error(y_test, pred_ens_fold))

        cv_r2_scores.append(r2_fold)
        cv_rmse_scores.append(rmse_fold)

        print(f"Fold-{fold} | R² = {r2_fold:.5f} | RMSE = {rmse_fold:.5f}")
        fold += 1

    print("\n--- Rata-rata Cross Validation ---")
    print("Mean R²   :", np.mean(cv_r2_scores).round(5))
    print("Mean RMSE :", np.mean(cv_rmse_scores).round(5))
    print("=" * 85)


# ============================================================
# RUN SCRIPT
# ============================================================
if __name__ == "__main__":
    main()
