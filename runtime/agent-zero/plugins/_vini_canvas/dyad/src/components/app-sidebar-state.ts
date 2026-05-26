export type AppSidebarHoverState =
  | "start-hover:app"
  | "clear-hover"
  | "no-hover";

export type AppSidebarPanel = "Apps";

export type AppSidebarItemTitle = AppSidebarPanel;

export function getRouteSidebarPanel(pathname: string): AppSidebarPanel | null {
  if (
    pathname === "/" ||
    pathname.startsWith("/apps") ||
    pathname.startsWith("/app-details") ||
    pathname === "/chat"
  ) {
    return "Apps";
  }

  return null;
}

export function getHoverSidebarPanel(
  hoverState: AppSidebarHoverState,
): AppSidebarPanel | null {
  if (hoverState === "start-hover:app") {
    return "Apps";
  }
  return null;
}

export function getSelectedSidebarPanel({
  hoverState,
  sidebarState,
  pathname,
}: {
  hoverState: AppSidebarHoverState;
  sidebarState: "expanded" | "collapsed";
  pathname: string;
}): AppSidebarPanel | null {
  const hoverPanel = getHoverSidebarPanel(hoverState);
  if (hoverPanel) {
    return hoverPanel;
  }

  if (sidebarState === "expanded") {
    return getRouteSidebarPanel(pathname);
  }

  return null;
}

export function isSidebarItemActive({
  title,
  pathname,
}: {
  title: AppSidebarItemTitle;
  pathname: string;
}) {
  if (title === "Apps") {
    return getRouteSidebarPanel(pathname) === "Apps";
  }
  return false;
}

export function shouldShowSelectedAppChatList({
  selectedPanel,
  selectedAppId,
  pathname,
}: {
  selectedPanel: AppSidebarPanel | null;
  selectedAppId: number | null;
  pathname: string;
}) {
  if (selectedPanel !== "Apps" || selectedAppId === null) {
    return false;
  }
  return pathname.startsWith("/app-details") || pathname === "/chat";
}
