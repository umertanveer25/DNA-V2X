"""
Baseline Cryptographic and Bio-Inspired Ciphers for V2X Comparison.
Includes:
  1. DNA-V2X (Proposed Dynamic 4-Mer Ephemeral Cipher)
  2. AES-128-GCM (NIST Authenticated Symmetric Standard)
  3. ChaCha20-Poly1305 (IETF Lightweight Stream Cipher)
  4. IEEE 1609.2 ECDSA Signature Verification (Vehicular PKI Standard)
  5. Static DNA Substitution (Naive Bio-Cipher Baseline)
  6. Unencrypted Plaintext (Zero-Security Baseline)
"""

import os
import time
import hmac
import hashlib
from typing import Dict, Any, Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes

from src.dna_4mer_engine import DNA4MerEngine, DynamicPermutationState, ALL_256_4MERS


class BaselineCiphers:
    def __init__(self):
        # AES-128-GCM Setup
        self.aes_key = AESGCM.generate_key(bit_length=128)
        self.aesgcm = AESGCM(self.aes_key)

        # ChaCha20-Poly1305 Setup
        self.chacha_key = ChaCha20Poly1305.generate_key()
        self.chacha = ChaCha20Poly1305(self.chacha_key)

        # IEEE 1609.2 ECDSA (NIST P-256 / secp256r1) Setup
        self.ec_private_key = ec.generate_private_key(ec.SECP256R1())
        self.ec_public_key = self.ec_private_key.public_key()

        # Static DNA Setup (Fixed standard table A=00, C=01, G=10, T=11)
        self.static_dna_table = ALL_256_4MERS
        self.static_dna_rev = {self.static_dna_table[b]: b for b in range(256)}

        # DNA-V2X Setup
        self.dna_engine = DNA4MerEngine()
        self.dna_state = DynamicPermutationState(b"BENCHMARK_SEED_01")

    # 1. DNA-V2X (Proposed)
    def encrypt_dna_v2x(self, payload: bytes) -> str:
        return self.dna_engine.encode_bytes(payload, self.dna_state)

    def decrypt_dna_v2x(self, strand: str) -> bytes:
        return self.dna_engine.decode_strand(strand, self.dna_state)

    # 2. AES-128-GCM
    def encrypt_aes_gcm(self, payload: bytes) -> Tuple[bytes, bytes]:
        nonce = os.urandom(12)
        ct = self.aesgcm.encrypt(nonce, payload, None)
        return (nonce, ct)

    def decrypt_aes_gcm(self, ct_tuple: Tuple[bytes, bytes]) -> bytes:
        nonce, ct = ct_tuple
        return self.aesgcm.decrypt(nonce, ct, None)

    # 3. ChaCha20-Poly1305
    def encrypt_chacha20(self, payload: bytes) -> Tuple[bytes, bytes]:
        nonce = os.urandom(12)
        ct = self.chacha.encrypt(nonce, payload, None)
        return (nonce, ct)

    def decrypt_chacha20(self, ct_tuple: Tuple[bytes, bytes]) -> bytes:
        nonce, ct = ct_tuple
        return self.chacha.decrypt(nonce, ct, None)

    # 4. IEEE 1609.2 ECDSA (Sign + Verify)
    def sign_ecdsa(self, payload: bytes) -> Tuple[bytes, bytes]:
        sig = self.ec_private_key.sign(payload, ec.ECDSA(hashes.SHA256()))
        return (payload, sig)

    def verify_ecdsa(self, sig_tuple: Tuple[bytes, bytes]) -> bytes:
        payload, sig = sig_tuple
        self.ec_public_key.verify(sig, payload, ec.ECDSA(hashes.SHA256()))
        return payload

    # 5. Static DNA Substitution
    def encrypt_static_dna(self, payload: bytes) -> str:
        return "".join(self.static_dna_table[b] for b in payload)

    def decrypt_static_dna(self, strand: str) -> bytes:
        return bytes([self.static_dna_rev[strand[i:i+4]] for i in range(0, len(strand), 4)])

    # 6. Plaintext (Zero-Security)
    def encrypt_plaintext(self, payload: bytes) -> bytes:
        return payload

    def decrypt_plaintext(self, payload: bytes) -> bytes:
        return payload
