"use client";

import { useEffect, useState } from "react";
import { Check, Copy, Crown, ExternalLink, LoaderCircle, Rocket, ShieldCheck, WalletCards } from "lucide-react";
import { api } from "@/components/api";

type Plan = {
  id: string;
  code: string;
  name: string;
  description: string;
  priceUsd: string;
  durationMonths: number;
  queryLimit: number | null;
  unlimitedHistory: boolean;
  features: string[];
};

type Membership = {
  status: string;
  planCode: string;
  planName: string;
  expiresAt: string | null;
  queryLimit: number | null;
  queryUsed: number;
  remaining: number | null;
  unlimited: boolean;
};

type PaymentConfig = {
  chain: string;
  chainId: number;
  receiver: string;
  tokens: Record<"USDT" | "USDC", { contract: string; decimals: number }>;
};

type OrderResponse = {
  order: {
    id: string;
    orderNo: string;
    amount: string;
    paymentToken: "USDT" | "USDC";
    receivingAddress: string;
    expiresAt: string;
    status: string;
  };
  payment: {
    chainId: number;
    chainHex: string;
    tokenContract: string;
    receiver: string;
    transferData: string;
  };
};

type Eip1193Provider = {
  request(args: { method: string; params?: unknown[] | object }): Promise<unknown>;
  disconnect?: () => Promise<void>;
};

declare global {
  interface Window {
    ethereum?: Eip1193Provider;
  }
}

export function MembershipCenter() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [payment, setPayment] = useState<PaymentConfig | null>(null);
  const [membership, setMembership] = useState<Membership | null>(null);
  const [token, setToken] = useState<"USDT" | "USDC">("USDT");
  const [wallet, setWallet] = useState("");
  const [provider, setProvider] = useState<Eip1193Provider | null>(null);
  const [order, setOrder] = useState<OrderResponse | null>(null);
  const [txHash, setTxHash] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    const [plansData, membershipData] = await Promise.all([
      api<{ plans: Plan[]; payment: PaymentConfig }>("/api/membership/plans"),
      api<{ membership: Membership }>("/api/membership")
    ]);
    setPlans(plansData.plans);
    setPayment(plansData.payment);
    setMembership(membershipData.membership);
  }

  useEffect(() => { load(); }, []);

  async function accountsFrom(target: Eip1193Provider) {
    const accounts = await target.request({ method: "eth_requestAccounts" }) as string[];
    if (!accounts[0]) throw new Error("钱包未返回账户");
    setWallet(accounts[0]);
    setProvider(target);
    return accounts[0];
  }

  async function connectMetaMask() {
    try {
      if (!window.ethereum) throw new Error("未检测到 MetaMask，请先安装钱包或使用 WalletConnect");
      setMessage("");
      await accountsFrom(window.ethereum);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "钱包连接失败");
    }
  }

  async function connectWalletConnect() {
    try {
      const projectId = process.env.NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID;
      if (!projectId) throw new Error("WalletConnect 尚未配置，请使用 MetaMask 或联系客服");
      const { default: EthereumProvider } = await import("@walletconnect/ethereum-provider");
      const target = await EthereumProvider.init({
        projectId,
        chains: [56],
        showQrModal: true,
        metadata: {
          name: "原石金手指",
          description: "IP查重管理系统会员支付",
          url: window.location.origin,
          icons: [`${window.location.origin}/brand/ck-logo.jpg`]
        }
      });
      await target.connect();
      await accountsFrom(target as unknown as Eip1193Provider);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "WalletConnect 连接失败");
    }
  }

  async function verify(targetOrderId: string, hash = txHash, autoPoll = false) {
    if (!hash) return setMessage("请输入 Transaction Hash");
    setBusy(true);
    try {
      const result = await api<{ confirmed: boolean; confirmations: number; required: number }>("/api/orders/verify", {
        method: "POST",
        body: JSON.stringify({ orderId: targetOrderId, txHash: hash })
      });
      if (result.confirmed) {
        setMessage("链上验证成功，会员已自动开通");
        await load();
      } else {
        setMessage(`交易已找到，等待确认 ${result.confirmations}/${result.required}`);
        if (autoPoll) window.setTimeout(() => verify(targetOrderId, hash, true), 10_000);
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "自动验单失败";
      setMessage(errorMessage);
      if (autoPoll && (errorMessage.includes("暂未查询") || errorMessage.includes("节点"))) {
        window.setTimeout(() => verify(targetOrderId, hash, true), 10_000);
      }
    } finally {
      setBusy(false);
    }
  }

  async function buy(planCode: string) {
    setBusy(true);
    setMessage("");
    try {
      const activeProvider = provider || window.ethereum;
      if (!activeProvider) throw new Error("请先连接 MetaMask 或 WalletConnect");
      const account = wallet || await accountsFrom(activeProvider);
      const created = await api<OrderResponse>("/api/orders", {
        method: "POST",
        body: JSON.stringify({ planCode, paymentToken: token, payerAddress: account })
      });
      setOrder(created);
      try {
        await activeProvider.request({
          method: "wallet_switchEthereumChain",
          params: [{ chainId: created.payment.chainHex }]
        });
      } catch {
        await activeProvider.request({
          method: "wallet_addEthereumChain",
          params: [{
            chainId: "0x38",
            chainName: "BNB Smart Chain",
            nativeCurrency: { name: "BNB", symbol: "BNB", decimals: 18 },
            rpcUrls: ["https://bsc-dataseed.binance.org"],
            blockExplorerUrls: ["https://bscscan.com"]
          }]
        });
      }
      const hash = await activeProvider.request({
        method: "eth_sendTransaction",
        params: [{
          from: account,
          to: created.payment.tokenContract,
          value: "0x0",
          data: created.payment.transferData
        }]
      }) as string;
      setTxHash(hash);
      setMessage("交易已提交，正在自动验证链上确认");
      await verify(created.order.id, hash, true);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "创建付款失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <header className="premium-hero grid gap-6 rounded-[2rem] p-6 md:grid-cols-[1fr_auto] md:p-8">
        <div className="max-w-3xl">
          <p className="inline-flex rounded-full border border-amber-400/20 bg-amber-400/10 px-3 py-1.5 text-[11px] font-black tracking-[.18em] text-amber-300">YS GOLD FINGER · MEMBERSHIP</p>
          <h1 className="mt-5 text-4xl font-black tracking-[-.05em] text-white md:text-5xl">会员中心</h1>
          <p className="mt-4 text-sm leading-6 text-slate-400 md:text-base">开通后即可使用 IP 查重、历史管理与高级权益。支持 USDT / USDC · BEP20，链上验证成功后自动开通，无需人工审核。</p>
        </div>
        <div className="flex items-center gap-5 md:flex-col md:items-end">
          <img src="/brand/ck-logo.jpg" alt="原石金手指 LOGO" className="premium-logo h-24 w-24 object-cover md:h-36 md:w-36" />
          <div className="glass-card rounded-2xl px-5 py-3 text-sm">
            <span className="text-slate-500">当前：</span><strong className="text-amber-300">{membership?.planName || "加载中"}</strong>
            <span className="ml-4 text-slate-500">剩余：</span><strong className="text-white">{membership?.unlimited ? "无限" : membership?.remaining ?? 0}</strong>
          </div>
        </div>
      </header>

      <section className="grid gap-4 lg:grid-cols-3">
        {plans.map((plan) => {
          const paid = plan.code !== "FREE";
          const featured = plan.code === "PRO";
          const starship = plan.code === "STARSHIP";
          const Icon = plan.code === "PRO" ? Crown : plan.code === "STARSHIP" ? Rocket : ShieldCheck;
          return (
            <article key={plan.id} className={`glass-card plan-card rounded-[2rem] p-6 ${featured ? "plan-pro" : starship ? "plan-starship" : ""}`}>
              {featured && <span className="absolute right-4 top-4 z-10 rounded-full bg-amber-400 px-3 py-1 text-[10px] font-black text-slate-950 shadow-lg shadow-amber-400/20">旗舰首选</span>}
              {starship && <span className="absolute right-4 top-4 z-10 rounded-full border border-blue-400/30 bg-blue-400/10 px-3 py-1 text-[10px] font-black text-blue-200">热门开通</span>}
              <span className="relative z-10 grid h-12 w-12 place-items-center rounded-2xl border border-amber-400/25 bg-amber-400/10 text-amber-300 shadow-inner"><Icon size={22} /></span>
              <h2 className="relative z-10 mt-5 text-2xl font-black tracking-[-.03em] text-white">{plan.name}</h2>
              <p className="mt-2 min-h-10 text-xs leading-5 text-slate-500">{plan.description}</p>
              <div className="relative z-10 mt-5">
                <span className={`text-5xl font-black tracking-[-.06em] ${featured ? "gold-text" : "text-white"}`}>{plan.priceUsd}</span>
                <span className="ml-2 text-sm font-bold text-slate-500">USDT / USDC{paid ? " / 月" : ""}</span>
              </div>
              <ul className="relative z-10 mt-6 space-y-3">
                {plan.features.map((feature) => <li key={feature} className="flex gap-2 text-sm text-slate-300"><Check size={16} className="mt-0.5 shrink-0 text-amber-400" />{feature}</li>)}
              </ul>
              {paid ? <button disabled={busy} onClick={() => buy(plan.code)} className="gold-button relative z-10 mt-7 w-full rounded-xl px-4 py-3 text-sm font-black disabled:opacity-50">{busy ? "处理中..." : "连接钱包并购买"}</button> : <button disabled className="relative z-10 mt-7 w-full rounded-xl border border-white/10 px-4 py-3 text-sm text-slate-600">默认账户</button>}
            </article>
          );
        })}
      </section>

      <section className="glass-card grid gap-6 rounded-3xl p-6 lg:grid-cols-[1fr_auto]">
        <div>
          <h2 className="flex items-center gap-2 font-bold text-white"><WalletCards className="text-amber-400" size={19} />支付设置</h2>
          <div className="mt-4 flex flex-wrap gap-2">
            {(["USDT", "USDC"] as const).map((item) => <button key={item} onClick={() => setToken(item)} className={`rounded-xl border px-4 py-2 text-sm ${token === item ? "border-amber-400/40 bg-amber-400/10 text-amber-300" : "border-white/10 text-slate-500"}`}>{item}</button>)}
          </div>
          <div className="mt-4 flex flex-wrap gap-3">
            <button onClick={connectMetaMask} className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200">连接 MetaMask</button>
            <button onClick={connectWalletConnect} className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200">WalletConnect</button>
          </div>
          <p className="mt-3 break-all text-xs text-slate-600">钱包：{wallet || "未连接"}</p>
          <p className="mt-2 text-xs text-slate-600">网络：BEP20（BSC） · 订单有效期 30 分钟</p>
        </div>
        {payment && (
          <div className="flex items-center gap-4 rounded-2xl bg-white p-3 text-slate-900">
            <img src={`/api/payment/qr?text=${encodeURIComponent(payment.receiver)}`} alt="BSC 收款地址二维码" className="h-28 w-28" />
            <div className="max-w-52">
              <p className="text-xs text-slate-500">收款地址</p>
              <p className="mt-1 break-all font-mono text-[10px]">{payment.receiver}</p>
              <button onClick={() => navigator.clipboard.writeText(payment.receiver)} className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-amber-700"><Copy size={13} />复制地址</button>
            </div>
          </div>
        )}
      </section>

      {order && (
        <section className="glass-card rounded-3xl p-6">
          <h2 className="font-bold text-white">订单 {order.order.orderNo}</h2>
          <div className="mt-4 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
            <div><span className="text-slate-600">金额</span><p className="mt-1 text-white">{order.order.amount} {order.order.paymentToken}</p></div>
            <div><span className="text-slate-600">网络</span><p className="mt-1 text-white">BEP20 (BSC)</p></div>
            <div><span className="text-slate-600">状态</span><p className="mt-1 text-amber-300">{order.order.status}</p></div>
            <div><span className="text-slate-600">有效期</span><p className="mt-1 text-white">{new Date(order.order.expiresAt).toLocaleString()}</p></div>
          </div>
          <div className="mt-5 flex flex-col gap-2 sm:flex-row">
            <input value={txHash} onChange={(e) => setTxHash(e.target.value)} placeholder="Transaction Hash（钱包付款后自动填写，也可手动粘贴）" className="dark-input min-w-0 flex-1 rounded-xl px-4 py-3 text-sm" />
            <button disabled={busy} onClick={() => verify(order.order.id)} className="gold-button inline-flex items-center justify-center gap-2 rounded-xl px-5 py-3 text-sm font-bold disabled:opacity-50">{busy ? <LoaderCircle size={16} className="animate-spin" /> : <ExternalLink size={16} />}自动验证</button>
          </div>
        </section>
      )}

      {message && <div className="rounded-2xl border border-amber-400/20 bg-amber-400/5 px-4 py-3 text-sm text-amber-200">{message}</div>}
    </div>
  );
}
