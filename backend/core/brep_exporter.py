"""
BREP Exporter Module

This module exports OpenCASCADE solid models to BREP format files.
"""

import os
import tempfile
import uuid
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass

from config import OCCT_AVAILABLE

if OCCT_AVAILABLE:
    from OCC.Core.TopoDS import TopoDS_Shape, TopoDS_Solid, TopoDS_Shell, TopoDS_Compound
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core import BRepTools


@dataclass
class BREPExportResult:
    """Result of BREP export operation"""
    success: bool
    file_path: Optional[str] = None
    error_message: Optional[str] = None
    shapes_exported: int = 0
    file_size_bytes: Optional[int] = None
    export_time: float = 0.0


class BREPExporter:
    """
    Exports OpenCASCADE solid models to BREP format files.
    """
    
    def __init__(self):
        if not OCCT_AVAILABLE:
            raise RuntimeError("OpenCASCADE Technology is required for BREP export")
        
        self.debug_mode = False
    
    def enable_debug(self, enabled: bool = True):
        """Enable debug mode for detailed logging"""
        self.debug_mode = enabled
    
    def export_shape(self, shape: 'TopoDS_Shape', output_path: str) -> BREPExportResult:
        """
        Export a single shape to BREP file
        
        Args:
            shape: OpenCASCADE shape to export
            output_path: Path for output BREP file
            
        Returns:
            BREPExportResult with export status
        """
        start_time = time.time()
        
        try:
            if shape.IsNull():
                return BREPExportResult(
                    success=False,
                    error_message="Shape is null",
                    export_time=time.time() - start_time
                )
            
            # Write BREP file
            success = self._write_brep_file(shape, output_path)
            
            if success:
                file_size = os.path.getsize(output_path) if os.path.exists(output_path) else None
                
                if self.debug_mode:
                    print(f"Successfully exported shape to BREP file: {file_size} bytes")
                
                return BREPExportResult(
                    success=True,
                    file_path=output_path,
                    shapes_exported=1,
                    file_size_bytes=file_size,
                    export_time=time.time() - start_time
                )
            else:
                return BREPExportResult(
                    success=False,
                    error_message="Failed to write BREP file",
                    export_time=time.time() - start_time
                )
        
        except Exception as e:
            return BREPExportResult(
                success=False,
                error_message=f"BREP export error: {str(e)}",
                export_time=time.time() - start_time
            )
    
    def _write_brep_file(self, shape: 'TopoDS_Shape', output_path: str) -> bool:
        """
        Write a TopoDS_Shape to BREP file using OpenCASCADE
        
        Args:
            shape: OpenCASCADE shape to write
            output_path: Output file path
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if shape.IsNull():
                if self.debug_mode:
                    print("Cannot write null shape to BREP file")
                return False
            
            # Use BRepTools to write the BREP file
            # Try different API methods for compatibility
            try:
                # Method 1: Direct Write method (newer API)
                success = BRepTools.Write(shape, output_path)
            except (AttributeError, TypeError):
                try:
                    # Method 2: Using breptools module (older API)
                    success = BRepTools.breptools.Write(shape, output_path)
                except (AttributeError, TypeError):
                    # Method 3: Using BRepTools_Write function
                    from OCC.Core.BRepTools import breptools_Write
                    success = breptools_Write(shape, output_path)
            
            if not success:
                if self.debug_mode:
                    print(f"BRepTools.Write returned False for {output_path}")
                return False
            
            # Verify file was created and has content
            if not os.path.exists(output_path):
                if self.debug_mode:
                    print(f"BREP file was not created: {output_path}")
                return False
            
            file_size = os.path.getsize(output_path)
            if file_size == 0:
                if self.debug_mode:
                    print(f"BREP file is empty: {output_path}")
                return False
            
            return True
        
        except Exception as e:
            if self.debug_mode:
                print(f"Error writing BREP file {output_path}: {e}")
            return False
    
    def create_temporary_output_path(self, prefix: str = "export") -> str:
        """Create a temporary output file path for BREP files"""
        temp_dir = tempfile.mkdtemp()
        filename = f"{prefix}_{uuid.uuid4().hex[:8]}.brep"
        return os.path.join(temp_dir, filename)
    
    def get_export_statistics(self, result: BREPExportResult) -> Dict[str, Any]:
        """Get statistics from BREP export result"""
        return {
            "export_successful": result.success,
            "brep_file_path": result.file_path,
            "shapes_exported": result.shapes_exported,
            "file_size_bytes": result.file_size_bytes,
            "export_time_seconds": result.export_time,
            "file_exists": os.path.exists(result.file_path) if result.file_path else False
        }