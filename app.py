import streamlit as st
import json, uuid, csv, io, smtplib, ssl, base64, urllib.request, urllib.error
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path

# ═══════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════
try: EMAIL_PASSWORD = st.secrets["EMAIL_PASSWORD"]
except: EMAIL_PASSWORD = "jrho ryew uguj nbsm"

try:
    TURSO_URL = st.secrets["TURSO_URL"]
    TURSO_TOKEN = st.secrets["TURSO_TOKEN"]
except:
    TURSO_URL = None
    TURSO_TOKEN = None

EMAIL_CONFIG = {
    "smtp_server": "smtp.gmail.com", "smtp_port": 587,
    "sender_email": "eetuk@churchgate.com", "sender_password": EMAIL_PASSWORD,
    "recipients": ["eetuk@churchgate.com","vinay@wtcabuja.com","eorimolade@churchgate.com","akarim@churchgate.com","tradeservices@wtcabuja.com"]
}

# ═══════════════════════════════════════════════════════════
# TURSO DATABASE — using urllib (no external deps needed)
# ═══════════════════════════════════════════════════════════
def turso_query(sql, params=None):
    if not TURSO_URL or not TURSO_TOKEN: return []
    try:
        parts = TURSO_URL.replace("libsql://", "")
        url = f"https://{parts}/v2/pipeline"
        body = json.dumps({"requests":[{"type":"execute","stmt":{"sql":sql,"args":params or []}}]}).encode()
        req = urllib.request.Request(url, data=body, headers={
            "Authorization": f"Bearer {TURSO_TOKEN}",
            "Content-Type": "application/json"
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            results = data.get("results",[])
            if results:
                result = results[0]
                if result.get("type") == "ok":
                    r = result.get("response",{}).get("result",{})
                    cols = [c["name"] for c in r.get("cols",[])]
                    rows = []
                    for row in r.get("rows",[]):
                        d = {}
                        for i, col_name in enumerate(cols):
                            cell = row[i] if i < len(row) else {}
                            d[col_name] = cell.get("value") if isinstance(cell, dict) else cell
                        rows.append(d)
                    return rows
        return []
    except Exception as e:
        st.error(f"DB Error: {e}")
        return []

def save_lead(d):
    lid = str(uuid.uuid4())
    now = datetime.now().isoformat()
    mats = json.dumps(d.get('mt',[]))
    tags = json.dumps(d.get('tg',[]))
    ins = 1 if d.get('ins') else 0
    mk = 1 if d.get('mk') else 1
    turso_query("INSERT INTO leads(id,first_name,last_name,email,phone,company,job_title,timing,materials,tags,inspection,marketing,campaign,device_id,submitted) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [lid,d.get('fn',''),d.get('ln',''),d.get('em',''),d.get('ph',''),d.get('co',''),d.get('jt',''),d.get('ti',''),mats,tags,ins,mk,'NOG Energy Week 2026',st.session_state.get('did',''),now])
    return True

def get_all_leads(n=200):
    return turso_query("SELECT * FROM leads ORDER BY submitted DESC LIMIT ?",[n])

def get_stats():
    r = turso_query("SELECT COUNT(*) as total, COALESCE(SUM(inspection),0) as inspections, COALESCE(SUM(marketing),0) as optins FROM leads")
    if r: return {'t':int(r[0].get('total') or 0),'i':int(r[0].get('inspections') or 0),'m':int(r[0].get('optins') or 0)}
    return {'t':0,'i':0,'m':0}

def export_csv():
    rows = get_all_leads(9999)
    if not rows: return ""
    o = io.StringIO()
    w = csv.DictWriter(o,fieldnames=['submitted','first_name','last_name','email','phone','company','job_title','materials','inspection','marketing'],extrasaction='ignore')
    w.writeheader()
    for r in rows:
        r['inspection']='Yes' if r.get('inspection') else 'No'
        r['marketing']='Yes' if r.get('marketing') else 'No'
        w.writerow(r)
    return o.getvalue()

# ═══════════════════════════════════════════════════════════
# EMAIL
# ═══════════════════════════════════════════════════════════
def send_lead_email(ld):
    try:
        fn,ln,em,ph,co,jt,ti,mt,ins,mk=ld.get('fn',''),ld.get('ln',''),ld.get('em',''),ld.get('ph',''),ld.get('co',''),ld.get('jt',''),ld.get('ti',''),ld.get('mt',[]),ld.get('ins',False),ld.get('mk',True)
        msg=MIMEMultipart()
        msg['From']=f"WTC Abuja Concierge <{EMAIL_CONFIG['sender_email']}>"
        msg['To']=", ".join(EMAIL_CONFIG['recipients'])
        msg['Subject']=f"{'🔑 INSPECTION' if ins else 'New Lead'} — {fn} {ln} | {co}"
        mh="".join(f'<tr><td style="padding:6px 8px;color:#c8a45c;">✦</td><td style="padding:6px 8px;color:#e8e4dc;">{m}</td></tr>' for m in mt) or '<tr><td colspan="2" style="color:#8a8680;">None</td></tr>'
        tm={"immediate":"⚡ Immediate","0-3_months":"📅 0–3 Months","3-6_months":"📅 3–6 Months","6-12_months":"📅 6–12 Months","future":"🔮 Future"}
        td=tm.get(ti,ti) if ti else "Not specified"
        pb="""<table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 20px 0;"><tr><td style="background:linear-gradient(135deg,#a88838,#c8a45c);padding:14px 20px;border-radius:4px;text-align:center;"><p style="color:#1a1a1a;font-size:14px;font-weight:700;margin:0;letter-spacing:1px;">🔑 PRIORITY — INSPECTION REQUESTED</p></td></tr></table>""" if ins else ""
        html=f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head><body style="margin:0;padding:0;background:#1a1a1a;font-family:Arial,sans-serif;"><table width="100%" cellpadding="0" cellspacing="0" style="background:#1a1a1a;padding:30px 20px;"><tr><td align="center"><table width="600" cellpadding="0" cellspacing="0" style="background:#1e1e1e;border:1px solid #333;border-radius:8px;"><tr><td style="background:#252525;padding:35px 40px 25px;text-align:center;border-bottom:2px solid #c8a45c;"><p style="color:#c8a45c;font-size:10px;letter-spacing:5px;margin:0 0 10px;text-transform:uppercase;">World Trade Center</p><h1 style="color:#e8e4dc;font-size:26px;font-weight:600;margin:0 0 8px;font-family:Georgia,serif;">WTC Abuja</h1><p style="color:#c8a45c;font-size:14px;margin:0;">New Lead Notification</p></td></tr><tr><td style="padding:30px 40px;">{pb}<table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 20px;"><tr><td width="50%" style="padding:12px 10px;border-bottom:1px solid #2a2a2a;"><p style="color:#8a8680;font-size:10px;text-transform:uppercase;letter-spacing:2px;margin:0 0 5px;">Name</p><p style="color:#f0ede8;font-size:17px;font-weight:600;margin:0;font-family:Georgia,serif;">{fn} {ln}</p></td><td width="50%" style="padding:12px 10px;border-bottom:1px solid #2a2a2a;"><p style="color:#8a8680;font-size:10px;text-transform:uppercase;letter-spacing:2px;margin:0 0 5px;">Company</p><p style="color:#f0ede8;font-size:17px;font-weight:600;margin:0;font-family:Georgia,serif;">{co}</p></td></tr><tr><td style="padding:12px 10px;border-bottom:1px solid #2a2a2a;"><p style="color:#8a8680;font-size:10px;text-transform:uppercase;letter-spacing:2px;margin:0 0 5px;">Title</p><p style="color:#e8e4dc;font-size:15px;margin:0;">{jt or 'Not provided'}</p></td><td style="padding:12px 10px;border-bottom:1px solid #2a2a2a;"><p style="color:#8a8680;font-size:10px;text-transform:uppercase;letter-spacing:2px;margin:0 0 5px;">Timing</p><p style="color:#e8e4dc;font-size:15px;margin:0;">{td}</p></td></tr></table><p style="color:#8a8680;font-size:10px;text-transform:uppercase;letter-spacing:2px;">Contact</p><p style="color:#c8a45c;font-size:14px;margin:3px 0;">✉️ {em}</p><p style="color:#c8a45c;font-size:14px;margin:3px 0;">📱 {ph}</p><table width="100%" cellpadding="0" cellspacing="0" style="background:#252525;border:1px solid #333;border-radius:6px;margin:15px 0;"><tr><td style="padding:18px 22px;"><p style="color:#8a8680;font-size:10px;text-transform:uppercase;letter-spacing:2px;margin:0 0 10px;">Materials</p><table width="100%">{mh}</table></td></tr></table><table width="100%" cellpadding="0" cellspacing="0"><tr><td width="50%" style="padding:0 5px 0 0;"><table width="100%" cellpadding="0" cellspacing="0" style="background:{'#c8a45c' if ins else '#333'};border-radius:4px;"><tr><td style="padding:10px 14px;text-align:center;"><p style="color:{'#1a1a1a' if ins else '#8a8680'};font-size:11px;font-weight:700;margin:0;">🔑 INSPECTION: {'YES' if ins else 'NO'}</p></td></tr></table></td><td width="50%" style="padding:0 0 0 5px;"><table width="100%" cellpadding="0" cellspacing="0" style="background:{'#c8a45c' if mk else '#333'};border-radius:4px;"><tr><td style="padding:10px 14px;text-align:center;"><p style="color:{'#1a1a1a' if mk else '#8a8680'};font-size:11px;font-weight:700;margin:0;">📬 MARKETING: {'OPT-IN' if mk else 'OUT'}</p></td></tr></table></td></tr></table></td></tr><tr><td style="background:#252525;padding:20px 40px;text-align:center;border-top:1px solid #333;"><p style="color:#6b6762;font-size:10px;margin:0 0 3px;">Captured via WTC Abuja Concierge App</p><p style="color:#6b6762;font-size:10px;margin:0 0 8px;">{datetime.now().strftime('%d %B %Y, %H:%M')} · NOG Energy Week 2026</p><p style="color:#c8a45c;font-size:9px;margin:0;letter-spacing:3px;">WORLD TRADE CENTER ABUJA</p></td></tr></table></td></tr></table></body></html>"""
        msg.attach(MIMEText(html,'html'))
        ctx=ssl.create_default_context()
        with smtplib.SMTP(EMAIL_CONFIG['smtp_server'],EMAIL_CONFIG['smtp_port']) as srv:
            srv.starttls(context=ctx); srv.login(EMAIL_CONFIG['sender_email'],EMAIL_CONFIG['sender_password']); srv.sendmail(EMAIL_CONFIG['sender_email'],EMAIL_CONFIG['recipients'],msg.as_string())
        return True
    except: return False

# ═══════════════════════════════════════════════════════════
# SESSION STATE
# ═══════════════════════════════════════════════════════════
for k,v in [("pg","idle"),("rt",None),("sc",0),("fd",{}),("adm",False),("did",str(uuid.uuid4())[:8]),("la",datetime.now()),("ct","digital_pack")]:
    if k not in st.session_state: st.session_state[k]=v

# ═══════════════════════════════════════════════════════════
# PAGE CONFIG
# ═══════════════════════════════════════════════════════════
fp=Path(__file__).parent/"assets"/"wtc-logo.jpg"
st.set_page_config("WTC Abuja Concierge",str(fp) if fp.exists() else "🏛️","wide","collapsed")

st.markdown("""<style>
#MainMenu,footer,header,.stDeployButton,[data-testid="stToolbar"]{display:none!important}
.stApp{background:#1a1a1a!important}
.stMainBlockContainer,.main,div[data-testid="stVerticalBlock"]{background:#1a1a1a!important;gap:0!important}
.stMarkdown,.stMarkdown p,.stMarkdown h1,.stMarkdown h2,.stMarkdown h3,.stMarkdown span,.stMarkdown div,p,h1,h2,h3,h4,label,span{color:#f0ede8!important}
.stTextInput input,.stSelectbox select{background:#2a2a2a!important;color:#f0ede8!important;border:1px solid #4a4a4a!important;border-radius:4px!important;padding:10px 14px!important;font-size:15px!important}
.stTextInput input:focus{border-color:#c8a45c!important;box-shadow:0 0 0 3px rgba(200,164,92,0.15)!important}
.stTextInput input::placeholder{color:#6b6762!important}
.stTextInput label,.stSelectbox label,.stCheckbox label{color:#b8b4ac!important;font-size:13px!important;font-family:Arial,sans-serif!important}
.stCheckbox label span{color:#b8b4ac!important;font-size:13px!important}
.stButton>button{background:linear-gradient(135deg,#a88838,#c8a45c)!important;color:#1a1a1a!important;border:none!important;border-radius:4px!important;padding:14px 28px!important;font-weight:600!important;font-size:14px!important;text-transform:uppercase!important;letter-spacing:1px!important;transition:all .15s!important;font-family:Arial,sans-serif!important;cursor:pointer!important}
.stButton>button:hover{background:linear-gradient(135deg,#c8a45c,#d4b56e)!important;transform:translateY(-1px)!important;box-shadow:0 4px 20px rgba(200,164,92,.3)!important}
[data-testid="stMetricValue"]{color:#c8a45c!important;font-size:2rem!important;font-weight:700!important}
[data-testid="stMetricLabel"]{color:#8a8680!important;font-size:.75rem!important}
[data-testid="stDataFrame"]{background:#1e1e1e!important;border:1px solid #333!important;border-radius:4px!important}
[data-testid="stDataFrame"] th{background:#252525!important;color:#8a8680!important;font-size:11px!important;text-transform:uppercase!important;letter-spacing:1px!important;padding:12px!important;border-bottom:2px solid #333!important}
[data-testid="stDataFrame"] td{background:#1a1a1a!important;color:#b8b4ac!important;font-size:13px!important;padding:10px 12px!important;border-bottom:1px solid #2a2a2a!important}
.stProgress>div>div>div{background:#c8a45c!important}
.stProgress>div>div{background:#2a2a2a!important}
.stDownloadButton>button{background:#252525!important;color:#c8a45c!important;border:1px solid #c8a45c!important;border-radius:4px!important;padding:10px 20px!important;font-weight:500!important}
.stDownloadButton>button:hover{background:rgba(200,164,92,.1)!important;color:#d4b56e!important}
hr{border-color:#333!important;margin:20px 0!important}
</style>""",unsafe_allow_html=True)

def go(pg,rt=None,sc=0):
    st.session_state.pg=pg; st.session_state.rt=rt; st.session_state.sc=sc; st.session_state.la=datetime.now()

if "admin" in st.query_params: st.session_state.pg="admin"; st.query_params.clear()
st.markdown('<div style="position:fixed;bottom:3px;right:3px;z-index:9999;"><a href="?admin=true" style="color:#1a1a1a;text-decoration:none;font-size:7px;">·</a></div>',True)

# ═══════════════════════════════════════════════════════════
# PAGES
# ═══════════════════════════════════════════════════════════
def idle():
    st.markdown("<br>"*4,True)
    _,c,_=st.columns([1,2,1])
    with c:
        st.markdown('<p style="text-align:center;color:#c8a45c;letter-spacing:5px;font-size:12px;font-family:Arial,sans-serif">WORLD TRADE CENTER</p>',True)
        st.markdown('<h1 style="text-align:center;color:#e8e4dc;font-size:56px;line-height:1.1;margin:6px 0;font-family:Georgia,serif">World Trade Center<br>Abuja</h1>',True)
        st.markdown('<hr style="width:60px;border:1px solid #c8a45c;margin:20px auto">',True)
        st.markdown('<p style="text-align:center;color:#b8b4ac;font-size:18px;font-family:Arial,sans-serif">Grade A offices and executive residences in the capital.</p>',True)
        st.markdown('<p style="text-align:center;color:#8a8680;font-size:14px;font-family:Arial,sans-serif">Completed. Operational. Available for private inspection.</p>',True)
        st.markdown("<br>",True)
        _,b,_=st.columns([1,2,1])
        with b:
            if st.button("✨ Tap to Explore →",key="idle_go",use_container_width=True,type="primary"): go("home"); st.rerun()
        st.markdown('<p style="text-align:center;color:#6b6762;font-size:12px;font-family:Arial,sans-serif;margin-top:25px">Receive the corporate prospectus, floorplates or residence plans</p>',True)

def home():
    st.markdown('<p style="text-align:center;color:#8a8680;font-size:11px;letter-spacing:4px;font-family:Arial,sans-serif;margin-top:30px">WORLD TRADE CENTER ABUJA</p>',True)
    st.markdown('<h2 style="text-align:center;color:#e8e4dc;font-size:32px;margin:6px 0 30px 0;font-family:Georgia,serif">What are you interested in?</h2>',True)
    routes=[("🏛️","Overview","WTC Abuja at a glance","overview"),("💼","Office Space","Grade A offices and floorplates","office"),("🏠","Executive Residences","Apartments and accommodation","residences"),("📍","Location","Constitution Avenue, CBD Abuja","location"),("🛡️","Security & Continuity","Access, CCTV, infrastructure","security"),("🔑","Request a Private Inspection","Office, residence or full walkthrough","convert_i"),("📋","Send Me the Digital Pack","Prospectus and materials","convert_d")]
    for row in range(0,7,3):
        cols=st.columns(3)
        for i in range(3):
            idx=row+i
            if idx>=7: break
            icon,title,desc,key=routes[idx]
            with cols[i]:
                st.markdown(f'<div style="background:#252525;border:1px solid #3a3a3a;border-radius:6px;padding:22px 18px;margin:4px;min-height:165px"><div style="font-size:1.8rem;margin-bottom:10px">{icon}</div><div style="color:#e8e4dc;font-size:1.05rem;font-weight:600;margin-bottom:5px;font-family:Georgia,serif">{title}</div><div style="color:#8a8680;font-size:0.78rem;font-family:Arial,sans-serif;line-height:1.4">{desc}</div></div>',True)
                if st.button("Select →",key=f"btn_{key}",use_container_width=True):
                    if key.startswith("convert"): go("convert"); st.session_state.fd={"pf":["Request a Private Inspection"] if "i" in key else ["Corporate Prospectus"]}
                    else: go("route",key)
                    st.rerun()

ROUTES={"overview":{"title":"Overview","screens":[{"t":"A completed Grade A address in Abuja's CBD","b":"World Trade Center Abuja is a completed and operational Grade A development on Constitution Avenue in the heart of Abuja's Central Business District.","p":["Completed and operational","Constitution Avenue, CBD Abuja","Offices, residences and amenities","Professionally managed environment"]},{"t":"One address. Multiple uses. One controlled environment.","b":"WTC Abuja integrates business, living, and leisure within a secure, professionally managed perimeter.","p":["Offices","Residences","Clubhouse","Security perimeter","CBD Location"]},{"t":"The Proof","b":"A working, operational building — not a promise.","h":[("33,180 m²","Office GLA"),("1,440 m²","Typical Floorplate"),("120","Executive Residences"),("500+","CCTV Cameras"),("CBD Address","Near NNPC & Petroleum Ministry")]}]},"office":{"title":"Office Space","screens":[{"t":"Grade A offices for serious occupiers","b":"Completed, operational office space in Abuja's CBD.","p":["33,180 m² total GLA","1,440 m² typical floorplate","~83% efficiency","130 m² to full-floor","Professional FM"]},{"t":"Floorplate Options","b":"Flexible space configurations:","h":[("130 m²","Representative office"),("230 m²","Single office suite"),("360 m²","Project team/embassy"),("720 m²","Larger corporate office"),("1,440 m²","Full-floor headquarters")]},{"t":"Built for Continuity","b":"The building is running.","p":["10 MVA on-site power","8×1,250 kVA generators","Daikin VRV cooling","4 ISPs","Schindler lifts","Honeywell BMS"]}]},"residences":{"title":"Executive Residences","screens":[{"t":"Executive accommodation inside the same secure development","b":"Secure accommodation for senior executives, expatriates, and visiting leadership.","p":["120 residences","1–6 bedroom range","Furnished/unfurnished","Private clubhouse access","Secure CBD location"]},{"t":"Residence Types","b":"Accommodation for different needs:","h":[("1-Bedroom","Executive singles"),("2-Bedroom","Couples, diplomatic staff"),("3-Bedroom","Families, senior execs"),("Penthouses & Villas","VIPs, leadership")]},{"t":"Simpler accommodation planning","b":"Your team lives within the same secure development as your offices.","p":["Reduced daily movement","Same development as offices","Easier planning for expats","Secure for families"]},{"t":"Private amenities for daily life","b":"The Clubhouse offers:","p":["Fitness — Technogym","Wellness — Pool, spa, sauna","Sport — Tennis & squash","Business — Meeting rooms","Family — Café, crèche"]}]},"security":{"title":"Security & Continuity","screens":[{"t":"Security governed as an operating system","b":"Trained personnel, defined procedures, and integrated technology.","p":["Trained personnel","Defined procedures","Integrated technology","Professional management"]},{"t":"Security Layers","b":"Four integrated layers:","h":[("Surveillance","500+ HD CCTV · 24/7 control room"),("Access Control","Honeywell · Access-controlled lifts"),("Vehicle & Perimeter","Bollards · Under-vehicle surveillance"),("Personnel","Manned guards · MOPOL · Fire Service")]},{"t":"Operational continuity built in","b":"Every critical system has redundancy.","p":["10 MVA on-site power","8×1,250 kVA generators","Twice building peak load","Daikin VRV cooling","4 ISPs","Fire & life safety"]}]},"location":{"title":"Location","screens":[{"t":"At the centre of business, government and diplomacy","b":"Constitution Avenue in the CBD — between Maitama and Asokoro.","p":["Constitution Avenue","CBD Abuja","Between Maitama & Asokoro","Near NNPC Towers","Near Petroleum Ministry"]},{"t":"Why the Location Matters","b":"A CBD address that works:","p":["Close to federal institutions","Near diplomatic missions","Near corporate headquarters","Practical for leadership","Reduced travel time"]}]}}

def route():
    rk=st.session_state.rt; si=st.session_state.sc; rt=ROUTES.get(rk)
    if not rt or si>=len(rt["screens"]): go("convert"); st.rerun(); return
    s=rt["screens"][si]; total=len(rt["screens"])
    c1,c2=st.columns([1,4])
    with c1:
        if st.button("← Back",key="rb",use_container_width=True):
            if si==0: go("home")
            else: go("route",rk,si-1)
            st.rerun()
    with c2: st.markdown(f'<p style="color:#e8e4dc;font-size:17px;margin-top:8px;font-family:Arial,sans-serif">{rt["title"]} <span style="color:#8a8680;font-size:12px">— {si+1}/{total}</span></p>',True)
    st.progress((si+1)/total)
    st.markdown(f'<h2 style="color:#e8e4dc;font-size:26px;margin:18px 0 8px;font-family:Georgia,serif">{s["t"]}</h2>',True)
    if "b" in s: st.markdown(f'<p style="color:#b8b4ac;font-size:15px;line-height:1.7;font-family:Arial,sans-serif">{s["b"]}</p>',True)
    if "h" in s:
        cols=st.columns(len(s["h"]))
        for i,(num,lab) in enumerate(s["h"]):
            with cols[i]: st.markdown(f'<div style="background:#252525;border:1px solid #3a3a3a;border-radius:4px;padding:18px;text-align:center;margin:4px"><div style="font-size:1.3rem;color:#c8a45c;font-weight:700">{num}</div><div style="font-size:0.68rem;color:#8a8680;text-transform:uppercase;font-family:Arial,sans-serif;margin-top:3px">{lab}</div></div>',True)
    if "p" in s:
        cols=st.columns(2)
        for i,p in enumerate(s["p"]):
            with cols[i%2]: st.markdown(f'<div style="background:#252525;border:1px solid #3a3a3a;border-radius:4px;padding:13px;text-align:center;margin:3px;color:#b8b4ac;font-family:Arial,sans-serif;font-size:13px">{p}</div>',True)
    st.markdown("<br>",True)
    c1,_,c3=st.columns(3)
    with c1:
        if st.button("🏠 Home",key="rh",use_container_width=True): go("home"); st.rerun()
    with c3:
        lbl="Continue →" if si<total-1 else "Get Materials →"
        if st.button(lbl,key="rn",use_container_width=True,type="primary"):
            if si<total-1: go("route",rk,si+1)
            else: go("convert")
            st.rerun()

def convert():
    st.markdown('<h2 style="color:#e8e4dc;font-size:26px;margin:20px 0;font-family:Georgia,serif">What would you like us to send you?</h2>',True)
    materials=["Corporate Prospectus","Office Floorplates","Residence Floorplans","Security & Continuity Brief","Clubhouse Overview","Location Overview","Request a Private Inspection","WTC Abuja Updates & Private Invitations"]
    selected=[]
    st.markdown('<p style="color:#c8a45c;font-size:12px;font-family:Arial,sans-serif;margin:8px 0;letter-spacing:1px">SELECT MATERIALS</p>',True)
    cols=st.columns(2)
    for i,m in enumerate(materials):
        with cols[i%2]:
            if st.checkbox(m,value=m in st.session_state.fd.get("pf",[]),key=f"cm_{i}"): selected.append(m)
    st.markdown('<p style="color:#c8a45c;font-size:12px;font-family:Arial,sans-serif;margin:18px 0 8px;letter-spacing:1px">YOUR DETAILS</p>',True)
    c1,c2=st.columns(2)
    with c1: fn=st.text_input("First Name *","",key="fn"); em=st.text_input("Email *","",key="em"); co=st.text_input("Company *","",key="co")
    with c2: ln=st.text_input("Last Name *","",key="ln"); ph=st.text_input("Mobile / WhatsApp *","",key="ph"); jt=st.text_input("Job Title (optional)","",key="jt")
    ti=st.selectbox("Timing (optional)",["","Immediate","0–3 months","3–6 months","6–12 months","Future/exploratory"],key="ti")
    st.markdown('<div style="background:#252525;border:1px solid #3a3a3a;border-radius:4px;padding:11px 14px;margin:12px 0"><p style="color:#b8b4ac;font-size:11px;font-family:Arial,sans-serif;margin:0">By submitting, you agree WTC Abuja may contact you about your enquiry.</p></div>',True)
    mk=st.checkbox("Send me updates, news and private invitations. I can opt out anytime.",True,key="mk")
    c1,_,c3=st.columns(3)
    with c1:
        if st.button("← Back",key="cvbk",use_container_width=True): go("route" if st.session_state.rt else "home"); st.rerun()
    with c3:
        if st.button("Submit →",key="cvsb",use_container_width=True,type="primary"):
            if not fn or not ln or not em or not ph or not co: st.error("Fill all required fields")
            else:
                tm={"Office Floorplates":"Office Leasing","Corporate Prospectus":"Office Leasing","Residence Floorplans":"Executive Residences","Security & Continuity Brief":"Security & Continuity","Clubhouse Overview":"Clubhouse","Location Overview":"Location","Request a Private Inspection":"Private Inspection","WTC Abuja Updates & Private Invitations":"Newsletter"}
                ld={"fn":fn,"ln":ln,"em":em,"ph":ph,"co":co,"jt":jt,"ti":ti,"mt":selected,"tg":list(set(tm.get(m,m) for m in selected)),"ins":"Request a Private Inspection" in selected,"mk":mk}
                save_lead(ld)
                send_lead_email(ld)
                st.session_state.ct="inspection" if "Request a Private Inspection" in selected else "digital_pack"
                st.session_state.fd={}; go("confirm"); st.rerun()

def confirm():
    cf={"inspection":("🔑","Inspection Requested","Your private inspection request has been received. The WTC Abuja team will contact you to confirm timing."),"digital_pack":("📋","Thank You","Your selected materials will be sent shortly. A team member may follow up.")}
    ic,hl,ms=cf.get(st.session_state.ct,cf["digital_pack"])
    st.markdown("<br>"*4,True)
    _,c,_=st.columns([1,2,1])
    with c:
        st.markdown(f'<div style="text-align:center"><div style="width:65px;height:65px;border-radius:50%;background:rgba(200,164,92,0.08);border:2px solid #c8a45c;display:flex;align-items:center;justify-content:center;font-size:1.8rem;margin:18px auto">{ic}</div><h2 style="color:#e8e4dc;font-size:26px;margin-bottom:8px;font-family:Georgia,serif">{hl}</h2><p style="color:#b8b4ac;font-size:15px;font-family:Arial,sans-serif;line-height:1.6">{ms}</p></div>',True)
        st.markdown("<br>",True)
        a,b=st.columns(2)
        with a:
            if st.button("Return to Home",key="cfh",use_container_width=True): go("home"); st.rerun()
        with b:
            if st.button("Explore More",key="cfe",use_container_width=True,type="primary"): go("home"); st.rerun()

def admin():
    if not st.session_state.adm:
        st.markdown("<br>"*5,True)
        _,c,_=st.columns([1,1,1])
        with c:
            st.markdown('<h2 style="text-align:center;color:#e8e4dc;font-family:Georgia,serif">Admin Access</h2>',True)
            p=st.text_input("PIN","",type="password",key="ap",placeholder="4-digit PIN")
            if st.button("Access Admin Panel",key="ag",use_container_width=True,type="primary"):
                if p=="4271": st.session_state.adm=True; st.rerun()
                else: st.error("Invalid PIN")
        return
    
    try: s=get_stats(); l=get_all_leads(100)
    except: s={'t':0,'i':0,'m':0}; l=[]
    
    t=int(s.get('t',0)); i=int(s.get('i',0)); m=int(s.get('m',0)); dp=t-i if t>=i else 0
    
    c1,c2=st.columns([3,1])
    with c1: st.markdown('<h2 style="color:#e8e4dc;margin:12px 0;font-family:Georgia,serif">Admin Panel — WTC Abuja Concierge</h2>',True)
    with c2:
        if st.button("🚪 Logout",key="ao",use_container_width=True): st.session_state.adm=False; go("idle"); st.rerun()
    
    col1,col2,col3,col4=st.columns(4)
    col1.metric("Total Leads",t); col2.metric("Inspections",i); col3.metric("Opt-Ins",m); col4.metric("Digital Packs",dp)
    
    csv_data=export_csv()
    if csv_data: st.download_button("📥 Download CSV",csv_data,f"wtc_leads_{datetime.now().strftime('%Y%m%d_%H%M')}.csv","text/csv")
    
    st.markdown(f'<p style="color:#8a8680;font-size:11px;font-family:Arial,sans-serif;margin:8px 0">📅 <b style="color:#c8a45c">NOG Energy Week 2026</b> | 💾 <b style="color:#c8a45c">Turso Cloud</b> | 🕐 {datetime.now().strftime("%d %b %Y, %H:%M")}</p>',True)
    st.markdown('<h3 style="color:#e8e4dc;font-family:Georgia,serif;margin-top:20px">Recent Leads</h3>',True)
    
    if l:
        td=[{"Time":str(r.get("submitted",""))[:16],"Name":f"{r.get('first_name','')} {r.get('last_name','')}".strip(),"Company":str(r.get("company","")),"Email":str(r.get("email","")),"Phone":str(r.get("phone","")),"Inspection":"✅" if r.get("inspection") else "—","Opt-In":"✅" if r.get("marketing") else "—"} for r in l]
        st.dataframe(td,use_container_width=True,hide_index=True,height=400)
    else:
        st.info("No leads yet.")
    
    st.markdown('<div style="background:#252525;border:1px solid #3a3a3a;border-radius:6px;padding:14px;margin:12px 0"><p style="color:#b8b4ac;font-size:11px;font-family:Arial,sans-serif;margin:0">💡 Access: <code style="color:#c8a45c;background:#1a1a1a;padding:2px 6px;border-radius:3px">?admin=true</code> | PIN: <b style="color:#c8a45c">4271</b></p></div>',True)

# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════
elapsed=(datetime.now()-st.session_state.la).total_seconds()
if st.session_state.pg!="idle" and elapsed>120: go("idle"); st.rerun()

pg=st.session_state.pg
if pg=="idle": idle()
elif pg=="home": home()
elif pg=="route": route()
elif pg=="convert": convert()
elif pg=="confirm": confirm()
elif pg=="admin": admin()
else: idle()