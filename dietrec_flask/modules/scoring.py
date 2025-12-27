from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any
import numpy as np
import pandas as pd

try:
    import joblib
except ImportError:
    joblib = None

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = BASE_DIR / "models"
ENSEMBLE_PATH = MODEL_DIR / "ensemble_komposisi.pkl"

# ==============================================================================
# MODUL SCORING
# ==============================================================================

def _normalize_list(values: List[str]) -> List[str]:
    return [v.strip().lower() for v in values if str(v).strip()]

def _row_has_label(cell_val: Any, user_labels: List[str]) -> bool:
    if pd.isna(cell_val): return False
    txt = str(cell_val).lower().replace(";", ",")
    tokens = [t.strip() for t in txt.split(",") if t.strip()]
    return any(u in tokens for u in user_labels)

# -------------------------------------------------------------------
# 1. FILTERING
# -------------------------------------------------------------------
def apply_filters(df: pd.DataFrame, mapping: Dict[str, str], halal_pref: bool, allergies: List[str], diseases: List[str]) -> pd.DataFrame:
    out = df.copy()
    
    # Halal
    if halal_pref and mapping.get("halal_flag"):
        col = mapping["halal_flag"]
        allowed = ["halal", "ya", "1", "true"]
        out = out[out[col].astype(str).str.lower().isin(allowed)]
    
    # Alergi
    user_al = _normalize_list(allergies)
    if user_al and mapping.get("allergy"):
        out = out[~out[mapping["allergy"]].apply(lambda x: _row_has_label(x, user_al))]
        
    # Penyakit
    user_dis = _normalize_list(diseases)
    if "hipertensi" in user_dis and mapping.get("sodium") in out.columns:
        out = out[out[mapping["sodium"]] < 800]
    if any(x in user_dis for x in ["diabetes", "kencing manis"]) and mapping.get("sugar") in out.columns:
        out = out[out[mapping["sugar"]] < 15]
        
    return out.reset_index(drop=True)

# -------------------------------------------------------------------
# 2. RULE BASED (S_RULE)
# -------------------------------------------------------------------
def _classify_category(row):
    # Klasifikasi sederhana 4 sehat 5 sempurna
    txt = (str(row.get("NAMA", "")) + " " + str(row.get("KATEGORI", ""))).lower()
    
    if any(x in txt for x in ["nasi", "beras", "mie", "roti", "ubi", "kentang", "jagung"]): return "staple"
    if any(x in txt for x in ["ayam", "daging", "ikan", "telur", "tempe", "tahu", "udang", "sapi"]): return "protein"
    if any(x in txt for x in ["sayur", "bayam", "kangkung", "wortel", "sawi", "tomat"]): return "vegetable"
    if any(x in txt for x in ["jeruk", "pisang", "apel", "pepaya", "buah", "mangga"]): return "fruit"
    if any(x in txt for x in ["susu", "keju", "yogurt"]): return "milk"
    return "other"

def score_rule_macro(df: pd.DataFrame, mapping: Dict[str, str], tdee: float) -> pd.DataFrame:
    df_rb = df.copy()
    target_kcal = tdee / 3.0 # per meal
    
    # Target Makro (Gram)
    t_K = (0.5 * target_kcal) / 4
    t_P = (0.2 * target_kcal) / 4
    t_L = (0.3 * target_kcal) / 9
    
    # Ambil kolom (Nama kolom sudah distandarisasi di io_utils)
    E = df_rb["ENERGI"]
    P = df_rb["PROTEIN"]
    L = df_rb["LEMAK"]
    K = df_rb["KARBO"]
    
    eps = 1e-9
    # Hitung Deviasi untuk S_RULE
    dev_E = (E - target_kcal).abs() / (target_kcal + eps)
    dev_P = (P - t_P).abs() / (t_P + eps)
    dev_L = (L - t_L).abs() / (t_L + eps)
    dev_K = (K - t_K).abs() / (t_K + eps)
    
    # Skor Rule-Based
    df_rb["S_ENERGY"] = 0.4 * dev_E
    df_rb["S_MACRO"] = (0.3 * dev_P) + (0.2 * dev_L) + (0.1 * dev_K)
    df_rb["S_RULE"] = df_rb["S_ENERGY"] + df_rb["S_MACRO"]
    
    df_rb["CLASS_45"] = df_rb.apply(_classify_category, axis=1)
    
    return df_rb.sort_values("S_RULE")

# -------------------------------------------------------------------
# 3. ML ENSEMBLE (PREDIKSI)
# -------------------------------------------------------------------
def score_ml_ensemble(df_scored: pd.DataFrame) -> pd.DataFrame:
    """
    Fungsi Prediksi ML.
    Model dilatih dengan fitur skor deviasi: S_ENERGY, S_MACRO, S_RULE.
    """
    df_ml = df_scored.copy()
    
    if joblib and ENSEMBLE_PATH.exists():
        try:
            bundle = joblib.load(ENSEMBLE_PATH)
            
            # --- FIX HYBRID ENSEMBLE ---
            # Berdasarkan log error, RF dan XGB dilatih dengan fitur berbeda:
            # 1. RF  -> Butuh S_ENERGY, S_MACRO, S_RULE
            # 2. XGB -> Butuh ENERGI, KARBO, LEMAK, PROTEIN
            
            fts_score = ["S_ENERGY", "S_MACRO", "S_RULE"]
            fts_macro = ["ENERGI", "KARBO", "LEMAK", "PROTEIN"]
            
            # --- FIX: DYNAMIC FEATURE SELECTION ---
            # Agar tidak menebak-nebak, kita baca atribut 'feature_names_in_' dari model
            # jika tersedia (Sklearn > 1.0 & XGBoost support ini)
            
            def predict_robust(model, df, default_feats, model_name="Model"):
                try:
                    # 1. Deteksi Fitur yang diminta model
                    needed_feats = getattr(model, "feature_names_in_", default_feats)
                    
                    # 2. Pastikan kolom ada di DF (Inject 0 jika missing)
                    missing = [f for f in needed_feats if f not in df.columns]
                    if missing:
                        for f in missing: df[f] = 0.0
                        
                    # 3. Select subset kolom
                    X = df[needed_feats]
                    
                    # 4. Predict
                    return model.predict(X)
                except Exception as e:
                    print(f"[Warning ML-{model_name}] {e}")
                    return None

            # Eksekusi dengan Fallback
            pred_rf = predict_robust(bundle["rf"], df_ml, fts_macro, "RF")
            if pred_rf is None: pred_rf = df_ml["S_RULE"]
            
            pred_xgb = predict_robust(bundle["xgb"], df_ml, fts_score, "XGB")
            if pred_xgb is None: pred_xgb = df_ml["S_RULE"]

            # 4. Gabung (Ensemble)
            df_ml["S_FINAL"] = (0.5 * pred_rf) + (0.5 * pred_xgb)
            return df_ml.sort_values("S_FINAL")
            
        except Exception as e:
            print(f"[Warning ML] {e}. Fallback ke Rule-Based.")
            
    # Fallback
    df_ml["S_FINAL"] = df_ml["S_RULE"]
    return df_ml