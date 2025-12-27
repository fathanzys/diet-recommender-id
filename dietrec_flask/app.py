from __future__ import annotations
import io
import datetime
import traceback
from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify

# --- IMPORT MODUL ---
try:
    from modules.io_utils import load_tkpi, extract_dropdown_options
    from modules.calc_utils import mifflin_st_jeor, tdee_with_goal, bmi_and_category
    from modules.scoring import apply_filters, score_rule_macro, score_ml_ensemble
    from modules.planner import optimize_meal_plan
except ImportError as e:
    print(f"CRITICAL ERROR: {e}")
    exit(1)

# --- IMPORT REPORTLAB ---
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
except ImportError:
    print("WARNING: ReportLab belum diinstall. PDF tidak bisa dibuat.")

app = Flask(__name__)
app.secret_key = "skripsi_secret_key_123"

# --- CORE LOGIC ---
def compute_engine(form_data: dict):
    try:
        age = int(form_data.get("age", 25))
        weight = float(form_data.get("weight", 60))
        height = float(form_data.get("height", 170))
        days = int(form_data.get("days", 3))
        sex = form_data.get("sex", "Laki-laki")
        activity = form_data.get("activity", "sedang")
        goal = form_data.get("goal", "maintain")
        halal_pref = (str(form_data.get("halal", "ya")).lower() == "ya")

        # Handle List/String input
        def norm_list(val):
            if isinstance(val, list): return [str(x).strip() for x in val if str(x).strip()]
            if isinstance(val, str): return [x.strip() for x in val.split(",") if x.strip()]
            return []

        allergies = norm_list(form_data.get("allergies"))
        diseases = norm_list(form_data.get("diseases"))

        # Hitung Gizi
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

        # Load & Filter
        df, mapping, errs = load_tkpi()
        if errs: return None, meta, errs

        df_filtered = apply_filters(df, mapping, halal_pref, allergies, diseases)
        meta["count_candidates"] = len(df_filtered)
        if df_filtered.empty: return None, meta, ["Tidak ada menu lolos filter."]

        # Scoring & Planning
        df_rb = score_rule_macro(df_filtered, mapping, tdee_val)
        df_ranked = score_ml_ensemble(df_rb)
        plan = optimize_meal_plan(df_ranked, tdee_val, days)

        return {"ranked": df_ranked, "plan": plan}, meta, []

    except Exception as e:
        traceback.print_exc()
        return None, {}, [f"System Error: {str(e)}"]

# --- ROUTES ---
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

    # --- HITUNG DATA CHART DI SINI (Supaya HTML Bersih) ---
    chart_days = [f"Hari {d['day']}" for d in res["plan"]]
    chart_kcal = [int(sum(m['agg']['kcal'] for m in d['meals'])) for d in res["plan"]]
    
    chart_radar = []
    for d in res["plan"]:
        P = sum(m['agg']['protein_g'] for m in d['meals'])
        L = sum(m['agg']['fat_g'] for m in d['meals'])
        K = sum(m['agg']['carb_g'] for m in d['meals'])
        total = max(1, P + L + K)
        chart_radar.append([
            round(P/total*100, 1), 
            round(L/total*100, 1), 
            round(K/total*100, 1)
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
    try:
        req = request.json
        base = session.get("form_data", {}).copy()
        base.update({
            "halal": req.get("halal"),
            "days": req.get("days"),
            "allergies": req.get("allergies", []),
            "diseases": req.get("diseases", [])
        })
        
        # Simpan session sebagai string csv
        sess = base.copy()
        if isinstance(sess["allergies"], list): sess["allergies"] = ",".join(sess["allergies"])
        if isinstance(sess["diseases"], list): sess["diseases"] = ",".join(sess["diseases"])
        session["form_data"] = sess

        res, meta, errs = compute_engine(base)
        if errs: return jsonify({"ok": False, "error": errs[0]})

        return jsonify({"ok": True}) # Client akan reload page
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route("/export_pdf")
def export_pdf():
    data = session.get("form_data")
    if not data: return redirect(url_for("input_page"))
    
    res, meta, errs = compute_engine(data)
    if errs or not res: return "Data tidak valid untuk PDF."

    try:
        buffer = io.BytesIO()
        # Mengatur Margin agar lebih rapi
        doc = SimpleDocTemplate(buffer, pagesize=A4, 
                                rightMargin=40, leftMargin=40, 
                                topMargin=40, bottomMargin=40)
        
        styles = getSampleStyleSheet()
        # Membuat style custom
        style_title = ParagraphStyle('CustomTitle', parent=styles['Title'], fontSize=20, textColor=colors.HexColor('#14532d'), spaceAfter=10)
        style_subtitle = ParagraphStyle('CustomSub', parent=styles['Normal'], fontSize=10, textColor=colors.grey, alignment=1) # Center
        style_h2 = ParagraphStyle('CustomH2', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor('#15803d'), spaceBefore=15, spaceAfter=8)
        style_normal = styles['Normal']
        
        story = []

        # --- HEADER ---
        story.append(Paragraph("Laporan Rencana Diet Personal", style_title))
        story.append(Paragraph(f"Dibuat oleh NutriPlan • {datetime.datetime.now().strftime('%d %B %Y')}", style_subtitle))
        story.append(Spacer(1, 20))

        # --- SECTION 1: PROFIL USER (Kotak Info) ---
        # Data disusun dalam tabel 2 kolom
        data_profil = [
            ["INFORMASI PENGGUNA", ""], # Header Row
            [f"Nama/ID: Pengguna Tamu", f"Target: {str(meta['goal']).upper()}"],
            [f"Usia: {meta['age']} Tahun", f"Berat: {meta['weight']} kg"],
            [f"Tinggi: {meta['height']} cm", f"BMI: {meta['bmi']} ({meta['bmi_cat']})"],
            [f"BMR: {meta['bmr']} kkal", f"Target Harian (TDEE): {meta['tdee']} kkal"],
            [f"Preferensi Halal: {meta['halal']}", f"Durasi: {meta['days']} Hari"]
        ]
        
        t_prof = Table(data_profil, colWidths=[230, 230])
        t_prof.setStyle(TableStyle([
            ('SPAN', (0,0), (1,0)), # Merge Header Title
            ('BACKGROUND', (0,0), (1,0), colors.HexColor('#dcfce7')), # Warna Hijau Muda Header
            ('TEXTCOLOR', (0,0), (1,0), colors.HexColor('#14532d')),
            ('ALIGN', (0,0), (1,0), 'CENTER'),
            ('FONTNAME', (0,0), (1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (1,0), 10),
            ('BOTTOMPADDING', (0,0), (1,0), 8),
            ('TOPPADDING', (0,0), (1,0), 8),
            
            ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey), # Garis tabel
            ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,1), (-1,-1), 9),
            ('PADDING', (0,1), (-1,-1), 6),
        ]))
        story.append(t_prof)
        story.append(Spacer(1, 25))

        # --- SECTION 2: MEAL PLAN ---
        for day in res["plan"]:
            total_cal = int(sum(m['agg']['kcal'] for m in day['meals']))
            story.append(Paragraph(f"HARI KE-{day['day']} — Total: {total_cal} kkal", style_h2))
            
            for meal in day['meals']:
                # Sub-header Meal (Sarapan/Siang/Malam)
                story.append(Paragraph(f"<b>{meal['name']}</b> (Est. {int(meal['agg']['kcal'])} kkal)", style_normal))
                story.append(Spacer(1, 4))
                
                # Tabel Menu Detail
                menu_header = [["Kategori", "Nama Menu", "Porsi (g)", "Energi (kkal)", "P", "L", "K"]]
                menu_data = []
                for item in meal['items']:
                    menu_data.append([
                        str(item.get('class','')).capitalize(),
                        Paragraph(str(item.get('name','')), styles['BodyText']), 
                        f"{item.get('portion_g',0)}",
                        f"{int(item.get('kcal',0))}",
                        f"{item.get('protein_g',0)}",
                        f"{item.get('fat_g',0)}",
                        f"{item.get('carb_g',0)}"
                    ])
                
                # Gabung header + data
                full_table_data = menu_header + menu_data
                
                t_menu = Table(full_table_data, colWidths=[60, 180, 50, 60, 30, 30, 30])
                t_menu.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke), # Header row background
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0,0), (-1,-1), 8),
                    ('ALIGN', (2,0), (-1,-1), 'RIGHT'), # Angka rata kanan
                    ('LINEBELOW', (0,0), (-1,0), 1, colors.HexColor('#16a34a')), # Garis hijau bawah header
                    ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ]))
                story.append(t_menu)
                story.append(Spacer(1, 12))
                
            story.append(Spacer(1, 10))
            # Garis pemisah antar hari (kecuali hari terakhir)
            if day != res["plan"][-1]:
                story.append(Paragraph("<hr width='100%' color='lightgrey'/>", style_normal))
                story.append(PageBreak())

        # --- FOOTER / DISCLAIMER ---
        story.append(Spacer(1, 30))
        disclaimer_text = """
        <b>Catatan Penting:</b><br/>
        Aplikasi NutriPlan bertujuan untuk memberikan estimasi kebutuhan gizi dan rekomendasi menu 
        berdasarkan data populasi umum (TKPI). Dokumen ini bukan pengganti saran medis profesional. 
        Jika Anda memiliki kondisi kesehatan khusus, mohon konsultasikan dengan dokter atau ahli gizi.
        """
        story.append(Paragraph(disclaimer_text, ParagraphStyle('Disclaimer', parent=styles['Normal'], fontSize=8, textColor=colors.grey)))

        doc.build(story)
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name=f"NutriPlan_{datetime.date.today()}.pdf", mimetype='application/pdf')

    except Exception as e:
        traceback.print_exc()
        return f"Gagal membuat PDF: {str(e)}"

if __name__ == "__main__":
    app.run(debug=True, port=5000)