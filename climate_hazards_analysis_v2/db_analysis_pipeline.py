import logging
from typing import Any, Dict, List, Optional, Tuple

from django.db.models import Q

from climate_hazards_analysis.models import Asset

logger = logging.getLogger(__name__)


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _centroid_from_polygon(geometry: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    if not isinstance(geometry, dict):
        return None, None
    geom_type = geometry.get("type")
    coords = geometry.get("coordinates", [])
    if geom_type == "MultiPolygon":
        if coords and isinstance(coords[0], list):
            coords = coords[0]
    elif geom_type != "Polygon":
        return None, None
    if not coords or not isinstance(coords[0], list) or len(coords[0]) < 3:
        return None, None
    ring = coords[0]
    points = ring[:-1] if len(ring) > 1 else ring
    if not points:
        return None, None
    try:
        sum_lng = sum(p[0] for p in points)
        sum_lat = sum(p[1] for p in points)
        n = len(points)
        return sum_lat / n, sum_lng / n
    except Exception:
        return None, None


def _get_session_assets_queryset(request) -> List[Asset]:
    session_key = request.session.session_key
    session_asset_ids = request.session.get("climate_hazards_v2_uploaded_asset_ids", [])
    asset_ids = [str(aid) for aid in session_asset_ids if str(aid).strip()]

    qs = Asset.objects.none()
    if asset_ids:
        qs = Asset.objects.filter(asset_id__in=asset_ids)

    if session_key:
        session_qs = Asset.objects.filter(session_key=session_key)
        qs = session_qs if not asset_ids else Asset.objects.filter(
            Q(asset_id__in=asset_ids) | Q(session_key=session_key)
        )

    assets = list(qs)

    # Keep session IDs in sync with DB for this session
    if session_key:
        db_ids = [str(a.asset_id) for a in assets]
        if set(db_ids) != set(asset_ids):
            request.session["climate_hazards_v2_uploaded_asset_ids"] = db_ids
            request.session.modified = True
            logger.info(
                "DB analysis pipeline refreshed session asset IDs: %s assets",
                len(db_ids),
            )

    return assets


def build_unified_assets_json_from_db(request) -> Optional[Dict[str, Any]]:
    assets = _get_session_assets_queryset(request)
    if not assets:
        return None

    unified_assets: Dict[str, Any] = {
        "metadata": {
            "total_assets": len(assets),
            "upload_session_id": request.session.session_key,
            "created_at": None,
            "files_uploaded": [],
            "asset_types": {"point_assets": 0, "polygon_assets": 0},
        },
        "assets": [],
    }

    files_index: Dict[str, Dict[str, Any]] = {}

    for asset in assets:
        polygon_geometry = asset.polygon_geometry
        asset_lat = _safe_float(asset.latitude)
        asset_lng = _safe_float(asset.longitude)
        if polygon_geometry and (asset_lat is None or asset_lng is None):
            cent_lat, cent_lng = _centroid_from_polygon(polygon_geometry)
            asset_lat = asset_lat if asset_lat is not None else cent_lat
            asset_lng = asset_lng if asset_lng is not None else cent_lng

        asset_type = asset.asset_type or ("polygon" if polygon_geometry else "point")

        asset_data = {
            "database_id": str(asset.asset_id),
            "name": asset.name,
            "latitude": asset_lat,
            "longitude": asset_lng,
            "archetype": asset.archetype,
            "asset_type": asset_type,
            "source": asset.source,
            "created_at": asset.created_at.isoformat() if asset.created_at else None,
            "properties": asset.properties or {},
            "polygon_geometry": polygon_geometry,
        }
        unified_assets["assets"].append(asset_data)

        if asset_type == "polygon":
            unified_assets["metadata"]["asset_types"]["polygon_assets"] += 1
        else:
            unified_assets["metadata"]["asset_types"]["point_assets"] += 1

        props = asset.properties or {}
        filename = props.get("original_filename", "unknown")
        if filename not in files_index:
            files_index[filename] = {
                "filename": filename,
                "file_type": props.get("file_type", "unknown"),
                "upload_id": props.get("file_upload_id", "unknown"),
                "asset_count": 0,
            }
        files_index[filename]["asset_count"] += 1

    unified_assets["metadata"]["files_uploaded"] = list(files_index.values())
    return unified_assets


def build_analysis_payload_from_db(request) -> Optional[Dict[str, Any]]:
    selected_hazards = request.session.get("climate_hazards_v2_selected_hazards", [])
    if not selected_hazards:
        return None

    unified_assets = build_unified_assets_json_from_db(request)
    if not unified_assets:
        return None

    analysis_data = {
        "metadata": {
            "session_id": unified_assets["metadata"]["upload_session_id"],
            "total_assets": unified_assets["metadata"]["total_assets"],
            "selected_hazards": selected_hazards,
            "files_uploaded": unified_assets["metadata"]["files_uploaded"],
            "asset_types": unified_assets["metadata"]["asset_types"],
            "analysis_status": "ready",
            "analysis_method": "db_asset_pipeline",
        },
        "assets_for_analysis": [],
        "polygon_geojson_records": [],
    }

    for asset in unified_assets["assets"]:
        if asset.get("latitude") is None or asset.get("longitude") is None:
            continue
        analysis_asset = {
            "Facility": asset["name"],
            "Lat": float(asset["latitude"]),
            "Long": float(asset["longitude"]),
            "Archetype": asset["archetype"],
            "_file_id": asset.get("properties", {}).get("file_upload_id"),
            "selected_hazards": selected_hazards,
            "Asset_ID": asset["database_id"],
            "asset_id": asset["database_id"],
            "asset_type": asset["asset_type"],
            "source_file": asset.get("properties", {}).get("original_filename", "unknown"),
        }

        if asset.get("polygon_geometry"):
            analysis_asset["polygon_geometry"] = asset["polygon_geometry"]
            analysis_data["polygon_geojson_records"].append(
                {
                    "Facility": asset["name"],
                    "Lat": asset["latitude"],
                    "Long": asset["longitude"],
                    "Asset_ID": str(asset["database_id"]),
                    "geometry": asset["polygon_geometry"],
                }
            )

        analysis_data["assets_for_analysis"].append(analysis_asset)

    if not analysis_data["assets_for_analysis"]:
        return None

    return analysis_data
