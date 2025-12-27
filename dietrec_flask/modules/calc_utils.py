from __future__ import annotations
from typing import Tuple

# ==============================================================================
# MODUL PERHITUNGAN GIZI PERSONAL
# Referensi: Bab 2.5 Perhitungan Kebutuhan Gizi Personal
# ==============================================================================

def mifflin_st_jeor(sex: str, weight_kg: float, height_cm: float, age_years: int) -> float:
    """
    Menghitung Basal Metabolic Rate (BMR) menggunakan persamaan Mifflin-St Jeor.
    
    [Ref: Bab 2.5.2, Persamaan 2.5 & 2.6]
    Rumus:
      - Pria: 10*BB + 6.25*TB - 5*Usia + 5
      - Wanita: 10*BB + 6.25*TB - 5*Usia - 161
    """
    sex_norm = (sex or "").strip().lower()
    
    # [Ref: Bab 2.5.2]
    if sex_norm.startswith("l") or sex_norm == "pria" or sex_norm == "male":
        return (10 * weight_kg) + (6.25 * height_cm) - (5 * age_years) + 5
    else:
        return (10 * weight_kg) + (6.25 * height_cm) - (5 * age_years) - 161

# [Ref: Bab 2.5.3, Tabel 2.3 Kategori TDEE]
PAL_MAP = {
    "sangat_ringan": 1.2,   # Pekerja Kantor
    "ringan": 1.375,        # Aktivitas harian ringan
    "sedang": 1.55,         # Aktivitas fisik sedang
    "berat": 1.725,         # Aktivitas berat
    "sangat_berat": 1.9,    # Atlet/Pekerja Berat
}

def tdee(bmr: float, activity: str) -> float:
    """
    Menghitung Total Daily Energy Expenditure (TDEE).
    
    [Ref: Bab 2.5.3, Persamaan 2.7]
    Rumus: TDEE = BMR x PAL
    """
    key = (activity or "sedang").lower().replace(" ", "_")
    pal = PAL_MAP.get(key, 1.55)
    return bmr * pal

def tdee_with_goal(bmr: float, activity: str, goal: str) -> float:
    """
    Penyesuaian TDEE berdasarkan tujuan diet.
    
    [Ref: Bab 2.5.3, Paragraf penjelas di bawah Tabel 2.3]
    - Turun Berat Badan (Cut): Kurangi 10-20% (Implementasi: 15% / 0.85)
    - Naik Berat Badan (Bulk): Tambah 10-20% (Implementasi: 15% / 1.15)
    - Pertahankan (Maintain): TDEE Normal
    """
    base_tdee = tdee(bmr, activity)
    g = (goal or "maintain").lower()
    
    if "turun" in g or "cut" in g:
        return base_tdee * 0.85  # Defisit 15%
    elif "naik" in g or "bulk" in g:
        return base_tdee * 1.15  # Surplus 15%
    
    return base_tdee  # Maintain

def bmi_and_category(weight_kg: float, height_cm: float) -> Tuple[float, str]:
    """
    Menghitung BMI dan Kategori berdasarkan standar Asia Pasifik.
    
    [Ref: Bab 2.5.1, Tabel 2.2 BMI Asia Pasifik]
    Kategori:
      - Underweight: < 18.5
      - Normal: 18.5 - 22.9
      - Overweight: 23.0 - 24.9
      - Obese: >= 25.0
    """
    h_m = height_cm / 100.0
    # [Ref: Persamaan 2.4]
    bmi = weight_kg / (h_m * h_m + 1e-9)
    r_bmi = round(bmi, 1)

    # [Ref: Tabel 2.2]
    if r_bmi < 18.5:
        cat = "Underweight"
    elif r_bmi <= 22.9:
        cat = "Normal"
    elif r_bmi <= 24.9:
        cat = "Overweight"
    else:
        cat = "Obese"
        
    return r_bmi, cat