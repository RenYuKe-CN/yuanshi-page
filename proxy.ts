import { NextRequest, NextResponse } from "next/server";

const protectedRoutes = ["/", "/ip-query", "/history", "/membership", "/profile", "/contact", "/admin", "/users", "/logs", "/settings"];

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const session = request.cookies.get("ys_jsz_session")?.value;

  if (protectedRoutes.some((route) => pathname === route || pathname.startsWith(`${route}/`))) {
    if (!session && pathname !== "/login") {
      return NextResponse.redirect(new URL("/login", request.url));
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"]
};
