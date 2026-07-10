"use client";

import { useEffect, useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { getStoredPartner } from "@/lib/auth";
import { fetchDocumentos, type BimDocumento } from "@/lib/documentos";
import { getOdooBaseUrl } from "@/lib/odoo";
import {
  FileText,
  Download,
  FolderOpen,
  Calendar,
  Building2,
  ChevronDown,
  ChevronRight,
  Folder,
  Link2,
} from "lucide-react";

const TYPE_LABEL: Record<string, string> = {
  contract: "Contrato",
  info: "Información",
  budget: "Presupuesto",
  other: "Otro",
};

function DocumentoCard({ doc }: { doc: BimDocumento }) {
  const base = getOdooBaseUrl();
  const url = doc.download_url.startsWith("http")
    ? doc.download_url
    : `${base}${doc.download_url}`;

  return (
    <div className="bg-white border border-gray-100 rounded-xl p-4 shadow-sm hover:shadow-md transition-shadow flex items-start justify-between gap-4">
      <div className="flex items-start gap-3 min-w-0">
        <div className="mt-0.5 shrink-0 w-9 h-9 bg-[#5c2d5c]/10 rounded-lg flex items-center justify-center">
          <FileText className="w-4 h-4 text-[#5c2d5c]" />
        </div>
        <div className="min-w-0">
          <p className="font-semibold text-gray-800 text-sm truncate">
            {doc.desc || doc.name}
          </p>
          <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1 text-xs text-gray-500">
            {doc.project_name && (
              <span className="flex items-center gap-1">
                <Building2 className="w-3 h-3" />
                {doc.project_name}
              </span>
            )}
            {doc.date && (
              <span className="flex items-center gap-1">
                <Calendar className="w-3 h-3" />
                {new Date(doc.date).toLocaleDateString("es-ES")}
              </span>
            )}
            {doc.type && (
              <span className="bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
                {TYPE_LABEL[doc.type] ?? doc.type}
              </span>
            )}
          </div>
          {doc.file_name && (
            <p className="text-xs text-gray-400 mt-0.5 truncate">
              {doc.file_name}
            </p>
          )}
        </div>
      </div>

      <div className="shrink-0 flex flex-col gap-1.5">
        {doc.has_file && (
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-[#5c2d5c] text-white hover:bg-[#4a2449] transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            Descargar
          </a>
        )}
        {doc.share_url && (
          <a
            href={doc.share_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-[#5c2d5c] text-[#5c2d5c] hover:bg-[#5c2d5c]/10 transition-colors"
          >
            <Link2 className="w-3.5 h-3.5" />
            Ver enlace
          </a>
        )}
      </div>
    </div>
  );
}

function CategorySection({ name, docs }: { name: string; docs: BimDocumento[] }) {
  const [open, setOpen] = useState(true);

  return (
    <div className="mb-4">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-3 py-2.5 bg-[#5c2d5c]/8 hover:bg-[#5c2d5c]/15 rounded-xl transition-colors text-left"
      >
        <Folder className="w-4 h-4 text-[#5c2d5c] shrink-0" />
        <span className="font-semibold text-[#5c2d5c] text-sm flex-1">{name}</span>
        <span className="text-xs text-[#5c2d5c]/60 mr-1">
          {docs.length} {docs.length === 1 ? "documento" : "documentos"}
        </span>
        {open ? (
          <ChevronDown className="w-4 h-4 text-[#5c2d5c]/60 shrink-0" />
        ) : (
          <ChevronRight className="w-4 h-4 text-[#5c2d5c]/60 shrink-0" />
        )}
      </button>

      {open && (
        <div className="mt-2 ml-3 space-y-2 border-l-2 border-[#5c2d5c]/10 pl-3">
          {docs.map((doc) => (
            <DocumentoCard key={doc.id} doc={doc} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function DocumentosPage() {
  const router = useRouter();
  const [docs, setDocs] = useState<BimDocumento[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    const p = getStoredPartner();
    if (!p) { router.replace("/login"); return; }
    if (!p.is_customer) { router.replace("/dashboard"); return; }
    fetchDocumentos().then((d) => { setDocs(d); setLoading(false); });
  }, [router]);

  const grouped = useMemo(() => {
    const q = search.toLowerCase();
    const filtered = q
      ? docs.filter(
          (d) =>
            d.desc.toLowerCase().includes(q) ||
            d.name.toLowerCase().includes(q) ||
            d.project_name.toLowerCase().includes(q) ||
            d.categoria_name.toLowerCase().includes(q)
        )
      : docs;

    const map = new Map<string, BimDocumento[]>();
    for (const doc of filtered) {
      const cat = doc.categoria_name || "Sin categoría";
      if (!map.has(cat)) map.set(cat, []);
      map.get(cat)!.push(doc);
    }
    return [...map.entries()].sort(([a], [b]) => {
      if (a === "Sin categoría") return 1;
      if (b === "Sin categoría") return -1;
      return a.localeCompare(b, "es");
    });
  }, [docs, search]);

  const total = grouped.reduce((s, [, d]) => s + d.length, 0);

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-800">Documentos</h1>
        <p className="text-sm text-gray-500 mt-1">Documentos compartidos de sus proyectos</p>
      </div>

      <div className="mb-5">
        <input
          type="text"
          placeholder="Buscar por descripción, proyecto, categoría…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full text-sm border border-gray-200 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#5c2d5c]/30 focus:border-[#5c2d5c]"
        />
      </div>

      {loading ? (
        <div className="text-center py-16 text-gray-400 text-sm">Cargando documentos…</div>
      ) : total === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <FolderOpen className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p className="text-sm">{search ? "Sin resultados." : "No hay documentos compartidos."}</p>
        </div>
      ) : (
        <>
          <p className="text-xs text-gray-400 mb-4">
            {total} {total === 1 ? "documento" : "documentos"} en{" "}
            {grouped.length} {grouped.length === 1 ? "categoría" : "categorías"}
          </p>
          {grouped.map(([cat, catDocs]) => (
            <CategorySection key={cat} name={cat} docs={catDocs} />
          ))}
        </>
      )}
    </div>
  );
}
