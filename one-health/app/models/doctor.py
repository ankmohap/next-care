from sqlalchemy import Column, String, func
import datetime

from app.db.base_class import Base
from sqlalchemy.dialects.mysql import CHAR, TIMESTAMP
from sqlalchemy.orm import relationship
from uuid import uuid4


class Doctor(Base):
    """
       Database Model for an application Doctor cases
       """
    __tablename__ = "Doctor"
    case_id = Column(CHAR(36), primary_key=True, index=True, default=uuid4)
    doctor_user_id = Column(String(255), index=True)
    patient_user_id = Column(String(255), index=True)
    insights = Column(String(255), index=True)
    status = Column(String(50), index=True)
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now()
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

