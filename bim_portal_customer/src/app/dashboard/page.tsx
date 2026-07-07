"use client";

import { useState, useEffect } from "react";
import { ChevronDown } from "lucide-react";
import KpiCard from "@/components/KpiCard";
import {
  fetchProjects,
  sumField,
  fmtCurrency,
  fmtHours,
  fmtPct,
  type BimProject,
} from "@/lib/projects";

export default function DashboardPage() {
  const [projects, setProjects] = useState<BimProject[]>([]);
  const [selectedId, setSelectedId] = useState<number | "all">("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchProjects()
      .then((data) => {
        setProjects(data);
        if (data.length === 1) setSelectedId(data[0].id);
      })
      .catch(() => setError("No se pudieron cargar las obras."))
      .finally(() => setLoading(false));
  }, []);

  // Proyecto(s) activos según selector
  const active: BimProject[] =
    selectedId === "all"
      ? projects
      : projects.filter((p) => p.id === selectedId);

  const currency = active[0]?.currency ?? "€";

  const kpis = {
    balance: sumField(active, "balance"),
    sale_total: sumField(active, "sale_total"),
    cost_total: sumField(active, "cost_total"),
    profit: sumField(active, "profit"),
    margin: active.length === 1 ? active[0].margin : (sumField(active, "sale_total") > 0 ? (1 - sumField(active, "cost_total") / sumField(active, "sale_total")) * 100 : 0),
    budgeted_hours: sumField(active, "budgeted_hours"),
    real_hours: sumField(active, "real_hours"),
  };

  return (
    <div className="space-y-5 max-w-[1400px]">

      {/* ── Selector de obra ──────────────────────────────────────── */}
      <div className="bg-white rounded-xl shadow-sm p-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 shrink-0">
          <div className="w-4 h-4 rounded bg-gray-800" />
          <span className="text-sm font-bold text-[#4fc3f7]">Mis Obras</span>
        </div>

        <div className="relative flex-1 min-w-[280px]">
          <select
            value={selectedId}
            onChange={(e) =>
              setSelectedId(e.target.value === "all" ? "all" : Number(e.target.value))
            }
            className="w-full appearance-none pl-3 pr-8 py-2 rounded-lg border border-gray-300 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-[#5c2d5c]"
            disabled={loading}
          >
            {projects.length > 1 && (
              <option value="all">— Todas mis obras ({projects.length}) —</option>
            )}
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}{p.nombre ? ` · ${p.nombre}` : ""}
              </option>
            ))}
            {!loading && projects.length === 0 && (
              <option value="all">Sin obras asignadas</option>
            )}
          </select>
          <ChevronDown className="absolute right-2 top-2.5 w-4 h-4 text-gray-400 pointer-events-none" />
        </div>

        {loading && (
          <span className="text-xs text-gray-400 animate-pulse">Cargando…</span>
        )}
      </div>

      {/* ── Error ─────────────────────────────────────────────────── */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3">
          {error}
        </div>
      )}

      {/* ── KPI Costes ────────────────────────────────────────────── */}
      {!loading && active.length > 0 && (
        <>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">
              Costes
            </span>
            <span className="text-xs text-gray-400">
              {selectedId === "all" ? `${projects.length} obras` : active[0]?.state || ""}
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-7 gap-4">
            <KpiCard
              title="Importe"
              value={fmtCurrency(kpis.balance, currency)}
              colorVariant="default"
            />
            <KpiCard
              title="Ventas"
              value={fmtCurrency(kpis.sale_total, currency)}
              colorVariant="default"
            />
            <KpiCard
              title="Costos de obra"
              value={fmtCurrency(kpis.cost_total, currency)}
              colorVariant="default"
            />
            <KpiCard
              title="Beneficio"
              value={fmtCurrency(kpis.profit, currency)}
              colorVariant={kpis.profit >= 0 ? "green" : "yellow"}
            />
            <KpiCard
              title="Margen %"
              value={fmtPct(kpis.margin)}
              colorVariant={kpis.margin >= 0 ? "teal" : "yellow"}
            />
            <KpiCard
              title="HH Presup."
              value={fmtHours(kpis.budgeted_hours)}
              colorVariant="default"
            />
            <KpiCard
              title="HH Real"
              value={fmtHours(kpis.real_hours)}
              colorVariant={kpis.real_hours <= kpis.budgeted_hours ? "green" : "yellow"}
            />
          </div>
        </>
      )}

      {/* ── Empty state ───────────────────────────────────────────── */}
      {!loading && projects.length === 0 && !error && (
        <div className="bg-white rounded-xl shadow-sm p-10 text-center text-gray-400 text-sm">
          No tienes obras asignadas como supervisor.
        </div>
      )}
    </div>
  );
}
