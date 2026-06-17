import hashlib
from functools import lru_cache
from typing import Iterable

import jieba
import numpy as np

from config import MINHASH_PRIME, MINHASH_RANDOM_SEED, SHINGLE_N


def tokenize_text(text: str, language: str) -> list[str]:
    if language == "zh":
        return [token.strip() for token in jieba.cut(text) if token.strip()]
    if language == "en":
        return [token.strip() for token in text.split() if token.strip()]
    raise ValueError("language must be zh or en")


def build_shingles(tokens: Iterable[str], shingle_n: int = SHINGLE_N) -> set[str]:
    token_list = list(tokens)
    if shingle_n <= 0:
        raise ValueError("shingle_n must be positive")
    if len(token_list) < shingle_n:
        return set()
    return {" ".join(token_list[idx:idx + shingle_n]) for idx in range(len(token_list) - shingle_n + 1)}


def stable_hash_int(value: str, digest_size: int = 8) -> int:
    digest = hashlib.blake2b(value.encode("utf-8"), digest_size=digest_size).digest()
    return int.from_bytes(digest, byteorder="big", signed=False)


@lru_cache(maxsize=32)
def _minhash_permutations(permutations: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(MINHASH_RANDOM_SEED)
    coeff_a = rng.integers(1, MINHASH_PRIME - 1, size=permutations, dtype=np.int64)
    coeff_b = rng.integers(0, MINHASH_PRIME - 1, size=permutations, dtype=np.int64)
    return coeff_a, coeff_b


def minhash_signature(shingles: set[str], permutations: int) -> list[int]:
    if permutations <= 0:
        raise ValueError("permutations must be positive")
    if not shingles:
        return [MINHASH_PRIME] * permutations

    coeff_a, coeff_b = _minhash_permutations(permutations)
    values = np.array(
        [stable_hash_int(shingle, digest_size=8) % MINHASH_PRIME for shingle in shingles],
        dtype=np.int64,
    )
    signature = np.full(permutations, MINHASH_PRIME, dtype=np.int64)

    chunk_size = 512
    for start in range(0, len(values), chunk_size):
        chunk = values[start:start + chunk_size]
        hashed = (coeff_a[:, None] * chunk[None, :] + coeff_b[:, None]) % MINHASH_PRIME
        signature = np.minimum(signature, hashed.min(axis=1))

    return [int(value) for value in signature.tolist()]


def simhash_signature(shingles: set[str], bits: int) -> int:
    if bits <= 0:
        raise ValueError("bits must be positive")
    if bits % 8 != 0:
        raise ValueError("bits must be a multiple of 8")
    if not shingles:
        return 0

    weights = np.zeros(bits, dtype=np.int32)
    digest_size = bits // 8
    for shingle in shingles:
        digest = hashlib.blake2b(shingle.encode("utf-8"), digest_size=digest_size).digest()
        bit_array = np.unpackbits(np.frombuffer(digest, dtype=np.uint8))
        weights += np.where(bit_array > 0, 1, -1)

    signature = 0
    for bit in weights >= 0:
        signature = (signature << 1) | int(bit)
    return signature


def hash_content(text: str, language: str, hash_method: str, parameter: int) -> dict:
    tokens = tokenize_text(text, language)
    shingles = build_shingles(tokens, SHINGLE_N)

    if hash_method == "MinHash":
        return {"minhash": minhash_signature(shingles, parameter)}
    if hash_method == "SimHash":
        return {"simhash": simhash_signature(shingles, parameter)}
    raise ValueError("hash_method must be MinHash or SimHash")
