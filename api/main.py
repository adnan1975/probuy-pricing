
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

mock_results = [
    {
        "vendor": "SCN Industrial",
        "title": "3M SecureFit SF201AF Safety Glasses, Clear Anti-Fog, Each",
        "sku": "SF201AF",
        "price": 13.10,
        "score": 97,
        "confidence": "High",
        "stock": "In Stock",
        "freshness": "12 mins ago",
        "badge": "Preferred Supplier"
    },
    {
        "vendor": "Grainger Canada",
        "title": "3M SecureFit Safety Glasses SF201AF, Clear Lens, Anti-Fog",
        "sku": "SF201AF",
        "price": 12.95,
        "score": 94,
        "confidence": "High",
        "stock": "In Stock",
        "freshness": "18 mins ago",
        "badge": "Trusted Market"
    },
    {
        "vendor": "Acklands-Grainger",
        "title": "3M SecureFit Protective Eyewear, Clear, Anti-Fog Coating",
        "sku": "SF201AF",
        "price": 12.40,
        "score": 88,
        "confidence": "Medium",
        "stock": "Low Stock",
        "freshness": "46 mins ago",
        "badge": "Competitive Price"
    },
    {
        "vendor": "Amazon Business",
        "title": "3M Safety Glasses SecureFit Clear, Similar Listing",
        "sku": "SF201AF?",
        "price": 11.80,
        "score": 73,
        "confidence": "Low",
        "stock": "Unknown",
        "freshness": "4 hrs ago",
        "badge": "Review Required"
    }
]

@app.get("/")
def home():
    return {"message": "ProBuy API running"}

@app.get("/search")
def search(product: str = ""):
    return {
        "query": product,
        "results": mock_results
    }