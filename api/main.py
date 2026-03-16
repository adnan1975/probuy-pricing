

import os
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://probuy-frontend.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
SERP_API_KEY = os.getenv("SERP_API_KEY")

mock_results = [
    {
        "vendor": "SCN Industrial",
        "source": "Preferred Supplier Feed",
        "sourceType": "preferred",
        "title": "DEWALT FLEXVOLT Perform & Protect Max Brushless Cordless Grinder, Tool Only, 4-1/2 - 6 in, 60 V, DCG418B",
        "sku": "UAK055 / DCG418B",
        "price": "$329.00",
        "score": 98,
        "confidence": "High",
        "stock": "In Stock",
        "freshness": "12 mins ago",
        "sourceNote": "Preferred supplier agreement",
        "why": "Exact product family and part number"
    }
]

@app.get("/")
def home():
    return {"message": "ProBuy API running"}

def map_serp_results(json_data):
    organic = json_data.get("organic_results", [])[:5]
    mapped = []

    for item in organic:
        mapped.append({
            "vendor": item.get("source") or item.get("displayed_link") or "Google SERP Result",
            "source": "Google Search Result",
            "sourceType": "google",
            "title": item.get("title", "Search result"),
            "sku": "Validation needed",
            "price": "$--",
            "score": 82,
            "confidence": "Medium",
            "stock": "Unknown",
            "freshness": "Live query",
            "sourceNote": item.get("link", ""),
            "why": "Returned from live Google search and needs page-level price validation"
        })

    return mapped

@app.get("/search")
def search(product: str = ""):
    results = list(mock_results)

    if SERP_API_KEY and product:
        try:
            response = requests.get(
                "https://serpapi.com/search.json",
                params={
                    "engine": "google",
                    "q": product,
                    "api_key": SERP_API_KEY,
                    "google_domain": "google.com"
                },
                timeout=20,
            )
            response.raise_for_status()
            serp_json = response.json()
            results.extend(map_serp_results(serp_json))
        except Exception as e:
            results.append({
                "vendor": "SERP API",
                "source": "Google Search Result",
                "sourceType": "review",
                "title": f"Live search unavailable: {str(e)}",
                "sku": "N/A",
                "price": "$--",
                "score": 40,
                "confidence": "Low",
                "stock": "Unknown",
                "freshness": "N/A",
                "sourceNote": "SERP error",
                "why": "Could not fetch live Google results"
            })

    return {
        "query": product,
        "results": results
    }