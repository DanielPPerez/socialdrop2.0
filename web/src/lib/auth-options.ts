import { NextAuthOptions } from "next-auth"
import GoogleProvider from "next-auth/providers/google"

export const authOptions: NextAuthOptions = {
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
      return true
    },
    async jwt({ token, account, user, profile }) {
      if (account && user) {
        token.sub = (profile as any)?.sub || (account as any)?.providerAccountId
        token.email = user.email
        token.name = user.name
        token.picture = user.image
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