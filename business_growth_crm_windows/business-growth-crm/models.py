from datetime import datetime
from flask_login import UserMixin
from extensions import db
class User(UserMixin,db.Model):
 id=db.Column(db.Integer,primary_key=True); username=db.Column(db.String(80),unique=True,nullable=False); password_hash=db.Column(db.String(255),nullable=False)
class Lead(db.Model):
 id=db.Column(db.Integer,primary_key=True); business_name=db.Column(db.String(180),nullable=False,index=True); category=db.Column(db.String(60),default="Other"); county=db.Column(db.String(80),default=""); town=db.Column(db.String(100),default=""); phone=db.Column(db.String(30),default="",index=True); email=db.Column(db.String(150),default=""); website=db.Column(db.String(300),default=""); website_status=db.Column(db.String(40),default="UNVERIFIED"); status=db.Column(db.String(40),default="New"); marketing_eligibility=db.Column(db.String(30),default="Pending"); source=db.Column(db.String(100),default="Manual"); source_url=db.Column(db.String(500),default=""); place_id=db.Column(db.String(200),unique=True,nullable=True); notes=db.Column(db.Text,default=""); score=db.Column(db.Integer,default=0); created_at=db.Column(db.DateTime,default=datetime.utcnow)
class Activity(db.Model):
 id=db.Column(db.Integer,primary_key=True); lead_id=db.Column(db.Integer,db.ForeignKey("lead.id"),nullable=False); kind=db.Column(db.String(50)); detail=db.Column(db.Text); created_at=db.Column(db.DateTime,default=datetime.utcnow)
class FollowUp(db.Model):
 id=db.Column(db.Integer,primary_key=True); lead_id=db.Column(db.Integer,db.ForeignKey("lead.id"),nullable=False); due_date=db.Column(db.Date,nullable=False); note=db.Column(db.String(500),default=""); completed=db.Column(db.Boolean,default=False); lead=db.relationship("Lead")
class Campaign(db.Model):
 id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(150)); offer=db.Column(db.String(300)); message_template=db.Column(db.Text); created_at=db.Column(db.DateTime,default=datetime.utcnow)
class FactFinding(db.Model):
 id=db.Column(db.Integer,primary_key=True)
 business_name=db.Column(db.String(180),nullable=False,index=True)
 category=db.Column(db.String(60),default="Other")
 county=db.Column(db.String(80),default="")
 town=db.Column(db.String(100),default="")
 phone=db.Column(db.String(30),default="",index=True)
 email=db.Column(db.String(150),default="")
 website=db.Column(db.String(300),default="")
 source_name=db.Column(db.String(120),nullable=False)
 source_url=db.Column(db.String(500),default="")
 retrieved_at=db.Column(db.DateTime,default=datetime.utcnow,nullable=False)
 evidence=db.Column(db.Text,default="")
 confidence=db.Column(db.Integer,default=50)
 status=db.Column(db.String(30),default="Pending review",index=True)
 duplicate_of_lead_id=db.Column(db.Integer,db.ForeignKey("lead.id"),nullable=True)
 promoted_lead_id=db.Column(db.Integer,db.ForeignKey("lead.id"),nullable=True)
 reviewer_note=db.Column(db.Text,default="")
 created_at=db.Column(db.DateTime,default=datetime.utcnow)
 duplicate_of_lead=db.relationship("Lead",foreign_keys=[duplicate_of_lead_id])
 promoted_lead=db.relationship("Lead",foreign_keys=[promoted_lead_id])
class OutreachMessage(db.Model):
 id=db.Column(db.Integer,primary_key=True)
 lead_id=db.Column(db.Integer,db.ForeignKey("lead.id"),nullable=False,index=True)
 body=db.Column(db.Text,nullable=False)
 status=db.Column(db.String(30),default="Needs review",index=True)
 reviewer_note=db.Column(db.Text,default="")
 created_at=db.Column(db.DateTime,default=datetime.utcnow)
 approved_at=db.Column(db.DateTime,nullable=True)
 sent_at=db.Column(db.DateTime,nullable=True)
 lead=db.relationship("Lead")
