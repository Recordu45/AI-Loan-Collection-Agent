from sqlalchemy import String, Integer, Float, Date, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, date
from app.db import Base

class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_name: Mapped[str] = mapped_column(String(120), index=True)
    phone: Mapped[str] = mapped_column(String(30))
    loan_ref: Mapped[str] = mapped_column(String(80), index=True)
    due_date: Mapped[date] = mapped_column(Date)
    outstanding_amount: Mapped[float] = mapped_column(Float, default=0)
    payment_status: Mapped[str] = mapped_column(String(20), default="upcoming", index=True)
    branch: Mapped[str] = mapped_column(String(100), default="")
    employee: Mapped[str] = mapped_column(String(100), default="")
    follow_up_required: Mapped[bool] = mapped_column(default=False)
    suppressed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class CallLog(Base):
    __tablename__ = "call_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(Integer, index=True)
    call_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    outcome: Mapped[str] = mapped_column(String(40), index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    ptp_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    ptp_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    employee: Mapped[str] = mapped_column(String(100), default="admin")
    simulated: Mapped[bool] = mapped_column(default=True)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    username: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str] = mapped_column(String(50))
    details: Mapped[str] = mapped_column(Text, default="")
