"use client";
import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { getSession, AuthUser, UserRole } from "@/lib/auth";

interface Props {
  children: (user: AuthUser) => React.ReactNode;
  allowedRoles?: UserRole[];
}

export default function AuthGuard({ children, allowedRoles }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<AuthUser | null | "loading">("loading");

  useEffect(() => {
    const session = getSession();
    if (!session) {
      router.replace("/login");
      return;
    }
    if (allowedRoles && !allowedRoles.includes(session.role)) {
      // Redirect to home — they are logged in but don't have access to this route
      router.replace("/");
      return;
    }
    setUser(session);
  }, [pathname, router, allowedRoles]);

  if (user === "loading") return null;
  if (!user) return null;

  return <>{children(user)}</>;
}
