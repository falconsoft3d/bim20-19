"use client";

import { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Globe } from "lucide-react";
import { login } from "@/lib/auth";
import { setOdooBaseUrl, ODOO_URL_KEY } from "@/lib/odoo";

// ── inner component (needs useSearchParams → requires Suspense) ─────────────

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [odooUrl, setOdooUrl] = useState("");
  const [urlFromParam, setUrlFromParam] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Pre-fill URL desde ?odoo=... o localStorage
  useEffect(() => {
    const param = searchParams.get("odoo");
    if (param) {
      const clean = param.replace(/\/$/, "");
      setOdooUrl(clean);
      setUrlFromParam(true);
      setOdooBaseUrl(clean);
    } else {
      const stored = localStorage.getItem(ODOO_URL_KEY);
      if (stored) setOdooUrl(stored);
    }
  }, [searchParams]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    const url = odooUrl.trim().replace(/\/$/, "");
    if (!url) {
      setError("Introduce la URL de tu servidor Odoo.");
      return;
    }
    if (!email || !password) {
      setError("Introduce tu usuario y contraseña.");
      return;
    }

    setLoading(true);
    try {
      const result = await login(email, password, url);
      if (result.success) {
        router.push("/dashboard/inicio");
      } else {
        setError(result.error || "Credenciales incorrectas.");
      }
    } catch {
      setError("No se pudo conectar con el servidor. Verifica la URL y tu conexión.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-linear-to-br from-[#3b1a3a] to-[#1a0a1a]">
      <div className="w-full max-w-md px-4">

        {/* Logo / Brand */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-white/10 mb-4">
            <svg className="w-9 h-9 text-white" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
              <polyline strokeLinecap="round" strokeLinejoin="round"
                points="9 22 9 12 15 12 15 22" />
            </svg>
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Portal BIM 2.0</h1>
          <p className="text-white/60 text-sm mt-1">Accede a tu portal de obra</p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <h2 className="text-xl font-semibold text-gray-800 mb-6">Iniciar sesión</h2>

          {error && (
            <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-red-600 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">

            {/* URL de Odoo */}
            {urlFromParam ? (
              <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#5c2d5c]/5 border border-[#5c2d5c]/20 text-sm text-[#5c2d5c]">
                <Globe className="w-4 h-4 shrink-0" />
                <span className="truncate font-medium">{odooUrl}</span>
              </div>
            ) : (
              <div>
                <label htmlFor="odoo_url" className="block text-sm font-medium text-gray-700 mb-1.5">
                  URL del servidor Odoo
                </label>
                <div className="relative">
                  <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <input
                    id="odoo_url"
                    type="url"
                    value={odooUrl}
                    onChange={(e) => setOdooUrl(e.target.value)}
                    placeholder="https://mi-empresa.odoo.com"
                    className="w-full pl-9 pr-4 py-2.5 rounded-lg border border-gray-300 text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#5c2d5c] focus:border-transparent transition text-sm"
                    required
                  />
                </div>
                <p className="mt-1 text-xs text-gray-400">
                  Ej: http://localhost:8069 · https://obra.bim20.com
                </p>
              </div>
            )}

            {/* Email / Usuario */}
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1.5">
                Email / Usuario
              </label>
              <input
                id="email"
                type="text"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="usuario@empresa.com"
                className="w-full px-4 py-2.5 rounded-lg border border-gray-300 text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#5c2d5c] focus:border-transparent transition text-sm"
              />
            </div>

            {/* Contraseña */}
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1.5">
                Contraseña
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full px-4 py-2.5 rounded-lg border border-gray-300 text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#5c2d5c] focus:border-transparent transition text-sm"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 rounded-lg bg-[#3b1a3a] hover:bg-[#5c2d5c] text-white font-semibold text-sm transition-colors duration-200 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10"
                      stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor"
                      d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  Entrando...
                </span>
              ) : "Entrar"}
            </button>
          </form>
        </div>

        <p className="text-center text-white/40 text-xs mt-6">
          © {new Date().getFullYear()} Portal BIM 2.0
        </p>
      </div>
    </div>
  );
}

// ── export con Suspense (requerido por useSearchParams en Next.js 15) ────────

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
