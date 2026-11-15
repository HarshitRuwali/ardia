import assert from "node:assert/strict";
import test from "node:test";
import { profileIndicatorLayout } from "./profileIndicatorLayout.ts";

const DEFAULT_SIDEBAR_ROOM = 98;

test("the default profile name fits beside the menu button at the default sidebar width", () => {
  const layout = profileIndicatorLayout({ room: DEFAULT_SIDEBAR_ROOM, textWidth: 64, named: true });
  assert.equal(layout.showName, true);
  assert.ok(layout.nameWidth - 2 * layout.pad >= 64, `the name gets ${layout.nameWidth - 2 * layout.pad}px of the 64px it needs`);
  assert.ok(layout.width <= DEFAULT_SIDEBAR_ROOM);
  assert.ok(layout.menuWidth >= 24);
});

test("a wide sidebar keeps the full menu button and padding", () => {
  const layout = profileIndicatorLayout({ room: 200, textWidth: 64, named: true });
  assert.deepEqual(layout, { shown: true, showName: true, nameWidth: 74, pad: 5, menuWidth: 32, width: 108 });
});

test("a name too long for the room is cut, with the menu at its narrowest", () => {
  const layout = profileIndicatorLayout({ room: DEFAULT_SIDEBAR_ROOM, textWidth: 140, named: true });
  assert.equal(layout.showName, true);
  assert.equal(layout.nameWidth, 72);
  assert.equal(layout.pad, 4);
  assert.equal(layout.menuWidth, 24);
  assert.equal(layout.width, DEFAULT_SIDEBAR_ROOM);
});

test("a room too small for a cut name shows the profile icon", () => {
  const layout = profileIndicatorLayout({ room: 70, textWidth: 140, named: true });
  assert.equal(layout.showName, false);
  assert.equal(layout.nameWidth, 32);
  assert.equal(layout.width, 32 + 2 + layout.menuWidth);
  assert.ok(layout.width <= 70);
});

test("one profile shows only the full-size menu button", () => {
  assert.deepEqual(profileIndicatorLayout({ room: DEFAULT_SIDEBAR_ROOM, textWidth: 64, named: false }), { shown: false, showName: false, nameWidth: 0, pad: 5, menuWidth: 32, width: 32 });
});
