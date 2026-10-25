import csv, io, secrets
from datetime import datetime, date
from fastapi import FastAPI, Request, Depends, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from app.db import Base, engine, get_db, SessionLocal
from app.models import Customer, CallLog, AuditLog
from app.config import APP_SECRET_KEY, SEED_DEMO_DATA
from app.security import authenticate, current_user, require_role
from app.telephony import place_call, TelephonyNotConfigured

app = FastAPI(title="AI Loan Collection Agent")
app.add_middleware(SessionMiddleware, secret_key=APP_SECRET_KEY, same_site="lax", https_only=False)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
Base.metadata.create_all(bind=engine)

OUTCOMES = {
    "answered_ptp": "Promise to pay",
    "paid_claimed": "Customer says paid (unverified)",
    "callback_requested": "Callback requested",
    "no_answer": "No answer",
    "wrong_number": "Wrong number",
    "dispute": "Dispute / complaint",
    "hardship": "Financial hardship",
    "refused": "Customer objected / refused",
}
SUPPRESS_OUTCOMES = {"wrong_number", "dispute", "hardship", "refused"}

def audit(db, user, action, entity_type, entity_id, details=""):
    db.add(AuditLog(username=user.get("username", "system"), action=action,
                    entity_type=entity_type, entity_id=str(entity_id), details=details[:1000]))

def seed_data():
    db = SessionLocal()
    try:
        if db.query(Customer).count() == 0 and SEED_DEMO_DATA:
            samples = [
                Customer(customer_name="Asha Kumari (DEMO)", phone="9000000001", loan_ref="DEMO-1001",
                         due_date=date(2026,10,28), outstanding_amount=2450, payment_status="upcoming",
                         branch="Demo Branch", employee="Demo Agent"),
                Customer(customer_name="Ravi Kumar (DEMO)", phone="9000000002", loan_ref="DEMO-1002",
                         due_date=date(2026,10,20), outstanding_amount=3200, payment_status="overdue",
                         branch="Demo Branch", employee="Demo Agent", follow_up_required=True),
                Customer(customer_name="Neha Devi (DEMO)", phone="9000000003", loan_ref="DEMO-1003",
                         due_date=date(2026,10,22), outstanding_amount=1800, payment_status="paid",
                         branch="Demo Branch", employee="Demo Agent"),
                Customer(customer_name="Imran Ansari (DEMO)", phone="9000000004", loan_ref="DEMO-1004",
                         due_date=date(2026,10,26), outstanding_amount=2750, payment_status="overdue",
                         branch="Demo Branch", employee="Demo Agent"),
            ]
            db.add_all(samples); db.commit()
    finally:
        db.close()
seed_data()

def customer_dict(c):
    return {"id": c.id, "customer_name": c.customer_name, "phone": c.phone,
            "loan_ref": c.loan_ref, "masked_loan_ref": ("••••" + c.loan_ref[-4:]) if len(c.loan_ref)>4 else "••••",
            "due_date": c.due_date.isoformat(), "outstanding_amount": c.outstanding_amount,
            "payment_status": c.payment_status, "branch": c.branch, "employee": c.employee,
            "follow_up_required": c.follow_up_required, "suppressed": c.suppressed}

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    if not request.session.get("user"):
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse("index.html", {"request": request, "user": request.session["user"]})

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": ""})

@app.post("/login", response_class=HTMLResponse)
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    user = authenticate(username, password)
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Login failed. Check credentials."}, status_code=401)
    request.session["user"] = user
    return RedirectResponse("/", status_code=303)

@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)

@app.get("/api/me")
def me(request: Request):
    return current_user(request)

@app.get("/api/dashboard")
def dashboard(request: Request, db: Session = Depends(get_db)):
    current_user(request)
    total = db.query(Customer).count()
    calls = db.query(CallLog).count()
    answered = db.query(CallLog).filter(CallLog.outcome.in_(["answered_ptp","paid_claimed","callback_requested","dispute","hardship","refused"])).count()
    ptp = db.query(CallLog).filter(CallLog.outcome=="answered_ptp").count()
    paid = db.query(Customer).filter(Customer.payment_status=="paid").count()
    followups = db.query(Customer).filter(or_(Customer.follow_up_required==True, Customer.suppressed==True)).count()
    failed = db.query(CallLog).filter(CallLog.outcome=="no_answer").count()
    callbacks = db.query(CallLog).filter(CallLog.outcome=="callback_requested").count()
    return {"total_customers":total, "calls_attempted":calls, "calls_answered":answered,
            "ptp_count":ptp, "payments_verified":paid, "follow_up":followups,
            "failed_calls":failed, "callback_requests":callbacks,
            "answer_rate": round(answered/calls*100,1) if calls else 0}

@app.get("/api/customers")
def customers(request: Request, q: str = "", status: str = "", branch: str = "", db: Session = Depends(get_db)):
    current_user(request)
    query = db.query(Customer)
    if q:
        like = f"%{q[:100]}%"
        query = query.filter(or_(Customer.customer_name.ilike(like), Customer.loan_ref.ilike(like), Customer.phone.ilike(like)))
    if status: query = query.filter(Customer.payment_status==status)
    if branch: query = query.filter(Customer.branch==branch)
    rows = query.order_by(Customer.due_date.asc()).limit(500).all()
    return [customer_dict(c) for c in rows]

@app.post("/api/customers")
def add_customer(request: Request, payload: dict, db: Session = Depends(get_db)):
    user = require_role(request, ["admin","agent"])
    try:
        name = str(payload.get("customer_name","")).strip()
        phone = str(payload.get("phone","")).strip()
        loan_ref = str(payload.get("loan_ref","")).strip()
        due = date.fromisoformat(str(payload.get("due_date","")))
        amount = float(payload.get("outstanding_amount",0))
        status = str(payload.get("payment_status","upcoming"))
        if not name or not phone or not loan_ref: raise ValueError("Name, phone and loan reference are required")
        if len(phone) > 30 or len(name)>120 or len(loan_ref)>80: raise ValueError("A field is too long")
        if amount < 0 or status not in {"upcoming","overdue","paid","disputed"}: raise ValueError("Invalid amount or payment status")
        c = Customer(customer_name=name, phone=phone, loan_ref=loan_ref, due_date=due,
                     outstanding_amount=amount, payment_status=status,
                     branch=str(payload.get("branch",""))[:100], employee=str(payload.get("employee",""))[:100])
        db.add(c); db.flush()
        audit(db,user,"customer_created","customer",c.id,"Customer record added")
        db.commit()
        return customer_dict(c)
    except (ValueError, TypeError) as e:
        db.rollback(); raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/customers/{customer_id}/payment")
def update_payment(customer_id: int, request: Request, payload: dict, db: Session = Depends(get_db)):
    user = require_role(request, ["admin","agent"])
    c = db.get(Customer, customer_id)
    if not c: raise HTTPException(404, "Customer not found")
    status = payload.get("payment_status")
    if status not in {"upcoming","overdue","paid","disputed"}: raise HTTPException(400, "Invalid status")
    c.payment_status = status
    if status == "paid":
        c.follow_up_required = False
        c.suppressed = True
    audit(db,user,"payment_status_updated","customer",c.id,f"Status set to {status}; verified in authorized source by employee")
    db.commit()
    return customer_dict(c)

@app.post("/api/customers/{customer_id}/call")
def simulate_call(customer_id: int, request: Request, payload: dict, db: Session = Depends(get_db)):
    user = require_role(request, ["admin","agent"])
    c = db.get(Customer, customer_id)
    if not c: raise HTTPException(404, "Customer not found")
    if c.payment_status == "paid": raise HTTPException(409, "Verified-paid records cannot be called")
    if c.suppressed: raise HTTPException(409, "This record is suppressed pending human review")
    outcome = payload.get("outcome")
    if outcome not in OUTCOMES: raise HTTPException(400, "Unknown call outcome")
    ptp_date = None; ptp_amount = None
    if outcome == "answered_ptp":
        try: ptp_date = date.fromisoformat(payload.get("ptp_date",""))
        except Exception: raise HTTPException(400, "A valid PTP date is required")
        if ptp_date < date.today(): raise HTTPException(400, "PTP date cannot be in the past")
        if payload.get("ptp_amount") not in (None,""):
            try: ptp_amount = float(payload["ptp_amount"])
            except Exception: raise HTTPException(400, "Invalid PTP amount")
            if ptp_amount < 0: raise HTTPException(400, "PTP amount cannot be negative")
    notes = str(payload.get("notes","")).strip()[:1000]
    log = CallLog(customer_id=c.id, outcome=outcome, notes=notes, ptp_date=ptp_date,
                  ptp_amount=ptp_amount, employee=user["username"], simulated=True)
    db.add(log)
    if outcome in SUPPRESS_OUTCOMES:
        c.suppressed = True; c.follow_up_required = True
    elif outcome == "callback_requested":
        c.follow_up_required = True
    elif outcome in {"answered_ptp","paid_claimed"}:
        c.follow_up_required = True
    audit(db,user,"simulated_call_logged","call",c.id,f"Outcome={outcome}; simulated=true")
    db.commit()
    return {"ok":True,"message":"Simulation logged. No phone call was placed.","outcome":outcome}

@app.post("/api/customers/import")
async def import_csv(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    user = require_role(request, ["admin","agent"])
    if not file.filename.lower().endswith(".csv"): raise HTTPException(400, "Upload a CSV file")
    raw = await file.read()
    if len(raw) > 2_000_000: raise HTTPException(413, "CSV must be smaller than 2 MB")
    try:
        text = raw.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        required = {"customer_name","phone","loan_ref","due_date","outstanding_amount","payment_status","branch","employee"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError("Missing required CSV headers")
        added = 0
        for row in reader:
            name, phone, ref = row["customer_name"].strip(), row["phone"].strip(), row["loan_ref"].strip()
            due = date.fromisoformat(row["due_date"].strip())
            amount = float(row["outstanding_amount"])
            status = row["payment_status"].strip().lower()
            if not name or not phone or not ref or amount < 0 or status not in {"upcoming","overdue","paid","disputed"}:
                raise ValueError(f"Invalid customer row near line {added+2}")
            db.add(Customer(customer_name=name[:120], phone=phone[:30], loan_ref=ref[:80], due_date=due,
                            outstanding_amount=amount, payment_status=status,
                            branch=row["branch"][:100], employee=row["employee"][:100]))
            added += 1
            if added > 5000: raise ValueError("Maximum 5,000 rows per import")
        audit(db,user,"customers_imported","customer","bulk",f"Imported {added} rows")
        db.commit()
        return {"ok":True,"imported":added}
    except Exception as e:
        db.rollback()
        raise HTTPException(400, detail=f"Import failed: {str(e)[:200]}")

@app.get("/api/export.csv")
def export_csv(request: Request, db: Session = Depends(get_db)):
    current_user(request)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["customer_id","customer_name","phone","masked_loan_ref","due_date","outstanding_amount","payment_status","branch","employee","follow_up_required","suppressed"])
    for c in db.query(Customer).order_by(Customer.id).all():
        writer.writerow([c.id,c.customer_name,c.phone,("****"+c.loan_ref[-4:]),c.due_date.isoformat(),c.outstanding_amount,c.payment_status,c.branch,c.employee,c.follow_up_required,c.suppressed])
    audit(db, request.session["user"], "customers_exported", "customer", "bulk", "CSV export")
    db.commit()
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition":"attachment; filename=loan-customers-report.csv"})

@app.get("/api/calls")
def call_logs(request: Request, db: Session = Depends(get_db)):
    current_user(request)
    rows = db.query(CallLog).order_by(CallLog.call_at.desc()).limit(200).all()
    result=[]
    for log in rows:
        c=db.get(Customer,log.customer_id)
        result.append({"id":log.id,"customer_name":c.customer_name if c else "Unknown",
                       "customer_id":log.customer_id,"call_at":log.call_at.isoformat(timespec="minutes"),
                       "outcome":log.outcome,"outcome_label":OUTCOMES.get(log.outcome,log.outcome),
                       "ptp_date":log.ptp_date.isoformat() if log.ptp_date else "",
                       "ptp_amount":log.ptp_amount,"notes":log.notes,"simulated":log.simulated})
    return result

@app.get("/api/audit")
def audit_logs(request: Request, db: Session = Depends(get_db)):
    require_role(request, ["admin"])
    rows=db.query(AuditLog).order_by(AuditLog.at.desc()).limit(100).all()
    return [{"at":x.at.isoformat(timespec="minutes"),"username":x.username,"action":x.action,
             "entity_type":x.entity_type,"entity_id":x.entity_id,"details":x.details} for x in rows]

@app.get("/api/branches")
def branches(request: Request, db: Session = Depends(get_db)):
    current_user(request)
    return [x[0] for x in db.query(Customer.branch).distinct().all() if x[0]]
