export type WindowChrome = {
  leadingWidth: number;
  trailingWidth: number;
  titleBarHeight: number;
};

export type WindowButtonStyle = "native" | "trafficLights";

export const WINDOW_CHROME: WindowChrome = { leadingWidth: 78, trailingWidth: 0, titleBarHeight: 0 };

export const WINDOW_BUTTON_STYLES: readonly WindowButtonStyle[] = [];

export const applyWindowButtonStyle = (_style: WindowButtonStyle): boolean => false;
