from datetime import datetime, timezone
import uuid
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models.base import Base
from src.models.tenant import Tenant

class RequestLog(Base):
    __tablename__ = "request_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String, ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    
    # Model Usage
    model_name: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=True) # e.g. openai, anthropic
    
    # Telemetry
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Routing & RAG Metadata
    route_used: Mapped[str] = mapped_column(String, nullable=True) # e.g. A/B variant
    rag_metadata: Mapped[dict] = mapped_column(JSON, nullable=True)
    
    # Status
    status_code: Mapped[int] = mapped_column(Integer, default=200)
    error_message: Mapped[str] = mapped_column(String, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )
    
    tenant = relationship(Tenant)
