(function () {
  function money(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "$--";
    return "$" + Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function percent(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "--";
    var num = Number(value);
    return (num >= 0 ? "📈 +" : "📉 ") + num.toFixed(2) + "%";
  }

  function compact(value) {
    var num = Number(value || 0);
    if (!num) return "--";
    if (num >= 1000000000) return (num / 1000000000).toFixed(2) + "B";
    if (num >= 1000000) return (num / 1000000).toFixed(2) + "M";
    if (num >= 1000) return (num / 1000).toFixed(2) + "K";
    return num.toFixed(0);
  }

  function sparkPath(seed, up) {
    var base = up ? [20, 18, 19, 15, 17, 12, 14, 9] : [10, 14, 12, 17, 15, 20, 18, 24];
    var shift = Math.abs(Math.round(seed || 0)) % 5;
    var values = base.map(function (v, index) { return v + ((index + shift) % 3) - 1; });
    return values.map(function (value, index) {
      var x = index * (220 / (values.length - 1));
      return (index === 0 ? "M" : "L") + x.toFixed(1) + " " + value.toFixed(1);
    }).join(" ");
  }

  function setText(id, value) {
    var node = document.getElementById(id);
    if (node) node.textContent = value;
  }

  async function loadMarket() {
    var source = document.getElementById("market-source");
    try {
      var response = await fetch("/market/tickers", { cache: "no-store" });
      if (!response.ok) throw new Error("行情接口暂时不可用");
      var payload = await response.json();
      (payload.items || []).forEach(function (item) {
        var prefix = item.symbol.split("-")[0].toLowerCase();
        var changeValue = Number(item.change24h || 0);
        var up = changeValue >= 0;
        var card = document.getElementById(prefix + "-card");
        var price = document.getElementById(prefix + "-price");
        var change = document.getElementById(prefix + "-change");
        var meta = document.getElementById(prefix + "-meta");
        var mini = document.querySelector("#" + prefix + "-mini path");
        var rsi = Math.max(18, Math.min(82, Math.round(50 + changeValue * 4.2)));
        var score = Math.max(1, Math.min(99, Math.round(62 + changeValue * 5 - (rsi > 72 || rsi < 28 ? 8 : 0))));
        var trend = changeValue > 0.35 ? "上涨" : (changeValue < -0.35 ? "下跌" : "震荡");
        var support = Number(item.low24h || (item.price * 0.96));
        var resistance = Number(item.high24h || (item.price * 1.04));
        if (card) card.className = (card.classList.contains("home-market-card") ? "home-market-card " : "market-tile ") + (up ? "up" : "down");
        if (price) price.textContent = money(item.price);
        if (change) change.textContent = percent(changeValue);
        if (meta) meta.textContent = item.venue + " · " + new Date(item.updatedAt).toLocaleTimeString();
        if (mini) mini.setAttribute("d", sparkPath(changeValue + Number(item.price || 0), up));
        setText(prefix + "-volume", compact(item.volume24h));
        setText(prefix + "-rsi", rsi > 70 ? "偏热" : (rsi < 30 ? "偏冷" : "中性"));
        setText(prefix + "-trend", trend);
        setText(prefix + "-score", score);
        setText(prefix + "-support", money(support));
        setText(prefix + "-resistance", money(resistance));
      });
      if (source) {
        source.style.display = "block";
        source.textContent = "数据源：" + (payload.source || "实时行情") + " · 每 15 秒自动刷新";
      }
    } catch (error) {
      if (source) {
        source.style.display = "block";
        source.textContent = "币种价格暂时无法连接，请稍后刷新。";
      }
    }
  }

  window.loadMarket = loadMarket;
  document.addEventListener("DOMContentLoaded", function () {
    loadMarket();
    window.setInterval(loadMarket, 15000);
  });
})();
