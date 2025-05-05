from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    TIMESTAMP,
    Boolean,
    JSON,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from api.database.session import Base
from api.core.encryption import EncryptedType

# Re-defining tables from init_schema.sql using SQLAlchemy ORM


class Company(Base):
    __tablename__ = "companies"
    company_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # payment_info = Column(JSONB) # Add later
    offices = relationship("Office", back_populates="company")


class Office(Base):
    __tablename__ = "offices"
    office_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(
        Integer, ForeignKey("companies.company_id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(255), nullable=False)
    address = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    company = relationship("Company", back_populates="offices")
    users = relationship("User", back_populates="office")
    branding = relationship("Branding", back_populates="office", uselist=False)


class Role(Base):
    __tablename__ = "roles"
    role_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    users = relationship("User", back_populates="role")


class User(Base):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True, index=True)
    office_id = Column(Integer, ForeignKey("offices.office_id", ondelete="SET NULL"))
    role_id = Column(Integer, ForeignKey("roles.role_id"), nullable=False)
    name = Column(EncryptedType(String(255)), nullable=False)
    email = Column(EncryptedType(String(255)), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    join_code = Column(String(10), unique=True, index=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    office = relationship("Office", back_populates="users")
    role = relationship("Role", back_populates="users")
    # Relationships for TherapyPlans, PlanAssignments, Progress if needed
    therapy_plans_created = relationship("TherapyPlan", back_populates="creator")
    assignments_given = relationship(
        "PlanAssignment",
        foreign_keys="[PlanAssignment.assigned_by_id]",
        back_populates="assigner",
    )
    assignments_received = relationship(
        "PlanAssignment",
        foreign_keys="[PlanAssignment.patient_id]",
        back_populates="patient",
    )


class TherapyPlan(Base):
    __tablename__ = "therapyplans"
    plan_id = Column(Integer, primary_key=True, index=True)
    chiropractor_id = Column(
        Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    title = Column(EncryptedType(String(255)), nullable=False)
    description = Column(EncryptedType(Text))
    version = Column(Integer, default=1)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    creator = relationship("User", back_populates="therapy_plans_created")
    exercises = relationship("PlanExercise", back_populates="plan")
    assignments = relationship("PlanAssignment", back_populates="plan")


class PlanExercise(Base):
    __tablename__ = "planexercises"
    plan_exercise_id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(
        Integer, ForeignKey("therapyplans.plan_id", ondelete="CASCADE"), nullable=False
    )
    title = Column(EncryptedType(String(255)), nullable=False)
    instructions = Column(EncryptedType(Text))
    sequence_order = Column(Integer, nullable=False)
    image_url = Column(String(1024))
    video_url = Column(String(1024))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    plan = relationship("TherapyPlan", back_populates="exercises")
    progress_entries = relationship("Progress", back_populates="exercise")


class PlanAssignment(Base):
    __tablename__ = "planassignments"
    assignment_id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(
        Integer, ForeignKey("therapyplans.plan_id", ondelete="CASCADE"), nullable=False
    )
    patient_id = Column(
        Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    assigned_by_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"))
    assigned_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    start_date = Column(TIMESTAMP(timezone=True))
    end_date = Column(TIMESTAMP(timezone=True))
    plan = relationship("TherapyPlan", back_populates="assignments")
    patient = relationship(
        "User", foreign_keys=[patient_id], back_populates="assignments_received"
    )
    assigner = relationship(
        "User", foreign_keys=[assigned_by_id], back_populates="assignments_given"
    )
    progress = relationship("Progress", back_populates="assignment")


class Progress(Base):
    __tablename__ = "progress"
    progress_id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(
        Integer,
        ForeignKey("planassignments.assignment_id", ondelete="CASCADE"),
        nullable=False,
    )
    plan_exercise_id = Column(
        Integer,
        ForeignKey("planexercises.plan_exercise_id", ondelete="CASCADE"),
        nullable=False,
    )
    completed_at = Column(TIMESTAMP(timezone=True))
    notes = Column(EncryptedType(Text))
    assignment = relationship("PlanAssignment", back_populates="progress")
    exercise = relationship("PlanExercise", back_populates="progress_entries")


class Branding(Base):
    __tablename__ = "branding"
    branding_id = Column(Integer, primary_key=True, index=True)
    office_id = Column(
        Integer,
        ForeignKey("offices.office_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    logo_url = Column(String(1024))
    colors = Column(JSON)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    office = relationship("Office", back_populates="branding")
