"""
JSON Console Logger for Climate Hazards Analysis

This module provides utilities to display JSON data in the console at each step
of the workflow: upload, hazard selection, and results.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List

# Configure console logger
console_logger = logging.getLogger('json_workflow_console')
console_logger.setLevel(logging.INFO)

# Create console handler if it doesn't exist
if not console_logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    console_logger.addHandler(console_handler)


class JSONConsoleLogger:
    """Utility class for logging JSON data to console"""

    @staticmethod
    def format_json_display(data: Any, title: str, max_length: int = 500) -> None:
        """
        Display JSON data in console with formatted output

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
            banner = f"{'='*60}"
            title_line = f"🔍 {title} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

            console_logger.info(f"\n{banner}")
            console_logger.info(f"{title_line}")
            console_logger.info(f"{'='*60}")
            console_logger.info(f"📋 JSON DATA:")
            console_logger.info(f"\n{json_str}")
            console_logger.info(f"\n{'='*60}\n")

        except Exception as e:
            console_logger.error(f"Error formatting JSON display: {str(e)}")

    @staticmethod
    def log_upload_step(facility_data: List[Dict], file_metadata: Dict, created_assets: List) -> None:
        """Log JSON data for upload step"""

        display_data = {
            "step": "UPLOAD ASSET DATA",
            "summary": {
                "total_facilities": len(facility_data),
                "file_uploaded": file_metadata.get('name', 'Unknown'),
                "file_size": file_metadata.get('size', 0),
                "database_records_created": len(created_assets)
            },
            "file_metadata": file_metadata,
            "sample_facilities": facility_data[:2] if facility_data else [],
            "created_asset_ids": [asset.id for asset in created_assets] if created_assets else []
        }

        JSONConsoleLogger.format_json_display(display_data, "UPLOAD ASSET DATA - JSON WORKFLOW")

    @staticmethod
    def log_hazard_selection_step(asset_ids: List, hazards: List, parameters: Dict = None) -> None:
        """Log JSON data for hazard selection step"""

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

        JSONConsoleLogger.format_json_display(display_data, "HAZARD SELECTION - JSON WORKFLOW")

    @staticmethod
    def log_analysis_step(analysis_data: List[Dict], hazards: List, processing_status: str) -> None:
        """Log JSON data for analysis processing step"""

        display_data = {
            "step": "CLIMATE HAZARDS ANALYSIS PROCESSING",
            "summary": {
                "assets_being_processed": len(analysis_data),
                "hazards_being_analyzed": hazards,
                "processing_status": processing_status
            },
            "analysis_input_data": analysis_data[:2] if analysis_data else [],  # Show sample
            "hazard_types": hazards
        }

        JSONConsoleLogger.format_json_display(display_data, "ANALYSIS PROCESSING - JSON WORKFLOW")

    @staticmethod
    def log_results_step(results_data: List[Dict], columns: List, groups: Dict, asset_count: int) -> None:
        """Log JSON data for results step"""

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

        JSONConsoleLogger.format_json_display(display_data, "RESULTS DISPLAY - JSON WORKFLOW")

    @staticmethod
    def log_asset_database_check(asset_count: int, with_hazards: int, with_results: int) -> None:
        """Log database state check"""

        display_data = {
            "step": "DATABASE STATE CHECK",
            "database_summary": {
                "total_assets": asset_count,
                "assets_with_hazard_selections": with_hazards,
                "assets_with_analysis_results": with_results,
                "check_timestamp": datetime.now().isoformat()
            }
        }

        JSONConsoleLogger.format_json_display(display_data, "DATABASE STATE - JSON WORKFLOW")


# Global instance for easy access
json_logger = JSONConsoleLogger()


def log_workflow_step(step_name: str, data: Any, additional_info: Dict = None) -> None:
    """
    Generic function to log any workflow step

    Args:
        step_name: Name of the workflow step
        data: Main data to log
        additional_info: Additional information to include
    """
    display_data = {
        "step": step_name.upper(),
        "timestamp": datetime.now().isoformat(),
        "data": data
    }

    if additional_info:
        display_data["additional_info"] = additional_info

    JSONConsoleLogger.format_json_display(display_data, f"{step_name.upper()} - JSON WORKFLOW")