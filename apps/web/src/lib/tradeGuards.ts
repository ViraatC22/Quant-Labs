import type { TradeAssetClass, TradeEntry } from "@/lib/types";

export type CapitalRequirement = {
  amount: number;
  label: string;
  blockingReason?: "missing-underlying-price" | "naked-short-call";
  perUnitRequirement?: number;
  underlyingShares?: number;
};

export type BuyingPowerCheck = {
  ok: boolean;
  accountSize: number;
  reserved: number;
  buyingPower: number;
  requirement: CapitalRequirement;
  reason?: "invalid-account" | "whole-contract" | "capital" | CapitalRequirement["blockingReason"];
  maxAffordableQuantity?: number;
};

const WHOLE_CONTRACT_ASSETS = new Set<TradeAssetClass>(["option", "future"]);

function normalizeAssetClass(value: unknown): TradeAssetClass {
  const normalized = String(value ?? "").toLowerCase().trim();
  if (["option", "options", "opt"].includes(normalized)) return "option";
  if (["future", "futures", "fut"].includes(normalized)) return "future";
  if (["crypto", "coin", "digital asset"].includes(normalized)) return "crypto";
  if (["forex", "fx", "currency"].includes(normalized)) return "forex";
  return "equity";
}

function contractMultiplier(trade: Pick<TradeEntry, "assetClass" | "contractMultiplier">) {
  if (trade.contractMultiplier && trade.contractMultiplier > 0) return trade.contractMultiplier;
  return normalizeAssetClass(trade.assetClass) === "option" ? 100 : 1;
}

function safeQuantity(trade: Pick<TradeEntry, "quantity">) {
  return Math.abs(Number.isFinite(trade.quantity) ? trade.quantity : 0);
}

function tradeText(trade: TradeEntry) {
  return [
    trade.symbol,
    trade.assetClass,
    trade.side,
    trade.strategy,
    trade.setup,
    trade.notes,
    trade.optionType,
    trade.underlyingSymbol
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function isCoveredCall(trade: TradeEntry) {
  const text = tradeText(trade);
  const isCall = String(trade.optionType ?? "").toLowerCase() === "call" || /\bcall(s)?\b/.test(text);
  return isCall && trade.side === "short" && /\bcovered[- ]call\b|\bcovered\b/.test(text);
}

function isCashSecuredPut(trade: TradeEntry) {
  const text = tradeText(trade);
  const isPut = String(trade.optionType ?? "").toLowerCase() === "put" || /\bput(s)?\b/.test(text);
  return isPut && trade.side === "short" && /\bcash[- ]secured\b|\bsecured[- ]put\b/.test(text);
}

function optionUnderlyingReference(trade: TradeEntry) {
  if (trade.strikePrice && trade.strikePrice > 0) return trade.strikePrice;
  if (trade.currentPrice && trade.currentPrice > 0) return trade.currentPrice;
  return null;
}

function isOpenTrade(trade: TradeEntry) {
  return trade.exitPrice === null || trade.exitPrice === undefined;
}

export function tradeCapitalRequirement(trade: TradeEntry, strict = false): CapitalRequirement {
  const assetClass = normalizeAssetClass(trade.assetClass);
  const quantity = safeQuantity(trade);
  const fees = Math.max(0, trade.fees || 0);
  const multiplier = contractMultiplier(trade);
  const notional = Math.max(0, trade.entryPrice * quantity * multiplier);
  const leverage = trade.leverage && trade.leverage > 0 ? trade.leverage : 1;

  if (assetClass === "option") {
    const contracts = quantity;
    const reference = optionUnderlyingReference(trade);

    if (isCoveredCall(trade)) {
      if (!reference && strict) {
        return {
          amount: 0,
          label: "Covered call collateral",
          blockingReason: "missing-underlying-price"
        };
      }
      const amount = Math.max(0, (reference ?? trade.entryPrice) * 100 * contracts + fees);
      return {
        amount,
        label: "Covered call collateral",
        perUnitRequirement: contracts ? amount / contracts : 0,
        underlyingShares: contracts * 100
      };
    }

    if (isCashSecuredPut(trade)) {
      if (!reference && strict) {
        return {
          amount: 0,
          label: "Cash-secured put collateral",
          blockingReason: "missing-underlying-price"
        };
      }
      const amount = Math.max(0, (reference ?? trade.entryPrice) * 100 * contracts + fees);
      return {
        amount,
        label: "Cash-secured put collateral",
        perUnitRequirement: contracts ? amount / contracts : 0
      };
    }

    if (trade.side === "short") {
      const optionType = String(trade.optionType ?? "").toLowerCase();
      if (optionType === "call" || /\bcall(s)?\b/.test(tradeText(trade))) {
        if (!strict) {
          const amount = Math.max(0, (reference ?? trade.entryPrice) * 100 * contracts + fees);
          return {
            amount,
            label: "Short call collateral",
            perUnitRequirement: contracts ? amount / contracts : 0
          };
        }
        return {
          amount: 0,
          label: "Naked short call",
          blockingReason: strict ? "naked-short-call" : undefined
        };
      }
      if (!reference && strict) {
        return {
          amount: 0,
          label: "Short option collateral",
          blockingReason: "missing-underlying-price"
        };
      }
      const amount = Math.max(0, (reference ?? trade.entryPrice) * 100 * contracts + fees);
      return {
        amount,
        label: "Short option collateral",
        perUnitRequirement: contracts ? amount / contracts : 0
      };
    }

    const amount = Math.max(0, notional + fees);
    return {
      amount,
      label: "Option premium",
      perUnitRequirement: contracts ? amount / contracts : 0
    };
  }

  if (assetClass === "future" || assetClass === "forex") {
    const amount = Math.max(0, notional / leverage + fees);
    return {
      amount,
      label: assetClass === "future" ? "Futures notional reserve" : "Forex notional reserve",
      perUnitRequirement: quantity ? amount / quantity : 0
    };
  }

  const amount = Math.max(0, notional + fees);
  return {
    amount,
    label: assetClass === "crypto" ? "Crypto cash reserve" : "Equity cash reserve",
    perUnitRequirement: quantity ? amount / quantity : 0
  };
}

export function accountBuyingPower(openTrades: TradeEntry[], accountSize: number) {
  const reserved = openTrades
    .filter(isOpenTrade)
    .reduce((sum, trade) => sum + tradeCapitalRequirement(trade).amount, 0);
  return {
    accountSize,
    reserved,
    buyingPower: accountSize - reserved
  };
}

export function validateTradeBuyingPower(
  trade: TradeEntry,
  openTrades: TradeEntry[],
  accountSize: number
): BuyingPowerCheck {
  const account = accountBuyingPower(openTrades, accountSize);
  const requirement = tradeCapitalRequirement(trade, true);
  const assetClass = normalizeAssetClass(trade.assetClass);
  const quantity = safeQuantity(trade);

  if (!Number.isFinite(accountSize) || accountSize <= 0) {
    return {
      ok: false,
      ...account,
      requirement,
      reason: "invalid-account"
    };
  }

  if (WHOLE_CONTRACT_ASSETS.has(assetClass) && !Number.isInteger(quantity)) {
    return {
      ok: false,
      ...account,
      requirement,
      reason: "whole-contract"
    };
  }

  if (requirement.blockingReason) {
    return {
      ok: false,
      ...account,
      requirement,
      reason: requirement.blockingReason
    };
  }

  if (requirement.amount > account.buyingPower + 0.000001) {
    return {
      ok: false,
      ...account,
      requirement,
      reason: "capital",
      maxAffordableQuantity: requirement.perUnitRequirement
        ? Math.floor(Math.max(0, account.buyingPower) / requirement.perUnitRequirement)
        : undefined
    };
  }

  return {
    ok: true,
    ...account,
    requirement
  };
}
