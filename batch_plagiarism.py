import ast
import heapq
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable

import pymysql
from fastapi import HTTPException

from ccpd import essay_overlap_analysis
from config import BATCH_TOP_N, DB_CONFIG_BY_ENV


LOGGER = logging.getLogger("batch_plagiarism")


@dataclass(frozen=True)
class CompositionItem:
    scene_type: int
    compare_id: str


@dataclass(frozen=True)
class CompositionRow:
    id: int
    content: str
    hash_value: str
    hash_param: int


@dataclass(frozen=True)
class Candidate:
    scene_type: int
    compare_id: str
    compare_id_int: int
    content: str
    hash_value: Any
    hash_param: int


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if isinstance(record.msg, dict):
            return json.dumps(record.msg, ensure_ascii=False, separators=(",", ":"))
        return super().format(record)


def configure_batch_logger() -> None:
    if LOGGER.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False


def validate_bigint(value: str, field_name: str) -> int:
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=400, detail={"msg": f"请求参数{field_name}不能为空"})
    stripped = value.strip()
    if not stripped.isdigit():
        raise HTTPException(status_code=400, detail={"msg": f"请求参数{field_name}必须为bigint字符串"})
    parsed = int(stripped)
    if parsed < 0 or parsed > 9_223_372_036_854_775_807:
        raise HTTPException(status_code=400, detail={"msg": f"请求参数{field_name}超出bigint范围"})
    return parsed


def dedupe_composition_items(items: Iterable[Any]) -> list[CompositionItem]:
    seen: set[tuple[int, str]] = set()
    result: list[CompositionItem] = []
    for item in items:
        if item.scene_type not in {1, 2, 3, 4}:
            raise HTTPException(status_code=400, detail={"msg": "请求参数scene_type仅支持1、2、3或4"})
        scene_type = int(item.scene_type)
        if item.compare_id is None:
            raise HTTPException(status_code=400, detail={"msg": "请求参数compare_id不能为空"})
        compare_id = item.compare_id.strip() if isinstance(item.compare_id, str) else item.compare_id
        compare_id_int = validate_bigint(compare_id, "compare_id")
        key = (scene_type, str(compare_id_int))
        if key in seen:
            continue
        seen.add(key)
        result.append(CompositionItem(scene_type=scene_type, compare_id=str(compare_id_int)))
    return result


def db_name_for_env(env: str) -> str:
    try:
        db_name = DB_CONFIG_BY_ENV[env]["MYSQL_DB"]
    except KeyError as exc:
        raise HTTPException(status_code=400, detail={"msg": "请求参数env仅支持prod、dev或uat"}) from exc
    if not str(db_name).replace("_", "").isalnum():
        raise HTTPException(status_code=500, detail={"msg": "数据库配置MYSQL_DB不合法"})
    return str(db_name)


def hash_column(hash_method: str) -> str:
    if hash_method == "MinHash":
        return "minhash"
    if hash_method == "SimHash":
        return "simhash"
    raise HTTPException(status_code=400, detail={"msg": "请求参数hashMethod仅支持MinHash或SimHash"})


def get_connection(env: str):
    config = DB_CONFIG_BY_ENV[env]
    return pymysql.connect(
        host=config["MYSQL_HOST"],
        port=int(config["MYSQL_PORT"]),
        user=config["MYSQL_USER"],
        password=config["MYSQL_PASSWORD"],
        database=config["MYSQL_DB"],
        charset=config["MYSQL_CHARSET"],
        cursorclass=pymysql.cursors.DictCursor,
    )


def placeholders(values: list[int]) -> str:
    return ",".join(["%s"] * len(values))


def fetch_work_row(conn, db_name: str, work_id: int, hash_col: str) -> CompositionRow | None:
    sql = (
        f"select id, composition_content as content, {hash_col} as hash_value, hash_param "
        f"from {db_name}.correct_task where id=%s and deleted=0"
    )
    with conn.cursor() as cursor:
        cursor.execute(sql, (work_id,))
        row = cursor.fetchone()
    return normalize_row(row) if row else None


def fetch_correct_task_candidates(conn, db_name: str, ids: list[int], hash_col: str) -> dict[int, CompositionRow]:
    if not ids:
        return {}
    sql = (
        f"select id, composition_content as content, {hash_col} as hash_value, hash_param "
        f"from {db_name}.correct_task where id in ({placeholders(ids)})"
    )
    return fetch_rows_by_id(conn, sql, ids)


def fetch_sample_candidates(conn, db_name: str, ids: list[int], hash_col: str) -> dict[int, CompositionRow]:
    if not ids:
        return {}
    sql = (
        f"select id, sample_content as content, {hash_col} as hash_value, hash_param "
        f"from {db_name}.composition_sample where id in ({placeholders(ids)})"
    )
    return fetch_rows_by_id(conn, sql, ids)


def fetch_rows_by_id(conn, sql: str, ids: list[int]) -> dict[int, CompositionRow]:
    rows: dict[int, CompositionRow] = {}
    with conn.cursor() as cursor:
        cursor.execute(sql, tuple(ids))
        for row in cursor.fetchall():
            normalized = normalize_row(row)
            rows[normalized.id] = normalized
    return rows


def normalize_row(row: dict[str, Any]) -> CompositionRow:
    return CompositionRow(
        id=int(row["id"]),
        content=row.get("content") or "",
        hash_value=row.get("hash_value"),
        hash_param=int(row["hash_param"]) if row.get("hash_param") is not None else 0,
    )


def parse_minhash(value: Any, hash_param: int) -> list[int]:
    if hash_param <= 0:
        raise ValueError("hash_param must be positive")
    if value is None or value == "":
        raise ValueError("empty minhash")
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = ast.literal_eval(value)
    else:
        parsed = value
    if not isinstance(parsed, list):
        raise ValueError("minhash must be a list")
    if len(parsed) != hash_param:
        raise ValueError("minhash length mismatch")
    result: list[int] = []
    for item in parsed:
        if isinstance(item, bool) or not isinstance(item, int):
            raise ValueError("minhash item must be int")
        if item < 0:
            raise ValueError("minhash item must be non-negative")
        result.append(item)
    return result


def parse_simhash(value: Any, hash_param: int) -> int:
    if hash_param <= 0:
        raise ValueError("hash_param must be positive")
    if value is None or value == "":
        raise ValueError("empty simhash")
    parsed = int(str(value).strip())
    if parsed < 0:
        raise ValueError("simhash must be non-negative")
    return parsed


def parse_hash(value: Any, hash_param: int, hash_method: str) -> Any:
    if hash_method == "MinHash":
        return parse_minhash(value, hash_param)
    return parse_simhash(value, hash_param)


def minhash_similarity(sig_a: list[int], sig_b: list[int]) -> float:
    if len(sig_a) != len(sig_b) or not sig_a:
        raise ValueError("minhash signatures must have equal positive length")
    matches = sum(1 for left, right in zip(sig_a, sig_b) if left == right)
    return matches / len(sig_a)


def simhash_similarity(sig_a: int, sig_b: int, bits: int) -> float:
    if bits <= 0:
        raise ValueError("simhash bits must be positive")
    return 1.0 - ((sig_a ^ sig_b).bit_count() / bits)


def hash_similarity(work_hash: Any, cand_hash: Any, hash_method: str, hash_param: int) -> float:
    if hash_method == "MinHash":
        return minhash_similarity(work_hash, cand_hash)
    return simhash_similarity(work_hash, cand_hash, hash_param)


def build_candidates(
    deduped_items: list[CompositionItem],
    correct_rows: dict[int, CompositionRow],
    sample_rows: dict[int, CompositionRow],
    hash_method: str,
    work_hash_param: int,
) -> tuple[list[Candidate], int]:
    candidates: list[Candidate] = []
    invalid_count = 0

    for item in deduped_items:
        compare_id_int = int(item.compare_id)
        row = sample_rows.get(compare_id_int) if item.scene_type == 3 else correct_rows.get(compare_id_int)
        if row is None:
            continue
        try:
            if row.hash_param != work_hash_param:
                raise ValueError("hash_param mismatch")
            parsed_hash = parse_hash(row.hash_value, row.hash_param, hash_method)
        except (ValueError, TypeError, SyntaxError, OverflowError):
            invalid_count += 1
            continue
        candidates.append(
            Candidate(
                scene_type=item.scene_type,
                compare_id=str(compare_id_int),
                compare_id_int=compare_id_int,
                content=row.content,
                hash_value=parsed_hash,
                hash_param=row.hash_param,
            )
        )

    return candidates, invalid_count


def clean_text(value: str) -> str:
    return (value or "").replace('"', "")


def process_batch_plagiarism(req: Any, connection_factory: Callable[[str], Any] = get_connection) -> dict[str, Any]:
    configure_batch_logger()
    total_start = time.perf_counter()
    stage_ms: dict[str, float] = {}
    recall_log: list[dict[str, Any]] = []

    work_id_int = validate_bigint(req.work_id, "work_id")
    if not req.env:
        raise HTTPException(status_code=400, detail={"msg": "请求参数env不能为空"})
    if req.env not in DB_CONFIG_BY_ENV:
        raise HTTPException(status_code=400, detail={"msg": "请求参数env仅支持prod、dev或uat"})
    if req.hashMethod is None:
        req.hashMethod = "MinHash"
    if req.hashMethod not in {"MinHash", "SimHash"}:
        raise HTTPException(status_code=400, detail={"msg": "请求参数hashMethod仅支持MinHash或SimHash"})
    if req.lang is None:
        req.lang = "zh"
    if req.lang != "zh":
        raise HTTPException(status_code=400, detail={"msg": "请求参数lang当前仅支持zh"})
    if not req.composition_list:
        raise HTTPException(status_code=400, detail={"msg": "请求参数composition_list不能为空"})

    t0 = time.perf_counter()
    deduped_items = dedupe_composition_items(req.composition_list)
    stage_ms["validate_ms"] = elapsed_ms(t0)

    db_name = db_name_for_env(req.env)
    hash_col = hash_column(req.hashMethod)
    work_row = None
    correct_rows: dict[int, CompositionRow] = {}
    sample_rows: dict[int, CompositionRow] = {}

    t0 = time.perf_counter()
    try:
        conn = connection_factory(req.env)
        try:
            work_row = fetch_work_row(conn, db_name, work_id_int, hash_col)
            if work_row is None:
                raise HTTPException(status_code=400, detail={"msg": "work_id在SQL查询结果总计数为0"})
            correct_ids = [int(item.compare_id) for item in deduped_items if item.scene_type in {1, 2, 4}]
            sample_ids = [int(item.compare_id) for item in deduped_items if item.scene_type == 3]
            correct_rows = fetch_correct_task_candidates(conn, db_name, correct_ids, hash_col)
            sample_rows = fetch_sample_candidates(conn, db_name, sample_ids, hash_col)
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"msg": f"数据库查询失败: {exc}"}) from exc
    stage_ms["db_query_ms"] = elapsed_ms(t0)

    t0 = time.perf_counter()
    try:
        work_hash = parse_hash(work_row.hash_value, work_row.hash_param, req.hashMethod)
    except (ValueError, TypeError, SyntaxError, OverflowError) as exc:
        raise HTTPException(status_code=400, detail={"msg": f"work_id hash不合法: {exc}"}) from exc

    candidates, invalid_candidate_hash_count = build_candidates(
        deduped_items=deduped_items,
        correct_rows=correct_rows,
        sample_rows=sample_rows,
        hash_method=req.hashMethod,
        work_hash_param=work_row.hash_param,
    )

    scored_candidates: list[tuple[float, int, Candidate]] = []
    for candidate in candidates:
        similarity = hash_similarity(work_hash, candidate.hash_value, req.hashMethod, work_row.hash_param)
        scored_candidates.append((similarity, candidate.compare_id_int, candidate))
    top_candidates = heapq.nlargest(BATCH_TOP_N, scored_candidates, key=lambda item: (item[0], item[1]))
    top_keys = {(candidate.scene_type, candidate.compare_id) for _score, _id, candidate in top_candidates}
    stage_ms["recall_ms"] = elapsed_ms(t0)

    t0 = time.perf_counter()
    compare_result: list[dict[str, Any]] = []
    repeat_rates: dict[tuple[int, str], float | None] = {}
    original_text = clean_text(work_row.content)
    for similarity, _compare_id_int, candidate in top_candidates:
        comparison = essay_overlap_analysis(original_text, clean_text(candidate.content))
        repeat_rate = round(float(comparison["symmetry_rate"]), 4)
        repeat_rates[(candidate.scene_type, candidate.compare_id)] = repeat_rate
        if repeat_rate > 0:
            compare_result.append(
                {
                    "compare_id": candidate.compare_id,
                    "scene_type": candidate.scene_type,
                    "repeat_rate": repeat_rate,
                }
            )

    compare_result.sort(key=lambda item: (item["repeat_rate"], int(item["compare_id"])), reverse=True)
    stage_ms["compare_ms"] = elapsed_ms(t0)

    for similarity, _compare_id_int, candidate in scored_candidates:
        key = (candidate.scene_type, candidate.compare_id)
        recall_log.append(
            {
                "cand_id": candidate.compare_id,
                "scene_type": candidate.scene_type,
                "hash_similarity": round(float(similarity), 6),
                "in_top_n": key in top_keys,
                "repeat_rate": repeat_rates.get(key),
            }
        )

    total_ms = elapsed_ms(total_start)
    log_payload = {
        "event": "batch_plagiarism_detection",
        "env": req.env,
        "hashMethod": req.hashMethod,
        "work_id": str(work_id_int),
        "candidate_request_count": len(req.composition_list),
        "candidate_deduped_count": len(deduped_items),
        "candidate_found_count": len(correct_rows) + len(sample_rows),
        "valid_hash_count": len(candidates),
        "invalid_hash_count": invalid_candidate_hash_count,
        "top_n": BATCH_TOP_N,
        "actual_top_n": len(top_candidates),
        "results_count": len(compare_result),
        "recall": recall_log,
        "stage_ms": stage_ms,
        "total_ms": round(total_ms, 3),
    }
    LOGGER.info(log_payload)

    data: dict[str, Any] = {"work_id": str(work_id_int)}
    if compare_result:
        data["compare_result"] = compare_result
    return {"code": 200, "msg": "success", "data": data}


def elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 3)
