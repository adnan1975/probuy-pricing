import os
import re
import requests
from statistics import mean
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

EXAMPLES = {
    "Flexvolt Perform & Protect Max Brushless Cordless Grinder": {
        "preferredResults": [
            {
                "vendor": "SCN Industrial",
                "source": "Preferred Supplier Feed",
                "sourceType": "preferred",
                "title": "DEWALT FLEXVOLT Perform & Protect Max Brushless Cordless Grinder, Tool Only, 4-1/2 - 6 in, 60 V, DCG418B",
                "sku": "UAK055 / DCG418B",
                "price": "$329.00",
                "priceValue": 329.00,
                "score": 98,
                "confidence": "High",
                "stock": "In Stock",
                "freshness": "12 mins ago",
                "sourceNote": "Preferred supplier agreement",
                "why": "Exact product family and part number"
            }
        ]
    },
    "3M SecureFit SF201AF clear anti-fog glasses": {
        "preferredResults": [
            {
                "vendor": "SCN Industrial",
                "source": "Preferred Supplier Feed",
                "sourceType": "preferred",
                "title": "3M SecureFit SF201AF Safety Glasses, Clear Anti-Fog, Each",
                "sku": "SF201AF",
                "price": "$13.10",
                "priceValue": 13.10,
                "score": 97,
                "confidence": "High",
                "stock": "In Stock",
                "freshness": "12 mins ago",
                "sourceNote": "Preferred supplier agreement",
                "why": "Exact manufacturer part match"
            }
        ]
    }
}


def parse_price(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    match = re.search(r"(\d[\d,]*\.?\d*)", text.replace(",", ""))
    if not match:
        return None

    try:
        return float(match.group(1))
    except ValueError:
        return None


def format_price(value):
    if value is None:
        return "$--"
    return f"${value:,.2f}"


def infer_vendor(link, fallback="Google SERP Result"):
    if not link:
        return fallback
    cleaned = link.replace("https://", "").replace("http://", "").split("/")[0]
    cleaned = cleaned.replace("www.", "")
    return cleaned or fallback


def build_serp_result(item, idx, result_type):
    link = item.get("link") or item.get("product_link") or item.get("serpapi_product_api") or ""
    title = item.get("title") or item.get("product_title") or "Search result"
    vendor = (
        item.get("source")
        or item.get("merchant_name")
        or item.get("store_name")
        or infer_vendor(link)
    )

    raw_price = (
        item.get("price")
        or item.get("extracted_price")
        or item.get("primary_offer", {}).get("price")
        or item.get("extensions", [None])[0]
    )

    price_value = parse_price(raw_price)
    has_price = price_value is not None

    if result_type == "shopping":
        confidence = "Medium" if has_price else "Low"
        score = 84 if has_price else 72
        note = "Google Shopping result"
        why = "Returned from Google Shopping and useful for market pricing context"
    else:
        confidence = "Medium" if has_price else "Low"
        score = 80 if has_price else 68
        note = "Google organic result"
        why = (
            "Returned from live Google search. "
            + ("Visible price found in result." if has_price else "No direct price in result; page validation recommended.")
        )

    return {
        "position": idx,
        "vendor": vendor,
        "domain": infer_vendor(link),
        "source": "Google Shopping Result" if result_type == "shopping" else "Google Search Result",
        "sourceType": "google",
        "resultType": result_type,
        "title": title,
        "sku": "Validation needed",
        "price": format_price(price_value),
        "priceValue": price_value,
        "score": score,
        "confidence": confidence,
        "stock": "Unknown",
        "freshness": "Live query",
        "sourceNote": note,
        "link": link,
        "why": why
    }


def fetch_serp_results(product):
    if not SERP_API_KEY:
        return []

    all_results = []

    # Google organic
    organic_resp = requests.get(
        "https://serpapi.com/search.json",
        params={
            "engine": "google",
            "google_domain": "google.com",
            "q": product,
            "api_key": SERP_API_KEY,
        },
        timeout=20,
    )
    organic_resp.raise_for_status()
    organic_json = organic_resp.json()

    organic_items = organic_json.get("organic_results", [])[:10]
    for idx, item in enumerate(organic_items, start=1):
        all_results.append(build_serp_result(item, idx, "organic"))

    # Google Shopping
    shopping_resp = requests.get(
        "https://serpapi.com/search.json",
        params={
            "engine": "google_shopping",
            "google_domain": "google.com",
            "q": product,
            "api_key": SERP_API_KEY,
        },
        timeout=20,
    )
    shopping_resp.raise_for_status()
    shopping_json = shopping_resp.json()

    shopping_items = shopping_json.get("shopping_results", [])[:10]
    offset = len(all_results)
    for idx, item in enumerate(shopping_items, start=1):
        all_results.append(build_serp_result(item, offset + idx, "shopping"))

    return all_results


def build_analysis(preferred_results, serp_results):
    priced_serp = [r for r in serp_results if r.get("priceValue") is not None]
    all_priced = [r for r in preferred_results + serp_results if r.get("priceValue") is not None]

    lowest = min((r["priceValue"] for r in priced_serp), default=None)
    highest = max((r["priceValue"] for r in priced_serp), default=None)
    average = round(mean([r["priceValue"] for r in priced_serp]), 2) if priced_serp else None

    exact_like = sum(1 for r in preferred_results + serp_results if r.get("confidence") == "High")
    review_count = sum(1 for r in serp_results if r.get("confidence") == "Low")

    summary = (
        "Preferred supplier pricing remains the safest quoting source. "
        "SERP results are useful as market intelligence, especially when prices are visible, "
        "but lower-confidence rows should be validated before quoting."
    )

    if all_priced:
        preferred_price = preferred_results[0]["priceValue"] if preferred_results else None
        if preferred_price is not None and lowest is not None:
            if preferred_price <= lowest:
                summary = (
                    "Preferred supplier pricing is at or below the visible market range, "
                    "so it is both operationally strong and commercially competitive."
                )
            elif preferred_price > lowest:
                summary = (
                    "Preferred supplier pricing is above the lowest visible market result, "
                    "but still recommended when product identity and supplier trust matter more than headline price."
                )

    return {
        "totalResults": len(serp_results),
        "pricedResults": len(priced_serp),
        "lowestPrice": format_price(lowest),
        "highestPrice": format_price(highest),
        "averagePrice": format_price(average),
        "exactMatchCount": exact_like,
        "reviewCount": review_count,
        "summary": summary
    }


@app.get("/")
def home():
    return {"message": "ProBuy API running"}


@app.get("/search")
def search(product: str = ""):
    preferred_results = EXAMPLES.get(product, {}).get("preferredResults", [])

    serp_results = []
    serp_error = None

    try:
        if product:
            serp_results = fetch_serp_results(product)
    except Exception as e:
        serp_error = str(e)

    analysis = build_analysis(preferred_results, serp_results)

    return {
        "query": product,
        "preferredResults": preferred_results,
        "serpResults": serp_results,
        "analysis": analysis,
        "serpError": serp_error
    }