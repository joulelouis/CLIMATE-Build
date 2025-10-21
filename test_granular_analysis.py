"""
Test script for granular analysis
"""

# Test 1: Import all modules
print("Test 1: Testing imports...")
try:
    from climate_hazards_analysis_v2.granular_analysis import (
        generate_sample_grid,
        query_hazard_for_points,
        classify_hazard_risk,
        consolidate_points_to_clusters,
        calculate_polygon_area_km2
    )
    print("[PASS] Granular analysis imports successful")
except Exception as e:
    print(f"[FAIL] Import error: {e}")

try:
    from climate_hazards_analysis_v2.hazard_raster_config import (
        get_hazard_raster_path,
        get_available_hazards
    )
    print("[PASS] Hazard config imports successful")
except Exception as e:
    print(f"[FAIL] Import error: {e}")

# Test 2: Test grid generation with a sample polygon
print("\nTest 2: Testing grid generation...")
try:
    from shapely.geometry import Polygon

    # Create a sample polygon (roughly 10 km²)
    polygon = Polygon([
        (121.0, 14.5),
        (121.1, 14.5),
        (121.1, 14.6),
        (121.0, 14.6),
        (121.0, 14.5)
    ])

    # Calculate area
    area = calculate_polygon_area_km2(polygon)
    print(f"  Polygon area: {area:.2f} km²")

    # Generate grid with 500m spacing
    sample_points = generate_sample_grid(polygon, grid_spacing_meters=500)
    print(f"  Generated {len(sample_points)} sample points")
    print(f"  [PASS] Grid generation successful")

except Exception as e:
    print(f"  [FAIL] Grid generation error: {e}")

# Test 3: Test risk classification
print("\nTest 3: Testing risk classification...")
try:
    # Test flood classification
    flood_low = classify_hazard_risk(0.3, 'Flood')
    flood_medium = classify_hazard_risk(1.0, 'Flood')
    flood_high = classify_hazard_risk(2.0, 'Flood')
    flood_very_high = classify_hazard_risk(3.0, 'Flood')

    print(f"  Flood 0.3m → {flood_low}")
    print(f"  Flood 1.0m → {flood_medium}")
    print(f"  Flood 2.0m → {flood_high}")
    print(f"  Flood 3.0m → {flood_very_high}")

    assert flood_low == 'Low'
    assert flood_medium == 'Medium'
    assert flood_high == 'High'
    assert flood_very_high == 'Very High'

    print(f"  [PASS] Risk classification successful")

except Exception as e:
    print(f"  [FAIL] Risk classification error: {e}")

# Test 4: Check available hazard rasters
print("\nTest 4: Checking available hazard rasters...")
try:
    available = get_available_hazards()
    print(f"  Available hazards: {available}")

    for hazard in ['Flood', 'Heat', 'Water Stress']:
        path = get_hazard_raster_path(hazard)
        if path:
            print(f"  [PASS] {hazard}: {path}")
        else:
            print(f"  [WARN]  {hazard}: No raster found")

except Exception as e:
    print(f"  [FAIL] Hazard raster check error: {e}")

print("\n" + "="*60)
print("Test Summary:")
print("If all tests passed, the granular analysis is properly configured!")
print("="*60)
