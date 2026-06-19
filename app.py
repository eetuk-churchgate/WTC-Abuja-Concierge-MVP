import streamlit as st
import sqlite3, json, uuid, csv, io, smtplib, ssl, base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from datetime import datetime
from pathlib import Path

# ═══════════════════════════════════════════════════════════
# EMAIL CONFIGURATION
# ═══════════════════════════════════════════════════════════
EMAIL_CONFIG = {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": "eetuk@churchgate.com",
    "sender_password": "jrho ryew uguj nbsm",
    "recipients": [
        "eetuk@churchgate.com",
        "vinay@wtcabuja.com",
        "eorimolade@wtcabuja.com",
    ]
}

# ═══════════════════════════════════════════════════════════
# WTC LOGO - Load and encode
# ═══════════════════════════════════════════════════════════
def get_logo_base64():
    logo_path = Path(__file__).parent / "assets" / "wtc-logo.jpg"
    if logo_path.exists():
        with open(logo_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None

LOGO_B64 = get_logo_base64()

# ═══════════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════════
class DB:
    def __init__(self):
        p = Path(__file__).parent / "data"
        p.mkdir(exist_ok=True)
        self.c = sqlite3.connect(str(p/"wtc_abuja.db"), check_same_thread=False)
        self.c.row_factory = sqlite3.Row
        self.c.executescript("""
            CREATE TABLE IF NOT EXISTS leads(
                id TEXT PRIMARY KEY,
                first_name TEXT, last_name TEXT, email TEXT, phone TEXT,
                company TEXT, job_title TEXT, timing TEXT,
                materials TEXT DEFAULT'[]', tags TEXT DEFAULT'[]',
                inspection INTEGER DEFAULT 0, marketing INTEGER DEFAULT 1,
                submitted TEXT DEFAULT(datetime('now'))
            );
        """)
        self.c.commit()
    
    def save(self, d):
        self.c.execute(
            "INSERT INTO leads VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [str(uuid.uuid4()), d.get('fn',''), d.get('ln',''), d.get('em',''),
             d.get('ph',''), d.get('co',''), d.get('jt',''), d.get('ti',''),
             json.dumps(d.get('mt',[])), json.dumps(d.get('tg',[])),
             1 if d.get('ins') else 0, 1 if d.get('mk') else 1,
             datetime.now().isoformat()]
        )
        self.c.commit()
    
    def all(self, n=200):
        return [dict(r) for r in self.c.execute(
            "SELECT * FROM leads ORDER BY submitted DESC LIMIT ?", [n]
        ).fetchall()]
    
    def stats(self):
        r = self.c.execute(
            "SELECT COUNT(*) as t, SUM(inspection) as i, SUM(marketing) as m FROM leads"
        ).fetchone()
        return dict(r) if r else {'t':0,'i':0,'m':0}
    
    def csv(self):
        rows = self.all(9999)
        if not rows: return ""
        o = io.StringIO()
        w = csv.DictWriter(o, fieldnames=[
            'submitted','first_name','last_name','email','phone',
            'company','job_title','materials','inspection','marketing'
        ])
        w.writeheader()
        for r in rows:
            r['inspection'] = 'Yes' if r.get('inspection') else 'No'
            r['marketing'] = 'Yes' if r.get('marketing') else 'No'
            w.writerow(r)
        return o.getvalue()

db = DB()

# ═══════════════════════════════════════════════════════════
# EMAIL SENDER
# ═══════════════════════════════════════════════════════════
def send_lead_email(lead_data):
    """Send lead notification to all recipients."""
    try:
        fn = lead_data.get('fn','')
        ln = lead_data.get('ln','')
        em = lead_data.get('em','')
        ph = lead_data.get('ph','')
        co = lead_data.get('co','')
        jt = lead_data.get('jt','')
        ti = lead_data.get('ti','')
        mt = lead_data.get('mt',[])
        ins = lead_data.get('ins', False)
        mk = lead_data.get('mk', True)
        
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG['sender_email']
        msg['To'] = ", ".join(EMAIL_CONFIG['recipients'])
        
        if ins:
            msg['Subject'] = f"🔑 NEW INSPECTION REQUEST — {fn} {ln} from {co}"
        else:
            msg['Subject'] = f"📋 New Lead — {fn} {ln} from {co}"
        
        body = f"""
╔═══════════════════════════════════════════╗
║     WTC ABUJA — NEW LEAD NOTIFICATION     ║
╚═══════════════════════════════════════════╝

NAME:       {fn} {ln}
COMPANY:    {co}
TITLE:      {jt or 'Not provided'}
EMAIL:      {em}
PHONE:      {ph}
TIMING:     {ti or 'Not specified'}

───────────────────────────────────────────
REQUESTED MATERIALS:
───────────────────────────────────────────
{chr(10).join(f'  ✓ {m}' for m in mt)}

───────────────────────────────────────────
INSPECTION REQUESTED: {'✅ YES — PRIORITY' if ins else '❌ No'}
MARKETING OPT-IN:     {'✅ Yes' if mk else '❌ No'}
───────────────────────────────────────────

SUBMITTED: {datetime.now().strftime('%d %B %Y, %H:%M')}
CAMPAIGN:  NOG Energy Week 2026
DEVICE:    {st.session_state.get('did','Unknown')}

───────────────────────────────────────────
This lead was captured via the WTC Abuja 
Concierge App at NOG Energy Week 2026.
───────────────────────────────────────────
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        context = ssl.create_default_context()
        with smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port']) as server:
            server.starttls(context=context)
            server.login(EMAIL_CONFIG['sender_email'], EMAIL_CONFIG['sender_password'])
            server.sendmail(EMAIL_CONFIG['sender_email'], EMAIL_CONFIG['recipients'], msg.as_string())
        
        return True
    except Exception as e:
        st.error(f"Email failed: {e}")
        return False

# ═══════════════════════════════════════════════════════════
# SESSION STATE
# ═══════════════════════════════════════════════════════════
for k,v in [("pg","idle"),("rt",None),("sc",0),("fd",{}),("adm",False),
            ("did",str(uuid.uuid4())[:8]),("la",datetime.now()),("ct","digital_pack")]:
    if k not in st.session_state: st.session_state[k]=v

# ═══════════════════════════════════════════════════════════
# PAGE CONFIG & STYLING
# ═══════════════════════════════════════════════════════════
st.set_page_config(
    page_title="WTC Abuja Concierge",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""<style>
/* === HIDE STREAMLIT BRANDING === */
#MainMenu, footer, header, .stDeployButton, [data-testid="stToolbar"] {display:none!important}

/* === GLOBAL BACKGROUND === */
.stApp {background:#1a1a1a!important}
.stMainBlockContainer,.main,div[data-testid="stVerticalBlock"] {background:#1a1a1a!important;gap:0!important}

/* === ALL TEXT LIGHT === */
.stMarkdown,.stMarkdown p,.stMarkdown h1,.stMarkdown h2,.stMarkdown h3,.stMarkdown span,.stMarkdown div,p,h1,h2,h3,h4,label,span {color:#f0ede8!important}

/* === INPUT FIELDS === */
.stTextInput input,.stSelectbox select,.stTextInput textarea {background:#2a2a2a!important;color:#f0ede8!important;border:1px solid #4a4a4a!important;border-radius:4px!important;padding:10px 14px!important;font-size:15px!important}
.stTextInput input:focus {border-color:#c8a45c!important;box-shadow:0 0 0 3px rgba(200,164,92,0.15)!important}
.stTextInput input::placeholder {color:#6b6762!important}
.stTextInput label,.stSelectbox label,.stCheckbox label {color:#b8b4ac!important;font-size:13px!important;font-family:Arial,sans-serif!important}
.stCheckbox label span {color:#b8b4ac!important;font-size:13px!important}

/* === BUTTONS - BRASS GOLD === */
.stButton>button {background:linear-gradient(135deg,#a88838,#c8a45c)!important;color:#1a1a1a!important;border:none!important;border-radius:4px!important;padding:14px 28px!important;font-weight:600!important;font-size:14px!important;text-transform:uppercase!important;letter-spacing:1px!important;transition:all .3s!important;font-family:Arial,sans-serif!important;cursor:pointer!important}
.stButton>button:hover {background:linear-gradient(135deg,#c8a45c,#d4b56e)!important;transform:translateY(-1px)!important;box-shadow:0 4px 20px rgba(200,164,92,.3)!important}

/* === METRICS === */
[data-testid="stMetricValue"] {color:#c8a45c!important;font-size:2rem!important;font-weight:700!important}
[data-testid="stMetricLabel"] {color:#8a8680!important;font-size:.75rem!important}

/* === DATAFRAME === */
[data-testid="stDataFrame"] {background:#1e1e1e!important;border:1px solid #333!important;border-radius:4px!important}
[data-testid="stDataFrame"] th {background:#252525!important;color:#8a8680!important;font-size:11px!important;text-transform:uppercase!important;letter-spacing:1px!important;padding:12px!important;border-bottom:2px solid #333!important}
[data-testid="stDataFrame"] td {background:#1a1a1a!important;color:#b8b4ac!important;font-size:13px!important;padding:10px 12px!important;border-bottom:1px solid #2a2a2a!important}

/* === PROGRESS === */
.stProgress>div>div>div {background:#c8a45c!important}
.stProgress>div>div {background:#2a2a2a!important}

/* === ALERTS === */
.stAlert {border-radius:4px!important}
.stAlert p {color:#e8c8c8!important}

/* === DOWNLOAD BUTTON === */
.stDownloadButton>button {background:#252525!important;color:#c8a45c!important;border:1px solid #c8a45c!important;border-radius:4px!important;padding:10px 20px!important;font-weight:500!important}
.stDownloadButton>button:hover {background:rgba(200,164,92,.1)!important;color:#d4b56e!important;border-color:#d4b56e!important}

/* === DIVIDERS === */
hr {border-color:#333!important;margin:20px 0!important}

/* === WTC LOGO === */
.wtc-logo-img {max-width:180px;margin-bottom:20px;filter:brightness(1.2)}
</style>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════
# ADMIN ACCESS
# ═══════════════════════════════════════════════════════════
if "admin" in st.query_params:
    st.session_state.pg = "admin"
    st.session_state.adm = True
    st.query_params.clear()

st.markdown('<div style="position:fixed;bottom:3px;right:3px;z-index:9999;"><a href="?admin=true" style="color:#1a1a1a;text-decoration:none;font-size:7px;" title="Admin">·</a></div>',True)

# ═══════════════════════════════════════════════════════════
# LOGO HELPER
# ═══════════════════════════════════════════════════════════
def logo_html(width="180px"):
    if LOGO_B64:
        return f'<img src="data:image/jpeg;base64,{LOGO_B64}" class="wtc-logo-img" style="width:{width};margin:0 auto;display:block;">'
    return ""

# ═══════════════════════════════════════════════════════════
# IDLE / ATTRACT
# ═══════════════════════════════════════════════════════════
def idle():
    st.markdown("<br>"*4,True)
    c1,c2,c3=st.columns([1,2,1])
    with c2:
        st.markdown(logo_html("200px"), True)
        st.markdown('<p style="text-align:center;color:#c8a45c;letter-spacing:4px;font-size:13px;font-family:Arial,sans-serif">WORLD TRADE CENTER</p>',True)
        st.markdown('<h1 style="text-align:center;color:#e8e4dc;font-size:54px;line-height:1.1;margin:8px 0">World Trade Center<br>Abuja</h1>',True)
        st.markdown('<hr style="width:60px;border:1px solid #c8a45c;margin:20px auto">',True)
        st.markdown('<p style="text-align:center;color:#b8b4ac;font-size:18px;font-family:Arial,sans-serif">Grade A offices and executive residences in the capital.</p>',True)
        st.markdown('<p style="text-align:center;color:#8a8680;font-size:14px;font-family:Arial,sans-serif">Completed. Operational. Available for private inspection.</p>',True)
        st.markdown("<br>",True)
        a,b,c=st.columns([1,2,1])
        with b:
            if st.button("✨ Tap to Explore →",key="idle_go",use_container_width=True,type="primary"):
                st.session_state.pg="home"; st.rerun()
        st.markdown('<p style="text-align:center;color:#6b6762;font-size:13px;font-family:Arial,sans-serif;margin-top:30px">Receive the corporate prospectus, floorplates or residence plans</p>',True)

# ═══════════════════════════════════════════════════════════
# HOME
# ═══════════════════════════════════════════════════════════
def home():
    st.markdown(logo_html("140px"), True)
    st.markdown('<p style="text-align:center;color:#8a8680;font-size:12px;letter-spacing:3px;font-family:Arial,sans-serif;margin-top:15px">WORLD TRADE CENTER ABUJA</p>',True)
    st.markdown('<h2 style="text-align:center;color:#e8e4dc;font-size:34px;margin:8px 0 30px 0">What are you interested in?</h2>',True)
    routes=[("🏛️","Overview","WTC Abuja at a glance","overview"),("💼","Office Space","Grade A offices and floorplates","office"),("🏠","Executive Residences","Apartments and accommodation","residences"),("📍","Location","Constitution Avenue, CBD Abuja","location"),("🛡️","Security & Continuity","Access, CCTV, infrastructure","security"),("🔑","Request a Private Inspection","Office, residence or full walkthrough","convert_i"),("📋","Send Me the Digital Pack","Prospectus and materials","convert_d")]
    for row in range(0,7,3):
        cols=st.columns(3)
        for i in range(3):
            idx=row+i
            if idx>=7: break
            icon,title,desc,key=routes[idx]
            with cols[i]:
                st.markdown(f'<div style="background:#252525;border:1px solid #3a3a3a;border-radius:6px;padding:24px 20px;margin:5px;min-height:170px"><div style="font-size:2rem;margin-bottom:12px">{icon}</div><div style="color:#e8e4dc;font-size:1.1rem;font-weight:600;margin-bottom:6px">{title}</div><div style="color:#8a8680;font-size:0.8rem;font-family:Arial,sans-serif">{desc}</div></div>',True)
                if st.button("Select →",key=f"btn_{key}",use_container_width=True):
                    if key.startswith("convert"): st.session_state.pg="convert"; st.session_state.rt=None; st.session_state.fd={"pf":["Request a Private Inspection"] if "i" in key else ["Corporate Prospectus"]}
                    else: st.session_state.pg="route"; st.session_state.rt=key; st.session_state.sc=0
                    st.rerun()

# ═══════════════════════════════════════════════════════════
# CONTENT ROUTES
# ═══════════════════════════════════════════════════════════
ROUTES={"overview":{"title":"Overview","screens":[{"t":"A completed Grade A address in Abuja's CBD","b":"World Trade Center Abuja is a completed and operational Grade A development on Constitution Avenue in the heart of Abuja's Central Business District.","p":["Completed and operational","Constitution Avenue, CBD Abuja","Offices, residences and amenities","Professionally managed environment"]},{"t":"One address. Multiple uses. One controlled environment.","b":"WTC Abuja integrates business, living, and leisure within a secure, professionally managed perimeter.","p":["Offices","Residences","Clubhouse","Security perimeter","CBD Location"]},{"t":"The Proof","b":"A working, operational building — not a promise.","h":[("33,180 m²","Office GLA"),("1,440 m²","Typical Floorplate"),("120","Executive Residences"),("500+","CCTV Cameras"),("CBD Address","Near NNPC & Petroleum Ministry")]}]},"office":{"title":"Office Space","screens":[{"t":"Grade A offices for serious occupiers","b":"Completed, operational office space in Abuja's CBD, with flexible floorplates, secure access, and professional building management.","p":["33,180 m² total GLA","1,440 m² typical floorplate","~83% efficiency","130 m² to full-floor","Professional FM"]},{"t":"Floorplate Options","b":"Flexible space configurations:","h":[("130 m²","Representative office"),("230 m²","Single office suite"),("360 m²","Project team/embassy"),("720 m²","Larger corporate office"),("1,440 m²","Full-floor headquarters")]},{"t":"Built for Continuity","b":"The building is not a promise. It is running.","p":["10 MVA on-site power","8×1,250 kVA generators","Daikin VRV cooling","4 ISPs","Schindler lifts","Honeywell BMS"]}]},"residences":{"title":"Executive Residences","screens":[{"t":"Executive accommodation inside the same secure development","b":"Secure accommodation for senior executives, expatriates, and visiting leadership within the same controlled development as the offices.","p":["120 residences","1–6 bedroom range","Furnished/unfurnished","Private clubhouse access","Secure CBD location"]},{"t":"Residence Types","b":"Accommodation for different needs:","h":[("1-Bedroom","Executive singles"),("2-Bedroom","Couples, diplomatic staff"),("3-Bedroom","Families, senior execs"),("Penthouses & Villas","VIPs, leadership")]},{"t":"Simpler accommodation planning","b":"For energy-sector organisations with rotating staff — your team lives within the same secure development as your offices.","p":["Reduced daily movement","Same development as offices","Easier planning for expats","Secure for families"]},{"t":"Private amenities for daily life","b":"The Clubhouse offers:","p":["Fitness — Technogym","Wellness — Pool, spa, sauna","Sport — Tennis & squash","Business — Meeting rooms","Family — Café, crèche"]}]},"security":{"title":"Security & Continuity","screens":[{"t":"Security governed as an operating system","b":"Security at WTC Abuja is a framework of trained personnel, defined procedures, and integrated technology.","p":["Trained personnel","Defined procedures","Integrated technology","Professional management"]},{"t":"Security Layers","b":"Four integrated layers of protection:","h":[("Surveillance","500+ HD CCTV · 24/7 control room"),("Access Control","Honeywell · Access-controlled lifts"),("Vehicle & Perimeter","Bollards · Under-vehicle surveillance"),("Personnel","Manned guards · MOPOL · Fire Service")]},{"t":"Operational continuity built in","b":"Every critical system has redundancy.","p":["10 MVA on-site power","8×1,250 kVA generators","Twice building peak load","Daikin VRV cooling","4 ISPs","Fire & life safety"]}]},"location":{"title":"Location","screens":[{"t":"At the centre of business, government and diplomacy","b":"WTC Abuja occupies Constitution Avenue in the CBD — between Maitama and Asokoro, minutes from NNPC Towers and the Ministry of Petroleum Resources.","p":["Constitution Avenue","CBD Abuja","Between Maitama & Asokoro","Near NNPC Towers","Near Petroleum Ministry"]},{"t":"Why the Location Matters","b":"A CBD address that works:","p":["Close to federal institutions","Near diplomatic missions","Near corporate headquarters","Practical for leadership","Reduced travel time"]}]}}

def route():
    rk=st.session_state.rt; si=st.session_state.sc; rt=ROUTES.get(rk)
    if not rt or si>=len(rt["screens"]): st.session_state.pg="convert"; st.rerun(); return
    s=rt["screens"][si]; total=len(rt["screens"])
    c1,c2=st.columns([1,4])
    with c1:
        if st.button("← Back",key="route_back",use_container_width=True):
            if si==0: st.session_state.pg="home"; st.session_state.rt=None
            else: st.session_state.sc-=1
            st.rerun()
    with c2: st.markdown(f'<p style="color:#e8e4dc;font-size:18px;margin-top:8px;font-family:Arial,sans-serif">{rt["title"]} <span style="color:#8a8680;font-size:13px">— {si+1}/{total}</span></p>',True)
    st.progress((si+1)/total)
    st.markdown(f'<h2 style="color:#e8e4dc;font-size:28px;margin:20px 0 10px">{s["t"]}</h2>',True)
    if "b" in s: st.markdown(f'<p style="color:#b8b4ac;font-size:16px;line-height:1.7;font-family:Arial,sans-serif">{s["b"]}</p>',True)
    if "h" in s:
        cols=st.columns(len(s["h"]))
        for i,(num,lab) in enumerate(s["h"]):
            with cols[i]: st.markdown(f'<div style="background:#252525;border:1px solid #3a3a3a;border-radius:4px;padding:20px;text-align:center;margin:5px"><div style="font-size:1.4rem;color:#c8a45c;font-weight:700">{num}</div><div style="font-size:0.7rem;color:#8a8680;text-transform:uppercase;font-family:Arial,sans-serif;margin-top:4px">{lab}</div></div>',True)
    if "p" in s:
        cols=st.columns(2)
        for i,p in enumerate(s["p"]):
            with cols[i%2]: st.markdown(f'<div style="background:#252525;border:1px solid #3a3a3a;border-radius:4px;padding:15px;text-align:center;margin:4px;color:#b8b4ac;font-family:Arial,sans-serif;font-size:14px">{p}</div>',True)
    st.markdown("<br>",True)
    c1,c2,c3=st.columns(3)
    with c1:
        if st.button("🏠 Home",key="route_home",use_container_width=True): st.session_state.pg="home"; st.session_state.rt=None; st.session_state.sc=0; st.rerun()
    with c3:
        lbl="Continue →" if si<total-1 else "Get Materials →"
        if st.button(lbl,key="route_next",use_container_width=True,type="primary"):
            if si<total-1: st.session_state.sc+=1
            else: st.session_state.pg="convert"
            st.rerun()

# ═══════════════════════════════════════════════════════════
# CONVERSION FORM
# ═══════════════════════════════════════════════════════════
def convert():
    st.markdown(logo_html("120px"), True)
    st.markdown('<h2 style="color:#e8e4dc;font-size:28px;margin:15px 0">What would you like us to send you?</h2>',True)
    materials=["Corporate Prospectus","Office Floorplates","Residence Floorplans","Security & Continuity Brief","Clubhouse Overview","Location Overview","Request a Private Inspection","WTC Abuja Updates & Private Invitations"]
    selected=[]
    st.markdown('<p style="color:#c8a45c;font-size:13px;font-family:Arial,sans-serif;margin:10px 0">SELECT MATERIALS:</p>',True)
    cols=st.columns(2)
    for i,m in enumerate(materials):
        with cols[i%2]:
            if st.checkbox(m,value=m in st.session_state.fd.get("pf",[]),key=f"cm_{i}"): selected.append(m)
    st.markdown('<p style="color:#c8a45c;font-size:13px;font-family:Arial,sans-serif;margin:20px 0 10px">YOUR DETAILS:</p>',True)
    c1,c2=st.columns(2)
    with c1: fn=st.text_input("First Name *","",key="fn"); em=st.text_input("Email *","",key="em"); co=st.text_input("Company *","",key="co")
    with c2: ln=st.text_input("Last Name *","",key="ln"); ph=st.text_input("Mobile / WhatsApp *","",key="ph"); jt=st.text_input("Job Title (optional)","",key="jt")
    ti=st.selectbox("Timing (optional)",["","Immediate","0–3 months","3–6 months","6–12 months","Future/exploratory"],key="ti")
    st.markdown('<div style="background:#252525;border:1px solid #3a3a3a;border-radius:4px;padding:12px;margin:15px 0"><p style="color:#b8b4ac;font-size:12px;font-family:Arial,sans-serif;margin:0">By submitting, you agree WTC Abuja may contact you about your enquiry.</p></div>',True)
    mk=st.checkbox("Send me updates, news and private invitations. I can opt out anytime.",True,key="mk")
    c1,c2,c3=st.columns(3)
    with c1:
        if st.button("← Back",key="cv_bk",use_container_width=True): st.session_state.pg="route" if st.session_state.rt else "home"; st.rerun()
    with c3:
        if st.button("Submit →",key="cv_sb",use_container_width=True,type="primary"):
            if not fn or not ln or not em or not ph or not co: st.error("Please fill all required fields (*)")
            else:
                tm={"Office Floorplates":"Office Leasing","Corporate Prospectus":"Office Leasing","Residence Floorplans":"Executive Residences","Security & Continuity Brief":"Security & Continuity","Clubhouse Overview":"Clubhouse","Location Overview":"Location","Request a Private Inspection":"Private Inspection","WTC Abuja Updates & Private Invitations":"Newsletter"}
                tags=list(set(tm.get(m,m) for m in selected))
                lead={"fn":fn,"ln":ln,"em":em,"ph":ph,"co":co,"jt":jt,"ti":ti,"mt":selected,"tg":tags,"ins":"Request a Private Inspection" in selected,"mk":mk}
                db.save(lead)
                send_lead_email(lead)
                st.session_state.pg="confirm"
                st.session_state.ct="inspection" if "Request a Private Inspection" in selected else "digital_pack"
                st.session_state.fd={}
                st.rerun()

# ═══════════════════════════════════════════════════════════
# CONFIRMATION
# ═══════════════════════════════════════════════════════════
def confirm():
    cf={"inspection":("🔑","Inspection Requested","Your private inspection request has been received. The WTC Abuja team will contact you to confirm timing and requirements."),"digital_pack":("📋","Thank You","Your selected WTC Abuja materials will be sent shortly. A member of the team may follow up based on your enquiry."),"updates":("📬","You're Subscribed","You have been added to WTC Abuja Updates & Private Invitations. You can opt out at any time.")}
    ic,hl,ms=cf.get(st.session_state.ct,cf["digital_pack"])
    st.markdown("<br>"*4,True)
    c1,c2,c3=st.columns([1,2,1])
    with c2:
        st.markdown(logo_html("150px"), True)
        st.markdown(f'<div style="text-align:center"><div style="width:70px;height:70px;border-radius:50%;background:rgba(200,164,92,0.1);border:2px solid #c8a45c;display:flex;align-items:center;justify-content:center;font-size:2rem;margin:20px auto">{ic}</div><h2 style="color:#e8e4dc;font-size:28px;margin-bottom:10px">{hl}</h2><p style="color:#b8b4ac;font-size:16px;font-family:Arial,sans-serif;line-height:1.6">{ms}</p></div>',True)
        st.markdown("<br>",True)
        a,b=st.columns(2)
        with a:
            if st.button("Return to Home",key="cf_hm",use_container_width=True): st.session_state.pg="home"; st.rerun()
        with b:
            if st.button("Explore More",key="cf_ex",use_container_width=True,type="primary"): st.session_state.pg="home"; st.rerun()

# ═══════════════════════════════════════════════════════════
# ADMIN PANEL
# ═══════════════════════════════════════════════════════════
def admin():
    if not st.session_state.adm:
        st.markdown("<br>"*6,True)
        c1,c2,c3=st.columns([1,1,1])
        with c2:
            st.markdown(logo_html("150px"), True)
            st.markdown('<h2 style="text-align:center;color:#e8e4dc;margin-top:15px">Admin Access</h2>',True)
            st.markdown('<p style="text-align:center;color:#8a8680;font-size:13px;font-family:Arial,sans-serif">Enter your admin PIN to continue</p>',True)
            p=st.text_input("PIN","",type="password",key="apin",placeholder="Enter 4-digit PIN")
            if st.button("Access Admin Panel",key="adm_go",use_container_width=True,type="primary"):
                if p=="4271": st.session_state.adm=True; st.rerun()
                else: st.error("Invalid PIN. Please try again.")
            st.markdown('<p style="text-align:center;color:#6b6762;font-size:11px;font-family:Arial,sans-serif;margin-top:10px">Authorized personnel only</p>',True)
        return
    
    s=db.stats(); l=db.all(100)
    
    # Header
    c1,c2,c3=st.columns([2,1,1])
    with c1: st.markdown('<h2 style="color:#e8e4dc;margin:15px 0">📊 Admin Panel — WTC Abuja Concierge</h2>',True)
    with c2:
        csv_data=db.csv()
        if csv_data: st.download_button("📥 Download CSV",csv_data,f"wtc_leads_{datetime.now().strftime('%Y%m%d_%H%M')}.csv","text/csv",use_container_width=True)
    with c3:
        if st.button("🚪 Logout",key="adm_out",use_container_width=True): st.session_state.adm=False; st.session_state.pg="idle"; st.rerun()
    
    # Stats
    st.markdown("<br>",True)
    c1,c2,c3,c4,c5=st.columns(5)
    c1.metric("Total Leads",s['t'])
    c2.metric("Inspections",s['i'])
    c3.metric("Opt-Ins",s['m'])
    c4.metric("Digital Packs",s['t']-s['i'])
    c5.metric("Database","SQLite ✅")
    
    # Campaign info
    st.markdown(f'<p style="color:#8a8680;font-size:12px;font-family:Arial,sans-serif;margin:5px 0">📅 Campaign: <b style="color:#c8a45c">NOG Energy Week 2026</b> | 💾 Database: <b style="color:#c8a45c">data/wtc_abuja.db</b> | 🕐 Last updated: {datetime.now().strftime("%d %b %Y, %H:%M")}</p>',True)
    
    st.markdown("<br>",True)
    st.markdown('<h3 style="color:#e8e4dc">📋 Recent Leads</h3>',True)
    
    if l:
        td=[]
        for r in l:
            try: m=json.loads(r.get("materials","[]") if isinstance(r.get("materials"),str) else "[]"); m=", ".join(m[:3])
            except: m=""
            td.append({
                "Time":r.get("submitted","")[:16],
                "Name":f"{r.get('first_name','')} {r.get('last_name','')}",
                "Company":r.get("company",""),
                "Email":r.get("email",""),
                "Phone":r.get("phone",""),
                "Materials":m,
                "Inspection":"✅" if r.get("inspection") else "—",
                "Opt-In":"✅" if r.get("marketing") else "—"
            })
        st.dataframe(td,use_container_width=True,hide_index=True,height=400)
        st.markdown(f'<p style="color:#6b6762;font-size:11px;font-family:Arial,sans-serif;margin-top:5px">Showing {len(td)} of {s["t"]} total leads. Download CSV for complete data.</p>',True)
    else:
        st.info("📭 No leads captured yet. Leads will appear here when visitors submit the form on the tablet.")
    
    st.markdown("<br>",True)
    st.markdown('<div style="background:#252525;border:1px solid #3a3a3a;border-radius:6px;padding:15px;margin:10px 0"><p style="color:#b8b4ac;font-size:12px;font-family:Arial,sans-serif;margin:0">💡 <b>Quick Tips:</b> Copy <code style="color:#c8a45c;background:#1a1a1a;padding:2px 6px;border-radius:3px">data/wtc_abuja.db</code> to backup all leads. | Access this panel anytime at <code style="color:#c8a45c;background:#1a1a1a;padding:2px 6px;border-radius:3px">?admin=true</code> | PIN: 4271</p></div>',True)

# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════
elapsed=(datetime.now()-st.session_state.la).total_seconds()
if st.session_state.pg!="idle" and elapsed>120: st.session_state.pg="idle"; st.session_state.rt=None; st.session_state.sc=0; st.rerun()

pg=st.session_state.pg
if pg=="idle": idle()
elif pg=="home": home()
elif pg=="route": route()
elif pg=="convert": convert()
elif pg=="confirm": confirm()
elif pg=="admin": admin()
else: idle()