"""
Simple JSON Console Display for Climate Hazards Analysis

This module provides simple console display using print() statements
to ensure JSON data is always visible in the console.
"""

import json
from datetime import datetime
from typing import Dict, Any, List


class SimpleJSONConsole:
    """Simple JSON display using print statements"""

    @staticmethod
    def display_json(data: Any, title: str, max_length: int = 1000) -> None:
        """
        Display JSON data in console using print statements

        Args:
            data: JSON data to display
            title: Title for the display section
            max_length: Maximum characters to display (truncated if longer)
        """
        try:
            # Convert to formatted JSON string
            json_str = json.dumps(data, indent=2, ensure_ascii=False, default=str)

            # Truncate if too long
            if len(json_str) > max_length:
                json_str = json_str[:max_length] + "\n... (truncated for display)"

            # Create display banner
            banner = "=" * 80
            title_line = f"JSON WORKFLOW: {title} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

            print(f"\n{banner}")
            print(title_line)
            print(banner)
            print("JSON DATA:")
            print(f"\n{json_str}")
            print(f"\n{banner}\n")

        except Exception as e:
            print(f"Error formatting JSON display: {str(e)}")

    @staticmethod
    def log_upload_step(facility_data: List[Dict], file_metadata: Dict, created_assets: List, unified_assets: Dict = None) -> None:
        """Log upload step with enhanced asset type breakdown"""
        # Analyze asset types in uploaded data
        point_assets = [f for f in facility_data if f.get('AssetType') != 'polygon' and not f.get('geometry')]
        polygon_assets = [f for f in facility_data if f.get('AssetType') == 'polygon' or f.get('geometry')]

        # Extract file extension from filename
        file_name = file_metadata.get('name', 'Unknown')
        file_extension = file_name.split('.')[-1].lower() if '.' in file_name else 'unknown'

        display_data = {
            "step": "UPLOAD ASSET DATA",
            "summary": {
                "total_facilities": len(facility_data),
                "file_uploaded": file_name,
                "file_extension": file_extension,
                "file_size_bytes": file_metadata.get('size', 0),
                "file_size_mb": round(file_metadata.get('size', 0) / (1024*1024), 2) if file_metadata.get('size') else 0,
                "database_records_created": len(created_assets),
                "asset_types": {
                    "point_assets": len(point_assets),
                    "polygon_assets": len(polygon_assets)
                }
            },
            "file_details": {
                "original_filename": file_name,
                "file_type": file_metadata.get('type', 'unknown'),
                "file_extension": file_extension,
                "upload_time": file_metadata.get('upload_time', 'unknown'),
                "file_path": file_metadata.get('file_path', 'not_stored')
            },
            "asset_breakdown": {
                "point_assets_count": len(point_assets),
                "polygon_assets_count": len(polygon_assets),
                "total_assets": len(facility_data)
            },
            "sample_data": {
                "sample_point_asset": point_assets[0] if point_assets else None,
                "sample_polygon_asset": polygon_assets[0] if polygon_assets else None
            },
            "database_records": {
                "created_asset_ids": [asset.id for asset in created_assets] if created_assets else [],
                "total_db_records": len(created_assets)
            }
        }

        # Add unified assets information if available
        if unified_assets and unified_assets.get('metadata'):
            display_data["unified_assets"] = {
                "session_total_assets": unified_assets['metadata'].get('total_assets', 0),
                "total_files_uploaded": len(unified_assets['metadata'].get('files_uploaded', [])),
                "session_asset_types": unified_assets['metadata'].get('asset_types', {}),
                "uploaded_files": unified_assets['metadata'].get('files_uploaded', []),
                "upload_session_id": unified_assets['metadata'].get('upload_session_id', 'unknown')[:8] + '...' if unified_assets['metadata'].get('upload_session_id') else 'unknown'
            }

        SimpleJSONConsole.display_json(display_data, "UPLOAD ASSET DATA")

    @staticmethod
    def log_hazard_selection_step(asset_ids: List, hazards: List, parameters: Dict = None, unified_assets: Dict = None) -> None:
        """Log hazard selection step"""
        display_data = {
            "step": "SELECT HAZARDS AND SCENARIOS",
            "summary": {
                "total_assets_selected": len(asset_ids),
                "hazards_selected": len(hazards),
                "selected_hazards": hazards,
                "parameters_provided": bool(parameters)
            },
            "asset_ids": asset_ids,
            "hazards": hazards,
            "parameters": parameters or {}
        }

        # Add unified assets information if available
        if unified_assets and unified_assets.get('metadata'):
            display_data["unified_assets_info"] = {
                "session_total_assets": unified_assets['metadata'].get('total_assets', 0),
                "total_files_uploaded": len(unified_assets['metadata'].get('files_uploaded', [])),
                "asset_types": unified_assets['metadata'].get('asset_types', {}),
                "session_id": unified_assets['metadata'].get('upload_session_id', 'unknown')[:8] + '...' if unified_assets['metadata'].get('upload_session_id') else 'unknown',
                "uploaded_files": [
                    {"filename": f.get('filename', 'unknown'), "asset_count": f.get('asset_count', 0)}
                    for f in unified_assets['metadata'].get('files_uploaded', [])
                ]
            }

        SimpleJSONConsole.display_json(display_data, "HAZARD SELECTION")

    @staticmethod
    def log_analysis_step(analysis_data: List[Dict], hazards: List, processing_status: str) -> None:
        """Log analysis step"""
        display_data = {
            "step": "CLIMATE HAZARDS ANALYSIS PROCESSING",
            "summary": {
                "assets_being_processed": len(analysis_data),
                "hazards_being_analyzed": hazards,
                "processing_status": processing_status
            },
            "analysis_input_data": analysis_data[:2] if analysis_data else [],
            "hazard_types": hazards
        }
        SimpleJSONConsole.display_json(display_data, "ANALYSIS PROCESSING")

    @staticmethod
    def log_results_step(results_data: List[Dict], columns: List, groups: Dict, asset_count: int) -> None:
        """Log results step"""
        display_data = {
            "step": "HAZARD EXPOSURE RESULTS",
            "summary": {
                "total_results_rows": len(results_data),
                "total_columns": len(columns),
                "column_groups": list(groups.keys()),
                "asset_count": asset_count
            },
            "table_structure": {
                "columns": columns,
                "groups": groups
            },
            "sample_results": results_data[:3] if results_data else []
        }
        SimpleJSONConsole.display_json(display_data, "RESULTS DISPLAY")


# Global instance for easy access
simple_json_console = SimpleJSONConsole()