---
description: Add new API endpoint with frontend integration
---

# Add New API Endpoint Workflow

This workflow guides you through adding a new API endpoint with proper backend-frontend integration, type safety, and error handling.

## Steps

### 1. Define API Contract

First, decide on the endpoint specification:

**Example**: Add a "Get Match Statistics" endpoint

```
Endpoint: POST /api/analysis/match-stats
Request: { session_id: string, video_id: string }
Response: { success: bool, stats: {...} }
```

### 2. Create Backend Endpoint

**Location**: `core/backend/modules/{module}/api_integration.py`

```bash
cd /mnt/b/cd_p/bmt_demo/core/backend/modules/{module}
```

**Option A**: Copy template
```bash
cp /mnt/b/cd_p/bmt_demo/.agent/skills/api_integration/examples/endpoint_template.py \
   api_integration.py
```

**Option B**: Create from scratch using the template as reference

**Edit the file**:
1. Replace `{Feature}` with your feature name (e.g., `MatchStats`)
2. Define request/response Pydantic models
3. Implement endpoint logic
4. Add error handling

**Example**:
```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/analysis")

class MatchStatsRequest(BaseModel):
    session_id: str
    video_id: str

class MatchStatsResponse(BaseModel):
    success: bool
    stats: dict

@router.post("/match-stats", response_model=MatchStatsResponse)
async def get_match_stats(request: MatchStatsRequest):
    try:
        # Implementation
        stats = calculate_stats(request.video_id)
        return MatchStatsResponse(success=True, stats=stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 3. Register Router in Main App

**Edit**: `core/backend/main.py`

```python
# Add import
from modules.{module}.api_integration import router as {module}_router

# Register router
app.include_router({module}_router)
```

### 4. Test Backend Endpoint

**Start backend**:
```bash
cd /mnt/b/cd_p/bmt_demo/core/backend
python main.py
```

**Test with curl**:
```bash
curl -X POST http://localhost:8000/api/analysis/match-stats \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test123", "video_id": "video1"}'
```

**Expected**: JSON response with success=true

**Check API docs**: http://localhost:8000/docs

### 5. Create Frontend API Client

**Location**: `core/birdie-buddies-frontend/src/services/{module}API.ts`

**Edit or create the file**:

```typescript
const API_BASE_URL = import.meta.env.VITE_ANALYSIS_API_BASE_URL || 'http://localhost:8000';

// Types (match backend models)
export interface MatchStatsRequest {
    session_id: string;
    video_id: string;
}

export interface MatchStatsResponse {
    success: boolean;
    stats: {
        total_rallies: number;
        average_rally_length: number;
        // ... other stats
    };
}

// API function
export async function getMatchStats(
    request: MatchStatsRequest
): Promise<MatchStatsResponse> {
    const response = await fetch(`${API_BASE_URL}/api/analysis/match-stats`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
    });

    if (!response.ok) {
        throw new Error(`API Error: ${response.statusText}`);
    }

    return response.json();
}
```

### 6. Create React Hook (Optional but Recommended)

**Location**: `core/birdie-buddies-frontend/src/hooks/useMatchStats.ts`

**Copy template**:
```bash
cp /mnt/b/cd_p/bmt_demo/.agent/skills/api_integration/examples/react_hook_template.ts \
   core/birdie-buddies-frontend/src/hooks/useMatchStats.ts
```

**Edit the file**:
1. Replace `{Feature}` with `MatchStats`
2. Import your API functions
3. Customize state management as needed

### 7. Use in Component

**Example**: `core/birdie-buddies-frontend/src/pages/Analysis/StatsPage.tsx`

```typescript
import { useMatchStats } from '@/hooks/useMatchStats';

function StatsPage() {
    const { loading, error, result, execute } = useMatchStats();
    const [sessionId, setSessionId] = useState('');
    const [videoId, setVideoId] = useState('');

    const handleGetStats = async () => {
        try {
            await execute({ session_id: sessionId, video_id: videoId });
        } catch (err) {
            console.error('Failed to get stats:', err);
        }
    };

    return (
        <div>
            <input value={sessionId} onChange={(e) => setSessionId(e.target.value)} />
            <input value={videoId} onChange={(e) => setVideoId(e.target.value)} />
            <button onClick={handleGetStats} disabled={loading}>
                {loading ? 'Loading...' : 'Get Stats'}
            </button>
            {error && <p className="error">{error}</p>}
            {result && <pre>{JSON.stringify(result.stats, null, 2)}</pre>}
        </div>
    );
}
```

### 8. Test Frontend Integration

**Start frontend**:
```bash
cd /mnt/b/cd_p/bmt_demo/core/birdie-buddies-frontend
npm run dev
```

**Test in browser**:
1. Navigate to your page (e.g., http://localhost:5173/analysis/stats)
2. Fill in form fields
3. Click button
4. Check browser console for errors
5. Verify response displays correctly

### 9. Add Error Handling

**Backend**: Add specific error cases
```python
if not session_exists(request.session_id):
    raise HTTPException(status_code=404, detail="Session not found")

if not video_exists(request.video_id):
    raise HTTPException(status_code=404, detail="Video not found")
```

**Frontend**: Handle specific errors
```typescript
try {
    await execute(request);
} catch (err) {
    if (err.message.includes('404')) {
        setError('Session or video not found');
    } else {
        setError('An unexpected error occurred');
    }
}
```

### 10. Document the Endpoint

**Add to README** or API documentation:

```markdown
## Match Statistics API

**Endpoint**: `POST /api/analysis/match-stats`

**Request**:
```json
{
    "session_id": "abc123",
    "video_id": "video1"
}
```

**Response**:
```json
{
    "success": true,
    "stats": {
        "total_rallies": 45,
        "average_rally_length": 12.3
    }
}
```
```

## Checklist

- [ ] Backend endpoint created with Pydantic models
- [ ] Router registered in main.py
- [ ] Backend tested with curl
- [ ] Frontend API client created with TypeScript types
- [ ] React hook created (optional)
- [ ] Component integration tested
- [ ] Error handling implemented
- [ ] API documented

## Related Skills

- API Integration: `.agent/skills/api_integration/SKILL.md`
- Templates: `.agent/skills/api_integration/examples/`
