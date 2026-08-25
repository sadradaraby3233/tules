"""
custom_encript.py
A highly obfuscated, multi-layered custom encryption engine designed for packing.
Uses dynamic S-Boxes, non-linear bitwise operations, and block permutation.
"""

import hashlib

class CustomCipher:
    """
    Multi-layered encryption scheme.
    Layer 1: Key-derived dynamic S-Box substitution.
    Layer 2: Non-linear bitwise rotation and XOR with hash-based PRNG.
    Layer 3: Variable block permutation.
    Layer 4: Rolling feedback XOR.
    """

    def __init__(self):
        pass

    def _derive_key_stream(self, key: str, length: int) -> bytes:
        """Generates a pseudo-random byte stream from the key."""
        base_hash = hashlib.sha512(key.encode('utf-8')).digest()
        stream = b""
        counter = 0
        while len(stream) < length:
            stream += hashlib.sha512(base_hash + counter.to_bytes(8, 'big')).digest()
            counter += 1
        return stream[:length]

    def _generate_sbox(self, key_bytes: bytes) -> list:
        """Generates a custom 256-byte substitution box."""
        sbox = list(range(256))
        j = 0
        for i in range(256):
            j = (j + sbox[i] + key_bytes[i % len(key_bytes)]) % 256
            sbox[i], sbox[j] = sbox[j], sbox[i]
        # Extra confusion pass
        for i in range(256):
            idx = (sbox[i] + key_bytes[i % len(key_bytes)]) % 256
            sbox[i], sbox[idx] = sbox[idx], sbox[i]
        return sbox

    def _generate_inv_sbox(self, sbox: list) -> list:
        """Generates the inverse substitution box."""
        inv_sbox = [0] * 256
        for i in range(256):
            inv_sbox[sbox[i]] = i
        return inv_sbox

    def _rotate_bits(self, byte_val: int, shift: int, direction: int = 1) -> int:
        """Rotates bits within a byte."""
        shift = shift % 8
        if direction == 1:
            return ((byte_val << shift) | (byte_val >> (8 - shift))) & 0xFF
        else:
            return ((byte_val >> shift) | (byte_val << (8 - shift))) & 0xFF

    def encrypt(self, data: bytes, key: str) -> bytes:
        """Encrypts data using the custom multi-layered cipher."""
        if not isinstance(data, bytes):
            data = str(data).encode('utf-8')
            
        key_bytes = hashlib.sha256(key.encode('utf-8')).digest()
        key_stream = self._derive_key_stream(key, len(data))
        
        # Layer 1: Dynamic S-Box Substitution
        sbox = self._generate_sbox(key_bytes)
        data = bytes(sbox[b] for b in data)
        
        # Layer 2: Bitwise Rotation and XOR
        rotated_data = bytearray()
        for i, b in enumerate(data):
            shift = key_stream[i] % 8
            rotated_data.append(self._rotate_bits(b, shift, 1))
        data = bytes(rotated_data)
        
        data = bytes(d ^ s for d, s in zip(data, key_stream))
        
        # Layer 3: Block Permutation
        block_size = 64
        permuted = bytearray()
        for i in range(0, len(data), block_size):
            block = bytearray(data[i:i+block_size])
            shift = key_bytes[i % len(key_bytes)] % len(block) if len(block) > 0 else 0
            if shift > 0:
                block = block[-shift:] + block[:-shift]
            permuted.extend(block)
        data = bytes(permuted)
        
        # Layer 4: Rolling Feedback XOR
        rolling_key = key_bytes[0]
        final_data = bytearray()
        for b in data:
            rolling_key = (rolling_key ^ b) & 0xFF
            final_data.append(rolling_key)
            
        return bytes(final_data)

    def decrypt(self, data: bytes, key: str) -> bytes:
        """Decrypts data using the custom multi-layered cipher."""
        key_bytes = hashlib.sha256(key.encode('utf-8')).digest()
        key_stream = self._derive_key_stream(key, len(data))
        
        # Reverse Layer 4: Rolling Feedback XOR
        rolling_key = key_bytes[0]
        unrolled = bytearray()
        for b in data:
            original_b = (b ^ rolling_key) & 0xFF
            rolling_key = b
            unrolled.append(original_b)
        data = bytes(unrolled)
        
        # Reverse Layer 3: Block Permutation
        block_size = 64
        unpermuted = bytearray()
        for i in range(0, len(data), block_size):
            block = bytearray(data[i:i+block_size])
            shift = key_bytes[i % len(key_bytes)] % len(block) if len(block) > 0 else 0
            if shift > 0:
                block = block[shift:] + block[:shift]
            unpermuted.extend(block)
        data = bytes(unpermuted)
        
        # Reverse Layer 2: Bitwise Rotation and XOR
        data = bytes(d ^ s for d, s in zip(data, key_stream))
        
        unrotated_data = bytearray()
        for i, b in enumerate(data):
            shift = key_stream[i] % 8
            unrotated_data.append(self._rotate_bits(b, shift, -1))
        data = bytes(unrotated_data)
        
        # Reverse Layer 1: Inverse S-Box Substitution
        sbox = self._generate_sbox(key_bytes)
        inv_sbox = self._generate_inv_sbox(sbox)
        data = bytes(inv_sbox[b] for b in data)
        
        return data

# Example usage and self-test
if __name__ == "__main__":
    cipher = CustomCipher()
    original_data = b"This is a secret message for packing!"
    secret_key = "super_secret_audiogame_key_123"
    
    encrypted = cipher.encrypt(original_data, secret_key)
    decrypted = cipher.decrypt(encrypted, secret_key)
    
    print(f"Original:  {original_data}")
    print(f"Encrypted: {encrypted.hex()}")
    print(f"Decrypted: {decrypted}")
    assert original_data == decrypted, "Decryption failed!"
    print("Self-test passed successfully.")
