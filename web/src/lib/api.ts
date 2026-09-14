import { getServerSession } from "next-auth"
import { authOptions } from "@/app/api/auth/[...nextauth]/route"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export interface Drop {
  id: string
  title: string
  video_filename: string
  schedule: string | null
  timezone: string
  platforms: Record<string, any>
  hashtags: string[]
  body: string
  public: boolean
  status: "draft" | "scheduled" | "publishing" | "published" | "failed"
  published: Array<{ platform: string; url: string; post_id: string }>
  insights: Array<{ platform: string; views: number | null; likes: number | null }>
}

export interface PublicDrop {
  id: string
  title: string
  thumbnail_url: string | null
  platforms: Array<{ name: string; url: string }>
  published_at: string | null
}

export interface PlatformStatus {
  platform: string
  configured: boolean
  authenticated: boolean
  detail: string | null
}

export interface User {
  id: string
  email: string
  name: string | null
  avatar_url: string | null
  created_at: string
}

export interface PlatformConnection {
  user_id: string
  platform: string
  account_label: string | null
  connected_at: string
}

async function getApiToken(): Promise<string | null> {
  const session = await getServerSession(authOptions)
  return (session as any)?.apiToken || null
}

async function fetchWithAuth(path: string, options: RequestInit = {}) {
  const token = await getApiToken()
  const isLocalMode = process.env.SOCIALDROP_MODE === "local"

  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...options.headers,
  }

  if (token && !isLocalMode) {
    ;(headers as Record<string, string>)["Authorization"] = `Bearer ${token}`
  } else if (isLocalMode) {
    // In local mode, use the fixed API key for server-to-server calls
    const localKey = process.env.SOCIALDROP_API_KEY
    if (localKey) {
      ;(headers as Record<string, string>)["X-API-Key"] = localKey
    }
  }

  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
    cache: "no-store",
  })

  if (!res.ok) {
    const error = await res.json().catch(() => ({ error: "Unknown error" }))
    throw new Error(error.error || `HTTP ${res.status}`)
  }

  return res.json()
}

export const api = {
  // Public drops (no auth)
  async getPublicDrops(): Promise<PublicDrop[]> {
    return fetchWithAuth("/api/v1/public/drops")
  },

  // Protected drops (requires auth)
  async getDrops(): Promise<Drop[]> {
    return fetchWithAuth("/api/v1/drops")
  },

  async getDrop(id: string): Promise<Drop> {
    return fetchWithAuth(`/api/v1/drops/${id}`)
  },

  async createDrop(video: File, data: Partial<Drop>): Promise<Drop> {
    const formData = new FormData()
    formData.append("video", video)
    formData.append("drop_create", JSON.stringify(data))

    const token = await getApiToken()
    const isLocalMode = process.env.SOCIALDROP_MODE === "local"

    const headers: HeadersInit = {}
    if (token && !isLocalMode) {
      headers["Authorization"] = `Bearer ${token}`
    } else if (isLocalMode) {
      const localKey = process.env.SOCIALDROP_API_KEY
      if (localKey) headers["X-API-Key"] = localKey
    }

    const res = await fetch(`${API_URL}/api/v1/drops`, {
      method: "POST",
      headers,
      body: formData,
    })

    if (!res.ok) {
      const error = await res.json().catch(() => ({ error: "Unknown error" }))
      throw new Error(error.error || `HTTP ${res.status}`)
    }

    return res.json()
  },

  async publishDrop(id: string): Promise<Drop> {
    return fetchWithAuth(`/api/v1/drops/${id}/publish`, { method: "POST" })
  },

  async refreshStats(id: string): Promise<Drop> {
    return fetchWithAuth(`/api/v1/drops/${id}/stats/refresh`, { method: "POST" })
  },

  async deleteDrop(id: string): Promise<void> {
    await fetchWithAuth(`/api/v1/drops/${id}`, { method: "DELETE" })
  },

  async suggestDrop(video: File): Promise<any> {
    const formData = new FormData()
    formData.append("video", video)

    const token = await getApiToken()
    const isLocalMode = process.env.SOCIALDROP_MODE === "local"

    const headers: HeadersInit = {}
    if (token && !isLocalMode) {
      headers["Authorization"] = `Bearer ${token}`
    } else if (isLocalMode) {
      const localKey = process.env.SOCIALDROP_API_KEY
      if (localKey) headers["X-API-Key"] = localKey
    }

    const res = await fetch(`${API_URL}/api/v1/drops/suggest`, {
      method: "POST",
      headers,
      body: formData,
    })

    if (!res.ok) {
      const error = await res.json().catch(() => ({ error: "Unknown error" }))
      throw new Error(error.error || `HTTP ${res.status}`)
    }

    return res.json()
  },

  // Platforms
  async getPlatforms(): Promise<PlatformStatus[]> {
    return fetchWithAuth("/api/v1/platforms")
  },

  async startAuth(platform: string): Promise<{ authorize_url: string; state: string }> {
    return fetchWithAuth(`/api/v1/platforms/${platform}/auth/start`, { method: "POST" })
  },

  // Auth
  async getMe(): Promise<User> {
    return fetchWithAuth("/api/v1/me")
  },

  async getConnections(): Promise<PlatformConnection[]> {
    return fetchWithAuth("/api/v1/me/connections")
  },
}