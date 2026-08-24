from datetime import datetime, timezone
import uuid
from sqlalchemy import String, Boolean, Float, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from src.models.base import Base

class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    api_key: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    
    # Budgeting & Billing
    budget_limit_usd: Mapped[float] = mapped_column(Float, default=100.0)
    current_spend_usd: Mapped[float] = mapped_column(Float, default=0.0)
    
    # RBAC & Status
    tier: Mapped[str] = mapped_column(String, default="free")  # e.g., free, pro, enterprise
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )
