import { useState, useEffect } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";

const MOCK_PRODUCTS = [
  {
    id: 1,
    name: "Teclado Mecânico Redragon",
    url: "https://mercadolivre.com.br/...",
    target_price: 250,
    current_price: 279.9,
    history: [
      { date: "01/05", price: 349.9 },
      { date: "05/05", price: 329.9 },
      { date: "09/05", price: 319.0 },
      { date: "13/05", price: 299.9 },
      { date: "17/05", price: 289.9 },
      { date: "21/05", price: 279.9 },
      { date: "25/05", price: 279.9 },
    ],
  },
  {
    id: 2,
    name: "Monitor LG 24' Full HD",
    url: "https://mercadolivre.com.br/...",
    target_price: 900,
    current_price: 899.0,
    history: [
      { date: "01/05", price: 1050 },
      { date: "05/05", price: 1020 },
      { date: "09/05", price: 980 },
      { date: "13/05", price: 960 },
      { date: "17/05", price: 940 },
      { date: "21/05", price: 920 },
      { date: "25/05", price: 899 },
    ],
  },
  {
    id: 3,
    name: "SSD Kingston 1TB NVMe",
    url: "https://mercadolivre.com.br/...",
    target_price: 320,
    current_price: 389.9,
    history: [
      { date: "01/05", price: 420 },
      { date: "05/05", price: 415 },
      { date: "09/05", price: 410 },
      { date: "13/05", price: 400 },
      { date: "17/05", price: 395 },
      { date: "21/05", price: 395 },
      { date: "25/05", price: 389.9 },
    ],
  },
];

const fmt = (v) => `R$ ${Number(v).toFixed(2).replace(".", ",")}`;

const StatusBadge = ({ current, target }) => {
  const reached = current <= target;
  const pct = Math.round(((current - target) / target) * 100);
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        padding: "3px 10px",
        borderRadius: 99,
        fontSize: 12,
        fontWeight: 700,
        letterSpacing: "0.05em",
        background: reached ? "#00ff9520" : "#ff443020",
        color: reached ? "#00e676" : "#ff6b6b",
        border: `1px solid ${reached ? "#00e67640" : "#ff6b6b40"}`,
      }}
    >
      <span style={{ fontSize: 9 }}>●</span>
      {reached ? "META ATINGIDA" : `+${pct}% acima`}
    </span>
  );
};

const CustomTooltip = ({ active, payload, label, target }) => {
  if (!active || !payload?.length) return null;
  const price = payload[0].value;
  const below = price <= target;
  return (
    <div style={{
      background: "#0f1117",
      border: "1px solid #2a2d3a",
      borderRadius: 8,
      padding: "10px 14px",
      fontSize: 13,
    }}>
      <div style={{ color: "#888", marginBottom: 4 }}>{label}</div>
      <div style={{ color: below ? "#00e676" : "#e2e8f0", fontWeight: 700 }}>{fmt(price)}</div>
      {below && <div style={{ color: "#00e676", fontSize: 11, marginTop: 2 }}>✓ Abaixo da meta</div>}
    </div>
  );
};

export default function PriceWatcher() {
  const [selected, setSelected] = useState(MOCK_PRODUCTS[0]);
  const [lastChecked] = useState("27/05/2026 às 14:32");
  const [pulse, setPulse] = useState(false);

  useEffect(() => {
    const t = setInterval(() => {
      setPulse(true);
      setTimeout(() => setPulse(false), 600);
    }, 4000);
    return () => clearInterval(t);
  }, []);

  const alertsCount = MOCK_PRODUCTS.filter(p => p.current_price <= p.target_price).length;
  const minPrice = Math.min(...selected.history.map(h => h.price));
  const maxPrice = Math.max(...selected.history.map(h => h.price));
  const drop = Math.round(((maxPrice - selected.current_price) / maxPrice) * 100);

  return (
    <div style={{
      minHeight: "100vh",
      background: "#080a10",
      fontFamily: "'DM Mono', 'Courier New', monospace",
      color: "#e2e8f0",
      padding: "0",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@300;400;500&family=Syne:wght@700;800&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: #0f1117; }
        ::-webkit-scrollbar-thumb { background: #2a2d3a; border-radius: 2px; }
        .card { background: #0d0f18; border: 1px solid #1e2130; border-radius: 12px; }
        .card:hover { border-color: #2a2d3a; }
        .product-row { cursor: pointer; transition: all .15s; border-radius: 10px; padding: 12px 14px; border: 1px solid transparent; }
        .product-row:hover { background: #0f1117; border-color: #1e2130; }
        .product-row.active { background: #111420; border-color: #3b82f620; }
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:.3} }
      `}</style>

      {/* Header */}
      <div style={{
        borderBottom: "1px solid #1e2130",
        padding: "18px 28px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        background: "#0a0c14",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{
            width: 36, height: 36,
            background: "linear-gradient(135deg, #3b82f6, #8b5cf6)",
            borderRadius: 10,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 18,
          }}>🔔</div>
          <div>
            <div style={{ fontFamily: "'Syne', sans-serif", fontSize: 18, fontWeight: 800, letterSpacing: "-0.01em" }}>
              price<span style={{ color: "#3b82f6" }}>watcher</span>
            </div>
            <div style={{ fontSize: 11, color: "#555", marginTop: 1 }}>monitor de preços · mercado livre</div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          {alertsCount > 0 && (
            <div style={{
              background: "#00e67615",
              border: "1px solid #00e67630",
              borderRadius: 8,
              padding: "6px 12px",
              fontSize: 12,
              color: "#00e676",
              fontWeight: 500,
            }}>
              🎯 {alertsCount} meta{alertsCount > 1 ? "s" : ""} atingida{alertsCount > 1 ? "s" : ""}
            </div>
          )}
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 11, color: "#555" }}>última verificação</div>
            <div style={{ fontSize: 12, color: "#888" }}>{lastChecked}</div>
          </div>
          <div style={{
            width: 10, height: 10, borderRadius: "50%",
            background: "#00e676",
            animation: pulse ? "blink .6s ease" : "none",
            boxShadow: "0 0 8px #00e676",
          }} />
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", height: "calc(100vh - 73px)" }}>

        {/* Sidebar */}
        <div style={{
          borderRight: "1px solid #1e2130",
          padding: "16px 12px",
          overflowY: "auto",
          background: "#090b12",
        }}>
          <div style={{ fontSize: 10, color: "#444", letterSpacing: "0.15em", padding: "0 4px 10px" }}>
            PRODUTOS MONITORADOS
          </div>
          {MOCK_PRODUCTS.map(p => {
            const reached = p.current_price <= p.target_price;
            return (
              <div
                key={p.id}
                className={`product-row ${selected.id === p.id ? "active" : ""}`}
                onClick={() => setSelected(p)}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, lineHeight: 1.3, flex: 1 }}>{p.name}</div>
                  <div style={{
                    width: 8, height: 8, borderRadius: "50%", flexShrink: 0, marginTop: 4,
                    background: reached ? "#00e676" : "#ff6b6b",
                    boxShadow: reached ? "0 0 6px #00e676" : "0 0 6px #ff6b6b",
                  }} />
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8 }}>
                  <div>
                    <div style={{ fontSize: 11, color: "#555" }}>atual</div>
                    <div style={{ fontSize: 15, fontWeight: 500, color: reached ? "#00e676" : "#e2e8f0" }}>
                      {fmt(p.current_price)}
                    </div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: 11, color: "#555" }}>meta</div>
                    <div style={{ fontSize: 15, color: "#666" }}>{fmt(p.target_price)}</div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Main */}
        <div style={{ padding: "24px 28px", overflowY: "auto" }}>

          {/* Product header */}
          <div style={{ marginBottom: 24 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
              <h1 style={{
                fontFamily: "'Syne', sans-serif",
                fontSize: 22,
                fontWeight: 800,
                flex: 1,
              }}>{selected.name}</h1>
              <StatusBadge current={selected.current_price} target={selected.target_price} />
            </div>
            <div style={{ fontSize: 12, color: "#444", fontFamily: "monospace" }}>
              {selected.url}
            </div>
          </div>

          {/* Stats */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 24 }}>
            {[
              { label: "Preço Atual", value: fmt(selected.current_price), accent: selected.current_price <= selected.target_price ? "#00e676" : "#e2e8f0" },
              { label: "Meta", value: fmt(selected.target_price), accent: "#3b82f6" },
              { label: "Mínimo Histórico", value: fmt(minPrice), accent: "#a78bfa" },
              { label: "Queda Total", value: `${drop}%`, accent: "#f59e0b" },
            ].map(stat => (
              <div key={stat.label} className="card" style={{ padding: "16px 18px" }}>
                <div style={{ fontSize: 11, color: "#555", marginBottom: 6, letterSpacing: "0.05em" }}>
                  {stat.label.toUpperCase()}
                </div>
                <div style={{ fontSize: 20, fontWeight: 500, color: stat.accent }}>
                  {stat.value}
                </div>
              </div>
            ))}
          </div>

          {/* Chart */}
          <div className="card" style={{ padding: "20px 20px 12px" }}>
            <div style={{ fontSize: 11, color: "#555", letterSpacing: "0.1em", marginBottom: 16 }}>
              HISTÓRICO DE PREÇOS — ÚLTIMOS 30 DIAS
            </div>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={selected.history} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e2130" vertical={false} />
                <XAxis
                  dataKey="date"
                  tick={{ fill: "#555", fontSize: 11, fontFamily: "DM Mono" }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: "#555", fontSize: 11, fontFamily: "DM Mono" }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={v => `R$${v}`}
                  domain={["auto", "auto"]}
                  width={70}
                />
                <Tooltip content={<CustomTooltip target={selected.target_price} />} />
                <ReferenceLine
                  y={selected.target_price}
                  stroke="#3b82f640"
                  strokeDasharray="6 4"
                  label={{ value: "meta", fill: "#3b82f6", fontSize: 10, position: "right" }}
                />
                <Line
                  type="monotone"
                  dataKey="price"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={{ fill: "#3b82f6", r: 4, strokeWidth: 0 }}
                  activeDot={{ r: 6, fill: "#fff", stroke: "#3b82f6", strokeWidth: 2 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Footer hint */}
          <div style={{
            marginTop: 20,
            padding: "14px 18px",
            background: "#0d0f18",
            borderRadius: 10,
            border: "1px solid #1e2130",
            fontSize: 12,
            color: "#555",
            display: "flex",
            gap: 16,
          }}>
            <span>💡 Execute <code style={{ color: "#3b82f6", background: "#3b82f610", padding: "1px 6px", borderRadius: 4 }}>python src/watcher.py --interval 30</code> para monitoramento contínuo</span>
          </div>
        </div>
      </div>
    </div>
  );
}
