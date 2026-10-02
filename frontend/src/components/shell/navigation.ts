import { Activity, ChartColumn, FolderOpen, LayoutList } from "lucide-react";
import type { ComponentType } from "react";

/**
 * The whole of the product's global navigation, in one list.
 *
 * `docs/ux-plan.md` §3.1 found three navigation systems that disagreed about
 * what the product contains: a header row with three links, a sidebar with four,
 * and a `<details>` menu on the Backlog route with five. Four destinations,
 * three lists, no two the same. §4 answers it — "One navigation, everywhere" —
 * and this array is what that means in practice: one declaration, read by the
 * sidebar and by nothing else, present on every route including Backlog.
 *
 * Four is the number. §4: "No new top-level destination. Anything new earns its
 * place inside one of them."
 */
export type NavDestination = {
  to: string;
  label: string;
  icon: ComponentType<{ size?: number | string; "aria-hidden"?: boolean | "true" | "false" }>;
  /** Match this path exactly, rather than as a prefix. Only "/" needs it. */
  end?: boolean;
};

export const DESTINATIONS: NavDestination[] = [
  { to: "/", label: "Requirements", icon: LayoutList, end: true },
  { to: "/documents", label: "Documents", icon: FolderOpen },
  { to: "/activity", label: "Activity", icon: Activity },
  { to: "/reports", label: "Reports", icon: ChartColumn },
];
