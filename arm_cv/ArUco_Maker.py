import cv2
import cv2.aruco as aruco

# ===================== PARAMETERS =====================
MARKER_ID = 18            # <-- CHANGE THIS (0 to 49)
MARKER_SIZE_MM = 50      # Physical size (mm)
DPI = 120                # Print quality

# ===================== PIXEL SIZE CALCULATION =====================
# 1 inch = 25.4 mm
marker_size_px = int((MARKER_SIZE_MM / 25.4) * DPI)

# ===================== ARUCO DICTIONARY =====================
aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_6X6_50)

# ===================== GENERATE MARKER =====================
marker_img = aruco.generateImageMarker(
    aruco_dict,
    MARKER_ID,
    marker_size_px
)

# ===================== SAVE IMAGE =====================
filename = f"aruco_6x6_id_{MARKER_ID}_50mm.png"
cv2.imwrite(filename, marker_img)

print(f"Saved: {filename}")
print(f"Size: {MARKER_SIZE_MM}mm x {MARKER_SIZE_MM}mm @ {DPI} DPI")
