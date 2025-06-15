import pytest
from app.models.base import EmailContent
from app.services.email_processor import EmailProcessor
from datetime import datetime

def test_extract_skus_and_quantities():
    processor = EmailProcessor("Product Catalog.csv")
    
    # Test case 1: Simple SKU and quantity
    text = "Please order ABC-123, 5 pieces"
    results = processor.extract_skus_and_quantities(text)
    assert len(results) == 1
    assert results[0][0] == "ABC-123"
    assert results[0][1] == 5
    assert 0.4 <= results[0][2] <= 1.0

    # Test case 2: Multiple SKUs with quantities
    text = "Need ABC-123 (10 pcs) and XYZ-789 (3 units)"
    results = processor.extract_skus_and_quantities(text)
    assert len(results) == 2
    assert results[0][0] == "ABC-123"
    assert results[0][1] == 10
    assert results[1][0] == "XYZ-789"
    assert results[1][1] == 3

    # Test case 3: SKU without quantity
    text = "Please send ABC-123"
    results = processor.extract_skus_and_quantities(text)
    assert len(results) == 1
    assert results[0][0] == "ABC-123"
    assert results[0][1] == 1
    assert results[0][2] == 0.4

def test_validate_against_catalog():
    processor = EmailProcessor("Product Catalog.csv")
    
    # Test case 1: Valid SKU and quantity
    is_valid, issues, suggestions = processor.validate_against_catalog("ABC-123", 10)
    assert is_valid is not None  # We don't know the exact result as it depends on the catalog
    
    # Test case 2: Invalid SKU
    is_valid, issues, suggestions = processor.validate_against_catalog("INVALID-123", 10)
    assert not is_valid
    assert len(issues) > 0
    assert "not found in catalog" in issues[0]

def test_process_email():
    processor = EmailProcessor("Product Catalog.csv")
    
    email = EmailContent(
        raw_content="Please order ABC-123, 5 pieces and XYZ-789, 3 units",
        received_at=datetime.now()
    )
    
    order = processor.process_email(email)
    assert order.order_id is not None
    assert order.customer_email == "unknown@email.com"
    assert len(order.items) > 0
    assert 0 <= order.total_confidence_score <= 1 