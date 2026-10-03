// node --test tests/   (run from survival-alpha/ after `npm ci`)
// Recorded mainnet Pump accounts (tests/fixtures/pump/accounts.json) decoded with
// the official @pump-fun/pump-sdk. Expected numbers were produced by the previous
// unofficial @nirholas/pump-sdk 2.0.0 on the SAME account bytes, so these tests
// pin that the SDK swap did not change quote semantics.
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { createRequire } from "node:module";
import BN from "bn.js";
import * as math from "../pump_quote_math.mjs";

const require = createRequire(import.meta.url);
const sdk = require("@pump-fun/pump-sdk");
const fx = JSON.parse(fs.readFileSync(new URL("./fixtures/pump/accounts.json", import.meta.url)));
const acct = (b64) => ({ data: Buffer.from(b64, "base64"), owner: sdk.PUMP_PROGRAM_ID, lamports: 0, executable: false });
const global = sdk.PUMP_SDK.decodeGlobal(acct(fx.global));
const feeConfig = sdk.PUMP_SDK.decodeFeeConfig(acct(fx.feeConfig));

const EXPECTED_0_1_SOL = {
  "5VnbrKp28Qs9CAH6PyZdxBNvLxZcbeX3YBsozgWnpump": { tokensOut: "632340897796", buyImpactBps: 28, sellImpactBps: 27, progressBps: 7801, solNeeded: "44699865693", sellback: "97532559" },
  "HhUzCsowKRnCrA2eq2oHPn9LTDqS7aySLmGURgrgpump": { tokensOut: "3421153072592", buyImpactBps: 65, sellImpactBps: 63, progressBps: 193, solNeeded: "85627497854", sellback: "97534805" },
  "4ZMfb4CrjSzZhLMR9YL3p4g7GAYdX6CTo6QmnbYnpump": { tokensOut: "2913598132876", buyImpactBps: 60, sellImpactBps: 58, progressBps: 1223, solNeeded: "83046967316", sellback: "97534501" },
};

for (const [mint, exp] of Object.entries(EXPECTED_0_1_SOL)) {
  test(`quote parity with previous SDK for ${mint.slice(0, 8)} @ 0.1 SOL`, () => {
    const curve = sdk.PUMP_SDK.decodeBondingCurve(acct(fx.curves[mint]));
    assert.equal(curve.complete, false);
    assert.ok(sdk.isSolLikeQuoteMint(curve.quoteMint));
    const sol = new BN("100000000");
    const base = { global, feeConfig, mintSupply: curve.tokenTotalSupply };
    const tokensOut = sdk.getBuyTokenAmountFromSolAmount({ ...base, bondingCurve: curve, amount: sol, quoteMint: curve.quoteMint });
    assert.equal(tokensOut.toString(), exp.tokensOut);
    assert.equal(math.buyPriceImpact(curve, sol, tokensOut).impactBps, exp.buyImpactBps);
    const solOut = sdk.getSellSolAmountFromTokenAmount({ ...base, bondingCurve: curve, amount: tokensOut });
    assert.equal(math.sellPriceImpact(curve, tokensOut, solOut).impactBps, exp.sellImpactBps);
    const prog = math.graduationProgress(global, curve, (c) =>
      sdk.getBuySolAmountFromTokenAmount({ ...base, mintSupply: c.tokenTotalSupply, bondingCurve: c, amount: c.realTokenReserves, quoteMint: c.quoteMint }));
    assert.equal(prog.progressBps, exp.progressBps);
    assert.equal(prog.solNeededToGraduate.toString(), exp.solNeeded);
    const sellback = sdk.getSellSolAmountFromTokenAmount({ ...base, bondingCurve: math.postBuyCurve(curve, sol, tokensOut), amount: tokensOut });
    assert.equal(sellback.toString(), exp.sellback);
    const rt = math.roundtripBps(sol, sellback);
    assert.ok(rt < 0 && rt > -400, `roundtrip ${rt} bps should be a small loss (fees)`);
  });
}

test("graduated curve short-circuits progress", () => {
  const curve = { complete: true, realTokenReserves: new BN(0) };
  assert.deepEqual(math.graduationProgress(global, curve, null).progressBps, 10_000);
});

test("zero-size and empty-reserve edge cases", () => {
  assert.equal(math.roundtripBps(new BN(0), new BN(5)), 0);
  assert.equal(math.spotPrice({ virtualQuoteReserves: new BN(1), virtualTokenReserves: new BN(0) }).toString(), "0");
});

test("sidecar source has no transaction building or signing", () => {
  for (const f of ["../pump_quote_service.mjs", "../pump_quote_math.mjs"]) {
    const src = fs.readFileSync(new URL(f, import.meta.url), "utf8");
    assert.doesNotMatch(src, /sendTransaction|Keypair\(|buyInstructions|sellInstructions|buyV2Instructions|routedBuyInstructions|routedSellInstructions|signTransaction/);
  }
});
