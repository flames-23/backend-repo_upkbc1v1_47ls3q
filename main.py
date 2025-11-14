import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from bson import ObjectId
import requests

from database import db, create_document, get_documents

app = FastAPI(title="Startup-Investor Matchmaking API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utility to safely cast string ids

def to_object_id(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")


# Schemas
from schemas import Startup, Investor, MatchPreference, Message, Match, Verification


@app.get("/")
def root():
    return {"message": "Matchmaking backend is running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Connected & Working"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"

    return response


# ----- Startup Endpoints -----
@app.post("/api/startups", response_model=dict)
async def create_startup(payload: Startup):
    inserted_id = create_document("startup", payload)
    return {"id": inserted_id}


@app.get("/api/startups", response_model=List[dict])
async def list_startups(industry: Optional[str] = None, stage: Optional[str] = None, q: Optional[str] = None):
    filt = {}
    if industry:
        filt["industry"] = {"$in": [industry]}
    if stage:
        filt["stage"] = stage
    if q:
        filt["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"tagline": {"$regex": q, "$options": "i"}}
        ]
    docs = get_documents("startup", filt)
    # Convert ObjectId to str
    for d in docs:
        d["_id"] = str(d["_id"]) if "_id" in d else None
    return docs


# ----- Investor Endpoints -----
@app.post("/api/investors", response_model=dict)
async def create_investor(payload: Investor):
    inserted_id = create_document("investor", payload)
    return {"id": inserted_id}


@app.get("/api/investors", response_model=List[dict])
async def list_investors(domain: Optional[str] = None, stage: Optional[str] = None, geo: Optional[str] = None):
    filt = {}
    if domain:
        filt["domains"] = {"$in": [domain]}
    if stage:
        filt["preferred_stage"] = {"$in": [stage]}
    if geo:
        filt["geography"] = geo
    docs = get_documents("investor", filt)
    for d in docs:
        d["_id"] = str(d["_id"]) if "_id" in d else None
    return docs


# ----- Matchmaking (baseline heuristic) -----
class MatchQuery(BaseModel):
    # Simple filter-based matching for MVP
    industry: Optional[List[str]] = None
    stage: Optional[str] = None
    geography: Optional[str] = None
    ticket_min: Optional[float] = None
    ticket_max: Optional[float] = None


@app.post("/api/matchmaking", response_model=List[Match])
async def get_matches(body: MatchQuery):
    startups = get_documents("startup", {})
    investors = get_documents("investor", {})

    results: List[Match] = []

    def score(si, inv) -> float:
        s = 0.0
        # Industry overlap
        if body.industry:
            overlap = len(set(si.get("industry", [])) & set(body.industry))
            s += min(0.4, 0.1 * overlap)
        # Stage
        if body.stage and body.stage == si.get("stage"):
            s += 0.2
        # Geography
        if body.geography and body.geography == inv.get("geography"):
            s += 0.1
        # Ticket
        if body.ticket_min is not None and inv.get("ticket_min") is not None and inv.get("ticket_min") <= body.ticket_min:
            s += 0.15
        if body.ticket_max is not None and inv.get("ticket_max") is not None and inv.get("ticket_max") >= body.ticket_max:
            s += 0.15
        return max(0.0, min(1.0, s))

    for s in startups:
        for i in investors:
            sc = score(s, i)
            if sc >= 0.2:
                results.append(Match(
                    a_id=str(s.get("_id")), a_type="startup",
                    b_id=str(i.get("_id")), b_type="investor",
                    score=round(sc, 2),
                    rationale="Heuristic overlap on filters"
                ))

    # Sort by score desc and cap
    results.sort(key=lambda m: m.score, reverse=True)
    return results[:50]


# ----- Chat (MVP) -----
@app.post("/api/chat", response_model=dict)
async def send_message(msg: Message):
    message_id = create_document("message", msg)
    return {"id": message_id}


@app.get("/api/chat", response_model=List[dict])
async def get_messages(a: str, b: str):
    # fetch conversation between a and b
    filt = {"$or": [
        {"sender_id": a, "receiver_id": b},
        {"sender_id": b, "receiver_id": a},
    ]}
    docs = get_documents("message", filt)
    for d in docs:
        d["_id"] = str(d["_id"]) if "_id" in d else None
    return docs


# ----- Verification -----
@app.post("/api/verify", response_model=dict)
async def submit_verification(v: Verification):
    verification_id = create_document("verification", v)
    return {"id": verification_id}


# ----- Google Auth (ID token verify) -----
class GoogleAuthRequest(BaseModel):
    id_token: str


@app.post("/api/auth/google")
async def auth_google(body: GoogleAuthRequest):
    try:
        # Verify with Google's tokeninfo endpoint
        tokeninfo_url = "https://oauth2.googleapis.com/tokeninfo"
        r = requests.get(tokeninfo_url, params={"id_token": body.id_token}, timeout=10)
        if r.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid Google token")
        info = r.json()
        aud = info.get("aud")
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        if client_id and aud != client_id:
            raise HTTPException(status_code=401, detail="Token audience mismatch")
        # Minimal profile payload
        profile = {
            "sub": info.get("sub"),
            "email": info.get("email"),
            "email_verified": info.get("email_verified"),
            "name": info.get("name"),
            "picture": info.get("picture"),
            "given_name": info.get("given_name"),
            "family_name": info.get("family_name"),
        }
        # Log activity
        try:
            create_document("activitylog", {
                "user_id": profile.get("sub") or "unknown",
                "user_type": "startup",  # placeholder until role chosen
                "action": "google_sign_in",
                "meta": {"email": profile.get("email")}
            })
        except Exception:
            pass
        return {"ok": True, "profile": profile}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:200])


# ----- Schema Introspection (for database viewer tooling) -----
@app.get("/schema")
async def get_schema():
    from schemas import Startup, Investor, MatchPreference, Match, Message, ActivityLog, Verification
    return {
        "schemas": [
            "startup", "investor", "matchpreference", "match", "message", "activitylog", "verification"
        ]
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
