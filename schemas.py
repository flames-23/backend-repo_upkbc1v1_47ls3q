"""
Database Schemas for the Startup-Investor Matchmaking Platform

Each Pydantic model maps to a MongoDB collection. The collection name is the
lowercase of the class name (e.g., Startup -> "startup").
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, EmailStr

# --- Core User Types ---
class Startup(BaseModel):
    name: str = Field(..., description="Company name")
    tagline: Optional[str] = Field(None, description="One-line description")
    website: Optional[str] = Field(None)
    industry: List[str] = Field(default_factory=list, description="Industries/domains")
    stage: Literal["idea","MVP","pre-seed","seed","series-a","series-b"] = Field("pre-seed")
    geography: Optional[str] = Field(None, description="Primary location or market")
    problem: Optional[str] = None
    solution: Optional[str] = None
    traction: Optional[str] = None
    team: Optional[str] = None
    funding_needs_min: Optional[float] = Field(None, ge=0)
    funding_needs_max: Optional[float] = Field(None, ge=0)
    valuation: Optional[float] = Field(None, ge=0)
    revenue: Optional[float] = Field(None, ge=0)
    pitch_deck_url: Optional[str] = None
    media_urls: List[str] = Field(default_factory=list)
    founder_name: Optional[str] = None
    founder_email: Optional[EmailStr] = None
    verified_founder: bool = Field(default=False)

class Investor(BaseModel):
    name: str = Field(..., description="Investor or fund name")
    email: Optional[EmailStr] = None
    thesis: Optional[str] = None
    domains: List[str] = Field(default_factory=list)
    preferred_stage: List[Literal["idea","MVP","pre-seed","seed","series-a","series-b"]] = Field(default_factory=lambda: ["pre-seed","seed"]) 
    geography: Optional[str] = None
    ticket_min: Optional[float] = Field(None, ge=0)
    ticket_max: Optional[float] = Field(None, ge=0)
    portfolio_highlights: Optional[str] = None
    exits: Optional[str] = None
    verified_investor: bool = Field(default=False)

# --- Verification ---
class Verification(BaseModel):
    user_id: str
    user_type: Literal["startup","investor"]
    kyc_provider: Optional[str] = None
    cin: Optional[str] = None
    pan: Optional[str] = None
    gst: Optional[str] = None
    sebi_reg: Optional[str] = None
    status: Literal["pending","approved","rejected"] = Field("pending")
    notes: Optional[str] = None

# --- Matchmaking ---
class MatchPreference(BaseModel):
    user_type: Literal["startup","investor"]
    id: Optional[str] = Field(None, description="If provided, compute matches for this entity")
    industry: Optional[List[str]] = None
    stage: Optional[List[str]] = None
    geography: Optional[str] = None
    ticket_min: Optional[float] = None
    ticket_max: Optional[float] = None

class Match(BaseModel):
    a_id: str
    a_type: Literal["startup","investor"]
    b_id: str
    b_type: Literal["startup","investor"]
    score: float = Field(0.0, ge=0, le=1)
    rationale: Optional[str] = None

# --- Chat ---
class Message(BaseModel):
    sender_id: str
    receiver_id: str
    body: str
    read: bool = False

# --- Minimal Analytics ---
class ActivityLog(BaseModel):
    user_id: str
    user_type: Literal["startup","investor"]
    action: str
    meta: Optional[dict] = None
