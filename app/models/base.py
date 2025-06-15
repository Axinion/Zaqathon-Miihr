from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime

class Product(BaseModel):
    sku: str
    description: str
    moq: int
    price: float
    stock: int
    category: Optional[str] = None

class OrderItem(BaseModel):
    sku: str
    quantity: int
    confidence_score: float = Field(ge=0.0, le=1.0)
    notes: Optional[str] = None
    suggested_replacements: Optional[List[str]] = None
    validation_issues: Optional[List[str]] = None
    price: float = 0.0

class DeliveryDetails(BaseModel):
    address: str
    date: str
    instructions: Optional[str] = None

class OrderRequest(BaseModel):
    id: str = Field(default_factory=lambda: datetime.now().strftime("%Y%m%d%H%M%S"))
    customer_name: str
    items: List[OrderItem]
    delivery_details: DeliveryDetails
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    status: str = "pending"
    total_confidence_score: float = Field(ge=0.0, le=1.0)
    validation_issues: Optional[List[str]] = None

class Order(BaseModel):
    order_id: str
    customer_email: str
    items: List[OrderItem]
    delivery_preferences: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    status: str = "pending"
    total_confidence_score: float = Field(ge=0.0, le=1.0)
    validation_issues: Optional[List[str]] = None

class EmailContent(BaseModel):
    raw_content: str
    subject: Optional[str] = None
    sender: Optional[str] = None
    received_at: Optional[datetime] = None
    thread_id: Optional[str] = None 