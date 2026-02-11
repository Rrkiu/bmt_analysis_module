---
name: API Integration Patterns
description: Standardized patterns for backend-frontend API integration in the badminton analysis system
---

# API Integration Skill

## Purpose
Provide standardized patterns for creating and integrating API endpoints between the FastAPI backend and React frontend. Ensures consistent error handling, type safety, and maintainable code structure.

## Architecture Overview

```
Frontend (React + TypeScript)          Backend (FastAPI + Python)
Port: 5173                             Port: 8000
─────────────────────────────────────────────────────────────
                                      
┌─────────────────┐                   ┌──────────────────┐
│ Component       │                   │ API Router       │
│ (Page/Feature)  │                   │ (main.py)        │
└────────┬────────┘                   └────────┬─────────┘
         │                                     │
         │ uses                                │ routes to
         ▼                                     ▼
┌─────────────────┐                   ┌──────────────────┐
│ Custom Hook     │                   │ Module API       │
│ (useFeature)    │                   │ (api_integration)│
└────────┬────────┘                   └────────┬─────────┘
         │                                     │
         │ calls                               │ uses
         ▼                                     ▼
┌─────────────────┐    HTTP Request    ┌──────────────────┐
│ API Service     │ ─────────────────→ │ Service Layer    │
│ (featureAPI.ts) │ ←───────────────── │ (service.py)     │
└─────────────────┘    JSON Response   └──────────────────┘
```

## API Endpoint Pattern

### Backend: FastAPI Endpoint

**Location**: `core/backend/main.py` or `core/backend/modules/{module}/api_integration.py`

```python
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api")

# Request/Response Models
class FeatureRequest(BaseModel):
    session_id: str
    parameter: str
    optional_param: Optional[int] = None

class FeatureResponse(BaseModel):
    success: bool
    message: str
    data: dict

# Endpoint
@router.post("/feature/action", response_model=FeatureResponse)
async def perform_action(request: FeatureRequest):
    """
    Perform specific action
    
    Args:
        request: Feature request parameters
    
    Returns:
        FeatureResponse with results
    """
    try:
        # 1. Validate input
        if not request.session_id:
            raise HTTPException(status_code=400, detail="session_id required")
        
        # 2. Call service layer
        from modules.feature.service import FeatureService
        service = FeatureService()
        result = service.process(request.parameter)
        
        # 3. Return response
        return FeatureResponse(
            success=True,
            message="Action completed successfully",
            data=result
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# File upload endpoint
@router.post("/feature/upload")
async def upload_file(
    session_id: str,
    file: UploadFile = File(...)
):
    """Handle file upload"""
    try:
        # Read file
        contents = await file.read()
        
        # Process
        from modules.feature.service import FeatureService
        service = FeatureService()
        result = service.process_file(session_id, contents)
        
        return {
            "success": True,
            "data": result
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### Frontend: TypeScript API Client

**Location**: `core/birdie-buddies-frontend/src/services/{feature}API.ts`

```typescript
/**
 * Feature API Client
 */

const API_BASE_URL = import.meta.env.VITE_ANALYSIS_API_BASE_URL || 'http://localhost:8000';

// ============================================
// Types (match backend Pydantic models)
// ============================================

export interface FeatureRequest {
    session_id: string;
    parameter: string;
    optional_param?: number;
}

export interface FeatureResponse {
    success: boolean;
    message: string;
    data: {
        result_field: string;
        numeric_value: number;
    };
}

// ============================================
// API Functions
// ============================================

/**
 * Perform action via API
 */
export async function performAction(
    request: FeatureRequest
): Promise<FeatureResponse> {
    const response = await fetch(`${API_BASE_URL}/api/feature/action`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`API Error: ${response.statusText} - ${JSON.stringify(errorData)}`);
    }

    return response.json();
}

/**
 * Upload file
 */
export async function uploadFile(
    sessionId: string,
    file: File
): Promise<FeatureResponse> {
    const formData = new FormData();
    formData.append('session_id', sessionId);
    formData.append('file', file);

    const response = await fetch(`${API_BASE_URL}/api/feature/upload`, {
        method: 'POST',
        body: formData,  // No Content-Type header for FormData
    });

    if (!response.ok) {
        throw new Error(`Upload failed: ${response.statusText}`);
    }

    return response.json();
}

/**
 * Get resource URL
 */
export function getResourceUrl(sessionId: string, type: string): string {
    return `${API_BASE_URL}/api/feature/resource/${sessionId}/${type}`;
}
```

### Frontend: React Hook

**Location**: `core/birdie-buddies-frontend/src/hooks/useFeature.ts`

```typescript
import { useState, useCallback } from 'react';
import { performAction, uploadFile, FeatureRequest, FeatureResponse } from '@/services/featureAPI';

export function useFeature() {
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [result, setResult] = useState<FeatureResponse | null>(null);

    const execute = useCallback(async (request: FeatureRequest) => {
        setLoading(true);
        setError(null);
        
        try {
            const response = await performAction(request);
            setResult(response);
            return response;
        } catch (err) {
            const errorMessage = err instanceof Error ? err.message : 'Unknown error';
            setError(errorMessage);
            throw err;
        } finally {
            setLoading(false);
        }
    }, []);

    const upload = useCallback(async (sessionId: string, file: File) => {
        setLoading(true);
        setError(null);
        
        try {
            const response = await uploadFile(sessionId, file);
            setResult(response);
            return response;
        } catch (err) {
            const errorMessage = err instanceof Error ? err.message : 'Unknown error';
            setError(errorMessage);
            throw err;
        } finally {
            setLoading(false);
        }
    }, []);

    return {
        loading,
        error,
        result,
        execute,
        upload,
    };
}
```

### Frontend: Component Usage

```typescript
import { useFeature } from '@/hooks/useFeature';

function FeatureComponent() {
    const { loading, error, result, execute } = useFeature();

    const handleAction = async () => {
        try {
            await execute({
                session_id: 'abc123',
                parameter: 'value',
                optional_param: 42
            });
            
            console.log('Success:', result);
        } catch (err) {
            console.error('Error:', error);
        }
    };

    return (
        <div>
            <button onClick={handleAction} disabled={loading}>
                {loading ? 'Processing...' : 'Execute'}
            </button>
            {error && <p className="error">{error}</p>}
            {result && <p>Result: {result.data.result_field}</p>}
        </div>
    );
}
```

## Common Patterns

### 1. File Upload with Progress

```typescript
export async function uploadWithProgress(
    file: File,
    onProgress: (percent: number) => void
): Promise<FeatureResponse> {
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        
        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                const percent = (e.loaded / e.total) * 100;
                onProgress(percent);
            }
        });
        
        xhr.addEventListener('load', () => {
            if (xhr.status === 200) {
                resolve(JSON.parse(xhr.responseText));
            } else {
                reject(new Error(`Upload failed: ${xhr.statusText}`));
            }
        });
        
        xhr.addEventListener('error', () => {
            reject(new Error('Network error'));
        });
        
        const formData = new FormData();
        formData.append('file', file);
        
        xhr.open('POST', `${API_BASE_URL}/api/feature/upload`);
        xhr.send(formData);
    });
}
```

### 2. Streaming Response (Video Analysis)

```python
# Backend
from fastapi.responses import StreamingResponse

@router.post("/feature/stream")
async def stream_results(request: FeatureRequest):
    async def generate():
        for i in range(10):
            data = {"frame": i, "result": f"data_{i}"}
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(0.1)
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )
```

```typescript
// Frontend
export async function streamResults(
    request: FeatureRequest,
    onData: (data: any) => void
): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/feature/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
    });

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    while (true) {
        const { done, value } = await reader!.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n\n');

        for (const line of lines) {
            if (line.startsWith('data: ')) {
                const data = JSON.parse(line.slice(6));
                onData(data);
            }
        }
    }
}
```

### 3. Error Handling Pattern

```python
# Backend: Custom exception handler
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "error": str(exc),
            "detail": "Invalid input parameters"
        }
    )
```

```typescript
// Frontend: Centralized error handling
export class APIError extends Error {
    constructor(
        public statusCode: number,
        public detail: string,
        message: string
    ) {
        super(message);
        this.name = 'APIError';
    }
}

export async function handleAPIResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new APIError(
            response.status,
            errorData.detail || response.statusText,
            `API Error: ${response.status}`
        );
    }
    return response.json();
}
```

## Environment Configuration

### Backend: `.env`
```bash
# CORS settings
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# File upload limits
MAX_UPLOAD_SIZE=10485760  # 10MB

# API settings
API_PREFIX=/api
```

### Frontend: `.env`
```bash
VITE_ANALYSIS_API_BASE_URL=http://localhost:8000
```

## Testing

### Backend: pytest
```python
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_perform_action():
    response = client.post(
        "/api/feature/action",
        json={
            "session_id": "test123",
            "parameter": "value"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
```

### Frontend: Vitest
```typescript
import { describe, it, expect, vi } from 'vitest';
import { performAction } from '@/services/featureAPI';

describe('Feature API', () => {
    it('should call API correctly', async () => {
        global.fetch = vi.fn(() =>
            Promise.resolve({
                ok: true,
                json: () => Promise.resolve({ success: true, data: {} })
            })
        );

        const result = await performAction({
            session_id: 'test',
            parameter: 'value'
        });

        expect(result.success).toBe(true);
    });
});
```

## Best Practices

1. **Type Safety**: Always define TypeScript interfaces matching Pydantic models
2. **Error Handling**: Use try-catch in hooks, HTTPException in backend
3. **Loading States**: Track loading/error/success in hooks
4. **CORS**: Configure properly for development and production
5. **Validation**: Validate on both frontend (UX) and backend (security)
6. **Documentation**: Document all endpoints with docstrings
7. **Versioning**: Use API prefix for future versioning (`/api/v1/...`)

## Related Files

- Backend main: `core/backend/main.py`
- Example API: `core/backend/modules/court_detection/api_integration.py`
- Frontend service: `core/birdie-buddies-frontend/src/services/analysisAPI.ts`
- Example hook: `core/birdie-buddies-frontend/src/hooks/useCalibration.ts`
