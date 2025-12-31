// FILE: static/js/app.js (FULL REVISION)

document.addEventListener('DOMContentLoaded', () => {
    initResultPage();
});

function initResultPage() {
    // Cek apakah kita berada di halaman Result (cari elemen kunci)
    const elHalal = document.getElementById('liveHalal');
    if (!elHalal) return; 

    // =========================================================
    // 1. AMBIL DATA DARI BACKEND (JSON PARSING)
    // =========================================================
    let appData = { days: [], totals: [], radar: [], target: 2000 };
    
    try {
        const scriptEl = document.getElementById('backend-data');
        if (scriptEl) {
            appData = JSON.parse(scriptEl.textContent);
        }
    } catch (e) {
        console.error("Gagal memparsing data backend:", e);
    }

    // =========================================================
    // 2. HITUNG RATA-RATA NUTRISI (REAL DATA)
    // =========================================================
    // Default values (jika data kosong)
    let avgCarb = 50, avgProt = 20, avgFat = 30;

    // Kita menggunakan data 'radar' dari app.py yang berisi [%Protein, %Lemak, %Karbo] per hari
    // Struktur app.py: chart_radar.append([P, L, K])
    if (appData.radar && appData.radar.length > 0) {
        let sumP = 0, sumL = 0, sumK = 0;
        
        appData.radar.forEach(dayStats => {
            sumP += dayStats[0]; // Index 0 = Protein
            sumL += dayStats[1]; // Index 1 = Lemak
            sumK += dayStats[2]; // Index 2 = Karbo
        });

        const count = appData.radar.length;
        avgProt = Math.round(sumP / count);
        avgFat  = Math.round(sumL / count);
        avgCarb = Math.round(sumK / count);
        
        // Normalisasi agar total selalu 100% (mencegah koma aneh)
        const total = avgProt + avgFat + avgCarb;
        if (total !== 100) {
            // Tambahkan selisih ke Karbo (sebagai filler terbesar)
            avgCarb += (100 - total);
        }
    }

    // =========================================================
    // 3. SETUP CHART: DOUGHNUT (Komposisi Makro)
    // =========================================================
    const donutEl = document.getElementById('donutTarget');
    if (donutEl && typeof Chart !== 'undefined') {
        new Chart(donutEl.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: ['Karbo (%)', 'Protein (%)', 'Lemak (%)'],
                datasets: [{ 
                    // Masukkan data hasil perhitungan rata-rata di atas
                    data: [avgCarb, avgProt, avgFat], 
                    backgroundColor: ['#3b82f6', '#10b981', '#f59e0b'], 
                    borderWidth: 0,
                    hoverOffset: 4
                }]
            },
            options: { 
                responsive: true, 
                maintainAspectRatio: false, 
                cutout: '75%', 
                plugins: { 
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return ` ${context.label}: ${context.raw}%`;
                            }
                        }
                    }
                } 
            }
        });
        
        // Update angka teks di tengah Donut (jika ada elemennya)
        // Opsional: Anda bisa menambahkan id="textKarbo" di HTML jika ingin angka ini berubah dinamis
        const textKarbo = document.querySelector('#donutTarget + div span.text-3xl');
        if (textKarbo) textKarbo.innerText = `${avgCarb}%`;
    }

    // =========================================================
    // 4. SETUP CHART: BAR (Konsistensi Kalori)
    // =========================================================
    const barEl = document.getElementById('barKcal');
    if (barEl && typeof Chart !== 'undefined') {
        new Chart(barEl.getContext('2d'), {
            type: 'bar',
            data: {
                labels: appData.days, // ["Hari 1", "Hari 2", ...]
                datasets: [
                    {
                        label: 'Kalori Menu',
                        data: appData.totals,
                        backgroundColor: '#10b981',
                        borderRadius: 6,
                        barPercentage: 0.6
                    },
                    {
                        label: 'Target (TDEE)',
                        // Garis target rata (array berisi nilai target berulang)
                        data: Array(appData.days.length).fill(appData.target),
                        type: 'line',
                        borderColor: '#94a3b8',
                        borderWidth: 2,
                        pointRadius: 0,
                        borderDash: [5, 5],
                        fill: false
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { 
                        beginAtZero: true, 
                        grid: { borderDash: [2, 4], color: '#f1f5f9' } 
                    },
                    x: { grid: { display: false } }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });
    }

    // =========================================================
    // 5. LOGIKA TOMBOL UPDATE (LIVE RECALC)
    // =========================================================
    async function recalc() {
        const btn = document.getElementById('btnApply');
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = `
            <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white inline" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            Memproses...`;

        // Helper untuk mengambil value dari multiselect (jika hidden inputs digunakan)
        const getVals = (id) => {
            const el = document.getElementById(id);
            return el ? Array.from(el.options).map(o => o.value) : [];
        };

        const payload = {
            halal: document.getElementById('liveHalal').value,
            // Jika elemen ini hidden/tidak ada, gunakan default dari backend data
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
                alert("Gagal memperbarui menu: " + (j.error || "Unknown error"));
            }
        } catch (e) {
            console.error("Error fetching recalc:", e);
            alert("Terjadi kesalahan koneksi.");
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }

    // Attach Event Listener ke Tombol Apply
    const btnApply = document.getElementById('btnApply');
    if (btnApply) {
        btnApply.addEventListener('click', (e) => {
            e.preventDefault();
            recalc();
        });
    }
}