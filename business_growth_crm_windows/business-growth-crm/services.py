import os,requests,re,csv
from datetime import datetime
from urllib.parse import quote,urlparse
from extensions import db
def normalize_phone(raw):
 # Spreadsheet cells may contain several public numbers. Normalize the first
 # complete number rather than concatenating every number into one invalid one.
 candidates=re.findall(r"(?:\+?\d[\d\s().-]{6,}\d)",str(raw or ""))
 raw=candidates[0] if candidates else raw
 d="".join(c for c in str(raw or "") if c.isdigit())
 if d.startswith("00"): d=d[2:]
 if d.startswith("2540"): d="254"+d[4:]
 if len(d)==10 and d.startswith("0"): d="254"+d[1:]
 elif len(d)==9 and d[0] in "17": d="254"+d
 return "+"+d if d else ""
def public_url(raw):
 value=str(raw or "").strip()
 return value if urlparse(value).scheme in ("http","https") else ""
def score(l):
 n=0
 website_status=str(l.website_status or "").upper()
 if website_status in ("CONFIRMED_NO_WEBSITE","WEBSITE_ABSENT"): n+=35
 elif website_status in ("LIKELY_NO_WEBSITE","NOT_CONFIRMED"): n+=20
 if l.phone or l.email: n+=20
 if l.town or l.county: n+=8
 if str(l.category or "").strip().casefold().rstrip("s") in ["salon","hotel","guesthouse","school","clinic"]: n+=15
 if l.source: n+=5
 return min(n,100)
def find_duplicate_lead(name,phone):
 from models import Lead
 if phone:
  match=Lead.query.filter_by(phone=phone).first()
  if match: return match
 clean=" ".join(str(name or "").casefold().split())
 return Lead.query.filter(db.func.lower(Lead.business_name)==clean).order_by(Lead.id).first() if clean else None
def parse_fact_csv(text,source_name,source_url):
 rows=list(csv.DictReader(text.splitlines()))
 if not rows: raise ValueError("The CSV has no data rows.")
 findings=[]
 def value(row,*names):
  normalized={re.sub(r"[^a-z0-9]+","_",str(k).casefold()).strip("_"):str(v or "").strip() for k,v in row.items()}
  for name in names:
   result=normalized.get(name)
   if result: return result
  return ""
 for row in rows:
  name=value(row,"business_name","business","name","company")
  if not name: continue
  phone=normalize_phone(value(row,"phone","telephone","phone_number","contact"))
  website=value(row,"website","website_url","url")
  evidence=value(row,"evidence","evidence_snippet","snippet","description","listing_text")
  fields=[]
  for label,names in [("Phone",("phone","telephone","phone_number","contact")),("Email",("email",)),("Website",("website","website_url","url")),("Address",("address","location")),("Category",("category",))]:
   item=value(row,*names)
   if item: fields.append(f"{label}: {item}")
  evidence=" | ".join(([evidence] if evidence else [])+fields)[:4000]
  raw_confidence=value(row,"confidence")
  try: confidence=max(0,min(100,int(raw_confidence))) if raw_confidence else (75 if phone or website else 50)
  except ValueError: confidence=50
  findings.append({"business_name":name,"category":value(row,"category","business_category") or "Other","county":value(row,"county"),"town":value(row,"town","city","location"),"phone":phone,"email":value(row,"email"),"website":public_url(website),"source_name":source_name,"source_url":public_url(value(row,"source_url","listing_url") or source_url),"retrieved_at":datetime.utcnow(),"evidence":evidence or "No evidence text was supplied in this export.","confidence":confidence})
 return findings
def wa_link(phone,message):
 digits="".join(c for c in (phone or "") if c.isdigit())
 return f"https://wa.me/{digits}?text={quote(message or '')}" if digits else None
def make_draft(l):
 fallback=f"Hello {l.business_name}, I came across your business and wanted to ask whether you currently have a website. I help businesses create mobile-friendly websites that make it easier for customers to find services and contact you. Would you be open to a brief conversation?"
 key=os.getenv("GROQ_API_KEY")
 if not key:return fallback
 try:
  from groq import Groq
  client=Groq(api_key=key)
  price=os.getenv("INTRODUCTORY_PRICE","15000")
  website_instruction=("The business is confirmed not to have a website; tactfully mention that it currently does not have one. "
                       if str(l.website_status or "").upper() in ("CONFIRMED_NO_WEBSITE","WEBSITE_ABSENT")
                       else "Ask neutrally whether the business currently has a website; do not imply it lacks one. ")
  prompt=("Write one concise, respectful first-contact WhatsApp message in 2–3 sentences. "
          f"Use KSh {price} only as internal context; do not mention any price, amount, deposit, discount, or fee. "
          "Greet the business by name, briefly offer mobile-friendly website help, " + website_instruction +
          "Invite a brief conversation. Do not invent the sender's name, company, experience, or contact details. "
          "Do not invent business facts or claim likely results. Do not include placeholders or a sign-off. "
          "Return only one short paragraph. "
          f"Business: {l.business_name}; category: {l.category}; location: {l.town}; website status: {l.website_status}.")
  r=client.chat.completions.create(model=os.getenv("GROQ_MODEL","openai/gpt-oss-120b"),messages=[{"role":"user","content":prompt}],temperature=.4,max_tokens=320,reasoning_effort="low",include_reasoning=False)
  return r.choices[0].message.content.strip()
 except Exception:return fallback
def places(key,category,location):
 url="https://places.googleapis.com/v1/places:searchText"
 headers={"Content-Type":"application/json","X-Goog-Api-Key":key,"X-Goog-FieldMask":"places.id,places.displayName,places.websiteUri,places.nationalPhoneNumber,places.googleMapsUri"}
 r=requests.post(url,headers=headers,json={"textQuery":f"{category} in {location}, Kenya","pageSize":20},timeout=30); r.raise_for_status()
 return [{"place_id":p.get("id"),"name":p.get("displayName",{}).get("text",""),"phone":p.get("nationalPhoneNumber",""),"website":p.get("websiteUri",""),"maps_url":p.get("googleMapsUri","")} for p in r.json().get("places",[])]
