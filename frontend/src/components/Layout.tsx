/**
 * Root layout: fixed left sidebar + scrollable main content area.
 * The sidebar is visible on md+ viewports. On small screens it collapses.
 */
import type { ReactNode } from "react";
import Sidebar from "./Sidebar";

interface LayoutProps {
  children: ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      <main className="flex-1 overflow-y-auto px-6 py-5">{children}</main>
    </div>
  );
}
