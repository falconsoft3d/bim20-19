"use client";

import { useState, useEffect, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Calendar, User, Building2, ImageOff, MessageSquare, Send } from "lucide-react";
import {
  fetchAvance,
  fetchAvanceMessages,
  postAvanceComment,
  type Avance,
  type AvanceMessage,
} from "@/lib/cliente";

export default function AvanceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [avance, setAvance] = useState<Avance | null>(null);
  const [loading, setLoading] = useState(true);
  const [lightbox, setLightbox] = useState<string | null>(null);

  const [messages, setMessages] = useState<AvanceMessage[]>([]);
  const [msgLoading, setMsgLoading] = useState(true);
  const [commentText, setCommentText] = useState("");
  const [sending, setSending] = useState(false);
  const commentsBottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!id) return;
    fetchAvance(Number(id))
      .then(setAvance)
      .finally(() => setLoading(false));
    fetchAvanceMessages(Number(id))
      .then(setMessages)
      .finally(() => setMsgLoading(false));
  }, [id]);

  async function handleSendComment(e: React.FormEvent) {
    e.preventDefault();
    const body = commentText.trim();
    if (!body || sending) return;
    setSending(true);
    const msg = await postAvanceComment(Number(id), body);
    if (msg) {
      setMessages((prev) => [...prev, msg]);
      setCommentText("");
      setTimeout(() => commentsBottomRef.current?.scrollIntoView({ behavior: "smooth" }), 100);
    }
    setSending(false);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-40 text-gray-400 text-sm animate-pulse">
        Cargando avance…
      </div>
    );
  }

  if (!avance) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3">
        Avance no encontrado.
      </div>
    );
  }

  return (
    <div className="max-w-4xl space-y-5">

      {/* Cabecera */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => router.back()}
          className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors text-gray-500"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <span className="text-xs font-mono text-[#5c2d5c] bg-[#5c2d5c]/10 px-2 py-0.5 rounded">
            {avance.name}
          </span>
          <h1 className="text-xl font-bold text-gray-900 mt-1">{avance.project_name}</h1>
        </div>
      </div>

      {/* Meta */}
      <div className="bg-white rounded-xl shadow-sm p-5">
        <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-gray-600">
          <span className="flex items-center gap-2">
            <Building2 className="w-4 h-4 text-gray-400" />
            <span className="font-medium">{avance.project_name}</span>
          </span>
          <span className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-gray-400" />
            {new Date(avance.fecha).toLocaleDateString("es-ES", {
              day: "2-digit", month: "long", year: "numeric",
            })}
          </span>
          <span className="flex items-center gap-2">
            <User className="w-4 h-4 text-gray-400" />
            {avance.user}
          </span>
        </div>

        {avance.descripcion && (
          <p className="mt-4 text-sm text-gray-700 leading-relaxed whitespace-pre-line">
            {avance.descripcion}
          </p>
        )}
      </div>

      {/* Galería de imágenes */}
      {avance.lines && avance.lines.length > 0 ? (
        <div>
          <h2 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">
            Imágenes · {avance.lines.length}
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {avance.lines.map((ln) => (
              <div key={ln.id} className="group relative bg-gray-100 rounded-xl overflow-hidden aspect-4/3">
                {ln.image ? (
                  <>
                    <img
                      src={`data:image/jpeg;base64,${ln.image}`}
                      alt={ln.name || "Imagen"}
                      className="w-full h-full object-cover cursor-pointer transition-transform group-hover:scale-105"
                      onClick={() => setLightbox(ln.image)}
                    />
                    {ln.name && (
                      <div className="absolute bottom-0 inset-x-0 bg-linear-to-t from-black/60 to-transparent px-3 py-2">
                        <p className="text-white text-xs truncate">{ln.name}</p>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="flex items-center justify-center h-full text-gray-300">
                    <ImageOff className="w-8 h-8" />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="bg-white rounded-xl shadow-sm p-8 text-center text-gray-400 text-sm">
          Este avance no tiene imágenes.
        </div>
      )}

      {/* ── Comentarios / Chatter ── */}
      <div className="bg-white rounded-xl shadow-sm p-5 space-y-4">
        <h2 className="flex items-center gap-2 text-sm font-bold text-gray-700 uppercase tracking-wider">
          <MessageSquare className="w-4 h-4 text-[#5c2d5c]" />
          Comentarios
        </h2>

        {/* Lista */}
        <div className="space-y-3 max-h-80 overflow-y-auto pr-1">
          {msgLoading ? (
            <p className="text-xs text-gray-400 animate-pulse">Cargando comentarios…</p>
          ) : messages.length === 0 ? (
            <p className="text-xs text-gray-400">Sin comentarios aún. ¡Sé el primero!</p>
          ) : (
            messages.map((msg) => (
              <div key={msg.id} className="flex gap-3">
                {/* Avatar iniciales */}
                <div className="shrink-0 w-8 h-8 rounded-full bg-[#5c2d5c]/15 text-[#5c2d5c] flex items-center justify-center text-xs font-bold select-none">
                  {msg.author.slice(0, 2).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline gap-2">
                    <span className="text-sm font-semibold text-gray-800">{msg.author}</span>
                    <span className="text-xs text-gray-400">
                      {new Date(msg.date).toLocaleString("es-ES", {
                        day: "2-digit", month: "short", year: "numeric",
                        hour: "2-digit", minute: "2-digit",
                      })}
                    </span>
                  </div>
                  <div
                    className="mt-0.5 text-sm text-gray-700 leading-relaxed prose prose-sm max-w-none"
                    dangerouslySetInnerHTML={{ __html: msg.body }}
                  />
                </div>
              </div>
            ))
          )}
          <div ref={commentsBottomRef} />
        </div>

        {/* Formulario nuevo comentario */}
        <form onSubmit={handleSendComment} className="flex gap-2 pt-2 border-t border-gray-100">
          <textarea
            value={commentText}
            onChange={(e) => setCommentText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSendComment(e as unknown as React.FormEvent); }
            }}
            placeholder="Escribe un comentario… (Enter para enviar, Shift+Enter nueva línea)"
            rows={2}
            className="flex-1 resize-none text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#5c2d5c]/30 focus:border-[#5c2d5c]"
          />
          <button
            type="submit"
            disabled={!commentText.trim() || sending}
            className="shrink-0 flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#5c2d5c] text-white text-sm font-medium disabled:opacity-40 hover:bg-[#7a3d7a] transition-colors"
          >
            <Send className="w-4 h-4" />
            {sending ? "…" : "Enviar"}
          </button>
        </form>
      </div>

      {/* Lightbox */}
      {lightbox && (
        <div
          className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4"
          onClick={() => setLightbox(null)}
        >
          <img
            src={`data:image/jpeg;base64,${lightbox}`}
            alt="Imagen ampliada"
            className="max-w-full max-h-full rounded-xl shadow-2xl object-contain"
            onClick={(e) => e.stopPropagation()}
          />
          <button
            className="absolute top-4 right-4 text-white/70 hover:text-white text-2xl font-bold"
            onClick={() => setLightbox(null)}
          >
            ✕
          </button>
        </div>
      )}
    </div>
  );
}
