import time
import uuid
from sqlalchemy import String, Float, Integer, ForeignKey, JSON, UniqueConstraint, Index, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

def uid(): return uuid.uuid4().hex

class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    password: Mapped[str] = mapped_column(String(255))
    firebase_uid: Mapped[str | None] = mapped_column(String(128),nullable=True,unique=True,index=True)
    role: Mapped[str] = mapped_column(String(20), default='customer', server_default='customer')
    created_at: Mapped[float] = mapped_column(Float, default=time.time)

class LoginSession(Base):
    __tablename__ = 'sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    expires_at: Mapped[float] = mapped_column(Float, index=True)

class RateBucket(Base):
    __tablename__ = 'rate_buckets'
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    hits: Mapped[int] = mapped_column(Integer, default=1)
    expires_at: Mapped[float] = mapped_column(Float, index=True)

class Project(Base):
    __tablename__ = 'projects'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    title: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(20), default='textile', server_default='textile')
    status: Mapped[str] = mapped_column(String(25), default='uploaded', index=True)
    image_key: Mapped[str] = mapped_column(String(255))
    image_hash: Mapped[str] = mapped_column(String(64))
    image_phash: Mapped[str] = mapped_column(String(64))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    tutorial_steps: Mapped[list] = mapped_column(JSON, default=list, server_default='[]')
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    preview: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    preview_revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    completed_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    updated_at: Mapped[float] = mapped_column(Float, default=time.time)

class Job(Base):
    __tablename__ = 'jobs'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))
    state: Mapped[str] = mapped_column(String(20), default='queued')
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    run_after: Mapped[float] = mapped_column(Float, default=time.time)
    lease_until: Mapped[float] = mapped_column(Float, default=0)
    lock_token: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    __table_args__ = (UniqueConstraint('project_id', 'revision', 'kind'), Index('ix_job_claim', 'state', 'run_after', 'lease_until'), Index('ix_job_claim_kind','kind','state','run_after','lease_until'))

class Completion(Base):
    __tablename__ = 'completions'
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    image_key: Mapped[str] = mapped_column(String(255))
    image_hash: Mapped[str] = mapped_column(String(64), unique=True)
    image_phash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[float] = mapped_column(Float, default=time.time)

class WorkerHeartbeat(Base):
    __tablename__ = 'worker_heartbeats'
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    updated_at: Mapped[float] = mapped_column(Float)
    model: Mapped[str] = mapped_column(String(30))
    queues: Mapped[list] = mapped_column(JSON, default=lambda: ["analyze","compile","preview"], server_default='["analyze","compile","preview"]')


class Maker(Base):
    __tablename__='makers'
    __table_args__=(Index('ix_makers_public_location','status','accepting_work','consent_to_list','latitude','longitude'),)
    id: Mapped[str]=mapped_column(String(32),primary_key=True,default=uid)
    user_id: Mapped[str]=mapped_column(ForeignKey('users.id'),unique=True)
    name: Mapped[str]=mapped_column(String(100))
    about: Mapped[str]=mapped_column(String(1000))
    city: Mapped[str]=mapped_column(String(80))
    latitude: Mapped[float | None]=mapped_column(Float,nullable=True)
    longitude: Mapped[float | None]=mapped_column(Float,nullable=True)
    categories: Mapped[list]=mapped_column(JSON)
    community: Mapped[str]=mapped_column(String(30),default='independent')
    address: Mapped[dict]=mapped_column(JSON)
    status: Mapped[str]=mapped_column(String(20),default='pending')
    accepting_work: Mapped[bool]=mapped_column(Boolean,default=True)
    consent_to_list: Mapped[bool]=mapped_column(Boolean,default=True)
    created_at: Mapped[float]=mapped_column(Float,default=time.time)

class RepairService(Base):
    __tablename__='repair_services'
    id: Mapped[str]=mapped_column(String(32),primary_key=True,default=uid)
    user_id: Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    project_id: Mapped[str]=mapped_column(ForeignKey('projects.id'),index=True)
    maker_id: Mapped[str | None]=mapped_column(ForeignKey('makers.id'),nullable=True,index=True)
    status: Mapped[str]=mapped_column(String(30),default='awaiting_match',index=True)
    brief: Mapped[str]=mapped_column(String(1000))
    consent_to_share: Mapped[bool]=mapped_column(Boolean)
    design_snapshot: Mapped[dict | None]=mapped_column(JSON,nullable=True)
    replacement_minor: Mapped[int | None]=mapped_column(Integer,nullable=True)
    budget_minor: Mapped[int | None]=mapped_column(Integer,nullable=True)
    return_address: Mapped[dict | None]=mapped_column(JSON,nullable=True)
    payment_status: Mapped[str]=mapped_column(String(20),default='not_requested')
    payment_reference: Mapped[str | None]=mapped_column(String(120),nullable=True)
    created_at: Mapped[float]=mapped_column(Float,default=time.time)
    updated_at: Mapped[float]=mapped_column(Float,default=time.time)

class ServiceQuote(Base):
    __tablename__='service_quotes'
    id: Mapped[str]=mapped_column(String(32),primary_key=True,default=uid)
    service_id: Mapped[str]=mapped_column(ForeignKey('repair_services.id'),unique=True)
    maker_id: Mapped[str]=mapped_column(ForeignKey('makers.id'))
    labour_minor: Mapped[int]=mapped_column(Integer)
    materials_minor: Mapped[int]=mapped_column(Integer)
    outbound_minor: Mapped[int]=mapped_column(Integer,default=0)
    return_minor: Mapped[int]=mapped_column(Integer,default=0)
    fee_minor: Mapped[int]=mapped_column(Integer,default=0)
    total_minor: Mapped[int]=mapped_column(Integer,default=0)
    days: Mapped[int]=mapped_column(Integer)
    notes: Mapped[str]=mapped_column(String(1000))
    version: Mapped[int]=mapped_column(Integer,default=1)
    accepted_at: Mapped[float | None]=mapped_column(Float,nullable=True)
    expires_at: Mapped[float | None]=mapped_column(Float,nullable=True)

class Shipment(Base):
    __tablename__='shipments'
    id: Mapped[str]=mapped_column(String(32),primary_key=True,default=uid)
    service_id: Mapped[str]=mapped_column(ForeignKey('repair_services.id'),index=True)
    leg: Mapped[str]=mapped_column(String(10))
    status: Mapped[str]=mapped_column(String(20),default='pending')
    courier: Mapped[str | None]=mapped_column(String(80),nullable=True)
    tracking: Mapped[str | None]=mapped_column(String(120),nullable=True)
    tracking_url: Mapped[str | None]=mapped_column(String(500),nullable=True)
    pickup_at: Mapped[str | None]=mapped_column(String(50),nullable=True)
    __table_args__=(UniqueConstraint('service_id','leg'),)

class MakerEarning(Base):
    __tablename__='maker_earnings'
    id: Mapped[str]=mapped_column(String(32),primary_key=True,default=uid)
    service_id: Mapped[str]=mapped_column(ForeignKey('repair_services.id'),unique=True)
    maker_id: Mapped[str]=mapped_column(ForeignKey('makers.id'),index=True)
    amount_minor: Mapped[int]=mapped_column(Integer)
    status: Mapped[str]=mapped_column(String(30),default='awaiting_delivery')
    payout_reference: Mapped[str | None]=mapped_column(String(120),nullable=True)
    paid_at: Mapped[float | None]=mapped_column(Float,nullable=True)

class ServiceEvent(Base):
    __tablename__='service_events'
    id: Mapped[str]=mapped_column(String(32),primary_key=True,default=uid)
    service_id: Mapped[str]=mapped_column(ForeignKey('repair_services.id'),index=True)
    actor_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    message: Mapped[str]=mapped_column(String(300))
    created_at: Mapped[float]=mapped_column(Float,default=time.time)

class RepairGeneration(Base):
    __tablename__='repair_generations'
    __table_args__=(UniqueConstraint('project_id','version'),UniqueConstraint('project_id','request_key'),Index('ix_generation_user_created','user_id','created_at'))
    id: Mapped[str]=mapped_column(String(32),primary_key=True,default=uid)
    project_id: Mapped[str]=mapped_column(ForeignKey('projects.id'),index=True)
    user_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    version: Mapped[int]=mapped_column(Integer)
    source_revision: Mapped[int]=mapped_column(Integer)
    request_key: Mapped[str | None]=mapped_column(String(36),nullable=True)
    requested_style: Mapped[str | None]=mapped_column(String(30),nullable=True)
    state: Mapped[str]=mapped_column(String(20),default='queued',index=True)
    stage: Mapped[str]=mapped_column(String(30),default='design')
    design: Mapped[dict | None]=mapped_column(JSON,nullable=True)
    image_key: Mapped[str | None]=mapped_column(String(255),nullable=True)
    error: Mapped[str | None]=mapped_column(String(300),nullable=True)
    created_at: Mapped[float]=mapped_column(Float,default=time.time)
    updated_at: Mapped[float]=mapped_column(Float,default=time.time)

class FirebaseOutbox(Base):
    __tablename__='firebase_outbox'
    key: Mapped[str]=mapped_column(String(200),primary_key=True)
    collection: Mapped[str]=mapped_column(String(80))
    document_id: Mapped[str]=mapped_column(String(128))
    payload: Mapped[dict | None]=mapped_column(JSON,nullable=True)
    payload_hash: Mapped[str]=mapped_column(String(64))
    version: Mapped[int]=mapped_column(Integer,default=1)
    synced_version: Mapped[int]=mapped_column(Integer,default=0)
    pending: Mapped[bool]=mapped_column(Boolean,default=True)
    attempts: Mapped[int]=mapped_column(Integer,default=0)
    next_attempt: Mapped[float]=mapped_column(Float,default=0)
    lease_until: Mapped[float]=mapped_column(Float,default=0)
    lock_token: Mapped[str | None]=mapped_column(String(32),nullable=True)
    last_error: Mapped[str | None]=mapped_column(String(200),nullable=True)
    synced_at: Mapped[float | None]=mapped_column(Float,nullable=True)
    __table_args__=(Index('ix_firebase_outbox_pending','pending','next_attempt','lease_until'),)
