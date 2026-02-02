import pandas as pd
import numpy as np
import joblib
import os

from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor

from sklearn.model_selection import train_test_split, KFold, cross_val_score
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# ==============================================================================
# KONFIGURASI MODEL
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(BASE_DIR, "models")

if not os.path.exists(MODEL_DIR):
    os.makedirs(MODEL_DIR)

# ==============================================================================
# 1. SAFETY LAYER (RULE-BASED FILTERING)
# ==============================================================================
def apply_filters(df, mapping, halal_pref, allergies, diseases):
    """
    LAPISAN 1: SAFETY LAYER (Rule-Based Filtering)

    Menyaring menu berdasarkan batasan absolut:
    - Halal
    - Alergi
    - Penyakit

    Sifat: Hard Constraint (menu yang tidak lolos langsung dibuang).
    """
    out = df.copy()

    def _row_has_label(cell_val, keywords):
        val_lower = str(cell_val).lower()
        return any(k.lower() in val_lower for k in keywords)

    # 1. Filter Halal
    if halal_pref and mapping.get("halal"):
        out = out[out[mapping["halal"]].astype(str).str.contains(
            "halal", case=False, na=False
        )]

    # 2. Filter Alergi
    if allergies and mapping.get("allergy"):
        col_a = mapping["allergy"]
        for allergy in allergies:
            mask = out[col_a].astype(str).apply(
                lambda x: _row_has_label(x, [allergy])
            )
            out = out[~mask]

    # 3. Filter Penyakit
    if diseases and mapping.get("penyakit"):
        col_p = mapping["penyakit"]
        for d in diseases:
            mask = out[col_p].astype(str).apply(
                lambda x: _row_has_label(x, [d])
            )
            out = out[~mask]

    return out


# ==============================================================================
# 2. PSEUDO-LABEL GENERATOR (RULE-BASED SCORE)
# ==============================================================================
def _calculate_pseudo_label(row, target_calories=2000):
    """
    Menghasilkan skor deviasi nutrisi (pseudo-label).

    Skor ini menjadi target pelatihan model Ensemble Learning.
    """
    e = float(row.get("ENERGI", 0))
    p = float(row.get("PROTEIN", 0))
    l = float(row.get("LEMAK", 0))

    # Target energi per meal (1/3 TDEE)
    meal_target = target_calories * 0.33
    diff_e = abs(e - meal_target)

    # Skor dasar (0–100)
    score = 100 * np.exp(-0.005 * diff_e)

    # Bonus keseimbangan makro sederhana
    if p > 10:
        score += 5
    if l < 20:
        score += 5

    return max(0, min(100, score))


# ==============================================================================
# 3. TRAINING + 5-FOLD CROSS VALIDATION
# ==============================================================================
def train_models(df):
    """
    Melatih model Random Forest dan XGBoost.

    Evaluasi dilakukan dengan:
    - Train-test split (80:20)
    - 5-Fold Cross Validation

    Target regresi: pseudo-label deviasi nutrisi.
    """
    df = df.copy()

    # Generate pseudo-label
    df["pseudo_score"] = df.apply(
        lambda r: _calculate_pseudo_label(r, 2000), axis=1
    )

    # Input features hanya 4 makronutrien utama
    feature_cols = ["ENERGI", "PROTEIN", "LEMAK", "KARBO"]

    for col in feature_cols:
        if col not in df.columns:
            df[col] = 0

    X = df[feature_cols].fillna(0)
    y = df["pseudo_score"]

    # ============================
    # Train-Test Split (80:20)
    # ============================
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # ============================
    # Model Definitions
    # ============================
    rf = RandomForestRegressor(
        n_estimators=100,
        random_state=42
    )

    xgb = XGBRegressor(
        n_estimators=100,
        learning_rate=0.1,
        random_state=42
    )

    # ============================
    # Training
    # ============================
    rf.fit(X_train, y_train)
    xgb.fit(X_train, y_train)

    # ============================
    # Test Evaluation
    # ============================
    pred_rf = rf.predict(X_test)
    pred_xgb = xgb.predict(X_test)

    # Ensemble output
    pred_ensemble = 0.5 * pred_rf + 0.5 * pred_xgb

    mae = mean_absolute_error(y_test, pred_ensemble)
    rmse = np.sqrt(mean_squared_error(y_test, pred_ensemble))
    r2 = r2_score(y_test, pred_ensemble)

    print("\n=== TEST SET PERFORMANCE ===")
    print("MAE  :", round(mae, 5))
    print("RMSE :", round(rmse, 5))
    print("R²   :", round(r2, 5))

    # ============================
    # 5-Fold Cross Validation
    # ============================
    print("\n=== 5-FOLD CROSS VALIDATION ===")

    kf = KFold(n_splits=5, shuffle=True, random_state=42)

    r2_scores = cross_val_score(
        rf, X, y, cv=kf, scoring="r2"
    )

    rmse_scores = cross_val_score(
        rf, X, y, cv=kf,
        scoring="neg_root_mean_squared_error"
    )

    print("RF Mean R²  :", round(np.mean(r2_scores), 5))
    print("RF Mean RMSE:", round(-np.mean(rmse_scores), 5))

    # ============================
    # Save Models
    # ============================
    joblib.dump(rf, os.path.join(MODEL_DIR, "rf_model.pkl"))
    joblib.dump(xgb, os.path.join(MODEL_DIR, "xgb_model.pkl"))

    print("\nModel berhasil dilatih dan disimpan.")
    return rf, xgb


# ==============================================================================
# 4. LOAD MODEL
# ==============================================================================
def load_models():
    """Memuat model Random Forest dan XGBoost dari disk."""
    rf_path = os.path.join(MODEL_DIR, "rf_model.pkl")
    xgb_path = os.path.join(MODEL_DIR, "xgb_model.pkl")

    if os.path.exists(rf_path) and os.path.exists(xgb_path):
        rf = joblib.load(rf_path)
        xgb = joblib.load(xgb_path)
        return {"rf": rf, "xgb": xgb}

    return None


# ==============================================================================
# 5. SCORING MENU (ENSEMBLE INFERENCE)
# ==============================================================================
def calculate_scores(df_filtered, bundle):
    """
    Menghitung skor akhir rekomendasi menggunakan Ensemble Learning (RF + XGB).
    """
    if df_filtered.empty:
        return df_filtered

    feature_cols = ["ENERGI", "PROTEIN", "LEMAK", "KARBO"]

    df_ml = df_filtered.copy()

    for col in feature_cols:
        if col not in df_ml.columns:
            df_ml[col] = 0

    X_input = df_ml[feature_cols].fillna(0)

    # Prediksi RF dan XGB
    pred_rf = bundle["rf"].predict(X_input)
    pred_xgb = bundle["xgb"].predict(X_input)

    # Ensemble score
    df_ml["S_FINAL"] = 0.5 * pred_rf + 0.5 * pred_xgb

    # Ranking final
    return df_ml.sort_values("S_FINAL", ascending=False)
