// static/js/app.js

function initResultPage() {
  const elHalal = document.getElementById('liveHalal');
  if (!elHalal) return; // Bukan halaman result

  // 1. AMBIL DATA DARI HTML (JSON PARSING)
  let appData = {};
  try {
    const scriptEl = document.getElementById('backend-data');
    if (scriptEl) {
      appData = JSON.parse(scriptEl.textContent);
    }
  } catch (e) {
    console.error("Gagal parse data:", e);
  }

  const initDays = appData.days || [];
  const initTotals = appData.totals || [];
  const initRadar = appData.radar || [];
  const targetTDEE = appData.target || 2000;

  // 2. Setup Chart: Donut
  const donutEl = document.getElementById('donutTarget');
  if (donutEl && typeof Chart !== 'undefined') {
    new Chart(donutEl.getContext('2d'), {
      type: 'doughnut',
      data: {
        labels: ['Karbo', 'Protein', 'Lemak'],
        datasets: [{ data: [50, 20, 30], backgroundColor: ['#3b82f6', '#10b981', '#f59e0b'], borderWidth: 0 }]
      },
      options: { responsive: true, maintainAspectRatio: false, cutout: '75%', plugins: { legend: { display: false } } }
    });
  }

  // 3. Setup Chart: BAR CHART (Konsistensi Kalori)
  const barEl = document.getElementById('barKcal');
  if (barEl && typeof Chart !== 'undefined') {
    new Chart(barEl.getContext('2d'), {
      type: 'bar',
      data: {
        labels: initDays,
        datasets: [{
          label: 'Total Kalori',
          data: initTotals,
          backgroundColor: '#22c55e',
          borderRadius: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, suggestedMax: targetTDEE * 1.2, grid: { display: false } },
          x: { grid: { display: false } }
        }
      }
    });
  }

  // 4. Live Recalc
  async function recalc() {
    const btn = document.getElementById('btnApply');
    btn.innerText = '...';

    // Helper ambil multiple select hidden
    const getVals = (id) => {
      const el = document.getElementById(id);
      return el ? Array.from(el.options).map(o => o.value) : [];
    };

    const payload = {
      halal: elHalal.value,
      days: document.getElementById('liveDays').value,
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
      else alert("Gagal: " + j.error);
    } catch (e) {
      console.error(e);
    } finally {
      btn.innerText = 'Update';
    }
  }

  document.getElementById('btnApply')?.addEventListener('click', (e) => {
    e.preventDefault();
    recalc();
  });
}

function initInputPage() {
  if (window.TomSelect && document.getElementById('alergiSelect')) {
    new TomSelect('#alergiSelect', { plugins: ['remove_button'], create: false });
    new TomSelect('#penyakitSelect', { plugins: ['remove_button'], create: false });
  }
}

document.addEventListener('DOMContentLoaded', () => {
  initResultPage();
  initInputPage();
});