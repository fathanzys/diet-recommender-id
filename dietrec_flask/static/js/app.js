// FILE: static/js/app.js
document.addEventListener('DOMContentLoaded', () => {
    initResultPage();
});

function initResultPage() {
    const elHalal = document.getElementById('liveHalal');
    if (!elHalal) return; 

    // 1. AMBIL DATA DARI BACKEND
    let appData = { days: [], totals: [], radar: [], target: 2000 };
    try {
        const scriptEl = document.getElementById('backend-data');
        if (scriptEl) appData = JSON.parse(scriptEl.textContent);
    } catch (e) { 
        console.error("Data Error:", e); 
    }

    // 2. HITUNG RATA-RATA NUTRISI (REAL TIME DARI MENU UNTUK DONUT CHART)
    let avgCarb = 50, avgProt = 20, avgFat = 30; // Fallback ideal sesuai Bab 3.3.3
    if (appData.radar && appData.radar.length > 0) {
        let sumP = 0, sumL = 0, sumK = 0;
        appData.radar.forEach(d => {
            sumP += d[0]; sumL += d[1]; sumK += d[2];
        });
        const n = appData.radar.length;
        avgProt = Math.round(sumP/n);
        avgFat = Math.round(sumL/n);
        avgCarb = Math.round(sumK/n);
    }

    // 3. CHART DONUT (PROPORSI MAKRONUTRIEN)
    const donutEl = document.getElementById('donutTarget');
    if (donutEl && typeof Chart !== 'undefined') {
        new Chart(donutEl.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: ['Karbo (%)', 'Protein (%)', 'Lemak (%)'],
                datasets: [{ 
                    data: [avgCarb, avgProt, avgFat], 
                    backgroundColor: ['#3b82f6', '#10b981', '#f59e0b'], 
                    borderWidth: 0 
                }]
            },
            options: { 
                responsive: true, 
                cutout: '75%', 
                plugins: { 
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (item) => ` ${item.label}: ${item.raw}%`
                        }
                    }
                } 
            }
        });
    }

    // 4. CHART BAR (EVALUASI KALORI / CALORIE GAP)
    const barEl = document.getElementById('barKcal');
    if (barEl && typeof Chart !== 'undefined') {
        // Variasi warna hijau untuk estetika visual antar hari
        const barColors = ['#10b981', '#059669', '#34d399', '#065f46', '#6ee7b7', '#064e3b', '#10b981'];

        new Chart(barEl.getContext('2d'), {
            type: 'bar',
            data: {
                labels: appData.days,
                datasets: [
                    { 
                        label: 'Kalori Menu Aktual', 
                        data: appData.totals, 
                        backgroundColor: barColors.slice(0, appData.days.length), 
                        borderRadius: 8,
                        order: 2
                    },
                    { 
                        label: 'Target Batas Energi (TDEE)', 
                        data: Array(appData.days.length).fill(appData.target), 
                        type: 'line', 
                        borderColor: '#ef4444', // Merah tegas untuk evaluasi presisi
                        borderWidth: 3,
                        pointRadius: 5,
                        pointBackgroundColor: '#ef4444',
                        fill: false,
                        order: 1 // Garis berada di depan batang
                    }
                ]
            },
            options: { 
                responsive: true, 
                scales: { 
                    x: { grid: { display: false } }, 
                    y: { 
                        beginAtZero: false, 
                        suggestedMin: Math.max(0, appData.target - 500),
                        title: { display: true, text: 'Kilo Kalori (kkal)' }
                    } 
                },
                plugins: {
                    legend: { position: 'top' },
                    tooltip: {
                        callbacks: {
                            label: (context) => `${context.dataset.label}: ${context.parsed.y} kkal`
                        }
                    }
                }
            }
        });
    }

    // 5. MEKANISME RECALC (AJAX / FETCH API)
    async function recalc() {
        const btn = document.getElementById('btnApply');
        if (!btn) return;

        const originalText = btn.innerHTML;
        btn.disabled = true; 
        btn.innerHTML = `<span class="animate-pulse">Memproses...</span>`;

        const getVals = (id) => {
            const el = document.getElementById(id);
            if (!el || !el.tomselect) {
                return el ? Array.from(el.options).filter(o => o.selected).map(o => o.value) : [];
            }
            return el.tomselect.getValue(); // Integrasi dengan TomSelect jika digunakan
        };

        const payload = {
            halal: document.getElementById('liveHalal').value,
            days: document.getElementById('liveDays')?.value || 3,
            allergies: getVals('liveAlergi'),
            diseases: getVals('livePenyakit')
        };

        try {
            const r = await fetch('/api/recalc', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const j = await r.json();
            if (j.ok) {
                window.location.reload();
            } else {
                alert("Gagal memperbarui rencana: " + j.error);
            }
        } catch (e) {
            alert("Terjadi kesalahan koneksi ke server.");
        } finally {
            btn.disabled = false; 
            btn.innerHTML = originalText;
        }
    }

    // Event Listener untuk tombol "Terapkan" atau "Update"
    document.getElementById('btnApply')?.addEventListener('click', (e) => {
        e.preventDefault();
        recalc();
    });
}