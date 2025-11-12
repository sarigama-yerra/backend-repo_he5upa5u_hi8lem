import os
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import db, create_document, get_documents

app = FastAPI(title="CryptoSleuth API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TraceRequest(BaseModel):
    address: str
    chain: str = "ethereum"


@app.get("/")
def read_root():
    return {"name": "CryptoSleuth API", "status": "ok"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": [],
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = (
                os.getenv("DATABASE_NAME") or (db.name if hasattr(db, "name") else None)
            )
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
                response["connection_status"] = "Connected"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


# --- Heuristic Risk Scoring ---
RISK_RULES = [
    {"id": "darknet_link", "label": "Direct link to darknet market", "impact": 70},
    {"id": "mixer_use", "label": "Used mixing service", "impact": 50},
    {"id": "hack_proceeds", "label": "Received from hack/scam", "impact": 90},
    {"id": "large_tx", "label": "Large sudden transfer", "impact": 30},
    {"id": "structuring", "label": "Frequent small transactions", "impact": 40},
    {"id": "hodl", "label": "Long-held funds", "impact": -10},
    {"id": "kyc_exchange", "label": "From known exchange", "impact": -20},
]


def clamp(v: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, v))


def compute_risk(flags: List[str]) -> int:
    score = 0
    for f in flags:
        rule = next((r for r in RISK_RULES if r["id"] == f), None)
        if rule:
            score += rule["impact"]
    return clamp(score)


# --- API Endpoints ---
@app.post("/api/trace")
async def trace_wallet(payload: TraceRequest):
    """
    MVP tracer endpoint.
    For the hackathon MVP, we simulate a small set of transactions and flags
    and compute risk according to the provided heuristic table.

    Later, this can be extended to call Alchemy/Etherscan/Blockstream etc.
    """
    address = payload.address.strip()
    if not address:
        raise HTTPException(status_code=400, detail="Address is required")

    # Simulated flags based on simple patterns for demo
    flags = []
    addr_lower = address.lower()
    if addr_lower.endswith("bad") or addr_lower.startswith("0xdead"):
        flags.append("hack_proceeds")
    if "mix" in addr_lower or "tornado" in addr_lower:
        flags.append("mixer_use")
    if addr_lower.startswith("bc1dark") or "hydra" in addr_lower:
        flags.append("darknet_link")

    # Example: large or structuring heuristic (random-ish demo based on length)
    if len(address) % 7 == 0:
        flags.append("large_tx")
    if len(address) % 5 == 0:
        flags.append("structuring")

    # Positive signals
    if "coinbase" in addr_lower or "binance" in addr_lower:
        flags.append("kyc_exchange")
    if len(address) % 11 == 0:
        flags.append("hodl")

    risk = compute_risk(flags)

    # Demo transactions payload
    now = datetime.utcnow()
    txs = [
        {
            "txid": f"demo-{i}-{address[:6]}",
            "from_address": address if i % 2 == 0 else f"peer-{i}",
            "to_address": f"peer-{i}" if i % 2 == 0 else address,
            "amount": round(0.5 * (i + 1), 4),
            "symbol": "ETH",
            "timestamp": now.isoformat() + "Z",
            "chain": payload.chain,
            "flags": [f for f in flags if (i + len(address)) % 2 == 0][:2],
        }
        for i in range(6)
    ]

    # Persist a minimal record in the database for later reporting
    try:
        create_document("wallet", {
            "address": address,
            "chain": payload.chain,
            "risk_score": risk,
            "last_scored_at": now,
        })
    except Exception:
        # Database might not be configured; continue without failing the demo
        pass

    return {
        "address": address,
        "chain": payload.chain,
        "risk_score": risk,
        "flags": flags,
        "transactions": txs,
    }


class ReportRequest(BaseModel):
    address: str
    chain: str = "ethereum"


@app.post("/api/report")
async def generate_report(payload: ReportRequest):
    """Generate a simple LE report based on most recent scoring for the address."""
    address = payload.address.strip()
    if not address:
        raise HTTPException(status_code=400, detail="Address is required")

    docs = []
    try:
        docs = get_documents("wallet", {"address": address}, limit=1)
    except Exception:
        pass

    if docs:
        latest = docs[0]
        score = int(latest.get("risk_score", 0))
    else:
        # If not found, compute quickly via trace
        resp = await trace_wallet(TraceRequest(address=address, chain=payload.chain))
        score = resp["risk_score"]

    classification = (
        "Safe" if score <= 20 else
        "Moderate Risk" if score <= 50 else
        "High Risk" if score <= 70 else
        "Extreme Risk"
    )

    summary = (
        f"Wallet {address} on {payload.chain} is classified as {classification} with score {score}. "
        "This automated report is generated for investigative triage and is not a legal determination."
    )

    report = {
        "address": address,
        "chain": payload.chain,
        "summary": summary,
        "risk_score": score,
        "details": {
            "recommendation": (
                "No restrictions" if score <= 20 else
                "Manual review needed" if score <= 50 else
                "Freeze transactions and notify authorities" if score <= 70 else
                "Block immediately and initiate legal action"
            )
        },
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }

    try:
        create_document("report", report)
    except Exception:
        pass

    return report


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
