import type { PopUpChrome, WindowButtonStyle, WindowChrome } from "./platformChrome";
import { WINDOW_CHROME as WINDOWS_CHROME } from "./platformChrome.windows";

export const NATIVE_BUTTONS_CHROME: WindowChrome = { ...WINDOWS_CHROME };

export const TRAFFIC_LIGHTS_CHROME: WindowChrome = { leadingWidth: 78, trailingWidth: 0, titleBarHeight: 0 };

export const WINDOW_CHROME: WindowChrome = { ...NATIVE_BUTTONS_CHROME };

export const WINDOW_BUTTON_STYLES: readonly WindowButtonStyle[] = ["native", "trafficLights"];

export function applyWindowButtonStyle(style: WindowButtonStyle): boolean {
  const next = style === "trafficLights" ? TRAFFIC_LIGHTS_CHROME : NATIVE_BUTTONS_CHROME;
  if (WINDOW_CHROME.leadingWidth === next.leadingWidth && WINDOW_CHROME.trailingWidth === next.trailingWidth && WINDOW_CHROME.titleBarHeight === next.titleBarHeight) return false;
  Object.assign(WINDOW_CHROME, next);
  return true;
}

export const POP_UP_CHROME: PopUpChrome = { indicator: "accentUpDown", growsToItsTitle: false };
