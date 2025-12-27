from __future__ import annotations
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np

# ==============================================================================
# MODUL PERENCANA MENU (PLANNER)
# Referensi: Bab 3.3.2 Alur Proses & Bab 2.6 Evaluasi Nutrisi
# ==============================================================================

def optimize_meal_plan(
    df_ranked: pd.DataFrame,
    tdee_target: float,
    days: int
) -> List[Dict[str, Any]]:
    """
    Menyusun Rencana Menu Harian.
    
    [Ref: Bab 3.3.2 Alur Proses Sistem]
    Langkah:
    1. Ambil menu valid dengan Skor Terbaik (S_FINAL terkecil).
    2. Susun kombinasi Staple + Protein + Sayur.
    3. Optimasi Porsi untuk meminimalkan Calorie Gap [Ref: Bab 2.6.1].
    """
    plan = []
    
    # Filter kandidat berdasarkan kelas (4 Sehat 5 Sempurna)
    staples = df_ranked[df_ranked["CLASS_45"] == "staple"]
    proteins = df_ranked[df_ranked["CLASS_45"] == "protein"]
    veggies = df_ranked[df_ranked["CLASS_45"] == "vegetable"]
    fruits = df_ranked[df_ranked["CLASS_45"] == "fruit"]
    milks = df_ranked[df_ranked["CLASS_45"] == "milk"]
    others = df_ranked[df_ranked["CLASS_45"] == "other"]

    # Target Energi per Meal (Asumsi 3x Makan Utama)
    target_per_meal = tdee_target / 3.0

    for d in range(1, days + 1):
        day_meals = []
        
        # [Ref: Bab 3.3.2 Variasi Menu]
        # Menggunakan shift index agar menu hari ke-n berbeda dengan hari ke-(n-1)
        shift = (d - 1) * 2 
        
        for meal_name in ["Sarapan", "Makan Siang", "Makan Malam"]:
            
            # Helper: Ambil item terbaik dengan offset rotasi
            # Return type explicit: Series atau None
            def pick_best(source_df: pd.DataFrame, offset: int = 0) -> Optional[pd.Series]:
                if source_df.empty: 
                    return None
                # Pilih berdasarkan S_FINAL terendah (sudah disort di module scoring)
                idx = (shift + offset) % len(source_df)
                return source_df.iloc[idx]

            # Komposisi Meal [Ref: Konsep Gizi Seimbang]
            st = pick_best(staples, offset=0 if meal_name=="Sarapan" else 1)
            pr = pick_best(proteins, offset=0 if meal_name=="Sarapan" else 1)
            vg = pick_best(veggies, offset=0)
            
            # Tambahan: Buah (Siang), Susu (Pagi)
            fr = pick_best(fruits, offset=0) if meal_name == "Makan Siang" else None
            mk = pick_best(milks, offset=0) if meal_name == "Sarapan" else None

            # Gabungkan item yang ada (Filter None)
            candidates: List[pd.Series] = [x for x in [st, pr, vg, fr, mk] if x is not None]
            
            # Fallback jika data kategori kosong (Fix Error Type Safety)
            # Pastikan item dari 'others' tidak None sebelum di-append
            if not candidates and not others.empty:
                backup_item = pick_best(others, 0)
                if backup_item is not None:
                    candidates.append(backup_item)

            # --- Optimasi Porsi (Minimalkan Calorie Gap) ---
            # [Ref: Bab 2.6.1 Calorie Gap (Delta E)]
            
            # Total energi mentah (per 100g)
            # Menggunakan .get() untuk keamanan akses kolom series
            base_kcal = sum(float(c.get("ENERGI", 0)) for c in candidates)
            
            # Hitung Ratio agar Total Energi Meal mendekati Target
            ratio = target_per_meal / (base_kcal + 1e-9)
            # Batasi scaling porsi (0.5x s.d 2.5x porsi standar 100g) agar wajar
            ratio = np.clip(ratio, 0.5, 2.5)

            current_agg = {"kcal": 0, "protein_g": 0, "fat_g": 0, "carb_g": 0}
            meal_items_formatted = []
            
            for item in candidates:
                # Konversi ke porsi matang/sajian
                porsi_gram = 100.0 * ratio
                
                # Akses aman ke nilai nutrisi
                val_energi = float(item.get("ENERGI", 0))
                val_protein = float(item.get("PROTEIN", 0))
                val_lemak = float(item.get("LEMAK", 0))
                val_karbo = float(item.get("KARBO", 0))
                
                it_kcal = val_energi * ratio
                it_p = val_protein * ratio
                it_l = val_lemak * ratio
                it_k = val_karbo * ratio
                
                current_agg["kcal"] += it_kcal
                current_agg["protein_g"] += it_p
                current_agg["fat_g"] += it_l
                current_agg["carb_g"] += it_k
                
                meal_items_formatted.append({
                    "name": str(item.get("NAMA", "Unknown")),
                    "class": str(item.get("CLASS_45", "other")),
                    "portion_g": round(porsi_gram),
                    "kcal": round(it_kcal),
                    "protein_g": round(it_p, 1),
                    "fat_g": round(it_l, 1),
                    "carb_g": round(it_k, 1)
                })
                
            day_meals.append({
                "name": meal_name,
                "items": meal_items_formatted,
                "agg": current_agg
            })
            
            # Increment shift intra-day
            shift += 1

        plan.append({"day": d, "meals": day_meals})

    return plan