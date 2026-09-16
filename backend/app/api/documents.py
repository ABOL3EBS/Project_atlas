from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile

from app.config import Settings, get_settings
from app.ingestion import UnsupportedFormatError
from app.models.schemas import DocumentOut
from app.services.ingestion_service import IngestionService, sanitize_filename

from .deps import get_ingestion_service

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentOut, status_code=201)
def upload_document(
    file: UploadFile,
    knowledge_base_id: str = Form(default="default"),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
    settings: Settings = Depends(get_settings),
) -> DocumentOut:
    content = file.file.read()
    if len(content) > settings.max_upload_size:
        raise HTTPException(status_code=413, detail="File too large")
    try:
        record = ingestion_service.ingest(
            knowledge_base_id, sanitize_filename(file.filename or "upload"), content
        )
    except (UnsupportedFormatError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return DocumentOut(**record)


@router.get("", response_model=list[DocumentOut])
def list_documents(
    knowledge_base_id: str = "default",
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> list[DocumentOut]:
    return [DocumentOut(**record) for record in ingestion_service.list(knowledge_base_id)]


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: str,
    knowledge_base_id: str = "default",
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> None:
    if not ingestion_service.delete(knowledge_base_id, document_id):
        raise HTTPException(status_code=404, detail="Document not found")