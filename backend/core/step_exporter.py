"""
STEP Exporter Module

This module exports OpenCASCADE solid geometries to STEP format files.
It handles both single solids and compound shapes.
"""

import os
import tempfile
import uuid
from typing import Dict, Any, Optional
from dataclasses import dataclass

from config import OCCT_AVAILABLE

if OCCT_AVAILABLE:
    from OCC.Core.STEPControl import STEPControl_Writer, STEPControl_AsIs
    from OCC.Core.Interface import Interface_Static
    from OCC.Core.IFSelect import IFSelect_ReturnStatus
    from OCC.Core.TopoDS import TopoDS_Shape, TopoDS_Solid, TopoDS_Shell, TopoDS_Compound
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.TCollection import TCollection_AsciiString
    from OCC.Core.Standard import Standard_Failure


@dataclass
class STEPExportResult:
    """Result of STEP export operation"""
    success: bool
    file_path: Optional[str] = None
    error_message: Optional[str] = None
    entities_exported: int = 0
    file_size_bytes: Optional[int] = None


class STEPExporter:
    """
    Exports OpenCASCADE solid models to STEP format files.
    Provides configuration options for STEP export parameters.
    """
    
    def __init__(self):
        if not OCCT_AVAILABLE:
            raise RuntimeError("OpenCASCADE Technology is required for STEP export")
        
        self.writer = None
        self.debug_mode = False
        self._configure_step_export()
    
    def _configure_step_export(self):
        """Configure STEP export parameters for optimal quality"""
        try:
            # Set STEP export parameters
            Interface_Static.SetCVal("write.step.schema", "AP214")
            Interface_Static.SetIVal("write.step.assembly", 1)
            Interface_Static.SetRVal("write.precision.val", 1e-6)
            Interface_Static.SetIVal("write.precision.mode", 1)
            Interface_Static.SetCVal("write.step.unit", "MM")
            Interface_Static.SetIVal("write.surfacecurve.mode", 1)
            
            if self.debug_mode:
                print("STEP export configured with AP214 schema and precision 1e-6")
        except Exception as e:
            if self.debug_mode:
                print(f"Warning: Could not configure STEP export parameters: {e}")
    
    def enable_debug(self, enabled: bool = True):
        """Enable debug mode for detailed logging"""
        self.debug_mode = enabled
    
    def export_shape(self, shape: 'TopoDS_Shape', output_path: str) -> STEPExportResult:
        """
        Export a single shape to STEP file
        
        Args:
            shape: OpenCASCADE shape to export
            output_path: Output file path
            
        Returns:
            STEPExportResult with export status
        """
        try:
            if shape is None or shape.IsNull():
                return STEPExportResult(
                    success=False,
                    error_message="Shape is null or invalid"
                )
            
            # Create STEP writer
            writer = STEPControl_Writer()
            
            # Transfer shape to STEP
            try:
                transfer_result = writer.Transfer(shape, STEPControl_AsIs)
            except Standard_Failure as e:
                return STEPExportResult(
                    success=False,
                    error_message=f"Failed to transfer shape: {e.GetMessageString()}"
                )
            
            if transfer_result != IFSelect_ReturnStatus.IFSelect_RetDone:
                return STEPExportResult(
                    success=False,
                    error_message=f"Transfer failed with status: {transfer_result}"
                )
            
            # Write STEP file
            write_result = writer.Write(output_path)
            
            if write_result != IFSelect_ReturnStatus.IFSelect_RetDone:
                return STEPExportResult(
                    success=False,
                    error_message=f"Write failed with status: {write_result}"
                )
            
            # Get file statistics
            file_size = None
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
            
            return STEPExportResult(
                success=True,
                file_path=output_path,
                entities_exported=1,
                file_size_bytes=file_size
            )
            
        except Exception as e:
            return STEPExportResult(
                success=False,
                error_message=f"STEP export error: {str(e)}"
            )
    
    def export_compound(self, shapes: list, output_path: str) -> STEPExportResult:
        """
        Export multiple shapes as a compound to STEP file
        
        Args:
            shapes: List of OpenCASCADE shapes
            output_path: Output file path
            
        Returns:
            STEPExportResult with export status
        """
        try:
            if not shapes:
                return STEPExportResult(
                    success=False,
                    error_message="No shapes provided"
                )
            
            # Create compound from shapes
            builder = BRep_Builder()
            compound = TopoDS_Compound()
            builder.MakeCompound(compound)
            
            valid_shapes = 0
            for shape in shapes:
                if shape and not shape.IsNull():
                    builder.Add(compound, shape)
                    valid_shapes += 1
            
            if valid_shapes == 0:
                return STEPExportResult(
                    success=False,
                    error_message="No valid shapes found"
                )
            
            # Export the compound
            result = self.export_shape(compound, output_path)
            if result.success:
                result.entities_exported = valid_shapes
            
            return result
            
        except Exception as e:
            return STEPExportResult(
                success=False,
                error_message=f"Compound export error: {str(e)}"
            )
    
    def create_temporary_step_file(self, prefix: str = "export") -> str:
        """
        Create a temporary STEP file path
        
        Args:
            prefix: Prefix for the filename
            
        Returns:
            Path to temporary STEP file
        """
        temp_dir = tempfile.mkdtemp()
        filename = f"{prefix}_{uuid.uuid4().hex[:8]}.step"
        return os.path.join(temp_dir, filename)
    
    def get_export_statistics(self, result: STEPExportResult) -> Dict[str, Any]:
        """
        Get statistics from STEP export result
        
        Args:
            result: STEPExportResult object
            
        Returns:
            Dictionary with export statistics
        """
        return {
            "export_successful": result.success,
            "step_file_path": result.file_path,
            "entities_exported": result.entities_exported,
            "file_size_bytes": result.file_size_bytes,
            "file_exists": os.path.exists(result.file_path) if result.file_path else False
        }