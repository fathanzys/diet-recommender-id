import matplotlib.pyplot as plt
import numpy as np

# ==========================================
# DATA HASIL EVALUASI (Dari Screenshot Anda)
# ==========================================
models = ['Random Forest', 'XGBoost', 'Ensemble']
mae_scores  = [0.00088, 0.00415, 0.00205]
rmse_scores = [0.00129, 0.00558, 0.00275]
r2_scores   = [0.99974, 0.99526, 0.99885]

# Setup Canvas
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
plt.suptitle('Evaluasi Kinerja Model Rekomendasi Diet (Metrik Regresi)', fontsize=16, y=1.02)

# ==========================================
# GRAFIK 1: PERBANDINGAN ERROR (MAE & RMSE)
# ==========================================
x = np.arange(len(models))
width = 0.35

rects1 = ax1.bar(x - width/2, mae_scores, width, label='MAE (Mean Abs Error)', color='#3b82f6', alpha=0.9)
rects2 = ax1.bar(x + width/2, rmse_scores, width, label='RMSE (Root Mean Sq)', color='#f59e0b', alpha=0.9)

ax1.set_ylabel('Tingkat Kesalahan (Semakin Kecil = Lebih Baik)', fontsize=10)
ax1.set_title('Tingkat Error Prediksi (Lower is Better)', fontsize=12, fontweight='bold')
ax1.set_xticks(x)
ax1.set_xticklabels(models)
ax1.legend()
ax1.grid(axis='y', linestyle='--', alpha=0.3)

# ==========================================
# GRAFIK 2: PERBANDINGAN AKURASI (R2 SCORE)
# ==========================================
rects3 = ax2.bar(models, r2_scores, width=0.5, color='#10b981', alpha=0.9)

ax2.set_ylabel('R2 Score (Mendekati 1.0 = Sempurna)', fontsize=10)
ax2.set_title('Akurasi Fitting Model (Higher is Better)', fontsize=12, fontweight='bold')

# PENTING: Zoom sumbu Y agar perbedaan antar model terlihat
# Karena semua nilainya 0.99xx, kalau dimulai dari 0 tidak akan kelihatan bedanya.
ax2.set_ylim(0.990, 1.0005) 
ax2.grid(axis='y', linestyle='--', alpha=0.3)

# ==========================================
# FUNGSI LABEL ANGKA DI ATAS BAR
# ==========================================
def autolabel(rects, ax):
    """Menempelkan label angka presisi di atas setiap bar"""
    for rect in rects:
        height = rect.get_height()
        ax.annotate(f'{height:.5f}',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=9, fontweight='bold')

autolabel(rects1, ax1)
autolabel(rects2, ax1)
autolabel(rects3, ax2)

# Finalisasi
plt.tight_layout()
filename = 'grafik_evaluasi.png'
plt.savefig(filename, dpi=300, bbox_inches='tight')
print(f"✅ Grafik berhasil disimpan sebagai '{filename}'")
plt.show()