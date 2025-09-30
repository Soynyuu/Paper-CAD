#!/usr/bin/env python
"""
Test BREP export with simple shapes to debug CAD compatibility
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCC.Core.BRepTools import BRepTools
from OCC.Core.TopoDS import TopoDS_Shape

def test_brep_export():
    """Test BREP export with a simple box"""
    
    # Create a simple box
    box = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
    
    # Test different export methods
    output_files = []
    
    # Method 1: Direct Write
    try:
        output1 = "test_box_method1.brep"
        success = BRepTools.Write(box, output1)
        print(f"Method 1 (BRepTools.Write): {'Success' if success else 'Failed'}")
        if success and os.path.exists(output1):
            size = os.path.getsize(output1)
            print(f"  File size: {size} bytes")
            output_files.append(output1)
    except Exception as e:
        print(f"Method 1 failed: {e}")
    
    # Method 2: breptools module
    try:
        output2 = "test_box_method2.brep"
        success = BRepTools.breptools.Write(box, output2)
        print(f"Method 2 (BRepTools.breptools.Write): {'Success' if success else 'Failed'}")
        if success and os.path.exists(output2):
            size = os.path.getsize(output2)
            print(f"  File size: {size} bytes")
            output_files.append(output2)
    except Exception as e:
        print(f"Method 2 failed: {e}")
    
    # Method 3: breptools_Write function
    try:
        from OCC.Core.BRepTools import breptools_Write
        output3 = "test_box_method3.brep"
        success = breptools_Write(box, output3)
        print(f"Method 3 (breptools_Write): {'Success' if success else 'Failed'}")
        if success and os.path.exists(output3):
            size = os.path.getsize(output3)
            print(f"  File size: {size} bytes")
            output_files.append(output3)
    except Exception as e:
        print(f"Method 3 failed: {e}")
    
    # Check file headers
    print("\nFile headers:")
    for output_file in output_files:
        if os.path.exists(output_file):
            with open(output_file, 'r') as f:
                header = f.read(100)
                print(f"{output_file}:")
                print(f"  {header[:50]}...")
    
    return output_files

if __name__ == "__main__":
    print("Testing BREP export methods...")
    files = test_brep_export()
    print(f"\nCreated {len(files)} BREP files")
    print("Try opening these files in your CAD software to see which format works.")