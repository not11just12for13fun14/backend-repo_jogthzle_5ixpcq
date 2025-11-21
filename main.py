import os
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from bson import ObjectId
from hashlib import sha256
import secrets

from database import db, create_document, get_documents
from schemas import User, Session, AnalysisRequest, WatchlistItem, ChatMessage

app = FastAPI(title="Wolf of Wall Street.site API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utilities

def hash_password(password: str) -> str:
    # Lightweight hash for demo; in production, use bcrypt/argon2
    return sha256(password.encode()).hexdigest()


def require_auth(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1]
    session = db["session"].find_one({"token": token})
    if not session:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db["user"].find_one({"_id": ObjectId(session["user_id"])})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return {"user": user, "session": session}


# Models for auth requests
class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@app.get("/")
def read_root():
    return {"message": "Wolf of Wall Street.site Backend Running"}


@app.post("/auth/signup")
def signup(payload: SignupRequest):
    existing = db["user"].find_one({"email": payload.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    user_id = create_document("user", user)
    token = secrets.token_urlsafe(32)
    db["session"].insert_one({
        "user_id": user_id,
        "token": token,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7)
    })
    return {"token": token, "user": {"id": user_id, "name": user.name, "email": user.email}}


@app.post("/auth/login")
def login(payload: LoginRequest):
    user = db["user"].find_one({"email": payload.email})
    if not user or user.get("hashed_password") != hash_password(payload.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = secrets.token_urlsafe(32)
    db["session"].insert_one({
        "user_id": str(user["_id"]),
        "token": token,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7)
    })
    return {"token": token, "user": {"id": str(user["_id"]), "name": user["name"], "email": user["email"]}}


@app.get("/me")
def me(ctx=Depends(require_auth)):
    u = ctx["user"]
    return {"id": str(u["_id"]), "name": u.get("name"), "email": u.get("email"), "plan": u.get("plan", "free")}


@app.post("/analysis")
def analyze(req: AnalysisRequest, ctx=Depends(require_auth)):
    # Placeholder analysis computation
    import math
    import random
    prices = [100 + math.sin(i/3) * 5 + random.uniform(-1,1) for i in range(60)]
    sma = sum(prices[-req.lookback:]) / req.lookback if len(prices) >= req.lookback else sum(prices)/len(prices)
    signal = "buy" if prices[-1] > sma else "sell"
    return {
        "symbol": req.symbol.upper(),
        "timeframe": req.timeframe,
        "strategy": req.strategy,
        "sma": round(sma, 2),
        "last": round(prices[-1], 2),
        "signal": signal,
        "confidence": 0.62 if signal == "buy" else 0.55
    }


@app.get("/watchlist")
def get_watchlist(ctx=Depends(require_auth)):
    user_id = str(ctx["user"]["_id"])
    items = list(db["watchlistitem"].find({"user_id": user_id}))
    return [{"id": str(i["_id"]), "symbol": i["symbol"], "note": i.get("note") } for i in items]


class WatchlistCreate(BaseModel):
    symbol: str
    note: Optional[str] = None


@app.post("/watchlist")
def add_watchlist(item: WatchlistCreate, ctx=Depends(require_auth)):
    doc = WatchlistItem(user_id=str(ctx["user"]["_id"]), symbol=item.symbol.upper(), note=item.note, created_at=datetime.now(timezone.utc))
    _id = create_document("watchlistitem", doc)
    return {"id": _id, "symbol": doc.symbol, "note": doc.note}


@app.delete("/watchlist/{item_id}")
def delete_watchlist(item_id: str, ctx=Depends(require_auth)):
    res = db["watchlistitem"].delete_one({"_id": ObjectId(item_id), "user_id": str(ctx["user"]["_id"])})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"ok": True}


class ChatPayload(BaseModel):
    message: str


@app.post("/chat")
def chat(payload: ChatPayload, ctx=Depends(require_auth)):
    user_id = str(ctx["user"]["_id"])
    # Store user message
    create_document("chatmessage", ChatMessage(user_id=user_id, role="user", content=payload.message, created_at=datetime.now(timezone.utc)))

    # Simple rule-based reply for demo
    text = payload.message.lower()
    reply = "I'm your trading copilot. Ask me about a symbol like AAPL or BTC."
    if any(sym in text for sym in ["buy", "sell", "entry", "exit"]):
        reply = "General guidance only: manage risk, set stops, and size positions responsibly."
    for sym in ["aapl", "tsla", "msft", "btc", "eth"]:
        if sym in text:
            reply = f"Quick take on {sym.upper()}: trend is up on daily, wait for pullback to 20EMA for better risk/reward."
            break

    create_document("chatmessage", ChatMessage(user_id=user_id, role="assistant", content=reply, created_at=datetime.now(timezone.utc)))
    return {"reply": reply}


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
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = getattr(db, 'name', '✅ Connected')
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
