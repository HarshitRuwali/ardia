import { cleanUrl } from "@ardia/core";
import type { ArdiaHost } from "../../host";
import { AUR_UPDATE_COMMAND, linuxUpdater, readPackageManager, scheduleUpdateChecks, updatesAvailable, type LinuxUpdater, type PackageManager, type UpdateLocks } from "./hostUpdates.ts";
import { isLinuxUtility } from "../../session.ts";
import { refreshDocument } from "../../shims/shellBase";
import { systemInfo } from "../../../../browser/src/platform/app";
import { copyAddress, copyText } from "../../../../browser/src/platform/clipboard";
import { confirm } from "../../../../browser/src/platform/dialogs";
import { readDocument, saveDocument } from "../../../../browser/src/platform/documents";
import { showToast } from "../../../../browser/src/state/app/toasts";
import { consentToken } from "../../../../browser/src/state/telemetry/consentPeriod";
import { openUrls } from "../../../../browser/src/state/browser/actions";
import { openUrlFromSettings } from "../../../../browser/src/state/settings/settingsWindows";
import { noteUpdateCommandCopied, noteUpdateNoticeDismissed, noteUpdatePageOpened } from "../../../../browser/src/state/telemetry/updateCounts.ts";

const updaters = new WeakMap<ArdiaHost, LinuxUpdater>();
const UPDATE_ICON = "arrow.down.circle";

const MANAGED_UPDATE: Record<Exclude<PackageManager, "pacman">, { toast: string; dialog: string }> = {
  rpm: {
    toast: "Install the new .rpm from its release page.",
    dialog: "This .rpm was installed from a downloaded file, so dnf and zypper have no repository to update it from: install the new .rpm from its release page.",
  },
  flatpak: {
    toast: "Install the new .flatpak from its release page.",
    dialog: "This Flatpak was installed from a .flatpak file, which flatpak update can't update: install the new .flatpak from its release page.",
  },
  package: {
    toast: "Update it with your package manager, or download it from its release page.",
    dialog: "Another package manager installed Ardia, so update it there, or download the new version from its release page.",
  },
};

const loadPackageManager = () => import("chrome://ardia/package-manager.js").then((marker) => readPackageManager(marker.default));

const browserLocks = (): UpdateLocks | undefined => (typeof navigator === "undefined" ? undefined : (navigator as { locks?: UpdateLocks }).locks);

export function linuxUpdaterFor(host: ArdiaHost): LinuxUpdater {
  const known = updaters.get(host);
  if (known) return known;
  const windowId = host.bootstrap.windowId;
  const browserWindow = !isLinuxUtility(windowId);
  const offerLink = (url: string) =>
    void confirm({
      title: "Ardia couldn't open the release page",
      message: `No browser window is open to show it in. Open a window and go to ${url}, or copy the link.`,
      confirmTitle: "Copy Link",
      cancelTitle: "OK",
      windowId,
    }).then((answer) => void (answer.confirmed && copyAddress(cleanUrl(url))), () => {});
  const open = (url: string) => (browserWindow ? (openUrls([url], windowId), true) : openUrlFromSettings(url) || (offerLink(url), false));
  let installedBy: Promise<PackageManager> | undefined;
  const toast: typeof showToast = (...args) => {
    if (browserWindow) showToast(...args);
  };
  const updater = linuxUpdater({
    host,
    appVersion: () => {
      try {
        return systemInfo().appVersion ?? null;
      } catch {
        return null;
      }
    },
    read: readDocument,
    write: saveDocument,
    refresh: refreshDocument,
    ask: (release, current, failed) =>
      confirm({
        title: `Ardia ${release.version} is available`,
        message: failed
          ? `You have Ardia ${current}. Ardia couldn't install the update itself: download the new package from its release page.`
          : `You have Ardia ${current}. Ardia on Linux doesn't update itself: download the new package from its release page.`,
        confirmTitle: "Open Release Page",
        cancelTitle: "Later",
        windowId,
      }).then((answer) => answer.confirmed, () => false),
    tell: async (title, message) => toast(windowId, title, message, { icon: UPDATE_ICON }),
    offer: (release, failed) =>
      toast(windowId, `Ardia ${release.version} is available`, failed ? "Ardia couldn't install it. Download it from its release page." : "Download it from its release page.", {
        icon: UPDATE_ICON,
        sticky: true,
        action: { title: "View", run: () => void (open(release.url) && noteUpdatePageOpened()) },
        secondary: { title: "Later", run: noteUpdateNoticeDismissed },
      }),
    offerInstall: (release, install) =>
      toast(windowId, `Ardia ${release.version} is available`, "Update now and restart when you're ready.", {
        icon: UPDATE_ICON,
        sticky: true,
        action: { title: "Update", run: install },
        secondary: { title: "Later", run: noteUpdateNoticeDismissed },
      }),
    ready: (version, restart) =>
      toast(windowId, `Ardia ${version} is ready`, "Restart to finish updating.", {
        icon: UPDATE_ICON,
        sticky: true,
        action: { title: "Restart", run: restart },
        secondary: { title: "Later", run: noteUpdateNoticeDismissed },
      }),
    managed: async (release, current, asked, manager) => {
      const consent = consentToken();
      if (manager === "pacman") {
        const copyCommand = (taken?: ReturnType<typeof consentToken>) => (copyText(AUR_UPDATE_COMMAND), noteUpdateCommandCopied(taken));
        if (!asked) {
          toast(windowId, `Ardia ${release.version} is available`, `Update it with ${AUR_UPDATE_COMMAND} or your AUR helper.`, {
            icon: UPDATE_ICON,
            sticky: true,
            action: { title: "Copy Command", run: () => copyCommand() },
            secondary: { title: "Later", run: noteUpdateNoticeDismissed },
          });
          return;
        }
        const answer = await confirm({
          title: `Ardia ${release.version} is available`,
          message: `You have Ardia ${current}. The AUR package installed Ardia, so update it with ${AUR_UPDATE_COMMAND} or your AUR helper.`,
          confirmTitle: "Copy Command",
          cancelTitle: "Later",
          windowId,
        }).catch(() => null);
        if (answer?.confirmed) copyCommand(consent);
        return;
      }
      const words = MANAGED_UPDATE[manager];
      if (!asked) {
        toast(windowId, `Ardia ${release.version} is available`, words.toast, {
          icon: UPDATE_ICON,
          sticky: true,
          action: { title: "View", run: () => void (open(release.url) && noteUpdatePageOpened()) },
          secondary: { title: "Later", run: noteUpdateNoticeDismissed },
        });
        return;
      }
      const answer = await confirm({
        title: `Ardia ${release.version} is available`,
        message: `You have Ardia ${current}. ${words.dialog}`,
        confirmTitle: "Open Release Page",
        cancelTitle: "Later",
        windowId,
      }).catch(() => null);
      if (answer?.confirmed && open(release.url)) noteUpdatePageOpened(consent);
    },
    packageManager: () => (installedBy ??= loadPackageManager().catch((): PackageManager => "package")),
    open,
    showsToasts: browserWindow,
    locks: browserLocks(),
  });
  updaters.set(host, updater);
  return updater;
}

const MENU_STATUS_WAIT_MS = 150;

export const updateMenuItem = async (host: ArdiaHost): Promise<"check" | "restart" | null> => {
  if (!updatesAvailable(host) || host.bootstrap.privateWindow) return null;
  const late = new Promise<"check">((resolve) => setTimeout(() => resolve("check"), MENU_STATUS_WAIT_MS));
  return Promise.race([linuxUpdaterFor(host).menuItem(), late]);
};

export function startLinuxUpdates(host: ArdiaHost, locks?: LockManager) {
  if (!updatesAvailable(host) || host.bootstrap.privateWindow) return;
  scheduleUpdateChecks(linuxUpdaterFor(host), { locks: locks as unknown as Parameters<typeof scheduleUpdateChecks>[1]["locks"] });
}
