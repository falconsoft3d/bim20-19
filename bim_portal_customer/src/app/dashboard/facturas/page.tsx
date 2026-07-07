"use client";

import { useState, useEffect, useRef } from "react";
import {
  Plus, FileText, Send, CheckCircle2, XCircle, Clock,
  Paperclip, Building2, CalendarDays, DollarSign, X,
} from "lucide-react";
import {
  fetchFacturas, fetchProveedores, fetchProyectosFactura,
  createFactura, fileToBase64, accionFactura,
  type FacturaProveedor, type SelectOption,
} from "@/lib/facturas";

// ── helpers ─────────────────────────────────────────────────────────────────

const STATE_STYLE: Record<string, string> = {
  draft:     "bg-gray-100 text-gray-600",
  submitted: "bg-yellow-100 text-yellow-700",
  approved:  "bg-green-100 text-green-700",
  rejected:  "bg-red-100 text-red-700",
};
const STATE_ICON: Record<string, React.ReactNode> = {
  draft:     <Clock className="w-3.5 h-3.5" />,
  submitted: <Send className="w-3.5 h-3.5" />,
  approved:  <CheckCircle2 className="w-3.5 h-3.5" />,
  rejected:  <XCircle className="w-3.5 h-3.5" />,
};

const fmt = (d: string) =>
  d ? new Date(d).toLocaleDateString("es-ES", { day: "2-digit", month: "short", year: "numeric" }) : "-";

const fmtMoney = (n: number) =>
  new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR" }).format(n);

// ── componente ───────────────────────────────────────────────────────────────

export default function FacturasPage() {
  const [facturas,    setFacturas]    = useState<FacturaProveedor[]>([]);
  const [proveedores, setProveedores] = useState<SelectOption[]>([]);
  const [proyectos,   setProyectos]   = useState<SelectOption[]>([]);
  const [loading,     setLoading]     = useState(true);
  const [showForm,    setShowForm]    = useState(false);

  // form
  const [proveedorId, setProveedorId] = useState<number>(0);
  const [provSearch,  setProvSearch]  = useState("");
  const [provLoading, setProvLoading] = useState(false);
  const [projectId,   setProjectId]   = useState<number>(0);
  const [importe,     setImporte]     = useState("");
  const [fecha,       setFecha]       = useState("");
  const [notas,       setNotas]       = useState("");
  const [adjunto,     setAdjunto]     = useState<File | null>(null);
  const [sending,     setSending]     = useState(false);
  const [formError,   setFormError]   = useState("");
  const [actioningId, setActioningId] = useState<number | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    Promise.all([
      fetchFacturas().then(setFacturas),
      fetchProyectosFactura().then(setProyectos),
    ]).finally(() => setLoading(false));
  }, []);

  // Búsqueda de proveedores con debounce
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (provSearch.trim().length < 1) { setProveedores([]); return; }
    setProvLoading(true);
    debounceRef.current = setTimeout(() => {
      fetchProveedores(provSearch).then(setProveedores).finally(() => setProvLoading(false));
    }, 300);
  }, [provSearch]);

  function resetForm() {
    setProveedorId(0); setProvSearch(""); setProjectId(0);
    setImporte(""); setFecha(""); setNotas(""); setAdjunto(null);
    setFormError(""); setShowForm(false);
    if (fileRef.current) fileRef.current.value = "";
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError("");
    if (!proveedorId) { setFormError("Selecciona un proveedor."); return; }
    if (!projectId)   { setFormError("Selecciona un proyecto."); return; }
    if (!importe || parseFloat(importe) <= 0) { setFormError("El importe debe ser mayor que 0."); return; }
    if (!fecha)       { setFormError("La fecha es obligatoria."); return; }

    setSending(true);
    try {
      let adjunto_b64: string | undefined;
      let adjunto_nombre: string | undefined;
      if (adjunto) {
        adjunto_b64    = await fileToBase64(adjunto);
        adjunto_nombre = adjunto.name;
      }
      const result = await createFactura({
        proveedor_id: proveedorId,
        project_id:   projectId,
        importe:      parseFloat(importe),
        fecha,
        notas,
        adjunto_b64,
        adjunto_nombre,
      });
      if ('error' in result) { setFormError(result.error); return; }
      setFacturas((prev) => [result.factura, ...prev]);
      resetForm();
    } finally {
      setSending(false);
    }
  }

  async function handleAccion(id: number, accion: 'approve' | 'reject') {
    setActioningId(id);
    const updated = await accionFactura(id, accion);
    if (updated) {
      setFacturas((prev) => prev.map((f) => (f.id === id ? updated : f)));
    }
    setActioningId(null);
  }

  const inputCls = "w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#5c2d5c]/30 focus:border-[#5c2d5c]";

  return (
    <div className="max-w-3xl space-y-5">

      {/* Cabecera */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Facturas de Proveedor</h1>
          <p className="text-sm text-gray-500 mt-0.5">Envía facturas para imputar a un proyecto</p>
        </div>
        <button
          onClick={() => { setShowForm((v) => !v); setFormError(""); }}
          className="flex items-center gap-2 px-4 py-2 bg-[#5c2d5c] text-white text-sm font-medium rounded-lg hover:bg-[#7a3d7a] transition-colors"
        >
          <Plus className="w-4 h-4" /> Nueva factura
        </button>
      </div>

      {/* Formulario */}
      {showForm && (
        <div className="bg-white rounded-xl shadow-sm border border-[#5c2d5c]/20 p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-gray-700 flex items-center gap-2">
              <FileText className="w-4 h-4 text-[#5c2d5c]" />
              Nueva Factura de Proveedor
            </h2>
            <button onClick={resetForm} className="text-gray-400 hover:text-gray-600">
              <X className="w-4 h-4" />
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Proveedor */}
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Proveedor *</label>
              <input
                type="text"
                value={provSearch}
                onChange={(e) => { setProvSearch(e.target.value); setProveedorId(0); }}
                placeholder="Escribe para buscar cualquier contacto…"
                className={inputCls}
              />
              {provLoading && (
                <p className="text-xs text-gray-400 mt-1 animate-pulse">Buscando…</p>
              )}
              {!provLoading && provSearch.trim().length >= 1 && !proveedorId && proveedores.length > 0 && (
                <div className="border border-gray-200 rounded-lg mt-1 max-h-40 overflow-y-auto bg-white shadow-sm">
                  {proveedores.map((p) => (
                    <button
                      key={p.id} type="button"
                      onClick={() => { setProveedorId(p.id); setProvSearch(p.name); }}
                      className="w-full text-left px-3 py-2 text-sm hover:bg-[#5c2d5c]/5 transition-colors"
                    >
                      {p.name}
                    </button>
                  ))}
                </div>
              )}
              {!provLoading && provSearch.trim().length >= 1 && !proveedorId && proveedores.length === 0 && (
                <p className="text-xs text-gray-400 mt-1">Sin resultados para "{provSearch}"</p>
              )}
              {proveedorId > 0 && (
                <p className="text-xs text-green-600 mt-1 flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Proveedor seleccionado
                </p>
              )}
            </div>

            {/* Proyecto */}
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Proyecto *</label>
              <select
                value={projectId}
                onChange={(e) => setProjectId(Number(e.target.value))}
                className={inputCls}
              >
                <option value={0}>— Selecciona un proyecto —</option>
                {proyectos.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>

            {/* Importe + Fecha */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1">Importe (€) *</label>
                <div className="relative">
                  <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" />
                  <input
                    type="number" min="0.01" step="0.01" value={importe}
                    onChange={(e) => setImporte(e.target.value)}
                    placeholder="0.00"
                    className={`${inputCls} pl-8`}
                    required
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1">Fecha *</label>
                <input type="date" value={fecha}
                  onChange={(e) => setFecha(e.target.value)}
                  className={inputCls} required />
              </div>
            </div>

            {/* Adjunto */}
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">
                Adjunto (PDF / imagen)
              </label>
              <label className="flex items-center gap-2 px-3 py-2 border border-dashed border-gray-300 rounded-lg cursor-pointer hover:border-[#5c2d5c] transition-colors">
                <Paperclip className="w-4 h-4 text-gray-400" />
                <span className="text-sm text-gray-500">
                  {adjunto ? adjunto.name : "Haz clic para seleccionar archivo…"}
                </span>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png,.webp"
                  className="hidden"
                  onChange={(e) => setAdjunto(e.target.files?.[0] ?? null)}
                />
              </label>
            </div>

            {/* Notas */}
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Notas</label>
              <textarea value={notas} onChange={(e) => setNotas(e.target.value)}
                placeholder="Observaciones adicionales…" rows={2}
                className={`${inputCls} resize-none`} />
            </div>

            {formError && (
              <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                {formError}
              </p>
            )}

            <div className="flex justify-end gap-2 pt-1">
              <button type="button" onClick={resetForm}
                className="px-4 py-2 text-sm rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors">
                Cancelar
              </button>
              <button type="submit" disabled={sending}
                className="flex items-center gap-1.5 px-4 py-2 text-sm rounded-lg bg-[#5c2d5c] text-white font-medium hover:bg-[#7a3d7a] disabled:opacity-40 transition-colors">
                <Send className="w-4 h-4" />
                {sending ? "Enviando…" : "Enviar factura"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Lista */}
      {loading ? (
        <p className="text-sm text-gray-400 animate-pulse py-8 text-center">Cargando facturas…</p>
      ) : facturas.length === 0 ? (
        <div className="bg-white rounded-xl shadow-sm p-10 text-center text-gray-400">
          <FileText className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p className="text-sm">No has enviado facturas aún.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {facturas.map((fp) => (
            <div key={fp.id} className="bg-white rounded-xl shadow-sm p-4">
              <div className="flex flex-col sm:flex-row sm:items-start gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-mono text-[#5c2d5c] bg-[#5c2d5c]/10 px-2 py-0.5 rounded">
                      {fp.name}
                    </span>
                    <span className="text-sm font-semibold text-gray-800">{fp.proveedor}</span>
                    <span className="text-sm font-bold text-gray-900">{fmtMoney(fp.importe)}</span>
                  </div>
                  <div className="flex items-center gap-3 mt-1.5 text-xs text-gray-500 flex-wrap">
                    <span className="flex items-center gap-1">
                      <Building2 className="w-3.5 h-3.5" />{fp.project}
                    </span>
                    <span className="text-gray-300">·</span>
                    <span className="flex items-center gap-1">
                      <CalendarDays className="w-3.5 h-3.5" />{fmt(fp.fecha)}
                    </span>
                  </div>
                  {fp.notas && (
                    <p className="mt-1.5 text-xs text-gray-500 line-clamp-1">{fp.notas}</p>
                  )}
                  {fp.adjuntos.length > 0 && (
                    <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                      {fp.adjuntos.map((att) => (
                        <a key={att.id}
                          href={`${typeof window !== 'undefined' ? localStorage.getItem('bim_odoo_url') || 'http://localhost:8069' : ''}${att.url}`}
                          target="_blank" rel="noreferrer"
                          className="flex items-center gap-1 text-xs text-[#5c2d5c] hover:underline">
                          <Paperclip className="w-3 h-3" />{att.name}
                        </a>
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex flex-col items-end gap-2 shrink-0">
                  <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold whitespace-nowrap ${STATE_STYLE[fp.state]}`}>
                    {STATE_ICON[fp.state]}{fp.state_label}
                  </span>
                  {fp.state === 'submitted' && (
                    <div className="flex gap-1.5">
                      <button
                        onClick={() => handleAccion(fp.id, 'approve')}
                        disabled={actioningId === fp.id}
                        className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-lg bg-green-50 text-green-700 hover:bg-green-100 disabled:opacity-40 transition-colors"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        {actioningId === fp.id ? '…' : 'Aprobar'}
                      </button>
                      <button
                        onClick={() => handleAccion(fp.id, 'reject')}
                        disabled={actioningId === fp.id}
                        className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-lg bg-red-50 text-red-700 hover:bg-red-100 disabled:opacity-40 transition-colors"
                      >
                        <XCircle className="w-3.5 h-3.5" />
                        Rechazar
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
