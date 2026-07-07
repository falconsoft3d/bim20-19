"use client";

import { useState } from "react";
import { ChevronDown, Download } from "lucide-react";
import KpiCard from "@/components/KpiCard";
import CostCenterCard from "@/components/CostCenterCard";
import DonutChart from "@/components/DonutChart";
import BarChartComp from "@/components/BarChartComp";

// ── Mock data (se reemplazará con llamadas a Odoo) ──────────────────────────

const MONTHS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
const YEARS = ["2024", "2025", "2026"];

const OBRAS = [
  "[S25/090] AUXILIAR DE OBRA ESPAI DONES (VALENCIA) CTR25.0716 (Ejecución)",
  "[S25/091] REFORMA OFICINAS CENTRAL (MADRID) CTR25.0812 (Ejecución)",
];

const EMPRESAS = [
  "SOLUCIONES TECNICAS ELECTRICAS 2013, S.L.",
  "cliente INSTALACIONES S.A.",
];

const donutData = [
  { name: "Materiales", value: 4139.47, color: "#4fc3f7" },
  { name: "Asistencias", value: 99.31, color: "#66bb6a" },
  { name: "Asist. partner", value: 0, color: "#ef5350" },
  { name: "Viajes", value: 4.42, color: "#ffa726" },
  { name: "Otros gastos", value: 0, color: "#bdbdbd" },
];

const barData = [
  {
    obra: "S25/090",
    Materiales: 4139.47,
    Asistencias: 99.31,
    "Asist. partner": 0,
    Viajes: 4.42,
    "Otros gastos": 0,
  },
  {
    obra: "S25/091",
    Materiales: 0,
    Asistencias: 0,
    "Asist. partner": 0,
    Viajes: 0,
    "Otros gastos": 0,
  },
];

// ──────────────────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const [empresa, setEmpresa] = useState(EMPRESAS[0]);
  const [obra, setObra] = useState(OBRAS[0]);
  const [mes, setMes] = useState(MONTHS[6]); // Jul
  const [año, setAño] = useState(YEARS[2]); // 2026
  const [vista, setVista] = useState<"origen" | "mes">("origen");

  return (
    <div className="space-y-5 max-w-[1400px]">

      {/* ── Filtros superiores ──────────────────────────────────── */}
      <div className="bg-white rounded-xl shadow-sm p-4 flex flex-wrap items-center gap-3">
        {/* ObraControl badge */}
        <div className="flex items-center gap-2 shrink-0">
          <div className="w-4 h-4 rounded bg-gray-800" />
          <span className="text-sm font-bold text-[#4fc3f7]">ObraControl</span>
        </div>

        {/* Empresa selector */}
        <div className="relative flex-1 min-w-[220px]">
          <select
            value={empresa}
            onChange={(e) => setEmpresa(e.target.value)}
            className="w-full appearance-none pl-3 pr-8 py-2 rounded-lg border border-gray-300 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-[#5c2d5c]"
          >
            {EMPRESAS.map((e) => (
              <option key={e}>{e}</option>
            ))}
          </select>
          <ChevronDown className="absolute right-2 top-2.5 w-4 h-4 text-gray-400 pointer-events-none" />
        </div>

        {/* Mes */}
        <div className="relative">
          <select
            value={mes}
            onChange={(e) => setMes(e.target.value)}
            className="appearance-none pl-3 pr-8 py-2 rounded-lg border border-gray-300 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-[#5c2d5c]"
          >
            {MONTHS.map((m) => (
              <option key={m}>{m}</option>
            ))}
          </select>
          <ChevronDown className="absolute right-2 top-2.5 w-4 h-4 text-gray-400 pointer-events-none" />
        </div>

        {/* Año */}
        <div className="relative">
          <select
            value={año}
            onChange={(e) => setAño(e.target.value)}
            className="appearance-none pl-3 pr-8 py-2 rounded-lg border border-gray-300 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-[#5c2d5c]"
          >
            {YEARS.map((y) => (
              <option key={y}>{y}</option>
            ))}
          </select>
          <ChevronDown className="absolute right-2 top-2.5 w-4 h-4 text-gray-400 pointer-events-none" />
        </div>
      </div>

      {/* ── Selector de obra + vista ─────────────────────────────── */}
      <div className="bg-white rounded-xl shadow-sm p-4 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[280px]">
          <select
            value={obra}
            onChange={(e) => setObra(e.target.value)}
            className="w-full appearance-none pl-3 pr-8 py-2 rounded-lg border border-gray-300 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-[#5c2d5c]"
          >
            {OBRAS.map((o) => (
              <option key={o}>{o}</option>
            ))}
          </select>
          <ChevronDown className="absolute right-2 top-2.5 w-4 h-4 text-gray-400 pointer-events-none" />
        </div>

        {/* Toggle vista */}
        <div className="flex rounded-lg border border-gray-200 overflow-hidden">
          <button
            onClick={() => setVista("origen")}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              vista === "origen"
                ? "bg-[#3b1a3a] text-white"
                : "bg-white text-gray-600 hover:bg-gray-50"
            }`}
          >
            A origen
          </button>
          <button
            onClick={() => setVista("mes")}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              vista === "mes"
                ? "bg-[#3b1a3a] text-white"
                : "bg-white text-gray-600 hover:bg-gray-50"
            }`}
          >
            Mes
          </button>
        </div>
      </div>

      {/* ── KPI cards ───────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-5 gap-4">
        <KpiCard
          title="Facturado"
          value="€6,2k"
          subtitle="A origen"
          hasArrow
          colorVariant="default"
        />
        <KpiCard
          title="Coste Total CC"
          value="€4,2k"
          subtitle="Suma 5 centros de coste"
          colorVariant="default"
        />
        <KpiCard
          title="AAPP"
          value="€0,00"
          subtitle="Acumulado mes"
          hasArrow
          colorVariant="default"
        />
        <KpiCard
          title="Resultado"
          value="€1,9k"
          subtitle="Fact - Coste"
          colorVariant="green"
        />
        <KpiCard
          title="MN %"
          value="21.4%"
          subtitle="Margen sobre facturado"
          colorVariant="teal"
        />
      </div>

      {/* ── Centros de coste ────────────────────────────────────── */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-bold text-gray-600 uppercase tracking-wider">
            Centros de coste · A origen · Clic para ver registros
          </h2>
          <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-300 text-xs text-gray-600 hover:bg-gray-50 transition-colors">
            <Download className="w-3.5 h-3.5" />
            Exportar XLSX
          </button>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-5 gap-4">
          <CostCenterCard
            title="Materiales"
            value="€4,1k"
            pctCte="47.8"
            pctFact="34.2"
            accentColor="#4fc3f7"
          />
          <CostCenterCard
            title="Asistencias"
            value="€99,31"
            pctCte="26.2"
            pctFact="18.7"
            accentColor="#66bb6a"
          />
          <CostCenterCard
            title="Asist. Partner"
            value="€0,00"
            pctCte="16.9"
            pctFact="12.1"
            accentColor="#ef5350"
          />
          <CostCenterCard
            title="Viajes"
            value="€4,42"
            pctCte="2.4"
            pctFact="1.7"
            accentColor="#ffa726"
          />
          <CostCenterCard
            title="Otros Gastos"
            value="€0,00"
            pctCte="6.7"
            pctFact="4.8"
            accentColor="#bdbdbd"
          />
        </div>
      </div>

      {/* ── Gráficas ────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <DonutChart data={donutData} />
        <BarChartComp data={barData} />
      </div>
    </div>
  );
}
