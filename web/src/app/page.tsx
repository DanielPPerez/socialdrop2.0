import { getServerSession } from "next-auth"
import { authOptions } from "@/lib/auth-options"
import Link from "next/link"
import { PublicDropsCarousel } from "@/components/PublicDropsCarousel"
import { ArrowUpRight, Loader2 } from "lucide-react"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

async function fetchPublicDrops(): Promise<any[]> {
  try {
    const res = await fetch(`${API_URL}/api/v1/public/drops`, {
      cache: "no-store",
    })
    if (!res.ok) return []
    return res.json()
  } catch {
    return []
  }
}

export default async function HomePage() {
  const session = await getServerSession(authOptions)
  const drops = await fetchPublicDrops()

  return (
    <main className="min-h-screen bg-white">
      {/* Hero Section */}
      <section className="relative py-24 sm:py-32 lg:py-40 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-gray-50 to-white" aria-hidden="true" />
        <div className="absolute inset-0 bg-[url('data:image/svg+xml,%3Csvg width=%2260%22 height=%2260%22 viewBox=%220 0 60 60%22 xmlns=%22http://www.w3.org/2000/svg%22%3E%3Cg fill=%22none%22 fill-rule=%22evenodd%22%3E%3Cg fill=%22%239C92AC%22 fill-opacity=%220.03%22%3E%3Cpath d=%22M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z%22/%3E%3C/g%3E%3C/g%3E%3C/svg%3E')] opacity-50" aria-hidden="true" />
        
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto">
            <span className="inline-block px-4 py-1.5 rounded-full bg-blue-50 text-blue-700 text-sm font-medium mb-6 border border-blue-100">
              Público · Sin login requerido
            </span>
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-gray-900 tracking-tight mb-6 leading-[1.1]">
              Soltás un video y un archivo de metadata en una carpeta, se publica solo en YouTube, TikTok, Instagram, X, LinkedIn y Bluesky
            </h1>
            <p className="text-lg sm:text-xl text-gray-600 mb-10 max-w-2xl mx-auto leading-relaxed">
              Automatizá tu flujo de publicación sin escribir código. Dropeás el archivo, definís la metadata y SocialDrop se encarga del resto.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              {session ? (
                <Link
                  href="/drops"
                  className="w-full sm:w-auto px-8 py-3.5 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 transition-colors text-center shadow-sm hover:shadow-md"
                >
                  Ir a mis drops
                </Link>
              ) : (
                <Link
                  href="/login"
                  className="w-full sm:w-auto px-8 py-3.5 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 transition-colors text-center shadow-sm hover:shadow-md"
                >
                  Empezar gratis
                </Link>
              )}
              <Link
                href="/drops"
                className="w-full sm:w-auto px-8 py-3.5 bg-white text-gray-700 font-semibold rounded-xl border border-gray-200 hover:bg-gray-50 hover:border-gray-300 transition-all text-center"
              >
                Ver ejemplos públicos
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section className="py-20 sm:py-28 bg-white border-y border-gray-100">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-4">Cómo funciona</h2>
            <p className="text-lg text-gray-600">Tres pasos para automatizar tu publicación multiplataforma.</p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {[
              {
                number: "01",
                title: "Crea el drop",
                description: "Poné tu video (MP4/MOV/WebM) y un archivo .md o .json con título, descripción, hashtags, schedule y plataformas objetivo en la carpeta drops/.",
                icon: (
                  <svg className="h-8 w-8" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                ),
              },
              {
                number: "02",
                title: "Sidecar automático",
                description: "SocialDrop lee el frontmatter YAML (o JSON sidecar), valida la metadata y prepara la cola de publicación con reintentos y backoff exponencial.",
                icon: (
                  <svg className="h-8 w-8" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                ),
              },
              {
                number: "03",
                title: "Publica y mide",
                description: "Publica en paralelo via APIs oficiales (OAuth). Recolecta métricas (views, likes, comments) y escribe insights de vuelta al sidecar. Notificaciones por Discord/Email.",
                icon: (
                  <svg className="h-8 w-8" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                ),
              },
            ].map((step, index) => (
              <article key={index} className="group relative p-6 rounded-2xl bg-gray-50 hover:bg-gray-100 transition-colors duration-300 border border-transparent hover:border-gray-200">
                <div className="absolute top-4 right-4 text-gray-200 font-bold text-4xl font-mono">{step.number}</div>
                <div className="relative z-10">
                  <div className="inline-flex items-center justify-center w-14 h-14 rounded-xl bg-blue-100 text-blue-600 mb-4 group-hover:bg-blue-600 group-hover:text-white transition-colors duration-300">
                    {step.icon}
                  </div>
                  <h3 className="text-xl font-semibold text-gray-900 mb-3">{step.title}</h3>
                  <p className="text-gray-600 leading-relaxed">{step.description}</p>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* Public Content Carousel */}
      <section className="py-20 sm:py-28 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-12">
            <div>
              <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-2">Contenido publicado recientemente</h2>
              <p className="text-gray-600">Drops públicos compartidos por la comunidad.</p>
            </div>
            {drops.length > 0 && (
              <Link
                href="/drops"
                className="inline-flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:text-blue-700 transition-colors mt-auto"
              >
                Ver todos
                <ArrowUpRight className="h-4 w-4" />
              </Link>
            )}
          </div>
          <PublicDropsCarousel drops={drops} />
        </div>
      </section>

      {/* Footer CTA */}
      <section className="py-16 bg-gray-900 text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl sm:text-4xl font-bold mb-4">¿Listo para automatizar tus publicaciones?</h2>
          <p className="text-gray-300 mb-8 max-w-2xl mx-auto">
            Conectá tus cuentas, configurá tus plantillas y empezá a dropear contenido. Gratis para uso personal.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            {session ? (
              <Link
                href="/drops"
                className="w-full sm:w-auto px-8 py-3.5 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 transition-colors text-center"
              >
                Ir al dashboard
              </Link>
            ) : (
              <Link
                href="/login"
                className="w-full sm:w-auto px-8 py-3.5 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 transition-colors text-center"
              >
                Empezar gratis
              </Link>
            )}
            <Link
              href="https://github.com/DanielPPerez/socialdrop2.0"
              target="_blank"
              rel="noopener noreferrer"
              className="w-full sm:w-auto px-8 py-3.5 bg-gray-800 text-white font-semibold rounded-xl hover:bg-gray-700 transition-colors text-center border border-gray-700"
            >
              Ver en GitHub
            </Link>
          </div>
        </div>
      </section>
    </main>
  )
}