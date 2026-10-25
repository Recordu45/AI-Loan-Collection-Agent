# AI Loan Collection Agent — Dashboard MVP

A mobile-friendly, local-first dashboard for managing authorized loan reminder records, call outcomes, Promise-to-Pay (PTP) commitments, and audit logs.

**This first version does not place real phone calls.** It includes a safe simulated-call workflow and a separate telephony adapter boundary. Real outbound calling must only be enabled after the lender approves the provider, caller identity, customer consent/notice process, calling hours, frequency limits, opt-out handling, and applicable Indian telecom/RBI/data-protection requirements. Do not put real customer data into the demo.

## Features
- FastAPI + SQLite backend; responsive HTML/CSS/JavaScript dashboard.
- Login with role-based access (`admin`, `agent`, `viewer`).
- Fictional sample customers; search and filter by status.
- Add customer, update payment status, import CSV, export CSV.
- Simulated call outcomes and PTP capture.
- Dashboard counts, call attempts, answered calls, PTPs, verified payments, callbacks/follow-ups.
- Audit log for significant changes.
- Sensitive account references masked in the UI.
- `.env` configuration; no real secrets included.

## Quick start (Android-friendly)
You can manage the repository in GitHub from a mobile browser/app. To run the app, use a Python-capable host such as Render/Railway (paid/free-tier availability changes) or a local Python environment. GitHub Pages alone cannot run this Python backend.

1. Upload the repository files to GitHub.
2. On a Python host, set the start command to:
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Set environment variables:
   - `APP_SECRET_KEY` to a long random secret
   - `ADMIN_USERNAME` to your chosen username
   - `ADMIN_PASSWORD` to a strong password
   - `DATABASE_URL` optional; default is local SQLite
   - `SEED_DEMO_DATA=true` only for a demo instance
4. Open the deployed app URL and log in with the credentials you configured.

For local development:
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux/Termux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```
Default demo credentials only apply when no environment variables are set: `admin` / `ChangeMe123!`. Change these immediately and never use the default on a public deployment.

## CSV import format
Required headers: `customer_name,phone,loan_ref,due_date,outstanding_amount,payment_status,branch,employee`
- `due_date`: `YYYY-MM-DD`
- `outstanding_amount`: numeric amount in INR
- `payment_status`: `upcoming`, `overdue`, `paid`, or `disputed`
- Use authorized, minimum-necessary records only. Demo data is fictional.

## Safe call workflow
Click **Simulate call** to record a test outcome. This does not dial a number, send an SMS, or contact a customer. Outcomes include `answered_ptp`, `paid_claimed`, `callback_requested`, `no_answer`, `wrong_number`, `dispute`, `hardship`, and `refused`.
- `paid_claimed` records the customer’s claim; it does **not** mark the account paid. Verify payment in the lender's authorized source first, then use **Mark verified paid**.
- Wrong-number, dispute, hardship, objection/refusal outcomes are flagged for human review and suppress further simulated reminder attempts until reviewed.
- PTP dates are stored as commitments, not guarantees.

## Production hardening checklist
Before production: use HTTPS; configure a persistent database; use a secret manager; add organization-specific SSO/MFA; configure backups/retention; encrypt storage and backups; obtain legal/compliance approval; apply approved call schedules and contact-frequency rules; add employee/branch data scoping; establish incident response and access review; conduct security testing. This starter app is not a compliance certification.

## Telephony integration
`app/telephony.py` provides a safe interface that refuses real calls unless explicitly configured. The MVP's dashboard uses simulation only. To connect a provider, implement and test the provider adapter against its official API, use approved caller IDs and consent/notice workflows, validate provider webhooks, and obtain compliance sign-off. Provider credentials and per-minute charges are external requirements. Do not use personal SIM automation or bypass carrier controls.
