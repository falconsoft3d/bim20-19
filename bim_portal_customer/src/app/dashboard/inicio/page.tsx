"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getStoredPartner, PartnerProfile } from "@/lib/auth";
import { LayoutDashboard, ArrowRight, Building2, User } from "lucide-react";

export default function InicioPage() {
  const router = useRouter();
  const [partner, setPartner] = useState<PartnerProfile | null>(null);

  useEffect(() => {
    const p = getStoredPartner();
    if (!p) { router.push("/login"); return; }
    setPartner(p);
  }, [router]);

  const hour = new Date().getHours();
  const greeting =
    hour < 12 ? "Buenos días" : hour < 19 ? "Buenas tardes" : "Buenas noches";

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-10rem)] text-center px-4">

      {/* Icono animado */}
      <div className="w-20 h-20 rounded-2xl bg-[#3b1a3a] flex items-center justify-center mb-6 shadow-lg">
        <LayoutDashboard className="w-10 h-10 text-white" />
      </div>

      {/* Saludo */}
      <p className="text-sm font-medium text-gray-500 mb-1">{greeting},</p>
      <h1 className="text-3xl font-bold text-gray-800 mb-2">
        {partner?.name ?? "..."}
      </h1>

      {/* Empresa / login */}
      <div className="flex items-center gap-4 mb-8 text-sm text-gray-500">
        {partner?.company && (
          <span className="flex items-center gap-1.5">
            <Building2 className="w-4 h-4" />
            {partner.company}
          </span>
        )}
        <span className="flex items-center gap-1.5">
          <User className="w-4 h-4" />
          @{partner?.login}
        </span>
      </div>

      {/* Descripción */}
      <p className="text-gray-500 max-w-md mb-10 leading-relaxed">
        Bienvenido al <strong className="text-gray-700">Portal BIM 2.0</strong>.
        Aquí puedes consultar el estado de tus obras, facturación,
        albaranes y más, en tiempo real desde Odoo.
      </p>

      {/* Roles */}
      {partner && (
        <div className="flex flex-wrap justify-center gap-2 mb-10">
          {partner.is_customer     && <RoleBadge label="Cliente"       color="blue" />}
          {partner.is_employee     && <RoleBadge label="Empleado"      color="purple" />}
          {partner.is_admin        && <RoleBadge label="Administrador" color="orange" />}
          {partner.is_tecno_cartas && <RoleBadge label="Tecno Cartas"  color="teal" />}
          {partner.is_proveedor    && <RoleBadge label="Proveedor"     color="yellow" />}
        </div>
      )}

      {/* CTA */}
      <button
        onClick={() => router.push("/dashboard")}
        className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-[#3b1a3a] hover:bg-[#5c2d5c] text-white font-semibold text-sm transition-colors shadow-md"
      >
        Ir al Dashboard
        <ArrowRight className="w-4 h-4" />
      </button>
    </div>
  );
}

// ── Badge de rol ──────────────────────────────────────────────────────────────

const roleColors: Record<string, string> = {
  blue:   "bg-blue-100 text-blue-700",
  purple: "bg-purple-100 text-purple-700",
  orange: "bg-orange-100 text-orange-700",
  teal:   "bg-teal-100 text-teal-700",
  yellow: "bg-yellow-100 text-yellow-700",
};

function RoleBadge({ label, color }: { label: string; color: string }) {
  return (
    <span className={`px-3 py-1 rounded-full text-xs font-semibold ${roleColors[color] ?? "bg-gray-100 text-gray-600"}`}>
      {label}
    </span>
  );
}
