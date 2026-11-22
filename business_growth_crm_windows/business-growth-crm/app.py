import os,csv,re
from io import BytesIO
from datetime import date,datetime
from flask import Flask,render_template,request,redirect,url_for,flash,send_file
from flask_login import LoginManager,UserMixin,login_user,login_required,logout_user
from werkzeug.security import generate_password_hash,check_password_hash
from dotenv import load_dotenv
from extensions import db
from models import User,Lead,Activity,FollowUp,Campaign,FactFinding,OutreachMessage
from services import normalize_phone,score,make_draft,wa_link,places,find_duplicate_lead,parse_fact_csv,public_url
load_dotenv()
app=Flask(__name__); app.config.update(SECRET_KEY=os.getenv("SECRET_KEY","change-me"),SQLALCHEMY_DATABASE_URI="sqlite:///"+os.path.join(app.root_path,"instance","crm.db"),SQLALCHEMY_TRACK_MODIFICATIONS=False,MAX_CONTENT_LENGTH=12*1024*1024)
os.makedirs(os.path.join(app.root_path,"instance"),exist_ok=True); db.init_app(app)
with app.app_context(): db.create_all()
lm=LoginManager(app); lm.login_view="login"
@lm.user_loader
def user_loader(uid): return db.session.get(User,int(uid))
@app.context_processor
def globals(): return {"app_name":"Business Growth CRM","today":date.today()}
@app.route("/setup",methods=["GET","POST"])
def setup():
 db.create_all()
 if User.query.first(): return redirect(url_for("login"))
 if request.method=="POST":
  u=request.form["username"].strip(); p=request.form["password"]
  if len(u)<3 or len(p)<10: flash("Username must be 3+ characters and password 10+ characters.","danger")
  else:
   db.session.add(User(username=u,password_hash=generate_password_hash(p))); db.session.commit()
   login_user(User.query.filter_by(username=u).first()); return redirect(url_for("dashboard"))
 return render_template("setup.html")
@app.route("/login",methods=["GET","POST"])
def login():
 if request.method=="POST":
  u=User.query.filter_by(username=request.form["username"].strip()).first()
  if u and check_password_hash(u.password_hash,request.form["password"]): login_user(u); return redirect(url_for("dashboard"))
  flash("Incorrect username or password.","danger")
 return render_template("login.html")
@app.route("/logout")
@login_required
def logout(): logout_user(); return redirect(url_for("login"))
@app.route("/")
@login_required
def dashboard():
 stages=["New","Contacted","Responded","Interested","Negotiating","Converted","Lost"]
 return render_template("dashboard.html",total=Lead.query.count(),counts={s:Lead.query.filter_by(status=s).count() for s in stages},due=FollowUp.query.filter_by(completed=False).order_by(FollowUp.due_date).limit(8).all(),recent=Lead.query.order_by(Lead.created_at.desc()).limit(8).all(),outreach_pending=OutreachMessage.query.filter_by(status="Needs review").count())
@app.route("/leads")
@login_required
def leads():
 q=request.args.get("q","").strip(); st=request.args.get("status",""); cat=request.args.get("category",""); query=Lead.query
 if q: query=query.filter(db.or_(Lead.business_name.ilike(f"%{q}%"),Lead.phone.ilike(f"%{q}%"),Lead.town.ilike(f"%{q}%")))
 if st: query=query.filter_by(status=st)
 if cat: query=query.filter_by(category=cat)
 return render_template("leads.html",leads=query.order_by(Lead.created_at.desc()).all(),q=q,status=st,category=cat)
@app.route("/leads/new",methods=["GET","POST"])
@login_required
def new_lead():
 if request.method=="POST":
  l=Lead(business_name=request.form["business_name"].strip(),category=request.form.get("category","Other"),county=request.form.get("county",""),town=request.form.get("town",""),phone=normalize_phone(request.form.get("phone","")),email=request.form.get("email",""),website=request.form.get("website",""),website_status=request.form.get("website_status","UNVERIFIED"),status=request.form.get("status","New"),marketing_eligibility=request.form.get("marketing_eligibility","Pending"),source=request.form.get("source","Manual entry"),source_url=request.form.get("source_url",""),notes=request.form.get("notes",""))
  l.score=score(l); db.session.add(l); db.session.commit(); return redirect(url_for("detail",lid=l.id))
 return render_template("lead_form.html")
@app.route("/leads/<int:lid>",methods=["GET","POST"])
@login_required
def detail(lid):
 l=db.get_or_404(Lead,lid)
 if request.method=="POST":
  for f in ["business_name","category","county","town","email","website","website_status","status","marketing_eligibility","notes"]: setattr(l,f,request.form.get(f,""))
  l.phone=normalize_phone(request.form.get("phone","")); l.score=score(l); db.session.commit(); flash("Lead updated.","success"); return redirect(url_for("detail",lid=lid))
 msg=request.args.get("message","")
 return render_template("lead_detail.html",lead=l,message=msg,wa=wa_link(l.phone,msg) if l.phone else None,activities=Activity.query.filter_by(lead_id=lid).order_by(Activity.created_at.desc()).all(),followups=FollowUp.query.filter_by(lead_id=lid).all())
@app.route("/leads/<int:lid>/draft",methods=["POST"])
@login_required
def draft(lid): return redirect(url_for("detail",lid=lid,message=make_draft(db.get_or_404(Lead,lid))))
@app.route("/leads/<int:lid>/outreach",methods=["POST"])
@login_required
def queue_outreach(lid):
 l=db.get_or_404(Lead,lid)
 if not l.phone: flash("Add a phone number before preparing a WhatsApp draft.","warning")
 elif str(l.marketing_eligibility or "").casefold()=="opted out": flash("This lead opted out. No outreach draft was created.","warning")
 else:
  db.session.add(OutreachMessage(lead_id=l.id,body=make_draft(l))); db.session.commit(); flash("Draft added to the outreach review queue. It will not send automatically.","success")
 return redirect(url_for("outreach"))
@app.route("/outreach")
@login_required
def outreach():
 status=request.args.get("status","")
 query=OutreachMessage.query
 if status: query=query.filter_by(status=status)
 return render_template("outreach.html",messages=query.order_by(OutreachMessage.created_at.desc()).all(),status=status)
@app.route("/outreach/<int:mid>",methods=["POST"])
@login_required
def update_outreach(mid):
 message=db.get_or_404(OutreachMessage,mid); action=request.form.get("action")
 message.body=request.form.get("body","").strip() or message.body
 message.reviewer_note=request.form.get("reviewer_note","").strip()
 if action=="approve":
  if str(message.lead.marketing_eligibility or "").casefold()=="opted out": flash("Cannot approve outreach for an opted-out lead.","warning"); return redirect(url_for("outreach"))
  message.status="Approved"; message.approved_at=datetime.utcnow(); db.session.commit(); flash("Draft approved. Open WhatsApp and send it yourself.","success")
 elif action=="skip": message.status="Skipped"; db.session.commit(); flash("Draft skipped; nothing was sent.","success")
 elif action=="sent":
  if message.status!="Approved": flash("Approve the draft before marking it sent.","warning"); return redirect(url_for("outreach"))
  message.status="Sent manually"; message.sent_at=datetime.utcnow(); message.lead.status="Contacted"; db.session.add(Activity(lead_id=message.lead_id,kind="WhatsApp sent",detail="Sent manually from approved outreach queue.")); db.session.commit(); flash("Manual send recorded.","success")
 elif action=="opt_out": message.lead.marketing_eligibility="Opted out"; message.status="Skipped"; db.session.add(Activity(lead_id=message.lead_id,kind="Opt-out",detail="Marketing opt-out recorded from outreach queue.")); db.session.commit(); flash("Opt-out recorded. Future queued outreach is blocked.","success")
 else: flash("Choose an outreach action.","warning")
 return redirect(url_for("outreach"))
@app.route("/leads/<int:lid>/activity",methods=["POST"])
@login_required
def activity(lid):
 kind=request.form.get("kind","Note"); detail=request.form.get("detail","").strip(); l=db.get_or_404(Lead,lid)
 if detail:
  db.session.add(Activity(lead_id=lid,kind=kind,detail=detail))
  if kind=="WhatsApp sent": l.status="Contacted"
  db.session.commit()
 return redirect(url_for("detail",lid=lid))
@app.route("/followups",methods=["GET","POST"])
@login_required
def followups():
 if request.method=="POST":
  db.session.add(FollowUp(lead_id=int(request.form["lead_id"]),due_date=date.fromisoformat(request.form["due_date"]),note=request.form.get("note",""))); db.session.commit(); return redirect(url_for("followups"))
 return render_template("followups.html",items=FollowUp.query.order_by(FollowUp.completed,FollowUp.due_date).all(),leads=Lead.query.order_by(Lead.business_name).all())
@app.route("/followups/<int:fid>/complete",methods=["POST"])
@login_required
def complete(fid): f=db.get_or_404(FollowUp,fid); f.completed=True; db.session.commit(); return redirect(url_for("followups"))
@app.route("/campaigns",methods=["GET","POST"])
@login_required
def campaigns():
 if request.method=="POST": db.session.add(Campaign(name=request.form["name"],offer=request.form.get("offer",""),message_template=request.form.get("message_template",""))); db.session.commit(); return redirect(url_for("campaigns"))
 return render_template("campaigns.html",campaigns=Campaign.query.all())
@app.route("/discovery",methods=["GET","POST"])
@login_required
def discovery():
 if request.method=="POST":
  key=os.getenv("GOOGLE_PLACES_API_KEY","")
  if not key: flash("Add GOOGLE_PLACES_API_KEY to .env first.","warning")
  else:
   try:
    found=places(key,request.form["category"],request.form["location"]); n=0
    for x in found:
     pid=x.get("place_id"); phone=normalize_phone(x.get("phone",""))
     if (pid and Lead.query.filter_by(place_id=pid).first()) or (phone and Lead.query.filter_by(phone=phone).first()): continue
     l=Lead(business_name=x["name"],category=request.form["category"],town=request.form["location"],phone=phone,website=x.get("website",""),website_status="WEBSITE_FOUND" if x.get("website") else "UNVERIFIED",source="Google Places",source_url=x.get("maps_url",""),place_id=pid,notes="Verify business and website manually."); l.score=score(l); db.session.add(l); n+=1
    db.session.commit(); flash(f"Added {n} prospects. Verify website status manually.","success")
   except Exception as e: flash(str(e),"danger")
 return render_template("discovery.html")
@app.route("/fact-finder",methods=["GET","POST"])
@login_required
def fact_finder():
 if request.method=="POST":
  f=request.files.get("file")
  source_name=request.form.get("source_name","").strip()
  source_url=public_url(request.form.get("source_url","").strip())
  if not f or not f.filename: flash("Choose a CSV export first.","warning"); return redirect(url_for("fact_finder"))
  if not source_name: flash("Name the public source or export provider.","warning"); return redirect(url_for("fact_finder"))
  try:
   if not f.filename.lower().endswith(".csv"): raise ValueError("Fact Finder accepts CSV exports only.")
   findings=parse_fact_csv(f.stream.read().decode("utf-8-sig"),source_name,source_url)
   added=0; duplicates=0
   for item in findings:
    duplicate=find_duplicate_lead(item["business_name"],item["phone"])
    existing=FactFinding.query.filter_by(source_name=source_name,source_url=item["source_url"],business_name=item["business_name"],phone=item["phone"]).first()
    if existing: continue
    db.session.add(FactFinding(**item,duplicate_of_lead_id=duplicate.id if duplicate else None,status="Possible duplicate" if duplicate else "Pending review")); added+=1; duplicates+=bool(duplicate)
   db.session.commit(); flash(f"Added {added} findings ({duplicates} possible matches). Review each finding before creating a lead.","success")
  except Exception as e: db.session.rollback(); flash(f"Fact Finder import failed: {e}","danger")
  return redirect(url_for("fact_review"))
 return render_template("fact_finder.html")
@app.route("/fact-finder/review")
@login_required
def fact_review():
 status=request.args.get("status","")
 query=FactFinding.query
 if status: query=query.filter_by(status=status)
 return render_template("fact_review.html",findings=query.order_by(FactFinding.created_at.desc()).all(),status=status)
@app.route("/fact-finder/<int:fid>/review",methods=["POST"])
@login_required
def review_fact(fid):
 finding=db.get_or_404(FactFinding,fid); action=request.form.get("action")
 finding.reviewer_note=request.form.get("reviewer_note","").strip()
 if action=="reject": finding.status="Rejected"; db.session.commit(); flash("Finding rejected; no lead was created.","success")
 elif action=="promote":
  lead=find_duplicate_lead(finding.business_name,finding.phone)
  if not lead:
   lead=Lead(business_name=finding.business_name,category=finding.category or "Other",county=finding.county,town=finding.town,phone=finding.phone,email=finding.email,website=finding.website,website_status="WEBSITE_FOUND" if finding.website else "UNVERIFIED",source=finding.source_name,source_url=finding.source_url,notes=f"Human-verified finding. Evidence: {finding.evidence}")
   lead.score=score(lead); db.session.add(lead); db.session.flush()
  else:
   finding.duplicate_of_lead_id=lead.id
  finding.promoted_lead_id=lead.id; finding.status="Promoted"; db.session.add(Activity(lead_id=lead.id,kind="Fact Finder",detail=f"Human-reviewed evidence from {finding.source_name}: {finding.evidence}")); db.session.commit(); flash("Finding promoted to the CRM after human review.","success")
 else: flash("Choose Promote or Reject.","warning")
 return redirect(url_for("fact_review"))
@app.route("/import",methods=["GET","POST"])
@login_required
def import_leads():
 if request.method=="POST":
  f=request.files.get("file")
  try:
   if f.filename.lower().endswith(".csv"): rows=list(csv.DictReader(f.stream.read().decode("utf-8-sig").splitlines()))
   elif f.filename.lower().endswith(".xlsx"):
    import pandas as pd
    rows=pd.read_excel(f).fillna("").to_dict("records")
   else: raise ValueError("Upload CSV or XLSX.")
   n=0; updated=0
   def cell(d,*names):
    for name in names:
     key=re.sub(r"[^a-z0-9]+","_",name.casefold()).strip("_")
     value=d.get(key)
     if value is not None and str(value).strip(): return str(value).strip()
    return ""
   for r in rows:
    d={re.sub(r"[^a-z0-9]+","_",str(k).casefold()).strip("_"):v for k,v in r.items()}; name=cell(d,"business_name","business","name")
    if not name: continue
    raw_phone=cell(d,"phone","public_contact","phone_public_contact")
    phone=normalize_phone(raw_phone)
    category=cell(d,"category","business_category") or ("Salon" if "salon" in f.filename.casefold() else "Other")
    location=cell(d,"town","location","location_address","address","county")
    county=cell(d,"county")
    raw_website_status=cell(d,"website_status","website_status_initial_verification")
    ws=raw_website_status.casefold()
    if not raw_website_status: website_status="WEBSITE_FOUND" if cell(d,"website","website_url") else "UNVERIFIED"
    elif "website absent" in ws or "no website" in ws or "confirmed no" in ws: website_status="CONFIRMED_NO_WEBSITE"
    elif "likely no website" in ws: website_status="LIKELY_NO_WEBSITE"
    elif "present" in ws or "website found" in ws: website_status="WEBSITE_FOUND"
    elif "not confirmed" in ws or "not listed" in ws or "unknown" in ws: website_status="UNVERIFIED"
    else: website_status="UNVERIFIED"
    website=cell(d,"website","website_url")
    metadata=[]
    for label,names in [("Sales potential",("sales_potential",)),("Introductory price (KSh)",("introductory_website_price_ksh","introductory_website_price")),("50% deposit (KSh)",("50_deposit_ksh","deposit_ksh")),("Outreach status",("outreach_status",)),("Additional public contacts",("phone_public_contact","public_contact")),("Address",("location_address","address"))]:
     value=cell(d,*names)
     if value and value!=raw_phone and not (label=="Address" and value==location): metadata.append(f"{label}: {value}")
    notes=cell(d,"notes")
    if raw_phone and ("/" in raw_phone or ";" in raw_phone or "," in raw_phone): metadata.append(f"Public contact as supplied: {raw_phone}")
    if metadata: notes="; ".join(([notes] if notes else [])+metadata)
    existing=Lead.query.filter_by(phone=phone).first() if phone else None
    if not existing: existing=Lead.query.filter(db.func.lower(Lead.business_name)==name.casefold()).order_by(Lead.id).first()
    l=existing or Lead(business_name=name)
    if existing: updated+=1
    l.business_name=name; l.category=category; l.county=county; l.town=location; l.phone=phone; l.email=cell(d,"email"); l.website=website; l.website_status=website_status; l.source=cell(d,"source","verification_source") or f.filename; l.source_url=cell(d,"source_url","verification_source_url"); l.notes=notes; l.score=score(l); db.session.add(l); n+=1
   db.session.commit(); flash(f"Processed {n} leads ({updated} existing records refreshed). Duplicate phones and names are matched to existing records.","success")
  except Exception as e: db.session.rollback(); flash(f"Import failed: {e}","danger")
  return redirect(url_for("leads"))
 return render_template("import.html")
@app.route("/export")
@login_required
def export():
 import pandas as pd
 cols=["business_name","category","county","town","phone","email","website","website_status","status","marketing_eligibility","score","source","source_url","notes"]
 rows=[{c:getattr(l,c) for c in cols} for l in Lead.query.all()]; b=BytesIO(); pd.DataFrame(rows,columns=cols).to_excel(b,index=False); b.seek(0)
 return send_file(b,as_attachment=True,download_name="business_growth_leads.xlsx")
@app.route("/settings")
@login_required
def settings(): return render_template("settings.html",groq=bool(os.getenv("GROQ_API_KEY")),places=bool(os.getenv("GOOGLE_PLACES_API_KEY")))
if __name__=="__main__":
 with app.app_context(): db.create_all()
 app.run(host="0.0.0.0",port=5000,debug=False)
