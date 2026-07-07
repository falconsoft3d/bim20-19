"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Camera, Calendar, User, Building2, ChevronRight, ImageOff } from "lucide-react";
import { fetchAvances, type Avance } from "@/lib/cliente";

export default function AvancesPage() {
  const [avances, setAvances] = useState<Avance[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchAvances()
      .then(setAvances)
      .catch(() => setError("No se pudieron cargar los avances."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-40 text-gray-400 text-sm animate-pulse">
        Cargando avances…
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3">
        {error}
      </div>
    );
  }

  return (
    <div className="max-w-4xl space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-900">Avances de Obra</h1>
        <span className="text-xs text-gray-400">{avances.length} registro{avances.length !== 1 ? "s" : ""}</span>
      </div>

      {avances.length === 0 && (
        <div className="bg-white rounded-xl shadow-sm p-10 text-center text-gray-400 text-sm">
          No hay avances de obra disponibles.
        </div>
      )}

      <div className="space-y-3">
        {avances.map((av) => (
          <Link
            key={av.id}
            href={`/dashboard/cliente/avances/${av.id}`}
            className="block bg-white rounded-xl shadow-sm p-5 hover:shadow-md hover:ring-1 hover:ring-[#5c2d5c]/20 transition-all group"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                {/* Título */}
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs font-mono text-[#5c2d5c] bg-[#5c2d5c]/10 px-2 py-0.5 rounded">
                    {av.name}
                  </span>
                </div>

                {/* Meta */}
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
                  <span className="flex items-center gap-1">
                    <Building2 className="w-3.5 h-3.5" />
                    {av.project_name}
                  </span>
                  <span className="flex items-center gap-1">
                    <Calendar className="w-3.5 h-3.5" />
                    {new Date(av.fecha).toLocaleDateString("es-ES", { day: "2-digit", month: "short", year: "numeric" })}
                  </span>
                  <span className="flex items-center gap-1">
                    <User className="w-3.5 h-3.5" />
                    {av.user}
                  </span>
                </div>

                {/* Descripción */}
                {av.descripcion && (
                  <p className="mt-2 text-sm text-gray-600 line-clamp-2">{av.descripcion}</p>
                )}
              </div>

              {/* Imágenes badge + flecha */}
              <div className="flex items-center gap-3 shrink-0">
                {av.image_count > 0 ? (
                  <span className="flex items-center gap-1 text-xs text-gray-400 bg-gray-50 border border-gray-200 px-2 py-1 rounded-lg">
                    <Camera className="w-3.5 h-3.5" />
                    {av.image_count}
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-xs text-gray-300">
                    <ImageOff className="w-3.5 h-3.5" />
                  </span>
                )}
                <ChevronRight className="w-4 h-4 text-gray-300 group-hover:text-[#5c2d5c] transition-colors" />
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
