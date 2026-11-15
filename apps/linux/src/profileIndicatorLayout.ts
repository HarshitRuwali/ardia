const PAD = 5;
const MIN_PAD = 4;
const MIN_CUT_NAME = 52;
const ICON_WIDTH = 32;
const MENU_WIDTH = 32;
const MENU_MIN_WIDTH = 24;
const GAP = 2;

export type ProfileIndicatorLayout = { shown: boolean; showName: boolean; nameWidth: number; pad: number; menuWidth: number; width: number };

export function profileIndicatorLayout({ room, textWidth, named }: { room: number; textWidth: number | undefined; named: boolean }): ProfileIndicatorLayout {
  const nameRoom = room - MENU_MIN_WIDTH - GAP;
  const shown = named && nameRoom >= ICON_WIDTH;
  const textRoom = nameRoom - 2 * MIN_PAD;
  const showName = shown && !!textWidth && (textWidth <= textRoom || textRoom >= MIN_CUT_NAME);
  const nameWidth = !shown ? 0 : showName ? Math.min(nameRoom, textWidth! + 2 * PAD) : ICON_WIDTH;
  const pad = showName ? Math.max(MIN_PAD, Math.min(PAD, Math.floor((nameWidth - textWidth!) / 2))) : PAD;
  const used = nameWidth + (shown ? GAP : 0);
  const menuWidth = Math.max(MENU_MIN_WIDTH, Math.min(MENU_WIDTH, room - used));
  return { shown, showName, nameWidth, pad, menuWidth, width: Math.max(0, Math.min(room, used + menuWidth)) };
}
