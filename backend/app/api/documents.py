from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile

from app.config import Settings, get_settings
from app.ingestion import UnsupportedFormatError
from app.models.schemas import DocumentChunkOut, DocumentOut, IsolatedKnowledgeBaseOut
from app.retrieval.base import VectorStore
from app.services.document_store import DocumentStore
from app.services.ingestion_service import IngestionService, sanitize_filename

from .deps import get_document_store, get_ingestion_service, get_vector_store

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/knowledge-bases", response_model=list[IsolatedKnowledgeBaseOut])
def list_knowledge_bases(
    document_store: DocumentStore = Depends(get_document_store),
    vector_store: VectorStore = Depends(get_vector_store),
    settings: Settings = Depends(get_settings),
) -> list[IsolatedKnowledgeBaseOut]:
    records = document_store.list_knowledge_bases()
    has_default = any(
        record["knowledge_base_id"] == settings.default_knowledge_base_id
        for record in records
    )
    if not has_default:
        records.append(
            {
                "knowledge_base_id": settings.default_knowledge_base_id,
                "document_count": 0,
                "chunk_count": 0,
                "created_at": None,
            }
        )
    return [
        IsolatedKnowledgeBaseOut(
            id=record["knowledge_base_id"],
            document_count=record["document_count"],
            chunk_count=record["chunk_count"],
            created_at=record["created_at"],
        )
        for record in records
    ]


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


@router.get("/{document_id}/chunks", response_model=list[DocumentChunkOut])
def document_chunks(
    document_id: str,
    knowledge_base_id: str = "default",
    vector_store: VectorStore = Depends(get_vector_store),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> list[DocumentChunkOut]:
    record = next(
        (
            candidate
            for candidate in ingestion_service.list(knowledge_base_id)
            if candidate["id"] == document_id
        ),
        None,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Document not found")
    chunks = vector_store.get_document_chunks(knowledge_base_id, document_id, limit=200)
    return [
        DocumentChunkOut(
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            document_name=record["name"],
            chunk_id=chunk["chunk_id"],
            text=chunk["text"],
            page=chunk.get("page"),
            section=chunk.get("section"),
        )
        for chunk in chunks
    ]


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: str,
    knowledge_base_id: str = "default",
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> None:
    if not ingestion_service.delete(knowledge_base_id, document_id):
        raise HTTPException(status_code=404, detail="Document not found")