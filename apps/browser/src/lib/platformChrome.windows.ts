import type { PopUpChrome, WindowButtonStyle, WindowChrome } from "./platformChrome";

export const WINDOW_CHROME: WindowChrome = { leadingWidth: 0, trailingWidth: 171, titleBarHeight: 32 };

export const WINDOW_BUTTON_STYLES: readonly WindowButtonStyle[] = [];

export const applyWindowButtonStyle = (_style: WindowButtonStyle): boolean => false;

export const POP_UP_CHROME: PopUpChrome = { indicator: "chevronDown", growsToItsTitle: true };
