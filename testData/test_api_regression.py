#!/usr/bin/env python3
import argparse
import csv
import json
import random
import sys
import urllib.error
import urllib.request
from pathlib import Path


CSV_PATH = Path(__file__).with_name("historic_essay_detail.csv")


def post_json(base_url, path, payload, timeout=60):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        raise AssertionError(f"POST {path} failed with HTTP {exc.code}: {message}") from exc


def load_sample(csv_path, sample_size, seed):
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = [
            row
            for row in csv.DictReader(file)
            if row.get("content_raw") and row.get("content_cand") and row.get("repeat_rate") != ""
        ]
    if len(rows) < sample_size:
        raise AssertionError(f"CSV only has {len(rows)} usable rows, need {sample_size}")
    return random.Random(seed).sample(rows, sample_size)


def assert_close(actual, expected, tolerance, label):
    if abs(actual - expected) > tolerance:
        raise AssertionError(
            f"{label}: expected {expected:.6f}, got {actual:.6f}, tolerance {tolerance}"
        )


def test_composition_compare(base_url, rows, tolerance):
    failures = []
    for index, row in enumerate(rows, start=1):
        status, payload = post_json(
            base_url,
            "/api/composition_compare",
            {
                "original_text": row["content_raw"],
                "candidate_text": row["content_cand"],
            },
        )
        if status != 200:
            failures.append(f"row {index}: HTTP status {status}")
            continue

        expected = round(float(row["repeat_rate"]), 4)
        actual = float(payload["symmetry_rate"])
        try:
            assert_close(actual, expected, tolerance, f"row {index} symmetry_rate")
        except AssertionError as exc:
            failures.append(
                f"{exc} (workId_raw={row.get('workId_raw')}, workId_cand={row.get('workId_cand')})"
            )

    if failures:
        raise AssertionError("composition_compare mismatches:\n" + "\n".join(failures))


def test_content_hash(base_url, rows, parameter):
    for index, row in enumerate(rows, start=1):
        common_payload = {
            "uuid": f"test-{row.get('workId_raw', index)}-{index}",
            "compositionContent": row["content_raw"],
            "language": "zh",
        }

        status, minhash_payload = post_json(
            base_url,
            "/api/contentHash",
            {**common_payload, "hashMethod": "MinHash"},
        )
        if status != 200:
            raise AssertionError(f"row {index}: MinHash HTTP status {status}")
        minhash = minhash_payload.get("minhash")
        if minhash_payload.get("parameter") != parameter:
            raise AssertionError(
                f"row {index}: MinHash parameter expected {parameter}, got {minhash_payload.get('parameter')}"
            )
        if not isinstance(minhash, list) or len(minhash) != parameter:
            raise AssertionError(
                f"row {index}: MinHash expected list length {parameter}, got {type(minhash).__name__}"
            )
        if not all(isinstance(value, int) and value >= 0 for value in minhash):
            raise AssertionError(f"row {index}: MinHash contains non-integer or negative values")
        if "simhash" in minhash_payload:
            raise AssertionError(f"row {index}: MinHash response should not include simhash")

        status, simhash_payload = post_json(
            base_url,
            "/api/contentHash",
            {**common_payload, "hashMethod": "SimHash"},
        )
        if status != 200:
            raise AssertionError(f"row {index}: SimHash HTTP status {status}")
        simhash = simhash_payload.get("simhash")
        if simhash_payload.get("parameter") != parameter:
            raise AssertionError(
                f"row {index}: SimHash parameter expected {parameter}, got {simhash_payload.get('parameter')}"
            )
        if not isinstance(simhash, int):
            raise AssertionError(f"row {index}: SimHash expected int, got {type(simhash).__name__}")
        if simhash < 0 or simhash >= (1 << parameter):
            raise AssertionError(f"row {index}: SimHash should be a non-negative {parameter}-bit integer, got {simhash}")
        if "minhash" in simhash_payload:
            raise AssertionError(f"row {index}: SimHash response should not include minhash")


def main():
    parser = argparse.ArgumentParser(description="Local API regression tests for composition compare service.")
    parser.add_argument("--base-url", default="http://8.153.13.104:8540")
    parser.add_argument("--csv", type=Path, default=CSV_PATH)
    parser.add_argument("--sample-size", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260617)
    parser.add_argument("--tolerance", type=float, default=0.0001)
    parser.add_argument("--hash-parameter", type=int, default=128)
    args = parser.parse_args()

    rows = load_sample(args.csv, args.sample_size, args.seed)
    print(f"Loaded {len(rows)} sampled rows from {args.csv}")

    test_composition_compare(args.base_url, rows, args.tolerance)
    print(f"composition_compare passed for {len(rows)} sampled rows")

    test_content_hash(args.base_url, rows, args.hash_parameter)
    print(f"contentHash passed for zh MinHash and SimHash on {len(rows)} sampled rows")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
