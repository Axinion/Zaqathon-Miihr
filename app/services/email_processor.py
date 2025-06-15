import re
import difflib
import dateparser
from dateparser.search import search_dates
from typing import List, Dict, Tuple
import pandas as pd
from app.models.base import EmailContent, Order, OrderItem, Product

NON_PRODUCT_PHRASES = [
    "deliver to", "let me know", "pricing", "availability", "before", "address", "do deliver", "meguro", "japan"
]

def build_product_name_regex(product_names):
    escaped_names = [re.escape(name) for name in product_names]
    escaped_names.sort(key=len, reverse=True)
    pattern = r'(' + '|'.join(escaped_names) + r')'
    return pattern

def extract_delivery_details(text: str) -> dict:
    print("=== Extracting delivery details from email ===")
    print(text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    address = None
    date = None

    # Address extraction: look for common keywords and grab the next non-empty line if needed
    address_keywords = [
        "ship to", "send to", "delivery address", "please deliver to", "deliver to", "recipient", "address is", "ship them to"
    ]
    for i, line in enumerate(lines):
        for keyword in address_keywords:
            if keyword in line.lower():
                after_colon = line.split(':', 1)[-1].strip()
                if after_colon and after_colon.lower() != keyword:
                    address = after_colon
                elif i+1 < len(lines):
                    next_line = lines[i+1]
                    # If the next line is a name, and the line after that looks like an address, combine them
                    if i+2 < len(lines) and re.search(r'(street|st|avenue|ave|road|rd|lane|ln|blvd|drive|dr|way|court|ct|plaza|circle|parkway|square|block|bldg|suite|apt|unit|room|po box|city|,)', lines[i+2], re.IGNORECASE):
                        address = next_line + ', ' + lines[i+2]
                    else:
                        address = next_line
                break
        if address:
            break

    # Fallback: look for lines that look like addresses but NOT product lines
    if not address:
        for i, line in enumerate(lines):
            # Ignore lines that look like product lines
            if re.search(r'(pcs|qty|x\s*\d+|need \d+)', line, re.IGNORECASE):
                continue
            # Look for address-like lines
            if re.search(r'(street|st|avenue|ave|road|rd|lane|ln|blvd|drive|dr|way|court|ct|plaza|circle|parkway|square|block|bldg|suite|apt|unit|room|po box|city|,)', line, re.IGNORECASE):
                address = line
                break

    print("Extracted address:", address)

    # Date extraction: look for common keywords and parse the date
    date_keywords = [
        "before", "by", "deadline", "requested delivery date", "deliver on", "deliver before",
        "delivery date", "needed on", "arrive by", "no later than", "expected on", "required delivery date"
    ]
    for line in lines:
        for keyword in date_keywords:
            if keyword in line.lower():
                date_str = line.split(':', 1)[-1] if ':' in line else line
                parsed_date = dateparser.parse(date_str, settings={'PREFER_DATES_FROM': 'future'})
                if parsed_date:
                    date = parsed_date.strftime('%Y-%m-%d')
                    break
        if date:
            break

    # Fallback: search for any date-like phrase in the email
    if not date:
        found = search_dates(text, settings={'PREFER_DATES_FROM': 'future'})
        if found:
            date = found[0][1].strftime('%Y-%m-%d')

    print("Extracted date:", date)
    return {"address": address, "date": date}

class EmailProcessor:
    def __init__(self, catalog_path: str):
        self.catalog = pd.read_csv(catalog_path)
        self.product_name_pattern = build_product_name_regex(self.catalog['Product_Name'].tolist())
        self.sku_pattern = re.compile(r'[A-Z]{2,3}-\d{3,4}', re.IGNORECASE)
        self.quantity_pattern = re.compile(r'(\d+)\s*(?:pcs|pieces|units|qty|quantity)?', re.IGNORECASE)

    def find_product(self, extracted_name: str) -> Dict:
        match = self.catalog[self.catalog['Product_Name'].str.lower() == extracted_name.lower()]
        if not match.empty:
            return match.iloc[0].to_dict()
        match = self.catalog[self.catalog['Product_Code'].str.lower() == extracted_name.lower()]
        if not match.empty:
            return match.iloc[0].to_dict()
        all_names = self.catalog['Product_Name'].tolist() + self.catalog['Product_Code'].tolist()
        matches = difflib.get_close_matches(extracted_name, all_names, n=1, cutoff=0.8)
        if matches:
            match_name = matches[0]
            match = self.catalog[(self.catalog['Product_Name'] == match_name) | (self.catalog['Product_Code'] == match_name)]
            if not match.empty:
                return match.iloc[0].to_dict()
        return None

    def extract_delivery_details(self, text: str) -> Dict:
        return extract_delivery_details(text)

    def extract_customer_notes(self, text: str) -> str:
        # Look for lines after 'Notes:', 'Let me know', etc.
        note_patterns = [
            r'notes?[:\-\s]*(.*)',
            r'let me know[:\-\s]*(.*)',
            r'if there are better alternatives for any item, (.*)',
            r'sincerely,\s*(.*)',
        ]
        for pat in note_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return None

    def extract_products_and_quantities(self, text: str) -> List[Tuple[Dict, int, float, str]]:
        results = []
        product_names = self.catalog['Product_Name'].tolist()
        for line in text.splitlines():
            num_match = re.search(r'(\d+)', line)
            if not num_match:
                continue
            quantity = int(num_match.group(1))
            # Remove the number and try to fuzzy match the rest
            candidate = re.sub(r'(\d+)', '', line).strip(' -:x*.,')
            best = difflib.get_close_matches(candidate, product_names, n=1, cutoff=0.6)
            if best:
                extracted_name = best[0]
                product = self.find_product(extracted_name)
                confidence = 1.0
            else:
                extracted_name = candidate
                product = None
                confidence = 0.5
            if any(phrase in extracted_name.lower() for phrase in NON_PRODUCT_PHRASES):
                continue
            results.append((product, quantity, confidence, extracted_name))
        return results

    def validate_against_catalog(self, product: Dict, quantity: int) -> Tuple[bool, List[str], List[str]]:
        issues = []
        suggestions = []
        if not product:
            issues.append("Product not found in catalog")
            # Suggest similar SKUs
            all_names = self.catalog['Product_Name'].tolist() + self.catalog['Product_Code'].tolist()
            similar = difflib.get_close_matches(product, all_names, n=2, cutoff=0.6) if product else []
            if similar:
                suggestions.extend(similar)
            return False, issues, suggestions
        if quantity < product['Min_Order_Quantity']:
            issues.append(f"Quantity {quantity} is below MOQ of {product['Min_Order_Quantity']} for {product['Product_Name']}")
            suggestions.append(f"Increase quantity to {product['Min_Order_Quantity']}")
        if quantity > product['Available_in_Stock']:
            issues.append(f"Requested quantity {quantity} exceeds available stock of {product['Available_in_Stock']} for {product['Product_Name']}")
            suggestions.append(f"Reduce quantity to {product['Available_in_Stock']}")
        return len(issues) == 0, issues, suggestions

    def process_email(self, email: EmailContent) -> Order:
        extracted_items = self.extract_products_and_quantities(email.raw_content)
        filtered_items = [item for item in extracted_items if item[2] >= 0.7]
        order_items = []
        total_confidence = 0.0
        for product, quantity, confidence, extracted_name in filtered_items:
            is_valid, issues, suggestions = self.validate_against_catalog(product, quantity)
            sku = product['Product_Code'] if product else extracted_name
            item = OrderItem(
                sku=sku,
                quantity=quantity,
                confidence_score=confidence,
                validation_issues=issues if not is_valid else None,
                suggested_replacements=suggestions if not is_valid else None,
                price=product['Price'] if product else 0.0
            )
            order_items.append(item)
            total_confidence += confidence
        avg_confidence = total_confidence / len(order_items) if order_items else 0.0
        # Extract delivery details and notes
        delivery_details = self.extract_delivery_details(email.raw_content)
        notes = self.extract_customer_notes(email.raw_content)
        order = Order(
            order_id=f"ORD-{email.received_at.strftime('%Y%m%d%H%M%S') if email.received_at else 'TEMP'}",
            customer_email=email.sender or "unknown@email.com",
            items=order_items,
            total_confidence_score=avg_confidence,
            validation_issues=[issue for item in order_items if item.validation_issues for issue in item.validation_issues],
            delivery_details=delivery_details,
            notes=notes
        )
        return order 