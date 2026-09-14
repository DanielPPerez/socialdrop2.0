"use client"

import { useState, useEffect, useMemo } from "react"
import { useSearchParams, useRouter, usePathname } from "next/navigation"
import Link from "next/link"
import { Drop } from "@/lib/api"
import { cn } from "@/lib/utils"
import {
  ChevronDown,
  ChevronUp,
  ChevronRight,
  Calendar,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Clock,
  XCircle,
} from "lucide-react"

type StatusFilter = "all" | "draft" | "scheduled" | "publishing" | "published" | "failed"

const STATUS_LABELS: Record<StatusFilter, string> = {
  all: "Todos",
  draft: "Borradores",
  scheduled: "Programados",
  publishing: "Publicando",
  published: "Publicados",
  failed: "Fallados",
}

const STATUS_ICONS = {
  draft: <Clock className="h-4 w-4 text-gray-500" />,
  scheduled: <Calendar className="h-4 w-4 text-blue-500" />,
  publishing: <Loader2 className="h-4 w-4 text-amber-500 animate-spin" />,
  published: <CheckCircle2 className="h-4 w-4 text-green-500" />,
  failed: <XCircle className="h-4 w-4 text-red-500" />,
}

const STATUS_COLORS: Record<Exclude<StatusFilter, "all">, string> = {
  draft: "bg-gray-100 text-gray-700 border-gray-200",
  scheduled: "bg-blue-50 text-blue-700 border-blue-100",
  publishing: "bg-amber-50 text-amber-700 border-amber-100",
  published: "bg-green-50 text-green-700 border-green-100",
  failed: "bg-red-50 text-red-700 border-red-100",
}

function formatDate(dateString: string | null): string {
  if (!dateString) return "—"
  try {
    return new Date(dateString).toLocaleDateString("es-ES", {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    })
  } catch {
    return "—"
  }
}

function getSortKey(drop: Drop, statusFilter: StatusFilter): [number, number] {
  // Primary sort: status order within each tab
  const statusOrder: Record<string, number> = {
    draft: 0,
    scheduled: 1,
    publishing: 2,
    published: 3,
    failed: 4,
  }

  // Secondary sort: schedule asc for non-published, published_at desc for published
  if (drop.status === "published" && drop.published.length > 0) {
    const publishedAt = drop.published[0]?.post_id // We don't have published_at in Drop type, use schedule as fallback
    return [statusOrder[drop.status] || 99, drop.schedule ? new Date(drop.schedule).getTime() : 0]
  }

  return [statusOrder[drop.status] || 99, drop.schedule ? new Date(drop.schedule).getTime() : 0]
}

interface DropsClientProps {
  initialDrops: Drop[]
  initialStatus: string
}

export function DropsClient({ initialDrops, initialStatus }: DropsClientProps) {
  const searchParams = useSearchParams()
  const router = useRouter()
  const pathname = usePathname()

  const [statusFilter, setStatusFilter] = useState<StatusFilter>(
    (initialStatus as StatusFilter) || "all"
  )
  const [drops, setDrops] = useState<Drop[]>(initialDrops)

  // Sync with URL on mount and when URL changes
  useEffect(() => {
    const urlStatus = searchParams.get("status") as StatusFilter | null
    if (urlStatus && urlStatus !== statusFilter) {
      setStatusFilter(urlStatus)
    }
  }, [searchParams, statusFilter])

  // Update URL when filter changes
  const handleFilterChange = (newStatus: StatusFilter) => {
    setStatusFilter(newStatus)
    const params = new URLSearchParams(searchParams.toString())
    if (newStatus === "all") {
      params.delete("status")
    } else {
      params.set("status", newStatus)
    }
    router.push(`${pathname}?${params.toString()}`, { scroll: false })
  }

  // Filter drops
  const filteredDrops = useMemo(() => {
    return drops.filter((drop) => {
      if (statusFilter === "all") return true
      return drop.status === statusFilter
    })
  }, [drops, statusFilter])

  // Sort drops
  const sortedDrops = useMemo(() => {
    return [...filteredDrops].sort((a, b) => {
      const [aStatus, aTime] = getSortKey(a, statusFilter)
      const [bStatus, bTime] = getSortKey(b, statusFilter)

      if (aStatus !== bStatus) return aStatus - bStatus

      // For published, sort by published_at desc (newest first)
      // For others, sort by schedule asc (oldest first)
      if (statusFilter === "published" || (statusFilter === "all" && a.status === "published" && b.status === "published")) {
        // We don't have published_at in the type, so use schedule as proxy
        return bTime - aTime
      }
      return aTime - bTime
    })
  }, [filteredDrops, statusFilter])

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    drops.forEach((drop) => {
      counts[drop.status] = (counts[drop.status] || 0) + 1
    })
    return counts
  }, [drops])

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Drops</h1>
            <p className="text-gray-600 mt-1">Gestiona tus videos programados y publicados</p>
          </div>
          <Link
            href="/drops/new"
            className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 transition-colors shadow-sm"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Nuevo drop
          </Link>
        </div>

        {/* Status Tabs */}
        <div className="mb-6">
          <div className="flex flex-wrap gap-2" role="tablist" aria-label="Filtrar por estado">
            {(["all", "draft", "scheduled", "publishing", "published", "failed"] as StatusFilter[]).map((status) => (
              <button
                key={status}
                role="tab"
                aria-selected={statusFilter === status}
                onClick={() => handleFilterChange(status)}
                className={cn(
                  "inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200",
                  "border",
                  statusFilter === status
                    ? "bg-blue-600 text-white border-blue-600 shadow-sm"
                    : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50 hover:border-gray-300"
                )}
              >
                {status !== "all" && STATUS_ICONS[status as Exclude<StatusFilter, "all">]}
                <span>{STATUS_LABELS[status]}</span>
                <span className={cn(
                  "px-2 py-0.5 text-xs font-semibold rounded-full",
                  statusFilter === status
                    ? "bg-white/20 text-white"
                    : "bg-gray-100 text-gray-600"
                )}>
                  {status === "all" ? drops.length : statusCounts[status] || 0}
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Drops List */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          {sortedDrops.length === 0 ? (
            <div className="py-16 text-center">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gray-100 mb-4">
                {statusFilter !== "all" && STATUS_ICONS[statusFilter as Exclude<StatusFilter, "all">]}
                {statusFilter === "all" && <Clock className="h-8 w-8 text-gray-400" />}
              </div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">
                {statusFilter === "all" ? "No hay drops aún" : `No hay drops en estado "${STATUS_LABELS[statusFilter]}"`}
              </h3>
              <p className="text-gray-500 max-w-sm mx-auto">
                {statusFilter === "all"
                  ? "Crea tu primer drop para empezar a automatizar publicaciones."
                  : "Los drops aparecerán aquí cuando coincidan con este filtro."}
              </p>
              {statusFilter === "all" && (
                <Link
                  href="/drops/new"
                  className="mt-4 inline-flex items-center gap-2 px-6 py-3 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 transition-colors"
                >
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  Crear primer drop
                </Link>
              )}
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {sortedDrops.map((drop) => (
                <article
                  key={drop.id}
                  className="p-6 hover:bg-gray-50 transition-colors flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start gap-4">
                      <div className="w-16 h-16 flex-shrink-0 rounded-xl bg-gray-100 overflow-hidden relative">
                        {drop.video_filename ? (
                          <div className="w-full h-full bg-gradient-to-br from-gray-200 to-gray-300 flex items-center justify-center">
                            <svg className="h-8 w-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h14" />
                            </svg>
                          </div>
                        ) : (
                          <div className="w-full h-full flex items-center justify-center">
                            <svg className="h-8 w-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h14" />
                            </svg>
                          </div>
                        )}
                      </div>
                      <div className="min-w-0">
                        <Link
                          href={`/drops/${drop.id}`}
                          className="font-semibold text-gray-900 hover:text-blue-600 transition-colors truncate block mb-1"
                        >
                          {drop.title}
                        </Link>
                        <div className="flex flex-wrap items-center gap-3 text-sm text-gray-500">
                          <span className="font-mono text-gray-400">{drop.video_filename || "Sin video"}</span>
                          {drop.schedule && (
                            <span className="flex items-center gap-1">
                              <Calendar className="h-3.5 w-3.5" />
                              Programado: {formatDate(drop.schedule)}
                            </span>
                          )}
                          {drop.status === "published" && drop.published.length > 0 && (
                            <span className="flex items-center gap-1 text-green-600">
                              <CheckCircle2 className="h-3.5 w-3.5" />
                              Publicado en {drop.published.map(p => p.platform).join(", ")}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 sm:flex-shrink-0">
                    <span
                      className={cn(
                        "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium",
                        STATUS_COLORS[drop.status as Exclude<StatusFilter, "all">] || STATUS_COLORS.draft
                      )}
                    >
                      {STATUS_ICONS[drop.status as Exclude<StatusFilter, "all">] || STATUS_ICONS.draft}
                      {STATUS_LABELS[drop.status as StatusFilter]}
                    </span>
                    <Link
                      href={`/drops/${drop.id}`}
                      className="p-2 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
                      aria-label={`Ver detalles de ${drop.title}`}
                    >
                      <ChevronRight className="h-5 w-5" />
                    </Link>
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>
      </div>
    </main>
  )
}