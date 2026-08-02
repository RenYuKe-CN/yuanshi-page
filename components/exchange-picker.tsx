"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, Search } from "lucide-react";
import { EXCHANGE_GROUPS, exchangeLabel } from "@/lib/constants";
import cmcIconMap from "@/public/brand/exchange_icons.json";

const MANUAL_ICON_PATHS: Record<string, string> = {
  "FX100": "/brand/exchanges/fx100.png"
};

const CMC_ICON_PATHS = cmcIconMap as Record<string, string>;

function initials(name: string) {
  const words = name.match(/[A-Za-z0-9]+/g) || [];
  if (!words.length) return "其";
  const first = words[0] || "";
  return (words.length > 1 ? words.slice(0, 2).map((word) => word[0] || "").join("") : first.slice(0, 2)).toUpperCase();
}

function hue(name: string) {
  let value = 0;
  for (const char of name) value = (value * 31 + char.charCodeAt(0)) % 360;
  return value;
}

export function ExchangeIcon({ name, size = "md" }: { name: string; size?: "sm" | "md" }) {
  const label = exchangeLabel(name);
  const iconFile = CMC_ICON_PATHS[label];
  const iconPath = iconFile ? `/brand/exchanges/${iconFile}` : MANUAL_ICON_PATHS[label];
  if (iconPath) {
    return (
      <img
        src={iconPath}
        alt=""
        aria-hidden="true"
        className={`shrink-0 rounded-full bg-white object-cover ${size === "sm" ? "h-7 w-7" : "h-9 w-9"}`}
      />
    );
  }
  return (
    <span
      aria-hidden="true"
      className={`inline-grid shrink-0 place-items-center rounded-lg font-extrabold text-white shadow-inner ${size === "sm" ? "h-6 w-6 text-[9px]" : "h-8 w-8 text-[10px]"}`}
      style={{ background: `linear-gradient(135deg, hsl(${hue(label)} 72% 52%), hsl(${hue(label)} 72% 34%))` }}
    >
      {initials(label)}
    </span>
  );
}

export function ExchangeName({ name, iconSize = "sm" }: { name: string; iconSize?: "sm" | "md" }) {
  return <span className="inline-flex items-center gap-2"><ExchangeIcon name={name} size={iconSize} /><span className="text-[15px] font-semibold tracking-normal text-slate-200">{exchangeLabel(name)}</span></span>;
}

export function ExchangePicker({
  value,
  onChange,
  allowAll = false
}: {
  value: string;
  onChange: (value: string) => void;
  allowAll?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [dynamicGroups, setDynamicGroups] = useState<{ label: string; items: readonly string[] }[] | null>(null);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  useEffect(() => {
    fetch("/api/exchanges")
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((data: { exchanges: { name: string; category: "CEX" | "DEX" | "OTHER" }[] }) => {
        const labels = { CEX: "CEX 中心化交易所", DEX: "DEX 去中心化交易所", OTHER: "其他" };
        setDynamicGroups((["CEX", "DEX", "OTHER"] as const).map((category) => ({
          label: labels[category],
          items: data.exchanges.filter((item) => item.category === category).map((item) => item.name)
        })).filter((group) => group.items.length));
      })
      .catch(() => setDynamicGroups(null));
  }, []);

  const groups = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return (dynamicGroups || EXCHANGE_GROUPS).map((group) => ({
      ...group,
      items: group.items.filter((item) => !normalized || item.toLowerCase().includes(normalized))
    })).filter((group) => group.items.length);
  }, [query, dynamicGroups]);

  function choose(next: string) {
    onChange(next);
    setOpen(false);
    setQuery("");
  }

  return (
    <div ref={root} className={`exchange-picker-root relative ${open ? "exchange-picker-open z-[9999]" : "z-0"}`}>
      <button type="button" onClick={() => setOpen((current) => !current)} className="dark-input flex min-h-11 w-full items-center justify-between rounded-xl border-amber-300/25 bg-[#07111f] px-3 py-2 text-left text-white shadow-[0_0_0_1px_rgba(245,196,81,.06),0_12px_30px_rgba(0,0,0,.22)]">
        {value ? <ExchangeName name={value} iconSize="md" /> : <span className="text-slate-500">{allowAll ? "全部交易所" : "请选择交易所"}</span>}
        <ChevronDown size={17} className={`text-slate-500 transition ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="absolute right-0 z-[9999] mt-2 w-[min(520px,88vw)] rounded-2xl border border-white/10 bg-[#0d1624] p-3 text-slate-200 shadow-[0_28px_90px_rgba(0,0,0,.55)]">
          <label className="mb-2 flex items-center gap-2 rounded-xl border border-white/10 bg-black/20 px-3">
            <Search size={15} className="text-slate-400" />
            <input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索交易所名称" className="w-full border-0 bg-transparent py-2 text-sm text-white outline-none" />
          </label>
          <div className="max-h-[min(32rem,68vh)] overflow-y-auto">
            {allowAll && !query && <button type="button" onClick={() => choose("")} className="mb-1 w-full rounded px-3 py-2 text-left text-sm hover:bg-white/5">全部交易所</button>}
            {groups.map((group) => (
              <section key={group.label}>
                <div className="sticky top-0 z-10 bg-[#121d2c] px-3 py-2 text-xs font-bold text-amber-400">{group.label}</div>
                {group.items.map((item) => (
                  <button key={item} type="button" onClick={() => choose(item)} className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-[16px] font-black tracking-[-.02em] transition hover:bg-white/8 hover:text-white ${value === item ? "bg-amber-400/10 text-amber-300" : "text-white"}`}>
                    <ExchangeIcon name={item} />
                    <span className="text-white drop-shadow-[0_2px_12px_rgba(0,0,0,.75)]">{item}</span>
                  </button>
                ))}
              </section>
            ))}
            {!groups.length && <div className="p-4 text-center text-sm text-slate-500">没有匹配的交易所</div>}
          </div>
        </div>
      )}
    </div>
  );
}
