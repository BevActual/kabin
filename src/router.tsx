import {
  Outlet,
  createRootRoute,
  createRoute,
  createRouter,
} from "@tanstack/react-router";
import { AppShell } from "./components/AppShell";
import { HomeView } from "./routes/HomeView";
import { LibraryView } from "./routes/LibraryView";
import { ModeSectionView } from "./routes/ModeSectionView";
import { OpenLastMode } from "./routes/OpenLastMode";
import { DownloadsView } from "./routes/DownloadsView";
import { SettingsView } from "./routes/SettingsView";
import { PlayerView } from "./routes/PlayerView";
import { ReaderView } from "./routes/ReaderView";
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
  component: OpenLastMode,
});

const browseRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/browse/$mode",
  component: HomeView,
});

const browseSectionRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/browse/$mode/$section",
  component: ModeSectionView,
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

const downloadsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/downloads",
  component: DownloadsView,
});

const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings",
  component: SettingsView,
});

const readRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/read/$titleId",
  component: ReaderView,
});

const playerRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/player/$titleId",
  component: PlayerView,
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  browseRoute,
  browseSectionRoute,
  libraryRoute,
  titleRoute,
  readRoute,
  playerRoute,
  downloadsRoute,
  settingsRoute,
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
