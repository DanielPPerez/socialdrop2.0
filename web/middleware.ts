import { withAuth } from "next-auth/middleware"
import { NextResponse } from "next/server"

export default withAuth(
  function middleware(req) {
    const isLocalMode = process.env.SOCIALDROP_MODE === "local"
    
    // In local mode, allow all requests
    if (isLocalMode) {
      return NextResponse.next()
    }
    
    // Check if user is authenticated
    const token = req.nextauth.token
    if (!token) {
      const loginUrl = new URL("/login", req.url)
      loginUrl.searchParams.set("callbackUrl", req.nextUrl.pathname)
      return NextResponse.redirect(loginUrl)
    }
    
    return NextResponse.next()
  },
  {
    callbacks: {
      authorized: ({ token, req }) => {
        const isLocalMode = process.env.SOCIALDROP_MODE === "local"
        if (isLocalMode) return true
        return !!token
      },
    },
  }
)

export const config = {
  matcher: [
    "/drops/:path*",
    "/platforms/:path*",
    "/calendar/:path*",
    "/settings/:path*",
  ],
}