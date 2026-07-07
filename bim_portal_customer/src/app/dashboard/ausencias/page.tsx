"use client";

import { useState, useEffect } from "react";
import {
  Plus, CalendarDays, Clock, CheckCircle2, XCircle, FileText, Send,
} from "lucide-react";
import {
  fetchAusencias, createAusencia,
  type Ausencia, type AusenciaTipo,
} from "@/lib/ausencias";

// ── helpers ────────────────────────────────────────────────────────────────

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

function fmt(d: string) {
  if (!d) return "-";
  return new Date(d).toLocaleDateString("es-ES", {
    day: "2-digit", month: "short", year: "numeric",
  });
}

function diffDays(from: string, to: string): number {
  const a = new Date(from), b = new Date(to);
  return Math.max(1, Math.round((b.getTime() - a.getTime()) / 86400000) + 1);
}

// ── componente principal ────────────────────────────────────────────────────

export default function AusenciasPage() {
  const [ausencias, setAusencias] = useState<Ausencia[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);

  // form state
  const [tipo, setTipo] = useState<AusenciaTipo>("vacaciones");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [sending, setSending] = useState(false);
  const [formError, setFormError] = useState("");

  useEffect(() => {
    fetchAusencias()
      .then(setAusencias)
      .finally(() => setLoading(false));
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError("");
    if (!dateFrom || !dateTo) { setFormError("Las fechas son obligatorias."); return; }
    if (dateFrom > dateTo) { setFormError("La fecha desde no puede ser posterior a la fecha hasta."); return; }
    setSending(true);
    const nueva = await createAusencia({ tipo, date_from: dateFrom, date_to: dateTo, descripcion });
    setSending(false);
    if (!nueva) { setFormError("Error al crear la solicitud. Inténtalo de nuevo."); return; }
    setAusencias((prev) => [nueva, ...prev]);
    setShowForm(false);
    setTipo("vacaciones");
    setDateFrom(""); setDateTo(""); setDescripcion("");
  }

  return (
    <div className="max-w-3xl space-y-5">

      {/* Cabecera */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Solicitudes de Ausencia</h1>
          <p className="text-sm text-gray-500 mt-0.5">Gestiona tus vacaciones y permisos</p>
        </div>
        <button
          onClick={() => { setShowForm((v) => !v); setFormError(""); }}
          className="flex items-center gap-2 px-4 py-2 bg-[#5c2d5c] text-white text-sm font-medium rounded-lg hover:bg-[#7a3d7a] transition-colors"
        >
          <Plus className="w-4 h-4" />
          Nueva solicitud
        </button>
      </div>

      {/* Formulario inline */}
      {showForm && (
        <div className="bg-white rounded-xl shadow-sm border border-[#5c2d5c]/20 p-5">
          <h2 className="text-sm font-bold text-gray-700 mb-4 flex items-center gap-2">
            <FileText className="w-4 h-4 text-[#5c2d5c]" />
            Nueva Solicitud de Ausencia
          </h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Tipo */}
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Tipo *</label>
              <div className="flex gap-3">
                {(["vacaciones", "permiso", "otros"] as AusenciaTipo[]).map((t) => (
                  <label key={t} className="flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="radio" name="tipo" value={t}
                      checked={tipo === t}
                      onChange={() => setTipo(t)}
                      className="accent-[#5c2d5c]"
                    />
                    <span className="text-sm capitalize text-gray-700">
                      {t === "vacaciones" ? "Vacaciones" : t === "permiso" ? "Permiso" : "Otros"}
                    </span>
                  </label>
                ))}
              </div>
            </div>

            {/* Fechas */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1">Fecha desde *</label>
                <input
                  type="date" value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                  className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#5c2d5c]/30 focus:border-[#5c2d5c]"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1">Fecha hasta *</label>
                <input
                  type="date" value={dateTo} min={dateFrom}
                  onChange={(e) => setDateTo(e.target.value)}
                  className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#5c2d5c]/30 focus:border-[#5c2d5c]"
                  required
                />
              </div>
            </div>

            {/* Descripción */}
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">
                Descripción / Aclaración
              </label>
              <textarea
                value={descripcion}
                onChange={(e) => setDescripcion(e.target.value)}
                placeholder="Motivo o detalle de la ausencia…"
                rows={3}
                className="w-full resize-none text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#5c2d5c]/30 focus:border-[#5c2d5c]"
              />
            </div>

            {formError && (
              <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                {formError}
              </p>
            )}

            <div className="flex justify-end gap-2 pt-1">
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="px-4 py-2 text-sm rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors"
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={sending}
                className="flex items-center gap-1.5 px-4 py-2 text-sm rounded-lg bg-[#5c2d5c] text-white font-medium hover:bg-[#7a3d7a] disabled:opacity-40 transition-colors"
              >
                <Send className="w-4 h-4" />
                {sending ? "Enviando…" : "Enviar solicitud"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Lista */}
      {loading ? (
        <div className="text-sm text-gray-400 animate-pulse py-8 text-center">
          Cargando solicitudes…
        </div>
      ) : ausencias.length === 0 ? (
        <div className="bg-white rounded-xl shadow-sm p-10 text-center text-gray-400">
          <CalendarDays className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p className="text-sm">No tienes solicitudes de ausencia aún.</p>
          <p className="text-xs mt-1">Haz clic en "Nueva solicitud" para crear una.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {ausencias.map((aus) => (
            <div key={aus.id} className="bg-white rounded-xl shadow-sm p-4 flex flex-col sm:flex-row sm:items-center gap-3">
              {/* Info principal */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs font-mono text-[#5c2d5c] bg-[#5c2d5c]/10 px-2 py-0.5 rounded">
                    {aus.name}
                  </span>
                  <span className="text-sm font-semibold text-gray-800">{aus.tipo_label}</span>
                </div>
                <div className="flex items-center gap-3 mt-1.5 text-xs text-gray-500">
                  <span className="flex items-center gap-1">
                    <CalendarDays className="w-3.5 h-3.5" />
                    {fmt(aus.date_from)} → {fmt(aus.date_to)}
                  </span>
                  <span className="text-gray-300">·</span>
                  <span>{diffDays(aus.date_from, aus.date_to)} día{diffDays(aus.date_from, aus.date_to) !== 1 ? "s" : ""}</span>
                </div>
                {aus.descripcion && (
                  <p className="mt-1.5 text-xs text-gray-500 line-clamp-2">{aus.descripcion}</p>
                )}
              </div>

              {/* Estado */}
              <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold whitespace-nowrap ${STATE_STYLE[aus.state]}`}>
                {STATE_ICON[aus.state]}
                {aus.state_label}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
