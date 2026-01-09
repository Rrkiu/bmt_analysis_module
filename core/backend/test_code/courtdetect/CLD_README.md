# Badminton Court Line Detection (CLD)

## 🎯 Overview

Professional computer vision solution for detecting badminton half-court geometry from raw RGB images using an **Anchor-Based Strategy** with Homography extrapolation.

## 🏗️ Algorithm Architecture

### **Step 1: Preprocessing**
- **Color Masking**: HLS color space filtering for white court lines
- **Edge Detection**: Canny edge detector on masked image
- **Morphological Operations**: Noise reduction (closing + opening)

### **Step 2: Line Detection**
- **Hough Transform**: Probabilistic line detection (`HoughLinesP`)
- **Angle Classification**:
  - Horizontal: -10° to +10°
  - Diagonal/Vertical: 30° to 80°

### **Step 3: Geometric Filtering (Anchor Strategy)**
1. **Baseline Detection**: Lowest + longest horizontal line
2. **Side Lines**: Diagonal lines extending from baseline ends
3. **SSL Detection**: First horizontal line above baseline (Short Service Line)

### **Step 4: Homography Extrapolation**
- Map 4 detected points (BL, BR, SSL_R, SSL_L) to real-world coordinates
- Calculate homography matrix
- Extrapolate virtual Net Line (TL, TR)

### **Step 5: Visualization**
- Multi-step output with annotated images
- Performance metrics logging

---

## 📁 Output Files

```
cld_output/
├── step_1_{filename}_white_mask.jpg      # White color filtering result
├── step_2_{filename}_edges.jpg           # Canny edge detection
├── step_3_{filename}_lines.jpg           # All detected Hough lines
├── step_4_{filename}_anchors.jpg         # Highlighted anchors (Baseline, SSL)
├── step_5_{filename}_final.jpg           # Final court overlay
└── result_{filename}.json                # Detection results (JSON)
```

---

## 🚀 Usage

### **Basic Usage**
```bash
cd /mnt/b/cd_p/bmt_demo/backend/test_code/courtdetect
python cld_test_court_detection.py
```

### **Custom Image**
```bash
python cld_test_court_detection.py /path/to/your/image.jpg
```

### **Python API**
```python
from cld_test_court_detection import BadmintonCourtDetector

detector = BadmintonCourtDetector(output_dir="my_output")
results = detector.detect("court_image.jpg")

# Access results
homography = results['homography']
anchors = results['anchors']
performance = results['performance']
```

---

## 📊 Performance Metrics

The script automatically logs:
- **Step-by-step timing** (milliseconds)
- **Total processing time**
- **Performance breakdown** (percentage per step)

Example output:
```
[Perf] Step 1: Preprocessing: 45.23 ms
[Perf] Step 2: Line Detection: 78.12 ms
[Perf] Step 3: Geometric Filtering: 12.34 ms
[Perf] Step 4: Extrapolation: 8.91 ms
[Perf] Total Processing Time: 144.60 ms

📊 Performance Breakdown:
  Step 1: Preprocessing: 45.23 ms (31.3%)
  Step 2: Line Detection: 78.12 ms (54.0%)
  Step 3: Geometric Filtering: 12.34 ms (8.5%)
  Step 4: Extrapolation: 8.91 ms (6.2%)
```

---

## 🎨 Visualization Legend

| Color | Meaning |
|-------|---------|
| 🔴 Red | Baseline (Bottom horizontal line) |
| 🟢 Green | Short Service Line (SSL) |
| 🔵 Blue | Side Lines (Left/Right diagonal) |
| 🟣 Magenta | Virtual Net Line (Extrapolated) |
| 🟡 Yellow | Complete court polygon |
| 🔵 Cyan | Corner points |

---

## 🔧 Configuration

### **Court Dimensions** (in meters)
```python
COURT_WIDTH = 6.1          # Doubles court width
SSL_DISTANCE = 1.98        # Short Service Line from net
BASELINE_DISTANCE = 6.7    # Baseline from net
```

### **Color Filtering** (HLS)
```python
lower_white = [0, 200, 0]    # H, L, S
upper_white = [180, 255, 50]
```

### **Hough Transform Parameters**
```python
rho = 1
theta = np.pi / 180
threshold = 80
minLineLength = 100
maxLineGap = 20
```

---

## 📝 JSON Output Format

```json
{
  "image_points": {
    "BL": [x, y],
    "BR": [x, y],
    "SSL_R": [x, y],
    "SSL_L": [x, y],
    "TL": [x, y],
    "TR": [x, y]
  },
  "world_points": {
    "BL": [-3.05, 6.7],
    "BR": [3.05, 6.7],
    "SSL_R": [3.05, 1.98],
    "SSL_L": [-3.05, 1.98]
  },
  "homography_matrix": [[...], [...], [...]]
}
```

---

## 🐛 Troubleshooting

### **No lines detected**
- Check image quality
- Adjust color filtering thresholds
- Reduce `minLineLength` parameter

### **Baseline not found**
- Ensure bottom of court is visible
- Check horizontal line tolerance (±10°)
- Verify minimum line length (200px)

### **SSL not detected**
- Ensure SSL is visible in image
- Check distance threshold (50px above baseline)
- Adjust minimum line length (150px)

---

## 🎓 Algorithm Details

### **Why Anchor-Based Strategy?**
1. **Robustness**: Top corners often invisible → use visible anchors
2. **Geometric Constraints**: Baseline + SSL define court structure
3. **Extrapolation**: Homography allows virtual point projection

### **Key Innovations**
- **HLS Color Space**: Better white detection than HSV
- **Geometric Filtering**: Physics-based line selection
- **Homography**: Accurate perspective transformation

---

## 📚 Dependencies

```
opencv-python >= 4.5.0
numpy >= 1.19.0
```

---

## 🔬 Future Enhancements

- [ ] Multi-court detection
- [ ] Deep learning integration (YOLOv8)
- [ ] Real-time video processing
- [ ] Automatic parameter tuning
- [ ] Confidence scoring

---

## 📄 License

Professional implementation for badminton court analysis.

---

## 👨‍💻 Author

Senior Computer Vision Engineer
Specialized in sports analytics and geometric computer vision.
