import NextAuth, { NextAuthOptions } from "next-auth"
import GoogleProvider from "next-auth/providers/google"
import { JWT } from "next-auth/jwt"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

async function syncWithBackend(token: JWT) {
  if (!token.email) return

  try {
    const res = await fetch(`${API_URL}/api/v1/auth/sync`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: token.email,
        name: token.name,
        avatar_url: token.picture,
        google_sub: token.sub,
      }),
    })

    if (res.ok) {
      const data = await res.json()
      token.apiToken = data.api_token
      token.userId = data.user_id
    }
  } catch (e) {
    console.error("Auth sync failed:", e)
  }
}

const authOptions: NextAuthOptions = {
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
      authorization: {
        params: {
          scope: "openid email profile",
          access_type: "offline",
          prompt: "consent",
        },
      },
    }),
  ],
  callbacks: {
    async signIn({ user, account, profile }) {
      // Allow sign in
      return true
    },
    async jwt({ token, account, user, profile }) {
      if (account && user) {
        token.sub = (profile as any)?.sub || (account as any)?.providerAccountId
        token.email = user.email
        token.name = user.name
        token.picture = user.image
        await syncWithBackend(token)
      }
      return token
    },
    async session({ session, token }) {
      ;(session as any).apiToken = token.apiToken
      ;(session as any).userId = token.userId
      return session
    },
  },
  pages: {
    signIn: "/login",
    error: "/login",
  },
  session: {
    strategy: "jwt",
  },
  secret: process.env.NEXTAUTH_SECRET,
}

const handler = NextAuth(authOptions)
export { handler as GET, handler as POST }
export { authOptions }