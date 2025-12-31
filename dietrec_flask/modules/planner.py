# FILE: planner.py (REVISI FULL)
from __future__ import annotations
from typing import List, Dict, Any
import pandas as pd
import numpy as np

# ==============================================================================
# MODUL PERENCANA MENU (PLANNER) - REVISED (RANDOMIZED TOP-N)
# ==============================================================================

def optimize_meal_plan(
    df_ranked: pd.DataFrame,
    tdee_target: float,
    days: int
) -> List[Dict[str, Any]]:
    """
    Menyusun Rencana Menu Harian dengan Variasi (Top-N Randomization).
    """
    plan = []
    
    # 1. Filter kandidat berdasarkan kelas
    # Kita ambil Top-50 terbaik dulu agar ada variasi saat sampling
    # S_FINAL ascending (semakin kecil semakin baik)
    staples = df_ranked[df_ranked["CLASS_45"] == "staple"].head(50)
    proteins = df_ranked[df_ranked["CLASS_45"] == "protein"].head(50)
    veggies = df_ranked[df_ranked["CLASS_45"] == "vegetable"].head(50)
    fruits = df_ranked[df_ranked["CLASS_45"] == "fruit"].head(50)
    
    # Rasio Kalori per Waktu Makan (Pagi 30%, Siang 40%, Malam 30%)
    meal_ratios = {
        "Pagi": 0.30,
        "Siang": 0.40,
        "Malam": 0.30
    }

    # Helper untuk mengambil item secara acak dari Top-N (misal Top 5)
    def get_random_top_n(df_source, n=5):
        if df_source.empty: return {}
        # Ambil sampel acak dari n teratas
        subset = df_source.head(n)
        return subset.sample(n=1).iloc[0].to_dict()

    for d in range(1, days + 1):
        day_meals = []
        daily_total = {"kcal": 0, "protein_g": 0, "fat_g": 0, "carb_g": 0}
        
        for meal_name, ratio in meal_ratios.items():
            target_kcal = tdee_target * ratio
            
            # 2. PILIH KOMPOSISI (VARIASI DITAMBAHKAN DISINI)
            # Menggunakan Top-5 Randomization agar menu tidak monoton
            s_item = get_random_top_n(staples, n=5)
            p_item = get_random_top_n(proteins, n=5)
            v_item = get_random_top_n(veggies, n=5)
            
            # Buat list items
            raw_items = [x for x in [s_item, p_item, v_item] if x]
            
            # Jika makan siang/pagi tambahkan buah (opsional)
            if meal_name in ["Pagi", "Siang"]:
                f_item = get_random_top_n(fruits, n=5)
                if f_item: raw_items.append(f_item)
            
            # 3. HITUNG PORSI (Sama seperti logika lama, tapi lebih rapi)
            current_agg = {"kcal": 0, "protein_g": 0, "fat_g": 0, "carb_g": 0}
            meal_items_formatted = []
            
            # Hitung total kalori 'base' (per 100g)
            base_total_kcal = sum([float(x.get("ENERGI", 0)) for x in raw_items])
            
            if base_total_kcal > 0:
                # Scaling factor agar sesuai target kalori sesi makan ini
                scaling_factor = target_kcal / base_total_kcal
            else:
                scaling_factor = 1.0

            for item in raw_items:
                # Gramasi dasar 100g * scaling
                # Kita batasi porsi minimal 30g dan maksimal 300g agar masuk akal
                porsi_gram = max(30, min(100 * scaling_factor, 400))
                
                # Hitung ulang nutrisi real berdasarkan porsi
                ratio_real = porsi_gram / 100.0
                
                it_kcal = float(item.get("ENERGI", 0)) * ratio_real
                it_p = float(item.get("PROTEIN", 0)) * ratio_real
                it_l = float(item.get("LEMAK", 0)) * ratio_real
                it_k = float(item.get("KARBO", 0)) * ratio_real
                
                # Akumulasi
                current_agg["kcal"] += it_kcal
                current_agg["protein_g"] += it_p
                current_agg["fat_g"] += it_l
                current_agg["carb_g"] += it_k
                
                meal_items_formatted.append({
                    "name": str(item.get("NAMA", "Unknown")),
                    "class": str(item.get("CLASS_45", "other")),
                    "portion_g": round(porsi_gram),
                    "kcal": round(it_kcal),
                    "protein": round(it_p, 1),
                    "fat": round(it_l, 1),
                    "carb": round(it_k, 1)
                })
            
            # Masukkan ke rekap harian
            day_meals.append({
                "name": meal_name,
                "items": meal_items_formatted,
                "total": current_agg
            })
            
            # Tambah ke total harian
            for k in daily_total:
                daily_total[k] += current_agg.get(k, 0)

        plan.append({
            "day": d,
            "meals": day_meals,
            "daily_total": {k: round(v, 1) for k, v in daily_total.items()}
        })
        
    return plan