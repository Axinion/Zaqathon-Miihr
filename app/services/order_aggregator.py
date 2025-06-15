from typing import List, Dict, Any
from collections import defaultdict
import pandas as pd
from datetime import datetime, timedelta
from app.models.base import OrderRequest

class OrderAggregator:
    def __init__(self):
        self.orders = []
        self.product_patterns = defaultdict(int)
        self.customer_patterns = defaultdict(int)
        self.time_patterns = defaultdict(int)

    def add_order(self, order: OrderRequest):
        """Add a new order to the aggregator"""
        self.orders.append(order)
        self._update_patterns(order)

    def _update_patterns(self, order: OrderRequest):
        """Update various pattern tracking"""
        # Product patterns
        for item in order.items:
            self.product_patterns[item.sku] += item.quantity

        # Customer patterns
        customer_key = f"{order.customer_name}_{order.delivery_details.address}"
        self.customer_patterns[customer_key] += 1

        # Time patterns (group by week)
        order_date = datetime.strptime(order.delivery_details.date, "%Y-%m-%d")
        week_key = order_date.strftime("%Y-%W")
        self.time_patterns[week_key] += 1

    def get_common_products(self, min_occurrences: int = 2) -> List[Dict[str, Any]]:
        """Get products that are commonly ordered together"""
        product_pairs = defaultdict(int)
        
        for order in self.orders:
            skus = [item.sku for item in order.items]
            for i in range(len(skus)):
                for j in range(i + 1, len(skus)):
                    pair = tuple(sorted([skus[i], skus[j]]))
                    product_pairs[pair] += 1

        return [
            {"products": pair, "occurrences": count}
            for pair, count in product_pairs.items()
            if count >= min_occurrences
        ]

    def get_customer_insights(self) -> List[Dict[str, Any]]:
        """Get insights about customer ordering patterns"""
        customer_insights = []
        
        for customer_key, order_count in self.customer_patterns.items():
            customer_name, address = customer_key.split("_", 1)
            customer_orders = [
                order for order in self.orders
                if order.customer_name == customer_name
                and order.delivery_details.address == address
            ]
            
            total_items = sum(
                item.quantity
                for order in customer_orders
                for item in order.items
            )
            
            customer_insights.append({
                "customer_name": customer_name,
                "address": address,
                "order_count": order_count,
                "total_items": total_items,
                "average_items_per_order": total_items / order_count if order_count > 0 else 0
            })
        
        return customer_insights

    def get_time_based_insights(self, days: int = 30) -> Dict[str, Any]:
        """Get insights about ordering patterns over time"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        orders_in_period = [
            order for order in self.orders
            if start_date <= datetime.strptime(order.delivery_details.date, "%Y-%m-%d") <= end_date
        ]
        
        daily_orders = defaultdict(int)
        for order in orders_in_period:
            date = order.delivery_details.date
            daily_orders[date] += 1
        
        return {
            "total_orders": len(orders_in_period),
            "average_orders_per_day": len(orders_in_period) / days,
            "daily_order_counts": dict(daily_orders)
        }

    def merge_orders(self, order_ids: List[str]) -> Dict[str, Any]:
        """Merge multiple orders into a single order"""
        selected_orders = [
            order for order in self.orders
            if order.id in order_ids
        ]
        
        if not selected_orders:
            return {"error": "No orders found with the provided IDs"}
        
        # Merge items
        merged_items = defaultdict(int)
        for order in selected_orders:
            for item in order.items:
                merged_items[item.sku] += item.quantity
        
        # Use the most recent delivery date
        latest_delivery = max(
            order.delivery_details.date
            for order in selected_orders
        )
        
        # Combine notes
        combined_notes = "\n".join(
            order.notes
            for order in selected_orders
            if order.notes
        )
        
        return {
            "merged_order": {
                "items": [
                    {"sku": sku, "quantity": quantity}
                    for sku, quantity in merged_items.items()
                ],
                "delivery_date": latest_delivery,
                "notes": combined_notes
            },
            "original_orders": [
                {
                    "id": order.id,
                    "customer_name": order.customer_name,
                    "delivery_date": order.delivery_details.date
                }
                for order in selected_orders
            ]
        }

    def export_insights(self) -> Dict[str, Any]:
        """Export all insights in a structured format"""
        return {
            "common_products": self.get_common_products(),
            "customer_insights": self.get_customer_insights(),
            "time_based_insights": self.get_time_based_insights(),
            "total_orders": len(self.orders),
            "total_customers": len(self.customer_patterns),
            "most_ordered_products": sorted(
                self.product_patterns.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
        } 