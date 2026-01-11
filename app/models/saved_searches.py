# app/models/saved_searches.py
"""SavedSearch model - 100% fidelity to database schema."""

from sqlalchemy import Column, BigInteger, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, SoftDeleteMixin


class SavedSearch(Base, TimestampMixin, SoftDeleteMixin):
    """
    Saved search model for user property search preferences.
    Primary Key: search_id (bigint GENERATED ALWAYS AS IDENTITY)
    """
    __tablename__ = "saved_searches"

    search_id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=True)
    search_params = Column(JSONB, nullable=False)
    name = Column(String, nullable=True)

    user = relationship("User", back_populates="saved_searches")

    def __repr__(self):
        return f"<SavedSearch(search_id={self.search_id}, name={self.name})>"