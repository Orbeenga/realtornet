# app/models/reviews.py
"""Review model - 100% fidelity to database schema."""

from sqlalchemy import Column, BigInteger, Integer, ForeignKey, Text, CheckConstraint, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base, AuditMixin, SoftDeleteMixin


class Review(Base, AuditMixin, SoftDeleteMixin):  # Add AuditMixin
    """
    Review model for properties and agents.
    Primary Key: review_id (bigint GENERATED ALWAYS AS IDENTITY)
    """
    __tablename__ = "reviews"

    review_id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=True)
    property_id = Column(BigInteger, ForeignKey("properties.property_id"), nullable=True)
    agent_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=True)
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    # Remove created_at/updated_at lines - inherited from mixins

    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="reviews_rating_check"),
    )

    user = relationship("User", back_populates="reviews_given", foreign_keys=[user_id])
    property = relationship("Property", back_populates="reviews")
    agent = relationship("User", back_populates="reviews_received", foreign_keys=[agent_id])

    def __repr__(self):
        return f"<Review(review_id={self.review_id}, rating={self.rating})>"