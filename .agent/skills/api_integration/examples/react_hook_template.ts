/**
 * React Hook Template
 * 
 * Copy this template when creating new React hooks for API integration.
 * Replace {Feature} with your feature name (e.g., CourtDetection, VideoAnalysis)
 */

import { useState, useCallback, useRef } from 'react';
import { 
    { feature }Action,
    upload{ Feature } File,
        { Feature }Request,
            { Feature }Response 
} from '@/services/{feature}API';

// ============================================
// Hook Interface
// ============================================

interface Use { Feature }Return {
    // State
    loading: boolean;
    error: string | null;
    result: { Feature } Response | null;
    progress: number;

    // Actions
    execute: (request: { Feature }Request) => Promise < { Feature }Response >;
    upload: (sessionId: string, file: File) => Promise < { Feature }Response >;
    reset: () => void;

    // Utilities
    isSuccess: boolean;
    isError: boolean;
}

// ============================================
// Hook Implementation
// ============================================

export function use{ Feature } (): Use{ Feature }Return {
    // State management
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [result, setResult] = useState < { Feature }Response | null > (null);
    const [progress, setProgress] = useState(0);

    // Abort controller for cancellation
    const abortControllerRef = useRef<AbortController | null>(null);

    /**
     * Execute main action
     */
    const execute = useCallback(async (request: { Feature }Request): Promise<{ Feature }Response> => {
        // Reset state
        setLoading(true);
        setError(null);
        setProgress(0);

        // Create abort controller
        abortControllerRef.current = new AbortController();

        try {
            const response = await { feature }Action(request, {
                signal: abortControllerRef.current.signal
            });

            setResult(response);
            setProgress(100);

            return response;
        } catch (err) {
            // Handle abort
            if (err instanceof Error && err.name === 'AbortError') {
                setError('Request cancelled');
                throw new Error('Request cancelled');
            }

            // Handle other errors
            const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
            setError(errorMessage);

            console.error('[use{Feature}] Error:', err);
            throw err;
        } finally {
            setLoading(false);
            abortControllerRef.current = null;
        }
    }, []);

    /**
     * Upload file with progress tracking
     */
    const upload = useCallback(async (sessionId: string, file: File): Promise<{ Feature }Response> => {
        setLoading(true);
        setError(null);
        setProgress(0);

        try {
            const response = await upload{ Feature }File(
                sessionId,
                file,
                (percent) => {
                    setProgress(percent);
                }
            );

            setResult(response);
            setProgress(100);

            return response;
        } catch (err) {
            const errorMessage = err instanceof Error ? err.message : 'Upload failed';
            setError(errorMessage);

            console.error('[use{Feature}] Upload error:', err);
            throw err;
        } finally {
            setLoading(false);
        }
    }, []);

    /**
     * Reset hook state
     */
    const reset = useCallback(() => {
        // Cancel ongoing request
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }

        setLoading(false);
        setError(null);
        setResult(null);
        setProgress(0);
    }, []);

    // Computed properties
    const isSuccess = result !== null && result.success;
    const isError = error !== null;

    return {
        // State
        loading,
        error,
        result,
        progress,

        // Actions
        execute,
        upload,
        reset,

        // Utilities
        isSuccess,
        isError,
    };
}

// ============================================
// Usage Example
// ============================================

/**
 * Example component using the hook
 */
/*
import { use{Feature} } from '@/hooks/use{Feature}';

function {Feature}Component() {
    const { loading, error, result, progress, execute, upload } = use{Feature}();
    const [sessionId, setSessionId] = useState<string>('');
    
    const handleExecute = async () => {
        try {
            const response = await execute({
                session_id: sessionId,
                parameter: 'value',
                optional_param: 42
            });
            
            console.log('Success:', response);
        } catch (err) {
            console.error('Failed:', err);
        }
    };
    
    const handleFileUpload = async (file: File) => {
        try {
            const response = await upload(sessionId, file);
            console.log('Uploaded:', response);
        } catch (err) {
            console.error('Upload failed:', err);
        }
    };
    
    return (
        <div>
            <input 
                value={sessionId}
                onChange={(e) => setSessionId(e.target.value)}
                placeholder="Session ID"
            />
            
            <button onClick={handleExecute} disabled={loading}>
                {loading ? 'Processing...' : 'Execute'}
            </button>
            
            <input 
                type="file"
                onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) handleFileUpload(file);
                }}
                disabled={loading}
            />
            
            {loading && <progress value={progress} max={100} />}
            {error && <p className="error">{error}</p>}
            {result && <pre>{JSON.stringify(result, null, 2)}</pre>}
        </div>
    );
}
*/
