"""
FastAPI Endpoint Template

Copy this template when creating new API endpoints.
Replace {Feature} with your feature name (e.g., CourtDetection, VideoAnalysis)
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from pydantic import BaseModel, Field
from typing import Optional, List
import logging

# Setup logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/{feature}")

# ============================================
# Request/Response Models
# ============================================

class {Feature}Request(BaseModel):
    """Request model for {feature} operation"""
    session_id: str = Field(..., description="Session identifier")
    parameter: str = Field(..., description="Main parameter")
    optional_param: Optional[int] = Field(None, description="Optional parameter")
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "abc123",
                "parameter": "value",
                "optional_param": 42
            }
        }

class {Feature}Response(BaseModel):
    """Response model for {feature} operation"""
    success: bool
    message: str
    data: dict
    error: Optional[str] = None

# ============================================
# Endpoints
# ============================================

@router.post("/process", response_model={Feature}Response)
async def process_{feature}(request: {Feature}Request):
    """
    Process {feature} request
    
    Args:
        request: {Feature}Request with parameters
    
    Returns:
        {Feature}Response with results
    
    Raises:
        HTTPException: If processing fails
    """
    try:
        logger.info(f"Processing {feature} for session: {request.session_id}")
        
        # 1. Validate input
        if not request.session_id:
            raise HTTPException(
                status_code=400,
                detail="session_id is required"
            )
        
        # 2. Import and call service layer
        from modules.{module}.service import {Feature}Service
        
        service = {Feature}Service()
        result = service.process(
            session_id=request.session_id,
            parameter=request.parameter,
            optional_param=request.optional_param
        )
        
        # 3. Return success response
        return {Feature}Response(
            success=True,
            message="{Feature} processed successfully",
            data=result
        )
    
    except ValueError as e:
        # Client error (400)
        logger.warning(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    except FileNotFoundError as e:
        # Resource not found (404)
        logger.warning(f"Resource not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    
    except Exception as e:
        # Server error (500)
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/upload")
async def upload_{feature}_file(
    session_id: str = Form(...),
    file: UploadFile = File(...),
    optional_param: Optional[str] = Form(None)
):
    """
    Upload file for {feature} processing
    
    Args:
        session_id: Session identifier
        file: Uploaded file
        optional_param: Optional parameter
    
    Returns:
        Upload result
    """
    try:
        logger.info(f"File upload for session: {session_id}, filename: {file.filename}")
        
        # 1. Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        
        # Check file extension
        allowed_extensions = {'.jpg', '.jpeg', '.png', '.mp4'}
        file_ext = Path(file.filename).suffix.lower()
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: {allowed_extensions}"
            )
        
        # 2. Read file contents
        contents = await file.read()
        
        # Check file size (e.g., max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        if len(contents) > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Max size: {max_size / 1024 / 1024}MB"
            )
        
        # 3. Process file
        from modules.{module}.service import {Feature}Service
        
        service = {Feature}Service()
        result = service.process_file(
            session_id=session_id,
            file_contents=contents,
            filename=file.filename
        )
        
        return {
            "success": True,
            "message": "File uploaded successfully",
            "data": result
        }
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Upload error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{session_id}")
async def get_{feature}_status(session_id: str):
    """
    Get processing status for a session
    
    Args:
        session_id: Session identifier
    
    Returns:
        Status information
    """
    try:
        from modules.{module}.service import {Feature}Service
        
        service = {Feature}Service()
        status = service.get_status(session_id)
        
        if not status:
            raise HTTPException(
                status_code=404,
                detail=f"Session not found: {session_id}"
            )
        
        return {
            "success": True,
            "session_id": session_id,
            "status": status
        }
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Status check error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/session/{session_id}")
async def delete_{feature}_session(session_id: str):
    """
    Delete session and cleanup resources
    
    Args:
        session_id: Session identifier
    
    Returns:
        Deletion confirmation
    """
    try:
        from modules.{module}.service import {Feature}Service
        
        service = {Feature}Service()
        service.cleanup_session(session_id)
        
        return {
            "success": True,
            "message": f"Session {session_id} deleted successfully"
        }
    
    except Exception as e:
        logger.error(f"Cleanup error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Register router in main.py
# ============================================
"""
# In main.py:

from modules.{module}.api_integration import router as {feature}_router

app.include_router({feature}_router)
"""
