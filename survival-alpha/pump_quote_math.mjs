// Pure, read-only bonding-curve quote helpers for the Pump quote sidecar.
//
// The official @pump-fun/pump-sdk exposes the curve math
// (getBuyTokenAmountFromSolAmount / getSellSolAmountFromTokenAmount /
// getBuySolAmountFromTokenAmount / bondingCurveMarketCap) but not the
// price-impact and graduation-progress helpers that the previous unofficial
// @nirholas/pump-sdk added. These re-implement those helpers with the SAME
// semantics (spot price = virtualQuote * 1e9 / virtualToken; impact measured
// on the post-trade virtual reserves; progress = sold share of
// initialRealTokenReserves) so downstream thresholds stay comparable.
// Semantics follow @nirholas/pump-sdk 2.0.0 (Apache-2.0); this file is an
// independent implementation. No transactions are constructed or signed.
import BN from "bn.js";

const LAMPORTS_PER_SOL = new BN(1_000_000_000);
const ZERO = new BN(0);

export function spotPrice(curve) {
  if (curve.virtualTokenReserves.isZero()) return ZERO;
  return curve.virtualQuoteReserves.mul(LAMPORTS_PER_SOL).div(curve.virtualTokenReserves);
}

function impactBps(before, after, direction) {
  if (before.isZero()) return 0;
  const diff = direction === "buy" ? after.sub(before) : before.sub(after);
  return diff.muln(10_000).div(before).toNumber();
}

export function buyPriceImpact(curve, solAmount, tokensOut) {
  const before = spotPrice(curve);
  const vq = curve.virtualQuoteReserves.add(solAmount);
  const vt = curve.virtualTokenReserves.sub(tokensOut);
  const after = vt.lte(ZERO) ? ZERO : vq.mul(LAMPORTS_PER_SOL).div(vt);
  return { priceBefore: before, priceAfter: after, impactBps: impactBps(before, after, "buy") };
}

export function sellPriceImpact(curve, tokenAmount, solOut) {
  const before = spotPrice(curve);
  const vq = BN.max(ZERO, curve.virtualQuoteReserves.sub(solOut));
  const vt = curve.virtualTokenReserves.add(tokenAmount);
  const after = vt.isZero() ? ZERO : vq.mul(LAMPORTS_PER_SOL).div(vt);
  return { priceBefore: before, priceAfter: after, impactBps: impactBps(before, after, "sell") };
}

// solNeededFn(curve) -> BN : caller supplies the SDK's getBuySolAmountFromTokenAmount
export function graduationProgress(global, curve, solNeededFn) {
  if (curve.complete) {
    return { progressBps: 10_000, isGraduated: true, solNeededToGraduate: ZERO };
  }
  const initialReal = global.initialRealTokenReserves;
  if (!initialReal || initialReal.isZero()) {
    return { progressBps: 0, isGraduated: false, solNeededToGraduate: ZERO };
  }
  const remaining = BN.min(curve.realTokenReserves, initialReal);
  const sold = initialReal.sub(remaining);
  return {
    progressBps: sold.muln(10_000).div(initialReal).toNumber(),
    isGraduated: false,
    solNeededToGraduate: solNeededFn ? solNeededFn(curve) : null,
  };
}

// Reserve transition immediately after a hypothetical buy (research only).
export function postBuyCurve(curve, solAmount, tokensOut) {
  return {
    ...curve,
    virtualQuoteReserves: curve.virtualQuoteReserves.add(solAmount),
    virtualTokenReserves: BN.max(ZERO, curve.virtualTokenReserves.sub(tokensOut)),
    realQuoteReserves: curve.realQuoteReserves.add(solAmount),
    realTokenReserves: BN.max(ZERO, curve.realTokenReserves.sub(tokensOut)),
  };
}

export function roundtripBps(solAmount, sellbackLamports) {
  if (solAmount.isZero()) return 0;
  return sellbackLamports.sub(solAmount).muln(10_000).div(solAmount).toNumber();
}
