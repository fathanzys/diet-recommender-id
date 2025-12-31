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
    } catch (e) { console.error("Data Error:", e); }

    // 2. HITUNG RATA-RATA NUTRISI (REAL TIME DARI MENU)
    let avgCarb = 50, avgProt = 20, avgFat = 30; // Default fallback
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

    // 3. CHART DONUT (PROPORSI)
    const donutEl = document.getElementById('donutTarget');
    if (donutEl && typeof Chart !== 'undefined') {
        new Chart(donutEl.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: ['Karbo (%)', 'Protein (%)', 'Lemak (%)'],
                datasets: [{ 
                    data: [avgCarb, avgProt, avgFat], 
                    backgroundColor: ['#3b82f6', '#10b981', '#f59e0b'], borderWidth: 0 
                }]
            },
            options: { responsive: true, cutout: '75%', plugins: { legend: {display: false} } }
        });
    }

    // 4. CHART BAR (KALORI)
    const barEl = document.getElementById('barKcal');
    if (barEl && typeof Chart !== 'undefined') {
        new Chart(barEl.getContext('2d'), {
            type: 'bar',
            data: {
                labels: appData.days,
                datasets: [
                    { label: 'Kalori Menu', data: appData.totals, backgroundColor: '#10b981', borderRadius: 6 },
                    { label: 'Target', data: Array(appData.days.length).fill(appData.target), type: 'line', borderColor: '#94a3b8', borderDash: [5,5] }
                ]
            },
            options: { responsive: true, scales: { x: {grid:{display:false}}, y: {beginAtZero: true} } }
        });
    }

    // 5. UPDATE BUTTON
    async function recalc() {
        const btn = document.getElementById('btnApply');
        const originalText = btn.innerHTML;
        btn.disabled = true; btn.innerHTML = "Memproses...";

        const getVals = (id) => {
            const el = document.getElementById(id);
            return el ? Array.from(el.options).map(o => o.value) : [];
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
            if (j.ok) window.location.reload();
            else alert("Error: " + j.error);
        } catch (e) {
            alert("Koneksi gagal.");
        } finally {
            btn.disabled = false; btn.innerHTML = originalText;
        }
    }

    document.getElementById('btnApply')?.addEventListener('click', (e) => {
        e.preventDefault();
        recalc();
    });
}