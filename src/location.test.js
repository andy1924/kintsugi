import test from "node:test";
import assert from "node:assert/strict";
import { currentArea } from "./location.js";

test("current location is requested once, rounded before leaving the browser, without a continuous watch", async () => {
  let calls = 0;
  const result = await currentArea({
    getCurrentPosition(success, failure, options) {
      calls++;
      assert.deepEqual(options, {
        enableHighAccuracy: false,
        timeout: 10000,
        maximumAge: 60000,
      });
      success({
        coords: { latitude: 18.523456, longitude: 73.856789, accuracy: 10 },
      });
    },
  });
  assert.equal(calls, 1);
  assert.deepEqual(result, { latitude: 18.52, longitude: 73.86 });
});

for (const code of [1, 2, 3])
  test(`location failure ${code} is surfaced, never replaced with a fabricated position`, async () => {
    await assert.rejects(
      currentArea({
        getCurrentPosition(success, failure) {
          failure({ code });
        },
      }),
      (error) => error.code === code,
    );
  });
