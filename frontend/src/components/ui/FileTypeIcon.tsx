import { FileIcon, FilePdfIcon, FileTextIcon } from "./icons";

interface FileTypeIconProps {
  name: string;
  className?: string;
}

export function fileKind(name: string): "pdf" | "docx" | "markdown" | "text" {
  const ext = name.split(".").pop()?.toLowerCase() ?? "";
  if (ext === "pdf") return "pdf";
  if (ext === "docx") return "docx";
  if (ext === "md" || ext === "markdown") return "markdown";
  return "text";
}

export function FileTypeIcon({ name, className = "h-4 w-4" }: FileTypeIconProps) {
  const kind = fileKind(name);
  const tones: Record<string, string> = {
    pdf: "bg-red-50 text-red-600",
    docx: "bg-blue-50 text-blue-600",
    markdown: "bg-slate-100 text-slate-600",
    text: "bg-slate-100 text-slate-500",
  };
  const Icon = kind === "pdf" ? FilePdfIcon : kind === "docx" ? FileTextIcon : FileIcon;
  return (
    <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${tones[kind]}`}>
      <Icon className={className} />
    </span>
  );
}