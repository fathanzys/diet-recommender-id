# FILE: modules/planner.py
from __future__ import annotations
from typing import List, Dict, Any
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
    Menyusun Rencana Menu Harian dengan pendekatan Top-N Randomization.
    Tujuannya agar menu bervariasi namun tetap bernutrisi tinggi.
    """
    plan = []
    
    # 1. Filter kandidat berdasarkan kelas (4 Sehat 5 Sempurna)
    # Kita ambil Top-50 terbaik dulu agar ada variasi saat sampling
    # Asumsi: Data sudah diurutkan S_FINAL ascending (semakin kecil semakin baik)
    staples = df_ranked[df_ranked["CLASS_45"] == "staple"].head(50)
    proteins = df_ranked[df_ranked["CLASS_45"] == "protein"].head(50)
    veggies = df_ranked[df_ranked["CLASS_45"] == "vegetable"].head(50)
    fruits = df_ranked[df_ranked["CLASS_45"] == "fruit"].head(50)
    
    # Rasio Kalori per Waktu Makan (Pagi 30%, Siang 40%, Malam 30%)
    meal_ratios = {
        "Sarapan": 0.30,
        "Makan Siang": 0.40,
        "Makan Malam": 0.30
    }

    # Helper: Ambil 1 item acak dari top-N
    def get_random_top_n(df_source, n=10):
        if df_source.empty: return {}
        # Ambil sampel acak dari n teratas
        subset = df_source.head(n)
        return subset.sample(n=1).iloc[0].to_dict()

    for d in range(1, days + 1):
        day_meals = []
        daily_total = {"kcal": 0, "protein_g": 0, "fat_g": 0, "carb_g": 0}
        
        for meal_name, ratio in meal_ratios.items():
            target_kcal = tdee_target * ratio
            
            # 2. PILIH KOMPOSISI (VARIASI)
            # Menggunakan Random Sampling dari Top-Tier items
            s_item = get_random_top_n(staples)
            p_item = get_random_top_n(proteins)
            v_item = get_random_top_n(veggies)
            
            # Buat list items dasar
            raw_items = [x for x in [s_item, p_item, v_item] if x]
            
            # Tambahkan buah hanya di Siang/Malam (opsional)
            if meal_name in ["Makan Siang", "Makan Malam"]:
                f_item = get_random_top_n(fruits)
                if f_item: raw_items.append(f_item)
            
            # 3. HITUNG PORSI (SCALING)
            current_meal_total = {"kcal": 0, "protein_g": 0, "fat_g": 0, "carb_g": 0}
            meal_items_formatted = []
            
            # Hitung total kalori 'base' (per 100g)
            base_total_kcal = sum([float(x.get("ENERGI", 0)) for x in raw_items])
            
            # Scaling factor: Target / Base
            # Jika base 0, hindari div by zero
            scaling_factor = (target_kcal / base_total_kcal) if base_total_kcal > 0 else 1.0

            for item in raw_items:
                # Batasi porsi agar masuk akal (Min 30g, Max 400g)
                # Agar user tidak disuruh makan 1kg nasi cuma demi ngejar kalori
                porsi_gram = max(30, min(100 * scaling_factor, 400))
                
                # Hitung nutrisi real berdasarkan porsi
                ratio_real = porsi_gram / 100.0
                
                it_kcal = float(item.get("ENERGI", 0)) * ratio_real
                it_p = float(item.get("PROTEIN", 0)) * ratio_real
                it_l = float(item.get("LEMAK", 0)) * ratio_real
                it_k = float(item.get("KARBO", 0)) * ratio_real
                
                # Akumulasi ke Meal Total
                current_meal_total["kcal"] += it_kcal
                current_meal_total["protein_g"] += it_p
                current_meal_total["fat_g"] += it_l
                current_meal_total["carb_g"] += it_k
                
                meal_items_formatted.append({
                    "name": str(item.get("NAMA", "Unknown")),
                    "class": str(item.get("CLASS_45", "other")),
                    "portion_g": round(porsi_gram),
                    "kcal": round(it_kcal),
                    "protein_g": round(it_p, 1),
                    "fat_g": round(it_l, 1),
                    "carb_g": round(it_k, 1)
                })
            
            # Masukkan ke rekap harian
            # PENTING: Gunakan key 'total', bukan 'agg'
            day_meals.append({
                "name": meal_name,
                "items": meal_items_formatted,
                "total": current_meal_total 
            })
            
            # Tambah ke total harian
            for k in daily_total:
                daily_total[k] += current_meal_total.get(k, 0)

        plan.append({
            "day": d,
            "meals": day_meals,
            "daily_total": {k: round(v, 1) for k, v in daily_total.items()}
        })
        
    return plan