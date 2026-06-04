import cv2
import numpy as np

# Buat gambar kotak putih 100x100 pixel
img = np.ones((100, 100), dtype=np.uint8) * 255
# Gambar lingkaran hitam di tengahnya
cv2.circle(img, (50, 50), 30, (0), -1)

# Simpan sebagai .bmp (karena BMP format murni/tanpa kompresi lossy)
cv2.imwrite("test_gambar.bmp", img)
print("Berhasil membuat test_gambar.bmp")
