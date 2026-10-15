import {
  Outlet,
  createRootRoute,
  createRoute,
  createRouter,
} from "@tanstack/react-router";
import { AppShell } from "./components/AppShell";
import { HomeView } from "./routes/HomeView";
import { LibraryView } from "./routes/LibraryView";
import { SettingsView } from "./routes/SettingsView";
import { PlayerView } from "./routes/PlayerView";
import { TitleDetailsView } from "./routes/TitleDetailsView";

const rootRoute = createRootRoute({
  component: () => (
    <AppShell>
      <Outlet />
    </AppShell>
  ),
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: HomeView,
});

const libraryRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/library/$kind",
  component: LibraryView,
});

const titleRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/title/$titleId",
  component: TitleDetailsView,
});

const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings",
  component: SettingsView,
});

const playerRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/player/$titleId",
  component: PlayerView,
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  libraryRoute,
  titleRoute,
  playerRoute,
  settingsRoute,
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
