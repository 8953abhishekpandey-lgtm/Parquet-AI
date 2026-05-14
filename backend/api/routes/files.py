from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.models import DatasetManifest, MultiUploadResponse, UploadFailure, UploadResponse
from backend.services.pipeline import AnalyticsPipeline


router = APIRouter(prefix="/api", tags=["files"])
pipeline = AnalyticsPipeline()

@router.post("/files/upload", response_model=UploadResponse)
async def upload_parquet(file: UploadFile = File(...)) -> UploadResponse:
    try:
        dataset = await pipeline.ingest_upload(file)
        return UploadResponse(dataset=dataset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}") from exc


@router.post("/files/upload-multiple", response_model=MultiUploadResponse)
async def upload_multiple_parquet(files: list[UploadFile] = File(...)) -> MultiUploadResponse:
    if not files:
        raise HTTPException(status_code=400, detail="At least one parquet file is required.")

    datasets: list[DatasetManifest] = []
    errors: list[UploadFailure] = []

    for file in files:
        filename = file.filename or "unknown"
        try:
            datasets.append(await pipeline.ingest_upload(file))
        except Exception as exc:
            errors.append(UploadFailure(filename=filename, error=str(exc)))

    return MultiUploadResponse(datasets=datasets, errors=errors)


@router.get("/datasets", response_model=list[DatasetManifest])
def list_datasets() -> list[DatasetManifest]:
    return pipeline.list_datasets()


@router.get("/datasets/{dataset_id}/schema", response_model=DatasetManifest)
def get_dataset_schema(dataset_id: str) -> DatasetManifest:
    try:
        return pipeline.get_dataset(dataset_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Dataset not found") from exc


@router.delete("/datasets/{dataset_id}", status_code=204)
def delete_dataset(dataset_id: str) -> None:
    try:
        pipeline.delete_dataset(dataset_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Dataset not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return None
