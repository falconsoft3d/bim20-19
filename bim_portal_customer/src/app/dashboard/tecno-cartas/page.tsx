"use client";

import { useState, useEffect, useMemo } from "react";
import { ChevronRight, ChevronDown, FolderOpen, Folder, FileText, Search, X } from "lucide-react";
import { fetchTecnoCartas, type TecnoCartaCategoria, type TecnoCarta } from "@/lib/tecnoCartas";

// ── Helpers de filtrado ───────────────────────────────────────────────────────

function filterTree(
  cats: TecnoCartaCategoria[],
  q: string,
): TecnoCartaCategoria[] {
  if (!q) return cats;
  const lq = q.toLowerCase();
  return cats.reduce<TecnoCartaCategoria[]>((acc, cat) => {
    const filteredChildren = filterTree(cat.children, q);
    const filteredCartas = cat.cartas.filter(
      (c) => c.titulo.toLowerCase().includes(lq),
    );
    const nameMatch = cat.name.toLowerCase().includes(lq);
    if (nameMatch || filteredChildren.length > 0 || filteredCartas.length > 0) {
      acc.push({
        ...cat,
        children: nameMatch ? cat.children : filteredChildren,
        cartas: nameMatch ? cat.cartas : filteredCartas,
      });
    }
    return acc;
  }, []);
}

// ── Nodo del árbol ────────────────────────────────────────────────────────────

function CategoryNode({
  cat,
  selectedCarta,
  onSelectCarta,
  depth = 0,
  forceOpen = false,
}: {
  cat: TecnoCartaCategoria;
  selectedCarta: (TecnoCarta & { categoryName: string }) | null;
  onSelectCarta: (carta: TecnoCarta & { categoryName: string }) => void;
  depth?: number;
  forceOpen?: boolean;
}) {
  const hasChildren = cat.children.length > 0;
  const hasCartas = cat.cartas.length > 0;
  const [open, setOpen] = useState(depth === 0);

  // Cuando hay búsqueda activa, forzar apertura
  useEffect(() => {
    if (forceOpen) setOpen(true);
  }, [forceOpen]);

  return (
    <div>
      {/* Cabecera de categoría */}
      <button
        onClick={() => (hasChildren || hasCartas) && setOpen((o) => !o)}
        className={`flex items-center gap-2 w-full text-left px-2 py-1.5 rounded-lg text-sm font-medium transition-colors hover:bg-[#5c2d5c]/20 ${
          depth === 0 ? "text-white" : "text-white/80"
        }`}
        style={{ paddingLeft: `${8 + depth * 16}px` }}
      >
        {(hasChildren || hasCartas) ? (
          open ? <ChevronDown className="w-4 h-4 shrink-0" /> : <ChevronRight className="w-4 h-4 shrink-0" />
        ) : (
          <span className="w-4 h-4 shrink-0" />
        )}
        {open ? (
          <FolderOpen className="w-4 h-4 shrink-0 text-[#4fc3f7]" />
        ) : (
          <Folder className="w-4 h-4 shrink-0 text-[#4fc3f7]" />
        )}
        <span className="truncate">{cat.name}</span>
        {hasCartas && (
          <span className="ml-auto text-xs text-white/40 shrink-0">{cat.cartas.length}</span>
        )}
      </button>

      {/* Contenido expandido */}
      {open && (
        <div>
          {/* Cartas de esta categoría */}
          {cat.cartas.map((carta) => {
            const isSelected = selectedCarta?.id === carta.id;
            return (
              <button
                key={carta.id}
                onClick={() => onSelectCarta({ ...carta, categoryName: cat.name })}
                className={`flex items-center gap-2 w-full text-left px-2 py-1.5 rounded-lg text-sm transition-colors ${
                  isSelected
                    ? "bg-[#5c2d5c] text-white"
                    : "text-white/70 hover:bg-white/10 hover:text-white"
                }`}
                style={{ paddingLeft: `${8 + (depth + 1) * 16}px` }}
              >
                <FileText className="w-3.5 h-3.5 shrink-0" />
                <span className="truncate">{carta.titulo}</span>
              </button>
            );
          })}

          {/* Subcategorías */}
          {cat.children.map((child) => (
            <CategoryNode
              key={child.id}
              cat={child}
              depth={depth + 1}
              forceOpen={forceOpen}
              selectedCarta={selectedCarta}
              onSelectCarta={onSelectCarta}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Página principal ──────────────────────────────────────────────────────────

export default function TecnoCartasPage() {
  const [categories, setCategories] = useState<TecnoCartaCategoria[]>([]);
  const [selected, setSelected] = useState<(TecnoCarta & { categoryName: string }) | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    fetchTecnoCartas()
      .then((data) => {
        setCategories(data);
        for (const cat of data) {
          if (cat.cartas.length > 0) {
            setSelected({ ...cat.cartas[0], categoryName: cat.name });
            break;
          }
        }
      })
      .catch(() => setError("No se pudieron cargar las Tecno Cartas."))
      .finally(() => setLoading(false));
  }, []);

  const visibleCategories = useMemo(() => filterTree(categories, query.trim()), [categories, query]);
  const isSearching = query.trim().length > 0;

  return (
    <div className="flex gap-4 h-full max-w-[1400px]" style={{ minHeight: "calc(100vh - 120px)" }}>

      {/* ── Panel izquierdo: árbol ───────────────────────────────── */}
      <aside className="w-64 shrink-0 bg-[#3b1a3a] rounded-xl flex flex-col overflow-hidden">
        <div className="px-4 py-3 border-b border-white/10">
          <h2 className="text-xs font-bold text-white/60 uppercase tracking-wider mb-2">Tecno Cartas</h2>
          {/* Buscador */}
          <div className="relative">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-white/40 pointer-events-none" />
            <input
              type="text"
              placeholder="Buscar…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full bg-white/10 text-white text-xs placeholder-white/30 rounded-lg pl-7 pr-7 py-1.5 outline-none focus:ring-1 focus:ring-[#4fc3f7]"
            />
            {query && (
              <button
                onClick={() => setQuery("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-white/40 hover:text-white"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-2 py-2 space-y-0.5">
          {loading && (
            <p className="text-xs text-white/40 text-center py-6 animate-pulse">Cargando…</p>
          )}
          {error && (
            <p className="text-xs text-red-400 text-center py-6">{error}</p>
          )}
          {!loading && visibleCategories.length === 0 && !error && (
            <p className="text-xs text-white/40 text-center py-6">
              {isSearching ? "Sin resultados." : "Sin categorías."}
            </p>
          )}
          {visibleCategories.map((cat) => (
            <CategoryNode
              key={cat.id}
              cat={cat}
              forceOpen={isSearching}
              selectedCarta={selected}
              onSelectCarta={setSelected}
            />
          ))}
        </div>
      </aside>

      {/* ── Panel derecho: contenido ─────────────────────────────── */}
      <main className="flex-1 bg-white rounded-xl shadow-sm overflow-hidden flex flex-col">
        {selected ? (
          <>
            {/* Cabecera */}
            <div className="px-6 py-4 border-b border-gray-100">
              <p className="text-xs text-gray-400 uppercase tracking-wider mb-1">
                {selected.categoryName}
              </p>
              <h1 className="text-xl font-bold text-gray-900">{selected.titulo}</h1>
            </div>

            {/* Contenido HTML */}
            <div
              className="flex-1 overflow-y-auto px-6 py-5 prose prose-sm max-w-none"
              dangerouslySetInnerHTML={{ __html: selected.texto || "<p class='text-gray-400'>Sin contenido.</p>" }}
            />
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
            {loading ? "Cargando…" : "Selecciona una Tecno Carta del panel izquierdo."}
          </div>
        )}
      </main>
    </div>
  );
}
