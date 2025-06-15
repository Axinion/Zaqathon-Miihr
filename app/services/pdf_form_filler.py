from typing import Dict, Any
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import io
import os
from datetime import datetime

class PDFFormFiller:
    def __init__(self, template_path: str = "data/templates/sales_order_template.pdf"):
        self.template_path = template_path
        if not os.path.exists(template_path):
            self._create_default_template()

    def _create_default_template(self):
        """Create a default sales order template if none exists"""
        c = canvas.Canvas(self.template_path, pagesize=letter)
        
        # Add header
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, 750, "SALES ORDER")
        
        # Add fields
        c.setFont("Helvetica", 12)
        fields = [
            ("Order Number:", 50, 700),
            ("Date:", 50, 680),
            ("Customer Name:", 50, 650),
            ("Delivery Address:", 50, 620),
            ("Delivery Date:", 50, 590),
            ("Items:", 50, 560),
        ]
        
        for text, x, y in fields:
            c.drawString(x, y, text)
        
        c.save()

    def fill_form(self, order_data: Dict[str, Any]) -> bytes:
        """
        Fill the PDF form with order data
        
        Args:
            order_data: Dictionary containing order information
            
        Returns:
            bytes: PDF file content
        """
        # Create a new PDF with ReportLab
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=letter)
        
        # Add header
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, 750, "SALES ORDER")
        
        # Add order details
        c.setFont("Helvetica", 12)
        c.drawString(200, 700, f"SO-{datetime.now().strftime('%Y%m%d%H%M%S')}")
        c.drawString(200, 680, datetime.now().strftime("%Y-%m-%d"))
        c.drawString(200, 650, order_data.get("customer_name", "N/A"))
        
        # Add delivery details
        delivery = order_data.get("delivery_details", {})
        address = delivery.get("address", "N/A")
        c.drawString(200, 620, address)
        c.drawString(200, 590, delivery.get("date", "N/A"))
        
        # Add items
        y_position = 560
        c.drawString(50, y_position, "Items:")
        y_position -= 20
        
        for item in order_data.get("items", []):
            item_text = f"{item['sku']} - {item['quantity']} units @ ${item['price']:.2f} each"
            c.drawString(70, y_position, item_text)
            y_position -= 20
            
            if y_position < 50:  # Start new page if needed
                c.showPage()
                y_position = 750
        
        # Add notes if any
        if order_data.get("notes"):
            c.showPage()
            c.setFont("Helvetica-Bold", 12)
            c.drawString(50, 750, "Additional Notes:")
            c.setFont("Helvetica", 12)
            c.drawString(50, 730, order_data["notes"])
        
        c.save()
        
        # Move to the beginning of the StringIO buffer
        packet.seek(0)
        return packet.getvalue()

    def save_filled_form(self, order_data: Dict[str, Any], output_path: str) -> str:
        """
        Save the filled form to a file
        
        Args:
            order_data: Dictionary containing order information
            output_path: Path to save the filled form
            
        Returns:
            str: Path to the saved file
        """
        pdf_content = self.fill_form(order_data)
        
        with open(output_path, "wb") as f:
            f.write(pdf_content)
            
        return output_path 