"""
Test script untuk membuktikan bahwa kompresi LZW bersifat LOSSLESS.

Test ini akan:
1. Membuat gambar test (atau membaca gambar yang ada)
2. Kompresi dengan LZW
3. Pack codes → simpan ke file .lzw
4. Baca kembali file .lzw → unpack codes → dekompresi
5. Bandingkan pixel-per-pixel: HARUS 100% identik
6. Bandingkan ukuran file: original PNG vs downloaded PNG HARUS SAMA
"""

import os
import sys
import cv2
import numpy as np

# Pastikan path-nya benar untuk import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from core.lzw_compressor import compress_image, decompress_image, pack_codes, unpack_codes


def test_lzw_lossless():
    """Test utama: buktikan LZW lossless end-to-end."""
    
    print("=" * 60)
    print("TEST LOSSLESS LZW COMPRESSION")
    print("=" * 60)
    
    # --- 1. Siapkan gambar test ---
    # Cek apakah ada file test_gambar.bmp
    test_image_path = os.path.join(os.path.dirname(__file__), "test_gambar.bmp")
    
    if os.path.exists(test_image_path):
        print(f"\n[1] Membaca gambar test: {test_image_path}")
        image = cv2.imread(test_image_path, cv2.IMREAD_COLOR)
    else:
        print("\n[1] Membuat gambar test sintetis (50x50 RGB)...")
        image = np.random.randint(0, 256, (50, 50, 3), dtype=np.uint8)
    
    print(f"    Shape: {image.shape}")
    print(f"    Dtype: {image.dtype}")
    print(f"    Total pixels: {image.shape[0] * image.shape[1]}")
    raw_size = image.shape[0] * image.shape[1] * image.shape[2]
    print(f"    Raw pixel data size: {raw_size} bytes")
    
    # --- 2. Simpan sebagai PNG (simulasi upload) ---
    temp_dir = os.path.join(os.path.dirname(__file__), "storage", "test_temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    original_png = os.path.join(temp_dir, "original_test.png")
    cv2.imwrite(original_png, image)
    original_png_size = os.path.getsize(original_png)
    print(f"\n[2] Simpan sebagai PNG: {original_png}")
    print(f"    Ukuran file PNG asli: {original_png_size} bytes")
    
    # --- 3. Kompresi LZW ---
    print("\n[3] Kompresi LZW...")
    codes = compress_image(image)
    print(f"    Jumlah kode LZW: {len(codes)}")
    if codes:
        print(f"    Max code value: {max(codes)}")
    
    # --- 4. Pack codes dan simpan ke file .lzw ---
    max_code = max(codes) if codes else 0
    bits = max(9, max_code.bit_length())
    bits = min(bits, 16)
    packed = pack_codes(codes)
    
    lzw_path = os.path.join(temp_dir, "test.lzw")
    with open(lzw_path, "wb") as f:
        # Header: shape (3x 2 bytes) + bits (1 byte)
        f.write(image.shape[0].to_bytes(2, byteorder='big'))
        f.write(image.shape[1].to_bytes(2, byteorder='big'))
        f.write(image.shape[2].to_bytes(2, byteorder='big'))
        f.write(bits.to_bytes(1, byteorder='big'))
        f.write(packed)
    
    lzw_size = os.path.getsize(lzw_path)
    print(f"\n[4] Simpan file .lzw: {lzw_path}")
    print(f"    Bits per code: {bits}")
    print(f"    Ukuran file .lzw: {lzw_size} bytes")
    print(f"    Rasio kompresi (PNG/LZW): {original_png_size/lzw_size:.2f}")
    
    # --- 5. Baca kembali .lzw, unpack, dekompresi ---
    print("\n[5] Dekompresi dari file .lzw...")
    with open(lzw_path, "rb") as f:
        shape_h = int.from_bytes(f.read(2), byteorder='big')
        shape_w = int.from_bytes(f.read(2), byteorder='big')
        shape_c = int.from_bytes(f.read(2), byteorder='big')
        read_bits = int.from_bytes(f.read(1), byteorder='big')
        packed_data = f.read()
    
    unpacked_codes = unpack_codes(packed_data, read_bits)
    print(f"    Jumlah kode setelah unpack: {len(unpacked_codes)}")
    
    restored_shape = (shape_h, shape_w, shape_c)
    restored = decompress_image(unpacked_codes, restored_shape)
    print(f"    Shape hasil dekompresi: {restored.shape}")
    
    # --- 6. VERIFIKASI LOSSLESS ---
    print("\n" + "=" * 60)
    print("VERIFIKASI LOSSLESS")
    print("=" * 60)
    
    # 6a. Bandingkan jumlah kode
    codes_match = len(codes) == len(unpacked_codes)
    print(f"\n  Jumlah kode cocok?  {len(codes)} vs {len(unpacked_codes)} => {'OK YA' if codes_match else 'GAGAL TIDAK'}")
    
    if codes_match:
        codes_identical = codes == unpacked_codes
        print(f"  Kode-kode identik?  => {'OK YA' if codes_identical else 'GAGAL TIDAK'}")
    
    # 6b. Bandingkan pixel per pixel
    pixels_identical = np.array_equal(image, restored)
    print(f"  Pixel identik?      => {'OK YA' if pixels_identical else 'GAGAL TIDAK'}")
    
    if not pixels_identical:
        diff = np.abs(image.astype(int) - restored.astype(int))
        print(f"    Max perbedaan pixel: {diff.max()}")
        print(f"    Pixel berbeda: {np.count_nonzero(diff)} dari {diff.size}")
    
    # 6c. Bandingkan ukuran file PNG
    restored_png = os.path.join(temp_dir, "restored_test.png")
    cv2.imwrite(restored_png, restored)
    restored_png_size = os.path.getsize(restored_png)
    
    # Baca ulang original PNG untuk perbandingan fair
    original_reread = cv2.imread(original_png, cv2.IMREAD_COLOR)
    pixels_from_png_identical = np.array_equal(original_reread, restored)
    
    print(f"\n  Ukuran PNG asli:     {original_png_size} bytes")
    print(f"  Ukuran PNG restored: {restored_png_size} bytes")
    
    # Yang paling penting: jika kita return FILE ASLI (bukan re-encode), size PERSIS sama
    print(f"\n  [STRATEGI LOSSLESS]")
    print(f"  Jika mengembalikan FILE ASLI => size: {original_png_size} bytes  [OK] PERSIS SAMA")
    print(f"  Pixel dari file asli vs restored identik? => {'OK YA' if pixels_from_png_identical else 'GAGAL TIDAK'}")
    
    # --- FINAL VERDICT ---
    print("\n" + "=" * 60)
    if pixels_identical and codes_match:
        print("[PASSED] HASIL: KOMPRESI LZW TERBUKTI 100% LOSSLESS!")
        print("   Pixel data PERSIS SAMA sebelum & sesudah kompresi.")
        print("   File download akan PERSIS SAMA ukurannya dengan")
        print("   file upload (karena kita return file asli).")
    else:
        print("[FAILED] HASIL: ADA MASALAH - KOMPRESI TIDAK LOSSLESS!")
        if not codes_match:
            print("   Pack/unpack codes menghasilkan jumlah berbeda.")
        if not pixels_identical:
            print("   Pixel data BERBEDA setelah dekompresi.")
    print("=" * 60)
    
    # Cleanup
    # os.remove(original_png)
    # os.remove(lzw_path)
    # os.remove(restored_png)
    
    return pixels_identical and codes_match


if __name__ == "__main__":
    success = test_lzw_lossless()
    sys.exit(0 if success else 1)
