import numpy as np

def compress_image(image_array):
    """
    Mengompresi array gambar menggunakan algoritma LZW + Delta Encoding.
    """
    # Flatten the array (ubah ke 1D)
    flat_data = image_array.flatten()
    
    # 1. DELTA ENCODING (Pre-processing)
    # Trik rahasia: Algoritma Lossless seperti LZW akan sangat buruk jika diberikan foto berwarna (RGB) 
    # karena banyak piksel yang 'mirip' tapi angkanya berbeda (noise foto).
    # Kita gunakan Delta Encoding (seperti format PNG asli) untuk mengubah piksel menjadi "selisih" angkanya saja.
    delta_data = np.zeros_like(flat_data)
    if len(flat_data) > 0:
        delta_data[0] = flat_data[0]
        delta_data[1:] = (flat_data[1:].astype(int) - flat_data[:-1].astype(int)) % 256
        
    data_bytes = delta_data.astype(np.uint8).tobytes()
    
    # Inisialisasi Kamus (Dictionary) LZW
    dictionary = {bytes([i]): i for i in range(256)}
    dict_size = 256
    w = bytes()
    result = []
    
    for byte in data_bytes:
        c = bytes([byte])
        wc = w + c
        if wc in dictionary:
            w = wc
        else:
            result.append(dictionary[w])
            # Limit ukuran kamus hingga 16-bit (65536) agar tidak memakan RAM
            if dict_size < 65536:
                dictionary[wc] = dict_size
                dict_size += 1
            w = c
    if w:
        result.append(dictionary[w])
        
    return result # Mengembalikan list integer (kode LZW)

def decompress_image(compressed_data, original_shape):
    """
    Mendekompresi data LZW dan mengembalikannya ke bentuk array gambar 2D semula.
    """
    dictionary = {i: bytes([i]) for i in range(256)}
    dict_size = 256
    w = bytes([compressed_data[0]])
    result = bytearray(w)
    
    for k in compressed_data[1:]:
        if k in dictionary:
            entry = dictionary[k]
        elif k == dict_size:
            entry = w + bytes([w[0]])
        else:
            raise ValueError('Data terkompresi rusak pada k: %s' % k)
            
        result.extend(entry)
        
        if dict_size < 65536:
            dictionary[dict_size] = w + bytes([entry[0]])
            dict_size += 1
        w = entry
        
    # INVERSE DELTA ENCODING
    delta_array = np.frombuffer(result, dtype=np.uint8)
    if len(delta_array) > 0:
        # Mengembalikan nilai 'selisih' menjadi angka piksel utuh menggunakan Cumulative Sum
        restored = np.cumsum(delta_array, dtype=np.uint64) % 256
        decompressed_array = restored.astype(np.uint8)
    else:
        decompressed_array = delta_array
        
    # Ubah kembali ke bentuk dimensi (shape) gambar aslinya
    return decompressed_array.reshape(original_shape)

def calculate_mse(imageA, imageB):
    """Fungsi pembuktian Lossless"""
    err = np.sum((imageA.astype("float") - imageB.astype("float")) ** 2)
    err /= float(imageA.shape[0] * imageA.shape[1])
    return err
def pack_codes(codes):
    if not codes:
        return b""
    max_code = max(codes)
    bits = max(9, max_code.bit_length())
    bits = min(bits, 16)
    bit_buffer = 0
    bit_len = 0
    out = bytearray()
    for code in codes:
        bit_buffer = (bit_buffer << bits) | code
        bit_len += bits
        while bit_len >= 8:
            bit_len -= 8
            out.append((bit_buffer >> bit_len) & 0xFF)
    if bit_len > 0:
        out.append((bit_buffer << (8 - bit_len)) & 0xFF)
    return bytes(out)

def unpack_codes(data, bits):
    if bits < 1:
        raise ValueError("bits must be positive")
    bit_buffer = 0
    bit_len = 0
    codes = []
    for b in data:
        bit_buffer = (bit_buffer << 8) | b
        bit_len += 8
        while bit_len >= bits:
            bit_len -= bits
            codes.append((bit_buffer >> bit_len) & ((1 << bits) - 1))
    return codes
