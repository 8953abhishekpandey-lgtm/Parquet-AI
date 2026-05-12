from fastapi import APIRouter, HTTPException

from backend.models import QueryAllRequest, QueryRequest, QueryResponse
from backend.services.pipeline import AnalyticsPipeline


router = APIRouter(prefix="/api", tags=["query"])
pipeline = AnalyticsPipeline()


@router.post("/chat/query", response_model=QueryResponse)
def query_dataset(payload: QueryRequest) -> QueryResponse:
    try:
        return pipeline.answer_question(payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Dataset not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Query failed: {exc}") from exc


@router.post("/chat/query-all", response_model=QueryResponse)
def query_all_datasets(payload: QueryAllRequest) -> QueryResponse:
    try:
        return pipeline.answer_question_all(payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Query failed: {exc}") from exc
