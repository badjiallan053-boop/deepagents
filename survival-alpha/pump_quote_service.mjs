import http from "node:http";
import BN from "bn.js";
import { Connection, PublicKey } from "@solana/web3.js";
import {
  OnlinePumpSdk,
  getBuyTokenAmountFromSolAmount,
  getSellSolAmountFromTokenAmount,
  calculateBuyPriceImpact,
  calculateSellPriceImpact,
  getGraduationProgress,
  bondingCurveMarketCap,
} from "@nirholas/pump-sdk";

const PORT = Number(process.env.PUMP_QUOTER_PORT || 10001);
const rpcUrl =
  process.env.SOLANA_RPC_URL ||
  process.env.HELIUS_RPC_URL ||
  (process.env.HELIUS_API_KEY
    ? `https://mainnet.helius-rpc.com/?api-key=${process.env.HELIUS_API_KEY}`
    : "");

if (!rpcUrl) {
  throw new Error("SOLANA_RPC_URL / HELIUS_API_KEY required for Pump quoter");
}

const connection = new Connection(rpcUrl, "processed");
const sdk = new OnlinePumpSdk(connection);

let cachedGlobal = null;
let cachedFee = null;
let cacheAt = 0;

async function protocolState() {
  const now = Date.now();
  if (!cachedGlobal || now - cacheAt > 60_000) {
    [cachedGlobal, cachedFee] = await Promise.all([
      sdk.fetchGlobal(),
      sdk.fetchFeeConfig(),
    ]);
    cacheAt = now;
  }
  return { global: cachedGlobal, feeConfig: cachedFee };
}

function bnString(v) {
  return v?.toString?.() ?? String(v ?? "0");
}

async function readCurve(mintString) {
  const mint = new PublicKey(mintString);
  const [{ global, feeConfig }, bondingCurve] = await Promise.all([
    protocolState(),
    sdk.fetchBondingCurve(mint),
  ]);
  return { mint, global, feeConfig, bondingCurve };
}

async function buyQuote(mintString, lamportsString) {
  const solAmount = new BN(lamportsString);
  const { global, feeConfig, bondingCurve } = await readCurve(mintString);

  if (bondingCurve.complete || bondingCurve.virtualTokenReserves.isZero()) {
    return { phase: "graduated", graduated: true };
  }

  const mintSupply = bondingCurve.tokenTotalSupply;
  const tokensOut = getBuyTokenAmountFromSolAmount({
    global,
    feeConfig,
    mintSupply,
    bondingCurve,
    amount: solAmount,
  });
  const impact = calculateBuyPriceImpact({
    global,
    feeConfig,
    mintSupply,
    bondingCurve,
    solAmount,
  });
  const progress = getGraduationProgress(global, bondingCurve, feeConfig);
  const marketCap = bondingCurveMarketCap({
    mintSupply,
    virtualQuoteReserves: bondingCurve.virtualQuoteReserves,
    virtualTokenReserves: bondingCurve.virtualTokenReserves,
  });

  // Build the state that would exist immediately after our hypothetical buy.
  // This mirrors the SDK's own price-impact reserve transition. It is used only
  // for research/paper sellability; no transaction is constructed or sent.
  const postCurve = {
    ...bondingCurve,
    virtualQuoteReserves: bondingCurve.virtualQuoteReserves.add(solAmount),
    virtualTokenReserves: BN.max(
      new BN(0),
      bondingCurve.virtualTokenReserves.sub(tokensOut)
    ),
    realQuoteReserves: bondingCurve.realQuoteReserves.add(solAmount),
    realTokenReserves: BN.max(
      new BN(0),
      bondingCurve.realTokenReserves.sub(tokensOut)
    ),
  };

  const sellbackLamports = getSellSolAmountFromTokenAmount({
    global,
    feeConfig,
    mintSupply,
    bondingCurve: postCurve,
    amount: tokensOut,
  });

  const roundtripBps = solAmount.isZero()
    ? 0
    : sellbackLamports
        .sub(solAmount)
        .muln(10_000)
        .div(solAmount)
        .toNumber();

  return {
    phase: "bonding_curve",
    graduated: false,
    tokensOut: bnString(tokensOut),
    sellbackLamports: bnString(sellbackLamports),
    roundtripBps,
    buyImpactBps: impact.impactBps,
    marketCapLamports: bnString(marketCap),
    graduationProgressBps: progress.progressBps,
    solNeededToGraduate: bnString(progress.solNeededToGraduate),
    realTokenReserves: bnString(bondingCurve.realTokenReserves),
    realQuoteReserves: bnString(bondingCurve.realQuoteReserves),
    virtualTokenReserves: bnString(bondingCurve.virtualTokenReserves),
    virtualQuoteReserves: bnString(bondingCurve.virtualQuoteReserves),
  };
}

async function sellQuote(mintString, tokenAmountString) {
  const amount = new BN(tokenAmountString);
  const { global, feeConfig, bondingCurve } = await readCurve(mintString);

  if (bondingCurve.complete || bondingCurve.virtualTokenReserves.isZero()) {
    return { phase: "graduated", graduated: true };
  }

  const mintSupply = bondingCurve.tokenTotalSupply;
  const solOut = getSellSolAmountFromTokenAmount({
    global,
    feeConfig,
    mintSupply,
    bondingCurve,
    amount,
  });
  const impact = calculateSellPriceImpact({
    global,
    feeConfig,
    mintSupply,
    bondingCurve,
    tokenAmount: amount,
  });

  return {
    phase: "bonding_curve",
    graduated: false,
    solOutLamports: bnString(solOut),
    sellImpactBps: impact.impactBps,
  };
}

function respond(res, status, body) {
  const payload = JSON.stringify(body);
  res.writeHead(status, {
    "content-type": "application/json",
    "content-length": Buffer.byteLength(payload),
  });
  res.end(payload);
}

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, `http://127.0.0.1:${PORT}`);

    if (url.pathname === "/health") {
      return respond(res, 200, {
        ok: true,
        mode: "quote-only",
        transaction_builder: false,
        signing: false,
      });
    }

    if (url.pathname === "/buy-quote") {
      const mint = url.searchParams.get("mint");
      const lamports = url.searchParams.get("lamports");
      if (!mint || !lamports) {
        return respond(res, 400, { error: "mint and lamports required" });
      }
      return respond(res, 200, await buyQuote(mint, lamports));
    }

    if (url.pathname === "/sell-quote") {
      const mint = url.searchParams.get("mint");
      const tokens = url.searchParams.get("tokens");
      if (!mint || !tokens) {
        return respond(res, 400, { error: "mint and tokens required" });
      }
      return respond(res, 200, await sellQuote(mint, tokens));
    }

    return respond(res, 404, { error: "not found" });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    const notFound = /Bonding curve account not found/i.test(message);
    return respond(res, notFound ? 404 : 500, { error: message });
  }
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`Pump quote-only sidecar listening on 127.0.0.1:${PORT}`);
});
