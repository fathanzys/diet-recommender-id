from __future__ import annotations
import io
import datetime
import traceback
from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify

# --- IMPORT MODUL UTAMA ---
try:
    from modules.io_utils import load_tkpi, extract_dropdown_options
    from modules.calc_utils import mifflin_st_jeor, tdee_with_goal, bmi_and_category
    from modules.scoring import apply_filters, score_rule_macro, score_ml_ensemble
    from modules.planner import optimize_meal_plan
except ImportError as e:
    print(f"CRITICAL ERROR: {e}")
    exit(1)

# --- IMPORT REPORTLAB (PDF GENERATOR) ---
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
except ImportError:
    print("WARNING: ReportLab belum diinstall. Fitur PDF tidak akan berjalan.")

app = Flask(__name__)
app.secret_key = "skripsi_secret_key_123"

# ==============================================================================
# CORE LOGIC (BACKEND ENGINE)
# ==============================================================================
def compute_engine(form_data: dict):
    try:
        # 1. Parsing Input User
        age = int(form_data.get("age", 25))
        weight = float(form_data.get("weight", 60))
        height = float(form_data.get("height", 170))
        days = int(form_data.get("days", 3))
        sex = form_data.get("sex", "Laki-laki")
        activity = form_data.get("activity", "sedang")
        goal = form_data.get("goal", "maintain")
        halal_pref = (str(form_data.get("halal", "ya")).lower() == "ya")

        # Helper untuk list input
        def norm_list(val):
            if isinstance(val, list): return [str(x).strip() for x in val if str(x).strip()]
            if isinstance(val, str): return [x.strip() for x in val.split(",") if x.strip()]
            return []

        allergies = norm_list(form_data.get("allergies"))
        diseases = norm_list(form_data.get("diseases"))

        # 2. Perhitungan Gizi (Bab 2.5)
        bmr = mifflin_st_jeor(sex, weight, height, age)
        tdee_val = tdee_with_goal(bmr, activity, goal)
        bmi, bmi_cat = bmi_and_category(weight, height)

        meta = {
            "age": age, "sex": sex, "weight": weight, "height": height,
            "bmr": round(bmr, 0), "tdee": round(tdee_val, 0),
            "bmi": bmi, "bmi_cat": bmi_cat,
            "activity": activity, "goal": goal, "days": days,
            "halal": "Ya" if halal_pref else "Tidak",
            "allergies": allergies, "diseases": diseases
        }

        # 3. Load Dataset & Filtering (Bab 3)
        df, mapping, errs = load_tkpi()
        if errs: return None, meta, errs

        df_filtered = apply_filters(df, mapping, halal_pref, allergies, diseases)
        meta["count_candidates"] = len(df_filtered)
        
        if df_filtered.empty: 
            return None, meta, ["Tidak ada menu yang lolos filter (Cek batasan Alergi/Penyakit)."]

        # 4. Scoring & Planning (Hybrid System)
        df_rb = score_rule_macro(df_filtered, mapping, tdee_val)
        df_ranked = score_ml_ensemble(df_rb)
        plan = optimize_meal_plan(df_ranked, tdee_val, days)

        return {"ranked": df_ranked, "plan": plan}, meta, []

    except Exception as e:
        traceback.print_exc()
        return None, {}, [f"System Error: {str(e)}"]

# ==============================================================================
# ROUTES (WEB ENDPOINTS)
# ==============================================================================
@app.route("/")
def welcome():
    return render_template("welcome.html")

@app.route("/input", methods=["GET", "POST"])
def input_page():
    df, mapping, _ = load_tkpi()
    al_opts, dis_opts = ([], []) if df is None else extract_dropdown_options(df, mapping)

    if request.method == "POST":
        data = request.form.to_dict()
        data["allergies"] = ",".join(request.form.getlist("allergies[]"))
        data["diseases"] = ",".join(request.form.getlist("diseases[]"))
        session["form_data"] = data
        return redirect(url_for("result"))

    return render_template("input.html", allergies_opts=al_opts, diseases_opts=dis_opts, form=session.get("form_data", {}))

@app.route("/result")
def result():
    data = session.get("form_data")
    if not data: return redirect(url_for("input_page"))

    res, meta, errs = compute_engine(data)
    if errs: return f"Error: {errs}"

    # --- PREPARE DATA FOR CHARTS (Frontend) ---
    chart_days = [f"Hari {d['day']}" for d in res["plan"]]
    
    # [SINKRONISASI] Menggunakan key 'total' (bukan 'agg')
    chart_kcal = [int(sum(m['total']['kcal'] for m in d['meals'])) for d in res["plan"]]
    
    chart_radar = []
    for d in res["plan"]:
        # [SINKRONISASI] Menggunakan key 'total'
        P = sum(m['total']['protein_g'] for m in d['meals'])
        L = sum(m['total']['fat_g'] for m in d['meals'])
        K = sum(m['total']['carb_g'] for m in d['meals'])
        
        # Konversi ke % Kalori (P=4, L=9, K=4)
        cal_P = P * 4
        cal_L = L * 9
        cal_K = K * 4
        total_cal = max(1, cal_P + cal_L + cal_K)
        
        chart_radar.append([
            round(cal_P/total_cal*100, 1), 
            round(cal_L/total_cal*100, 1), 
            round(cal_K/total_cal*100, 1)
        ])

    df, mapping, _ = load_tkpi()
    al_opts, dis_opts = ([], []) if df is None else extract_dropdown_options(df, mapping)

    return render_template("result.html", 
                           meta=meta, 
                           plan=res["plan"],
                           chart_days=chart_days,
                           chart_kcal=chart_kcal,
                           chart_radar=chart_radar,
                           tdee_target=meta["tdee"],
                           allergies_opts=al_opts,
                           diseases_opts=dis_opts)

@app.route("/api/recalc", methods=["POST"])
def api_recalc():
    """Endpoint untuk update menu tanpa reload halaman penuh"""
    try:
        req = request.json
        base = session.get("form_data", {}).copy()
        
        # Update preferensi baru
        base.update({
            "halal": req.get("halal"),
            "days": req.get("days"),
            "allergies": req.get("allergies", []),
            "diseases": req.get("diseases", [])
        })
        
        # Simpan kembali ke session
        sess = base.copy()
        if isinstance(sess["allergies"], list): sess["allergies"] = ",".join(sess["allergies"])
        if isinstance(sess["diseases"], list): sess["diseases"] = ",".join(sess["diseases"])
        session["form_data"] = sess

        # Re-run engine
        res, meta, errs = compute_engine(base)
        if errs: return jsonify({"ok": False, "error": errs[0]})

        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route("/export_pdf")
def export_pdf():
    """
    Generate Laporan PDF dengan fitur Clean Name (menghapus kata 'mentah', 'segar', dll).
    """
    data = session.get("form_data")
    if not data: return redirect(url_for("input_page"))
    
    res, meta, errs = compute_engine(data)
    if errs or not res: return "Data tidak valid untuk PDF."

    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, 
                                rightMargin=40, leftMargin=40, 
                                topMargin=40, bottomMargin=40)
        
        styles = getSampleStyleSheet()
        style_title = ParagraphStyle('CustomTitle', parent=styles['Title'], fontSize=20, textColor=colors.HexColor('#14532d'), spaceAfter=10)
        style_h2 = ParagraphStyle('CustomH2', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor('#15803d'), spaceBefore=15, spaceAfter=8)
        style_normal = styles['Normal']
        
        story = []

        # --- FUNGSI PEMBERSIH NAMA (Supaya PDF enak dibaca) ---
        def clean_name(txt):
            # Hapus kata teknis agar terlihat seperti "Menu", bukan "Bahan"
            bad_words = [", mentah", " mentah", ", segar", " segar", ", kering", " kering", "Daging, "]
            cleaned = str(txt)
            for w in bad_words:
                cleaned = cleaned.replace(w, "")
                cleaned = cleaned.replace(w.lower(), "")
                cleaned = cleaned.replace(w.upper(), "")
            return cleaned.strip()

        # --- HEADER ---
        story.append(Paragraph("Laporan Rencana Diet Personal", style_title))
        story.append(Paragraph(f"Dibuat oleh NutriPlan • {datetime.datetime.now().strftime('%d %B %Y')}", style_normal))
        story.append(Spacer(1, 20))

        # --- SECTION 1: PROFIL ---
        data_profil = [
            ["INFORMASI PENGGUNA", ""],
            [f"Target: {str(meta['goal']).upper()}", f"BMR: {meta['bmr']} kkal"],
            [f"BMI: {meta['bmi']} ({meta['bmi_cat']})", f"TDEE: {meta['tdee']} kkal"]
        ]
        t_prof = Table(data_profil, colWidths=[230, 230])
        t_prof.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (1,0), colors.HexColor('#dcfce7')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
            ('FONTNAME', (0,0), (1,0), 'Helvetica-Bold'),
            ('PADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(t_prof)
        story.append(Spacer(1, 25))

        # --- SECTION 2: MEAL PLAN ---
        for day in res["plan"]:
            # Hitung Total Kalori Harian
            total_cal = int(sum(m['total']['kcal'] for m in day['meals']))
            story.append(Paragraph(f"HARI KE-{day['day']} — Total: {total_cal} kkal", style_h2))
            
            for meal in day['meals']:
                story.append(Paragraph(f"<b>{meal['name']}</b> (Est. {int(meal['total']['kcal'])} kkal)", style_normal))
                story.append(Spacer(1, 4))
                
                # Tabel Menu Detail
                menu_data = [["Kategori", "Nama Menu", "Porsi", "Energi", "P", "L", "K"]]
                for item in meal['items']:
                    # Gunakan clean_name() di sini
                    display_name = clean_name(item.get('name',''))
                    
                    menu_data.append([
                        str(item.get('class','')).capitalize(),
                        Paragraph(display_name, styles['BodyText']), 
                        f"{item.get('portion_g',0)}g",
                        f"{int(item.get('kcal',0))}",
                        f"{item.get('protein_g',0)}",
                        f"{item.get('fat_g',0)}",
                        f"{item.get('carb_g',0)}"
                    ])
                
                t_menu = Table(menu_data, colWidths=[60, 180, 50, 40, 30, 30, 30])
                t_menu.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
                    ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
                    ('FONTSIZE', (0,0), (-1,-1), 8),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('ALIGN', (2,0), (-1,-1), 'RIGHT'), # Angka rata kanan
                ]))
                story.append(t_menu)
                story.append(Spacer(1, 12))
                
            story.append(PageBreak())

        # --- FOOTER ---
        doc.build(story)
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name=f"NutriPlan_{datetime.date.today()}.pdf", mimetype='application/pdf')

    except Exception as e:
        traceback.print_exc()
        return f"Gagal membuat PDF: {str(e)}"

if __name__ == "__main__":
    app.run(debug=True, port=5000)