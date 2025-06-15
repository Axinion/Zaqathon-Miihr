from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
import uvicorn
from datetime import datetime
import json
import os
from typing import List

from app.models.base import EmailContent, Order
from app.services.email_processor import EmailProcessor
from app.services.pdf_form_filler import PDFFormFiller
from app.services.order_aggregator import OrderAggregator
from app.models.base import OrderRequest

app = FastAPI(title="Smart Order Intake System")

# In-memory order store
ORDERS = {}

# Keep track of the last processed order for fallback
LAST_PROCESSED_ORDER = None

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize email processor with new path
email_processor = EmailProcessor("content/Product Catalog.csv")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize services
pdf_form_filler = PDFFormFiller(template_path="content/sales_order_form_full.pdf")
order_aggregator = OrderAggregator()

@app.post("/api/process-email")
async def process_email(file: UploadFile = File(...)):
    """Process raw email content and extract order information."""
    try:
        result = await email_processor.process_email(file)
        order_id = result.get("order_id")
        global LAST_PROCESSED_ORDER
        if order_id:
            ORDERS[order_id] = result
            LAST_PROCESSED_ORDER = result
        order_aggregator.add_order(result)
        output_dir = "content/generated_orders"
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_path = os.path.join(output_dir, f"order_{timestamp}.pdf")
        order_data = {
            "customer_name": result.get("customer_name", "N/A"),
            "delivery_details": result.get("delivery_details", {}),
            "items": [
                {
                    "sku": item.sku,
                    "quantity": item.quantity,
                    "price": item.price
                }
                for item in result.get("items", [])
            ],
            "notes": result.get("notes", "")
        }
        pdf_form_filler.save_filled_form(order_data, pdf_path)
        result["pdf_path"] = pdf_path
        return result
    except Exception as e:
        print(f"Error in process_email: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload-email")
async def upload_email(file: UploadFile = File(...)):
    """Upload and process email content from a file."""
    try:
        content = await file.read()
        email_content = EmailContent(
            raw_content=content.decode(),
            received_at=datetime.now()
        )
        order = email_processor.process_email(email_content)
        order_id = order.order_id if hasattr(order, 'order_id') else None
        global LAST_PROCESSED_ORDER
        if order_id:
            ORDERS[order_id] = order
            LAST_PROCESSED_ORDER = order
        return order
    except Exception as e:
        print(f"Error in upload_email: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/validate-order/{order_id}")
async def validate_order(order_id: str):
    """Validate an existing order against the catalog."""
    # In a real application, this would fetch the order from a database
    # For now, we'll return a mock response
    return {"status": "validated", "order_id": order_id}

@app.post("/api/approve-order")
async def approve_order(order: Order):
    """Approve and finalize an order."""
    order_id = order.order_id
    if not order_id or order_id not in ORDERS:
        raise HTTPException(status_code=404, detail="Order not found")
    # Update status
    ORDERS[order_id]["status"] = "approved"
    return {"status": "approved", "order_id": order_id}

@app.get("/api/export-pdf/{order_id}")
async def export_pdf(order_id: str):
    global LAST_PROCESSED_ORDER
    if not LAST_PROCESSED_ORDER:
        raise HTTPException(status_code=404, detail="No order available for export. Please process an email first.")
    order = LAST_PROCESSED_ORDER
    output_dir = "content/generated_orders"
    os.makedirs(output_dir, exist_ok=True)
    pdf_path = os.path.join(output_dir, f"order_{order.get('order_id', 'latest')}.pdf")
    order_data = {
        "customer_name": order.get("customer_name", "N/A"),
        "delivery_details": order.get("delivery_details", {}),
        "items": [
            {
                "sku": item.sku if hasattr(item, 'sku') else item.get('sku'),
                "quantity": item.quantity if hasattr(item, 'quantity') else item.get('quantity'),
                "price": item.price if hasattr(item, 'price') else item.get('price', 0.0)
            }
            for item in order.get("items", [])
        ],
        "notes": order.get("notes", "")
    }
    pdf_form_filler.save_filled_form(order_data, pdf_path)
    return FileResponse(pdf_path, media_type="application/pdf", filename=os.path.basename(pdf_path))

@app.get("/api/download-pdf/{filename}")
async def download_pdf(filename: str):
    pdf_path = os.path.join("content/generated_orders", filename)
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(pdf_path, media_type="application/pdf", filename=filename)

# Order Aggregation Endpoints
@app.get("/api/insights/common-products")
async def get_common_products(min_occurrences: int = 2):
    """Get products that are commonly ordered together"""
    return order_aggregator.get_common_products(min_occurrences)

@app.get("/api/insights/customer-patterns")
async def get_customer_insights():
    """Get insights about customer ordering patterns"""
    return order_aggregator.get_customer_insights()

@app.get("/api/insights/time-based")
async def get_time_based_insights(days: int = 30):
    """Get insights about ordering patterns over time"""
    return order_aggregator.get_time_based_insights(days)

@app.post("/api/orders/merge")
async def merge_orders(order_ids: List[str]):
    """Merge multiple orders into a single order"""
    return order_aggregator.merge_orders(order_ids)

@app.get("/api/insights/export")
async def export_insights():
    """Export all insights in a structured format"""
    return order_aggregator.export_insights()

@app.get("/")
async def root():
    return {"message": "Welcome to Smart Order Intake API"}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True) 