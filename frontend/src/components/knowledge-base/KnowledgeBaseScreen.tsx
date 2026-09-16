import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { useApp } from "../../context/AppContext";
import { deleteDocument, listDocuments, uploadDocument } from "../../lib/client";
import type { Citation, Document } from "../../lib/types";
import { SourceDrawer } from "../chat/SourceDrawer";
import { Header } from "../layout/Header";
import { Button } from "../ui/Button";
import { DocumentMultiIcon, UploadCloudIcon } from "../ui/icons";
import { CollectionSelector } from "./CollectionSelector";
import { DocumentRow } from "./DocumentRow";

export function KnowledgeBaseScreen() {
  const { knowledgeBase, refreshKnowledgeBases } = useApp();
  const location = useLocation();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [uploadOpen, setUploadOpen] = useState<boolean>(false);
  const [uploading, setUploading] = useState(false);
  const [uploadErrors, setUploadErrors] = useState<string[]>([]);
  const [deleting, setDeleting] = useState<Document | null>(null);
  const [preview, setPreview] = useState<Citation | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      setDocuments(await listDocuments(knowledgeBase));
    } catch (cause) {
      setLoadError(cause instanceof Error ? cause.message : "Failed to load documents.");
    } finally {
      setLoading(false);
    }
  }, [knowledgeBase]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if ((location.state as { openUpload?: boolean } | null)?.openUpload) {
      setUploadOpen(true);
    }
  }, [location.state]);

  const handleFiles = async (files: File[]) => {
    if (files.length === 0) return;
    setUploading(true);
    setUploadErrors([]);
    const errors: string[] = [];
    for (const file of files) {
      try {
        const created = await uploadDocument(knowledgeBase, file);
        setDocuments((current) => [created, ...current.filter((d) => d.id !== created.id)]);
      } catch (cause) {
        errors.push(`${file.name}: ${cause instanceof Error ? cause.message : "upload failed"}`);
      }
    }
    setUploadErrors(errors);
    setUploading(false);
    void refreshKnowledgeBases();
  };

  const confirmDelete = async () => {
    if (!deleting) return;
    try {
      await deleteDocument(knowledgeBase, deleting.id);
      setDocuments((current) => current.filter((d) => d.id !== deleting.id));
      void refreshKnowledgeBases();
    } catch (cause) {
      setUploadErrors([`Delete failed: ${cause instanceof Error ? cause.message : "unknown error"}`]);
    } finally {
      setDeleting(null);
    }
  };

  const indexed = documents.filter((d) => d.status === "indexed").length;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <Header
        title="Knowledge Base"
        subtitle="Manage your ingested documents."
        right={
          <Button
            variant="primary"
            icon={<UploadCloudIcon className="h-4 w-4" />}
            onClick={() => {
              setUploadOpen(true);
              setUploadErrors([]);
            }}
          >
            Upload
          </Button>
        }
      />

      <div className="flex-1 overflow-y-auto px-6 py-6 lg:px-8">
        <div className="mx-auto max-w-4xl">
          <div className="mb-5 flex items-center justify-between">
            <CollectionSelector />
            <p className="text-sm text-slate-500">
              {indexed} document{indexed === 1 ? "" : "s"} indexed
            </p>
          </div>

          {uploadOpen && (
            <div
              className={`mb-4 rounded-xl border-2 border-dashed p-8 text-center transition-colors ${
                dragOver ? "border-blue-400 bg-blue-50/40" : "border-slate-300"
              }`}
              onDragOver={(event) => {
                event.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(event) => {
                event.preventDefault();
                setDragOver(false);
                void handleFiles(Array.from(event.dataTransfer.files));
              }}
            >
              <UploadCloudIcon className="mx-auto mb-2 h-8 w-8 text-slate-300" />
              <p className="text-sm text-slate-600">
                Drag files here or{" "}
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="font-medium text-blue-600 underline underline-offset-2 hover:text-blue-700"
                >
                  browse
                </button>
              </p>
              <p className="mt-1 text-xs text-slate-400">Accepted formats: PDF, DOCX, MD, TXT</p>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".pdf,.docx,.md,.txt"
                className="hidden"
                onChange={(event) => {
                  void handleFiles(Array.from(event.target.files ?? []));
                  event.target.value = "";
                }}
              />
              {uploading && <p className="mt-3 text-sm text-slate-500">Processing…</p>}
            </div>
          )}

          {uploadErrors.length > 0 && (
            <div className="mb-4 space-y-1 rounded-xl border border-red-200 bg-red-50 px-4 py-3">
              {uploadErrors.map((error) => (
                <p key={error} className="text-xs text-red-700">
                  {error}
                </p>
              ))}
            </div>
          )}

          {loading ? (
            <p className="text-sm text-slate-500">Loading documents…</p>
          ) : loadError ? (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {loadError}
            </div>
          ) : documents.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 py-16">
              <DocumentMultiIcon className="mb-3 h-10 w-10 text-slate-300" />
              <h3 className="text-base font-semibold text-slate-900">No documents yet</h3>
              <p className="mt-1 text-sm text-slate-500">
                Upload a document to start asking questions about it.
              </p>
              <Button
                className="mt-4"
                variant="primary"
                icon={<UploadCloudIcon className="h-4 w-4" />}
                onClick={() => setUploadOpen(true)}
              >
                Upload
              </Button>
            </div>
          ) : (
            <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
              {documents.map((document) => (
                <DocumentRow
                  key={document.id}
                  document={document}
                  onPreview={() =>
                    setPreview({
                      chunk_id: document.id,
                      document_id: document.id,
                      document_name: document.name,
                    })
                  }
                  onDelete={() => setDeleting(document)}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {deleting && (
        <div className="fixed inset-0 z-50 flex items-center justify-center" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-slate-900/20" onClick={() => setDeleting(null)} aria-hidden />
          <div className="relative w-full max-w-sm rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="text-base font-semibold text-slate-900">Delete document?</h3>
            <p className="mt-1 text-sm text-slate-500">
              This removes <span className="font-medium text-slate-700">{deleting.name}</span> and
              its {deleting.chunk_count} chunks from the index. This cannot be undone.
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setDeleting(null)}>
                Cancel
              </Button>
              <Button variant="danger" onClick={() => void confirmDelete()}>
                Delete
              </Button>
            </div>
          </div>
        </div>
      )}

      {preview && <SourceDrawer citation={preview} onClose={() => setPreview(null)} />}
    </div>
  );
}