"""
SpecbookGenerator - Multi-format specbook generation
pandas-based CSV generation with Revit column mapping and PDF support
"""

import io
import logging
from typing import List, Dict, Any, Optional, BinaryIO
from datetime import datetime
from pathlib import Path
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

# Import models
from models.schemas import Product, SpecbookExport, ExportFormat
from config.settings import get_settings

logger = logging.getLogger(__name__)


class SpecbookGenerator:
    """Generate specbooks in multiple formats with customizable templates"""
    
    def __init__(self):
        """Initialize specbook generator"""
        self.settings = get_settings()
        
        # Column mappings for different templates
        self.column_mappings = {
            "default": {
                "Item": "key",
                "Description": "description", 
                "Type": "type",
                "Model/Part Number": "model_no",
                "Quantity": "qty",
                "Image URL": "image_url",
                "Product Link": "url",
                "Verified": "verified"
            },
            "revit": {
                "Key": "key",
                "Type": "type", 
                "Description": "description",
                "Model": "model_no",
                "Qty": "qty",
                "Image": "image_url",
                "Source": "url",
                "Status": "verified"
            },
            "minimal": {
                "Description": "description",
                "Type": "type", 
                "Model": "model_no",
                "Qty": "qty"
            },
            "detailed": {
                "Project Key": "key",
                "Product Type": "type",
                "Full Description": "description", 
                "Manufacturer Model": "model_no",
                "Quantity Required": "qty",
                "Product Image": "image_url",
                "Source URL": "url",
                "Verification Status": "verified",
                "Confidence Score": "confidence_score",
                "Date Added": "created_at",
                "Last Updated": "updated_at"
            }
        }
    
    def generate_csv(self, products: List[Product], template: str = "revit", include_metadata: bool = False) -> bytes:
        """Generate CSV format specbook"""
        try:
            if not products:
                raise ValueError("No products provided for export")
            
            # Get column mapping
            column_mapping = self.column_mappings.get(template, self.column_mappings["default"])
            
            # Convert products to DataFrame
            data = []
            for product in products:
                row = {}
                for display_name, field_name in column_mapping.items():
                    value = getattr(product, field_name, None)
                    
                    # Format specific fields
                    if field_name == "verified":
                        value = "Yes" if value else "No"
                    elif field_name == "confidence_score":
                        value = f"{value:.2f}" if value else "0.00"
                    elif field_name in ["created_at", "updated_at"] and value:
                        value = value.strftime("%Y-%m-%d %H:%M:%S") if hasattr(value, 'strftime') else str(value)
                    elif field_name == "url" or field_name == "image_url":
                        value = str(value) if value else ""
                    elif value is None:
                        value = ""
                    
                    row[display_name] = value
                
                # Add metadata if requested
                if include_metadata:
                    row["Export Date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    row["Project ID"] = product.project_id
                    row["Product ID"] = product.id
                
                data.append(row)
            
            # Create DataFrame
            df = pd.DataFrame(data)
            
            # Generate CSV
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False, encoding=self.settings.export_csv_encoding)
            csv_content = csv_buffer.getvalue()
            
            logger.info(f"Generated CSV with {len(products)} products using {template} template")
            return csv_content.encode(self.settings.export_csv_encoding)
            
        except Exception as e:
            logger.error(f"Failed to generate CSV: {e}")
            raise
    
    def generate_excel(self, products: List[Product], template: str = "detailed") -> bytes:
        """Generate Excel format specbook with formatting"""
        try:
            if not products:
                raise ValueError("No products provided for export")
            
            # Generate DataFrame similar to CSV
            column_mapping = self.column_mappings.get(template, self.column_mappings["default"])
            
            data = []
            for product in products:
                row = {}
                for display_name, field_name in column_mapping.items():
                    value = getattr(product, field_name, None)
                    
                    # Format specific fields
                    if field_name == "verified":
                        value = "Yes" if value else "No"
                    elif field_name == "confidence_score":
                        value = value if value else 0.0
                    elif field_name in ["created_at", "updated_at"] and value:
                        value = value if hasattr(value, 'strftime') else str(value)
                    elif value is None:
                        value = ""
                    
                    row[display_name] = value
                
                data.append(row)
            
            df = pd.DataFrame(data)
            
            # Create Excel file
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Products', index=False)
                
                # Get workbook and worksheet for formatting
                workbook = writer.book
                worksheet = writer.sheets['Products']
                
                # Auto-adjust column widths
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
            
            excel_buffer.seek(0)
            logger.info(f"Generated Excel with {len(products)} products")
            return excel_buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Failed to generate Excel: {e}")
            raise
    
    def generate_pdf(self, products: List[Product], project_name: str = "Project", style_config: Dict[str, Any] = None) -> bytes:
        """Generate PDF format specbook"""
        try:
            if not products:
                raise ValueError("No products provided for export")
            
            # Default style configuration
            default_style = {
                "page_size": letter,
                "font_name": self.settings.export_pdf_font,
                "title_size": 16,
                "header_size": 12,
                "body_size": 10,
                "show_images": False  # Images in PDF are complex, disabled for now
            }
            style = {**default_style, **(style_config or {})}
            
            # Create PDF buffer
            pdf_buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                pdf_buffer,
                pagesize=style["page_size"],
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=18
            )
            
            # Build PDF content
            story = []
            styles = getSampleStyleSheet()
            
            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=style["title_size"],
                spaceAfter=30,
                alignment=1  # Center
            )
            story.append(Paragraph(f"{project_name} - Product Specification Book", title_style))
            
            # Generation info
            info_text = f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br/>Total Products: {len(products)}"
            story.append(Paragraph(info_text, styles['Normal']))
            story.append(Spacer(1, 20))
            
            # Create product table
            table_data = []
            
            # Headers
            headers = ["Type", "Description", "Model", "Qty", "Status"]
            table_data.append(headers)
            
            # Product rows
            for product in products:
                row = [
                    product.type,
                    product.description[:50] + "..." if len(product.description) > 50 else product.description,
                    product.model_no or "N/A",
                    str(product.qty),
                    "Verified" if product.verified else "Pending"
                ]
                table_data.append(row)
            
            # Create table
            table = Table(table_data, colWidths=[1*inch, 3*inch, 1.5*inch, 0.5*inch, 1*inch])
            
            # Table style
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), style["header_size"]),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), style["body_size"]),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            
            story.append(table)
            
            # Build PDF
            doc.build(story)
            pdf_buffer.seek(0)
            
            logger.info(f"Generated PDF with {len(products)} products")
            return pdf_buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Failed to generate PDF: {e}")
            raise
    
    def generate_json(self, products: List[Product], include_metadata: bool = True) -> bytes:
        """Generate JSON format export"""
        try:
            if not products:
                raise ValueError("No products provided for export")
            
            # Convert products to JSON-serializable format
            export_data = {
                "metadata": {
                    "export_date": datetime.now().isoformat(),
                    "product_count": len(products),
                    "format_version": "1.0"
                } if include_metadata else {},
                "products": []
            }
            
            for product in products:
                product_data = product.model_dump()
                
                # Convert datetime objects to ISO strings
                for field in ['created_at', 'updated_at', 'last_checked']:
                    if field in product_data and product_data[field]:
                        if hasattr(product_data[field], 'isoformat'):
                            product_data[field] = product_data[field].isoformat()
                
                # Convert URLs to strings
                if product_data.get('url'):
                    product_data['url'] = str(product_data['url'])
                if product_data.get('image_url'):
                    product_data['image_url'] = str(product_data['image_url'])
                
                export_data["products"].append(product_data)
            
            import json
            json_content = json.dumps(export_data, indent=2, ensure_ascii=False)
            
            logger.info(f"Generated JSON with {len(products)} products")
            return json_content.encode('utf-8')
            
        except Exception as e:
            logger.error(f"Failed to generate JSON: {e}")
            raise
    
    def generate_export(self, export_config: SpecbookExport, products: List[Product]) -> bytes:
        """Generate export based on configuration"""
        try:
            # Filter products based on configuration
            filtered_products = self._filter_products(products, export_config)
            
            if not filtered_products:
                raise ValueError("No products match export criteria")
            
            # Generate based on format
            if export_config.format == ExportFormat.CSV:
                return self.generate_csv(
                    filtered_products, 
                    export_config.template,
                    include_metadata=True
                )
            elif export_config.format == ExportFormat.EXCEL:
                return self.generate_excel(
                    filtered_products,
                    export_config.template
                )
            elif export_config.format == ExportFormat.PDF:
                project_name = export_config.filters.get("project_name", "Project")
                return self.generate_pdf(
                    filtered_products,
                    project_name
                )
            elif export_config.format == ExportFormat.JSON:
                return self.generate_json(
                    filtered_products,
                    include_metadata=True
                )
            else:
                raise ValueError(f"Unsupported export format: {export_config.format}")
                
        except Exception as e:
            logger.error(f"Failed to generate export: {e}")
            raise
    
    def get_export_summary(self, products: List[Product], export_config: SpecbookExport) -> Dict[str, Any]:
        """Get summary of what would be exported"""
        try:
            filtered_products = self._filter_products(products, export_config)
            
            # Count by type
            type_counts = {}
            verified_count = 0
            confidence_scores = []
            
            for product in filtered_products:
                # Count by type
                product_type = product.type
                type_counts[product_type] = type_counts.get(product_type, 0) + 1
                
                # Count verified
                if product.verified:
                    verified_count += 1
                
                # Collect confidence scores
                if product.confidence_score:
                    confidence_scores.append(product.confidence_score)
            
            avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
            
            return {
                "total_products": len(filtered_products),
                "verified_products": verified_count,
                "unverified_products": len(filtered_products) - verified_count,
                "verification_rate": verified_count / len(filtered_products) if filtered_products else 0,
                "average_confidence": avg_confidence,
                "product_types": dict(sorted(type_counts.items())),
                "filters_applied": export_config.filters,
                "export_format": export_config.format,
                "template": export_config.template
            }
            
        except Exception as e:
            logger.error(f"Failed to generate export summary: {e}")
            return {"error": str(e)}
    
    def _filter_products(self, products: List[Product], export_config: SpecbookExport) -> List[Product]:
        """Filter products based on export configuration"""
        try:
            filtered = products
            
            # Apply filters
            if not export_config.include_unverified:
                filtered = [p for p in filtered if p.verified]
            
            # Apply custom filters
            filters = export_config.filters
            
            if filters.get("product_type"):
                product_type = filters["product_type"].lower()
                filtered = [p for p in filtered if product_type in p.type.lower()]
            
            if filters.get("min_confidence"):
                min_confidence = float(filters["min_confidence"])
                filtered = [p for p in filtered if p.confidence_score >= min_confidence]
            
            if filters.get("has_model_no"):
                filtered = [p for p in filtered if p.model_no]
            
            if filters.get("has_image"):
                filtered = [p for p in filtered if p.image_url]
            
            return filtered
            
        except Exception as e:
            logger.error(f"Failed to filter products: {e}")
            return products  # Return unfiltered on error
    
    def get_available_templates(self) -> Dict[str, Dict[str, str]]:
        """Get available export templates with descriptions"""
        return {
            "default": {
                "name": "Default",
                "description": "Standard format with all key fields",
                "use_case": "General purpose export"
            },
            "revit": {
                "name": "Revit Compatible", 
                "description": "Optimized for Revit import with proper column names",
                "use_case": "Direct import into Revit schedules"
            },
            "minimal": {
                "name": "Minimal",
                "description": "Essential fields only for simple lists",
                "use_case": "Quick reference or simplified reports"
            },
            "detailed": {
                "name": "Detailed",
                "description": "Comprehensive export with metadata and timestamps",
                "use_case": "Full documentation and audit trails"
            }
        }