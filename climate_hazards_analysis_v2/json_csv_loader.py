"""
JSON/CSV Data Loader for Climate Hazards Analysis

This module provides utilities to load analysis results from either JSON or CSV files,
with JSON preferred as part of the gradual migration strategy.
"""

import json
import os
import pandas as pd
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


class JSONCSVLoader:
    """Utility class for loading data from JSON or CSV with fallback"""

    @staticmethod
    def load_analysis_results(json_path: str = None) -> Tuple[List[Dict], List[str]]:
        """
        Load analysis results from JSON file (JSON-only workflow)

        Args:
            json_path: Path to JSON file

        Returns:
            Tuple of (data_list, columns_list)
        """
        data = []
        columns = []
        source_used = None

        try:
            # Load from JSON file (JSON-only workflow)
            if json_path and os.path.exists(json_path):
                data, columns, source_used = JSONCSVLoader._load_from_json(json_path)
                logger.info(f"Loaded analysis results from JSON: {json_path}")
            else:
                raise FileNotFoundError(f"JSON file not found: {json_path}")

            logger.info(f"Successfully loaded {len(data)} records from {source_used}")
            return data, columns

        except Exception as e:
            logger.error(f"Error loading analysis results: {str(e)}")
            raise

    @staticmethod
    def _load_from_json(json_path: str) -> Tuple[List[Dict], List[str], str]:
        """Load data from JSON file"""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)

            # Check if it's the new structured format or legacy format
            if isinstance(json_data, dict) and 'data' in json_data:
                # New structured format
                data = json_data['data']
                metadata = json_data.get('metadata', {})
                source_used = f"JSON (structured) - {metadata.get('total_facilities', len(data))} facilities"
            else:
                # Legacy format (direct list)
                data = json_data if isinstance(json_data, list) else [json_data]
                source_used = f"JSON (legacy) - {len(data)} records"

            # Extract columns from first record
            if data:
                columns = list(data[0].keys())
            else:
                columns = []

            return data, columns, source_used

        except Exception as e:
            logger.error(f"Error loading from JSON {json_path}: {str(e)}")
            raise

    @staticmethod
    def _load_from_csv(csv_path: str) -> Tuple[List[Dict], List[str], str]:
        """Load data from CSV file"""
        try:
            df = pd.read_csv(csv_path, encoding='utf-8')

            # Handle metadata lines that start with #
            if df.empty:
                # Try to skip metadata lines
                df = pd.read_csv(csv_path, encoding='utf-8', comment='#')

            data = df.to_dict(orient='records')
            columns = df.columns.tolist()
            source_used = f"CSV - {len(data)} records"

            return data, columns, source_used

        except Exception as e:
            logger.error(f"Error loading from CSV {csv_path}: {str(e)}")
            raise

    @staticmethod
    def get_analysis_file_paths(analysis_result: Dict[str, Any]) -> Dict[str, Optional[str]]:
        """
        Extract JSON file path from analysis result dictionary (JSON-only workflow)

        Args:
            analysis_result: Result from generate_climate_hazards_analysis

        Returns:
            Dictionary with json_path
        """
        base_dir = None

        # Extract base directory from JSON path
        json_path = analysis_result.get('combined_json_path')
        if json_path:
            base_dir = os.path.dirname(json_path)

        # If no base directory found, use default
        if not base_dir:
            from django.conf import settings
            base_dir = os.path.join(settings.BASE_DIR, 'climate_hazards_analysis', 'static', 'input_files')

        # Construct JSON path if not provided
        if not json_path and base_dir:
            json_path = os.path.join(base_dir, 'combined_output.json')

        return {
            'json_path': json_path if os.path.exists(json_path) else None,
            'base_dir': base_dir
        }

    @staticmethod
    def log_file_status(json_path: str) -> None:
        """Log the status of JSON file for debugging"""
        logger.info("=== JSON FILE STATUS CHECK ===")

        if json_path:
            if os.path.exists(json_path):
                size = os.path.getsize(json_path)
                logger.info(f"✓ JSON file exists: {json_path} ({size} bytes)")
            else:
                logger.warning(f"✗ JSON file missing: {json_path}")

        logger.info("=== END JSON FILE STATUS ===")


# Global instance for easy access
json_csv_loader = JSONCSVLoader()