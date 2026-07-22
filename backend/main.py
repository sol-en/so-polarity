from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(env_path)

from .database import engine, Base
from .routers import apartments, transactions, categories, tariffs, charges, dashboard, contractors, forecast, auth
from .bank_integration.router import router as bank_router
from . import bank_models  # Ensure bank integration tables are created

app = FastAPI(title="ЖБК Accounting API", version="0.1.0")

# Create tables on startup
@app.on_event("startup")
async def startup():
    Base.metadata.create_all(bind=engine)

# Include API routers
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(apartments.router, prefix="/api/apartments", tags=["Apartments"])
app.include_router(tariffs.router, prefix="/api/tariffs", tags=["Tariffs"])
app.include_router(categories.router, prefix="/api/categories", tags=["Categories"])
app.include_router(transactions.router, prefix="/api/transactions", tags=["Transactions"])
app.include_router(charges.router, prefix="/api/charges", tags=["Charges"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(contractors.router, prefix="/api/contractors", tags=["Contractors"])
app.include_router(bank_router, prefix="/api/bank", tags=["Bank Integration"])
app.include_router(forecast.router, prefix="/api/forecast", tags=["Forecast"])

# Serve Static Files
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/static", StaticFiles(directory=frontend_path), name="static")

@app.get("/")
async def read_index():
    return FileResponse(os.path.join(frontend_path, "index.html"))

# Also serve CSS and JS directly if they are in root of frontend
@app.get("/{file_path:path}")
async def serve_file(file_path: str):
    file_full_path = os.path.join(frontend_path, file_path)
    if os.path.isfile(file_full_path):
        return FileResponse(file_full_path)
    return FileResponse(os.path.join(frontend_path, "index.html"))
