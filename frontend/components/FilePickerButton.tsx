"use client";
import { useRef } from "react";

interface Props {
  accept: string;
  selectedFile: File | null;
  onChange: (file: File) => void;
}

export default function FilePickerButton({ accept, selectedFile, onChange }: Props) {
  const ref = useRef<HTMLInputElement>(null);

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 8 }}>
      <input
        ref={ref}
        type="file"
        accept={accept}
        style={{ display: "none" }}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onChange(f);
        }}
      />
      <button
        type="button"
        onClick={() => ref.current?.click()}
        style={{
          display: "flex", alignItems: "center", gap: 7,
          padding: "7px 14px",
          background: "var(--surface2)",
          border: "1px solid var(--accent)",
          borderRadius: 7,
          color: "var(--accent-light)",
          fontSize: 12, fontWeight: 600,
          cursor: "pointer",
          whiteSpace: "nowrap",
          transition: "background 0.15s",
        }}
        onMouseEnter={(e) => ((e.currentTarget as HTMLButtonElement).style.background = "rgba(124,106,247,0.12)")}
        onMouseLeave={(e) => ((e.currentTarget as HTMLButtonElement).style.background = "var(--surface2)")}
      >
        <span style={{ fontSize: 14 }}>📎</span>
        Choose File
      </button>

      <span style={{
        fontSize: 12,
        color: selectedFile ? "var(--text)" : "var(--muted)",
        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        maxWidth: 220,
      }}>
        {selectedFile ? selectedFile.name : "No file chosen"}
      </span>
    </div>
  );
}
