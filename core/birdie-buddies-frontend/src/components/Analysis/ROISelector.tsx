/**
 * ROISelector.tsx
 * 코트 검출을 위한 ROI(Region of Interest) 선택 컴포넌트
 * react-image-crop 라이브러리 사용
 */

import { useState, useRef } from 'react';
import ReactCrop, { type Crop, type PixelCrop } from 'react-image-crop';
import 'react-image-crop/dist/ReactCrop.css';
import './ROISelector.css';

interface ROISelectorProps {
    imageUrl: string;
    onROIConfirm: (roi: { x: number; y: number; width: number; height: number }) => void;
    onSkip: () => void;
}

export function ROISelector({ imageUrl, onROIConfirm, onSkip }: ROISelectorProps) {
    const [crop, setCrop] = useState<Crop>();
    const [completedCrop, setCompletedCrop] = useState<PixelCrop>();
    const imgRef = useRef<HTMLImageElement>(null);


    /**
     * 이미지 로드 시 초기 ROI 가이드 설정
     * 이미지 중앙 80% 영역을 기본 ROI로 제공
     */
    const onImageLoad = () => {
        // 초기 ROI: 이미지 중앙 80% 영역
        const initialCrop: Crop = {
            unit: '%',
            x: 10,
            y: 10,
            width: 80,
            height: 80,
        };

        setCrop(initialCrop);
        console.log('[ROISelector] Initial ROI guide set:', initialCrop);
    };


    /**
     * ROI 확인 버튼 클릭
     */
    const handleConfirm = () => {
        if (!completedCrop || !imgRef.current) {
            alert('ROI 영역을 선택해주세요.');
            return;
        }

        const scaleX = imgRef.current.naturalWidth / imgRef.current.width;
        const scaleY = imgRef.current.naturalHeight / imgRef.current.height;

        // 실제 이미지 좌표로 변환
        const roi = {
            x: Math.round(completedCrop.x * scaleX),
            y: Math.round(completedCrop.y * scaleY),
            width: Math.round(completedCrop.width * scaleX),
            height: Math.round(completedCrop.height * scaleY),
        };

        console.log('[ROISelector] ROI confirmed:', roi);
        onROIConfirm(roi);
    };

    /**
     * 전체 영역 선택 (ROI 스킵)
     */
    const handleSelectAll = () => {
        if (!imgRef.current) return;

        const roi = {
            x: 0,
            y: 0,
            width: imgRef.current.naturalWidth,
            height: imgRef.current.naturalHeight,
        };

        console.log('[ROISelector] Full image selected (ROI skipped):', roi);
        onROIConfirm(roi);
    };

    return (
        <div className="roi-selector">
            <h2>📐 코트 영역 선택 (ROI)</h2>

            <div className="roi-instructions">
                <p className="roi-hint">
                    💡 <strong>코트 전체가 포함되도록</strong> 박스를 조정하세요.
                </p>
                <ul className="roi-tips">
                    <li>✓ 박스를 드래그하여 위치 조정</li>
                    <li>✓ 모서리를 드래그하여 크기 조정</li>
                    <li>✓ 코트 라인이 모두 포함되도록 설정</li>
                    <li>⚠️ 사람, 짐 등 불필요한 영역은 제외</li>
                </ul>
            </div>

            <div className="roi-crop-container">
                <ReactCrop
                    crop={crop}
                    onChange={(c) => setCrop(c)}
                    onComplete={(c) => setCompletedCrop(c)}
                    minWidth={100}
                    minHeight={100}
                >
                    <img
                        ref={imgRef}
                        src={imageUrl}
                        alt="Court Image"
                        onLoad={onImageLoad}
                        style={{ maxWidth: '100%', maxHeight: '70vh' }}
                    />
                </ReactCrop>
            </div>

            {completedCrop && (
                <div className="roi-info">
                    <p>
                        선택된 영역: {completedCrop.width.toFixed(0)} × {completedCrop.height.toFixed(0)} px
                    </p>
                </div>
            )}

            <div className="roi-actions">
                <button onClick={handleConfirm} className="roi-confirm-button" disabled={!completedCrop}>
                    ✓ ROI 확인 및 자동 검출 시작
                </button>
                <button onClick={handleSelectAll} className="roi-skip-button">
                    전체 영역 선택 (ROI 스킵)
                </button>
                <button onClick={onSkip} className="roi-cancel-button">
                    취소
                </button>
            </div>
        </div>
    );
}
