from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from typing import Any, List, Optional
from pathlib import Path
import uvicorn

from batch_plagiarism import process_batch_plagiarism
from ccpd import essay_overlap_analysis
from config import DEFAULT_HASH_PARAMETER
from content_hash import hash_content

app = FastAPI(title="作文文本比对服务")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CompareRequest(BaseModel):
    original_text: str = None
    candidate_text: str = None


class ContentHashRequest(BaseModel):
    uuid: Optional[str] = None
    compositionContent: Optional[str] = None
    language: Optional[str] = "zh"
    hashMethod: Optional[str] = "MinHash"
    para: Optional[int] = DEFAULT_HASH_PARAMETER


class DetailItem(BaseModel):
    sentence: str
    best_match: str
    sentence_score: float
    word_score: float
    is_repeated: bool


class CompareResponse(BaseModel):
    symmetry_rate: float
    sentence_repeat_rate: float
    word_repeat_rate: float
    details: List[DetailItem]


class ContentHashResponse(BaseModel):
    uuid: str
    minhash: Optional[List[int]] = None
    simhash: Optional[int] = None
    parameter: int


class BatchCompositionItem(BaseModel):
    scene_type: Optional[int] = None
    compare_id: Optional[str] = None


class BatchPlagiarismRequest(BaseModel):
    work_id: Optional[str] = None
    env: Optional[str] = None
    hashMethod: Optional[str] = "MinHash"
    lang: Optional[str] = "zh"
    composition_list: Optional[List[BatchCompositionItem]] = None


class BatchCompareResultItem(BaseModel):
    compare_id: str
    scene_type: int
    repeat_rate: float


class BatchPlagiarismData(BaseModel):
    work_id: str
    compare_result: Optional[List[BatchCompareResultItem]] = None


class BatchPlagiarismResponse(BaseModel):
    code: int
    msg: str
    data: BatchPlagiarismData


@app.post("/api/composition_compare", response_model=CompareResponse)
def composition_compare(req: CompareRequest):
    if not req.original_text:
        raise HTTPException(status_code=400, detail={"msg": "请求参数original_text不能为空"})
    if not req.candidate_text:
        raise HTTPException(status_code=400, detail={"msg": "请求参数candidate_text不能为空"})

    # 清洗英文双引号
    original_text = req.original_text.replace('"', '')
    candidate_text = req.candidate_text.replace('"', '')

    result = essay_overlap_analysis(original_text, candidate_text)

    details = [
        DetailItem(
            sentence=d["sentence"],
            best_match=d["best_match"],
            sentence_score=float(d["sentence_score"]),
            word_score=float(d["word_score"]),
            is_repeated=bool(d["is_repeated"]),
        )
        for d in result["details"]
    ]

    return CompareResponse(
        symmetry_rate=round(float(result["symmetry_rate"]), 4),
        sentence_repeat_rate=round(float(result["sentence_repeat_rate"]), 4),
        word_repeat_rate=round(float(result["word_repeat_rate"]), 4),
        details=details,
    )


@app.post("/api/contentHash", response_model=ContentHashResponse, response_model_exclude_none=True)
def content_hash(req: ContentHashRequest):
    if not req.uuid:
        raise HTTPException(status_code=400, detail={"msg": "请求参数uuid不能为空"})
    if not req.compositionContent:
        raise HTTPException(status_code=400, detail={"msg": "请求参数compositionContent不能为空"})
    if req.language not in {"zh", "en"}:
        raise HTTPException(status_code=400, detail={"msg": "请求参数language仅支持zh或en"})
    if req.hashMethod not in {"MinHash", "SimHash"}:
        raise HTTPException(status_code=400, detail={"msg": "请求参数hashMethod仅支持MinHash或SimHash"})
    if not isinstance(req.para, int) or req.para <= 0:
        raise HTTPException(status_code=400, detail={"msg": "请求参数para必须为正整数"})
    if req.hashMethod == "SimHash" and req.para % 8 != 0:
        raise HTTPException(status_code=400, detail={"msg": "SimHash请求参数para必须为8的倍数"})

    result = hash_content(req.compositionContent, req.language, req.hashMethod, req.para)
    return ContentHashResponse(uuid=req.uuid, parameter=req.para, **result)


@app.post(
    "/api/batch_plagiarism_detection",
    response_model=BatchPlagiarismResponse,
    response_model_exclude_none=True,
)
def batch_plagiarism_detection(payload: dict[str, Any]):
    try:
        req = BatchPlagiarismRequest(**payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"msg": f"请求参数结构不合法: {exc}"}) from exc
    return process_batch_plagiarism(req)


# 前端静态文件托管（API 路由必须在静态挂载和 SPA fallback 之前注册）
_frontend_dist = Path(__file__).resolve().parent / "frontend" / "dist"
_frontend_index = _frontend_dist / "index.html"
_frontend_assets = _frontend_dist / "assets"

if _frontend_assets.is_dir():
    app.mount("/assets", StaticFiles(directory=_frontend_assets), name="assets")


def _serve_frontend_index():
    if not _frontend_index.is_file():
        raise HTTPException(
            status_code=503,
            detail={"msg": "前端构建产物不存在，请先执行 cd frontend && npm run build"},
        )
    return FileResponse(_frontend_index)


@app.get("/", include_in_schema=False)
def redirect_root():
    return RedirectResponse(url="/simulate")


@app.get("/simulate", include_in_schema=False)
@app.get("/simulate/{path:path}", include_in_schema=False)
def serve_frontend(path: str = ""):
    return _serve_frontend_index()


@app.get("/{path:path}", include_in_schema=False)
def serve_frontend_fallback(path: str):
    if path == "api" or path.startswith("api/") or path == "assets" or path.startswith("assets/"):
        raise HTTPException(status_code=404, detail="Not Found")
    return _serve_frontend_index()


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8540, reload=False)
