import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  BarChart, Bar, LineChart, Line, AreaChart, Area,
  PieChart, Pie, Cell, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';
import axios from 'axios';
import { format } from 'date-fns';

const API = 'https://supachat-devops-production.up.railway.app';

// ─── Color System ─────────────────────────────────────────────────────────────
const PALETTE = {
  emerald: '#00D4AA',
  emeraldDim: '#00D4AA22',
  sapphire: '#4F8EF7',
  sapphireDim: '#4F8EF722',
  coral: '#FF6B6B',
  amber: '#FFC947',
  violet: '#A78BFA',
  bg: '#0A0E1A',
  surface: '#111827',
  surfaceHigh: '#1C2537',
  border: '#1F2D45',
  text: '#E2E8F0',
  textMuted: '#64748B',
  textDim: '#334155',
};

const CHART_COLORS = [
  PALETTE.emerald, PALETTE.sapphire, PALETTE.coral,
  PALETTE.amber, PALETTE.violet, '#06B6D4', '#F97316', '#84CC16',
];

// ─── Utility ──────────────────────────────────────────────────────────────────
const fmtNum = (n) => {
  if (typeof n !== 'number') return n;
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toFixed(n % 1 === 0 ? 0 : 1);
};

// ─── CSS (injected) ───────────────────────────────────────────────────────────
const styles = `
  @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Sora:wght@300;400;500;600;700&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: ${PALETTE.bg}; color: ${PALETTE.text}; font-family: 'Sora', sans-serif; min-height: 100vh; overflow-x: hidden; }
  ::-webkit-scrollbar { width: 4px; }
  ::-webkit-scrollbar-track { background: ${PALETTE.bg}; }
  ::-webkit-scrollbar-thumb { background: ${PALETTE.border}; border-radius: 2px; }
  @keyframes fadeSlideUp { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
  @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:.4; } }
  @keyframes scanline { 0% { transform:translateY(-100%); } 100% { transform:translateY(100vh); } }
  @keyframes shimmer { 0% { background-position:-200% 0; } 100% { background-position:200% 0; } }
  .fade-in { animation: fadeSlideUp 0.35s ease forwards; }
  .blink { animation: pulse 1.4s ease-in-out infinite; }
`;

// ─── Sub-components ───────────────────────────────────────────────────────────
function GridBg() {
  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 0, pointerEvents: 'none',
      backgroundImage: `linear-gradient(${PALETTE.border}22 1px, transparent 1px), linear-gradient(90deg, ${PALETTE.border}22 1px, transparent 1px)`,
      backgroundSize: '40px 40px',
    }} />
  );
}

function Logo() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <div style={{
        width: 36, height: 36, borderRadius: 8,
        background: `linear-gradient(135deg, ${PALETTE.emerald}, ${PALETTE.sapphire})`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 18, fontWeight: 700, color: '#fff', fontFamily: 'Space Mono, monospace',
        boxShadow: `0 0 20px ${PALETTE.emerald}44`,
      }}>S</div>
      <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 16, fontWeight: 700, letterSpacing: 1, color: PALETTE.text }}>
        SUPA<span style={{ color: PALETTE.emerald }}>CHAT</span>
      </span>
    </div>
  );
}

function StatusDot({ ok }) {
  return (
    <span style={{
      display: 'inline-block', width: 7, height: 7, borderRadius: '50%',
      background: ok ? PALETTE.emerald : PALETTE.coral,
      boxShadow: ok ? `0 0 6px ${PALETTE.emerald}` : `0 0 6px ${PALETTE.coral}`,
      marginRight: 5,
    }} />
  );
}

function Tag({ children, color = PALETTE.emerald }) {
  return (
    <span style={{
      display: 'inline-block', padding: '2px 8px', borderRadius: 4, fontSize: 11,
      fontFamily: 'Space Mono, monospace', border: `1px solid ${color}44`,
      background: `${color}11`, color,
    }}>{children}</span>
  );
}

function Card({ children, style = {} }) {
  return (
    <div style={{
      background: PALETTE.surface, border: `1px solid ${PALETTE.border}`,
      borderRadius: 12, padding: 20, ...style,
    }}>{children}</div>
  );
}

function Spinner() {
  return (
    <div style={{ display: 'flex', gap: 6, alignItems: 'center', padding: '12px 16px' }}>
      {[0, 1, 2].map(i => (
        <div key={i} className="blink" style={{
          width: 8, height: 8, borderRadius: '50%',
          background: PALETTE.emerald,
          animationDelay: `${i * 0.2}s`,
          boxShadow: `0 0 8px ${PALETTE.emerald}`,
        }} />
      ))}
      <span style={{ color: PALETTE.textMuted, fontSize: 13, marginLeft: 6, fontFamily: 'Space Mono, monospace' }}>
        Analyzing...
      </span>
    </div>
  );
}

// ─── Chart Renderer ───────────────────────────────────────────────────────────
function DynamicChart({ data, config }) {
  if (!config || !data || data.length === 0) return null;
  const { type, x, y, label } = config;
  const h = 260;

  const tooltipStyle = {
    background: PALETTE.surfaceHigh, border: `1px solid ${PALETTE.border}`,
    borderRadius: 8, color: PALETTE.text, fontSize: 12,
    fontFamily: 'Space Mono, monospace',
  };

  const axisProps = {
    stroke: PALETTE.textDim, tick: { fill: PALETTE.textMuted, fontSize: 11, fontFamily: 'Space Mono, monospace' },
    tickLine: false, axisLine: { stroke: PALETTE.border },
  };

  const commonProps = {
    data, margin: { top: 10, right: 10, left: -10, bottom: 0 },
  };

  const renderChart = () => {
    switch (type) {
      case 'bar':
        return (
          <BarChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" stroke={PALETTE.border} />
            <XAxis dataKey={x} {...axisProps} />
            <YAxis tickFormatter={fmtNum} {...axisProps} />
            <Tooltip contentStyle={tooltipStyle} formatter={(v) => [fmtNum(v), label]} />
            <Bar dataKey={y} radius={[4, 4, 0, 0]}>
              {data.map((_, i) => (
                <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]}
                  style={{ filter: `drop-shadow(0 0 6px ${CHART_COLORS[i % CHART_COLORS.length]}66)` }} />
              ))}
            </Bar>
          </BarChart>
        );
      case 'line':
        return (
          <LineChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" stroke={PALETTE.border} />
            <XAxis dataKey={x} {...axisProps} />
            <YAxis tickFormatter={fmtNum} {...axisProps} />
            <Tooltip contentStyle={tooltipStyle} />
            <Line type="monotone" dataKey={y} stroke={PALETTE.emerald} strokeWidth={2}
              dot={{ fill: PALETTE.emerald, r: 3 }} activeDot={{ r: 6, stroke: PALETTE.emerald }} />
          </LineChart>
        );
      case 'area':
        return (
          <AreaChart {...commonProps}>
            <defs>
              <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={PALETTE.emerald} stopOpacity={0.3} />
                <stop offset="95%" stopColor={PALETTE.emerald} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={PALETTE.border} />
            <XAxis dataKey={x} {...axisProps} />
            <YAxis tickFormatter={fmtNum} {...axisProps} />
            <Tooltip contentStyle={tooltipStyle} />
            <Area type="monotone" dataKey={y} stroke={PALETTE.emerald} strokeWidth={2}
              fill="url(#areaGrad)" />
          </AreaChart>
        );
      case 'pie':
        return (
          <PieChart>
            <Pie data={data} dataKey={y} nameKey={x} cx="50%" cy="50%" outerRadius={90}
              label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
              labelLine={{ stroke: PALETTE.textMuted }}>
              {data.map((_, i) => (
                <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip contentStyle={tooltipStyle} />
          </PieChart>
        );
      default:
        return null;
    }
  };

  return (
    <Card style={{ marginTop: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: PALETTE.text }}>{label}</span>
        <Tag color={PALETTE.sapphire}>{type} chart</Tag>
      </div>
      <ResponsiveContainer width="100%" height={h}>
        {renderChart()}
      </ResponsiveContainer>
    </Card>
  );
}

// ─── Data Table ───────────────────────────────────────────────────────────────
function DataTable({ data, columns }) {
  if (!data || data.length === 0) return null;
  return (
    <Card style={{ marginTop: 12, padding: 0, overflow: 'hidden' }}>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, fontFamily: 'Space Mono, monospace' }}>
          <thead>
            <tr style={{ background: PALETTE.surfaceHigh }}>
              {columns.map(col => (
                <th key={col} style={{
                  padding: '10px 14px', textAlign: 'left', color: PALETTE.emerald,
                  fontWeight: 600, fontSize: 11, textTransform: 'uppercase',
                  letterSpacing: 0.5, borderBottom: `1px solid ${PALETTE.border}`,
                  whiteSpace: 'nowrap',
                }}>{col.replace(/_/g, ' ')}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => (
              <tr key={i} style={{
                borderBottom: `1px solid ${PALETTE.border}`,
                background: i % 2 === 0 ? 'transparent' : `${PALETTE.surfaceHigh}55`,
                transition: 'background 0.15s',
              }}
                onMouseEnter={e => e.currentTarget.style.background = PALETTE.emeraldDim}
                onMouseLeave={e => e.currentTarget.style.background = i % 2 === 0 ? 'transparent' : `${PALETTE.surfaceHigh}55`}
              >
                {columns.map(col => (
                  <td key={col} style={{ padding: '9px 14px', color: PALETTE.text }}>
                    {typeof row[col] === 'number' ? fmtNum(row[col]) : String(row[col] ?? '—')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div style={{
        padding: '8px 14px', color: PALETTE.textMuted, fontSize: 11,
        borderTop: `1px solid ${PALETTE.border}`, fontFamily: 'Space Mono, monospace',
      }}>
        {data.length} rows returned
      </div>
    </Card>
  );
}

// ─── SQL Viewer ───────────────────────────────────────────────────────────────
function SQLBlock({ sql }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ marginTop: 10 }}>
      <button onClick={() => setOpen(!open)} style={{
        background: 'none', border: 'none', cursor: 'pointer',
        color: PALETTE.textMuted, fontSize: 12, fontFamily: 'Space Mono, monospace',
        display: 'flex', alignItems: 'center', gap: 5, padding: 0,
      }}>
        <span style={{ fontSize: 10 }}>{open ? '▼' : '▶'}</span> View SQL
      </button>
      {open && (
        <pre style={{
          marginTop: 8, padding: '12px 14px', background: `${PALETTE.surfaceHigh}`,
          border: `1px solid ${PALETTE.border}`, borderRadius: 8,
          fontSize: 12, fontFamily: 'Space Mono, monospace',
          color: PALETTE.emerald, overflowX: 'auto', lineHeight: 1.6,
        }}>{sql}</pre>
      )}
    </div>
  );
}

// ─── Chat Message ─────────────────────────────────────────────────────────────
function Message({ msg }) {
  const isUser = msg.role === 'user';
  return (
    <div className="fade-in" style={{
      display: 'flex', flexDirection: isUser ? 'row-reverse' : 'row',
      gap: 12, marginBottom: 20, alignItems: 'flex-start',
    }}>
      {/* Avatar */}
      <div style={{
        width: 32, height: 32, borderRadius: 8, flexShrink: 0,
        background: isUser
          ? `linear-gradient(135deg, ${PALETTE.sapphire}, ${PALETTE.violet})`
          : `linear-gradient(135deg, ${PALETTE.emerald}, ${PALETTE.sapphire})`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 12, fontWeight: 700, color: '#fff', fontFamily: 'Space Mono, monospace',
        boxShadow: isUser ? `0 0 12px ${PALETTE.sapphire}44` : `0 0 12px ${PALETTE.emerald}44`,
      }}>
        {isUser ? 'U' : 'AI'}
      </div>

      {/* Content */}
      <div style={{ maxWidth: '85%', minWidth: 0 }}>
        {/* Main bubble */}
        <div style={{
          background: isUser ? `${PALETTE.sapphire}22` : PALETTE.surface,
          border: `1px solid ${isUser ? PALETTE.sapphire + '44' : PALETTE.border}`,
          borderRadius: 12, padding: '12px 16px',
          fontSize: 14, lineHeight: 1.7, color: PALETTE.text,
        }}>
          {msg.content}
        </div>

        {/* Result attachments */}
        {msg.result && (
          <div style={{ marginTop: 4 }}>
            {msg.result.narrative && msg.result.narrative !== msg.content && (
              <div style={{
                marginTop: 10, padding: '10px 14px',
                background: `${PALETTE.emerald}11`, border: `1px solid ${PALETTE.emerald}33`,
                borderRadius: 8, fontSize: 13, color: PALETTE.text, lineHeight: 1.6,
              }}>
                💡 {msg.result.narrative}
              </div>
            )}
            <DynamicChart data={msg.result.data} config={msg.result.chart_config} />
            <DataTable data={msg.result.data} columns={msg.result.columns} />
            <SQLBlock sql={msg.result.sql} />
            <div style={{ marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <Tag color={PALETTE.textMuted}>{msg.result.duration_ms}ms</Tag>
              <Tag color={PALETTE.textMuted}>ID: {msg.result.query_id}</Tag>
              <Tag color={PALETTE.textMuted}>{msg.result.data.length} rows</Tag>
            </div>
          </div>
        )}

        {msg.error && (
          <div style={{
            marginTop: 8, padding: '10px 14px',
            background: `${PALETTE.coral}11`, border: `1px solid ${PALETTE.coral}33`,
            borderRadius: 8, fontSize: 13, color: PALETTE.coral,
          }}>
            ⚠ {msg.error}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Main App ─────────────────────────────────────────────────────────────────
export default function App() {
  const [messages, setMessages] = useState([{
    id: 'welcome',
    role: 'assistant',
    content: "Hello! I'm SupaChat — your conversational analytics interface for blog data. Ask me anything about your content performance, trending topics, author metrics, or engagement patterns.",
  }]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const [health, setHealth] = useState(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('chat'); // chat | schema
  const [schema, setSchema] = useState(null);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  // Fetch suggestions & health on mount
  useEffect(() => {
    axios.get(`${API}/api/suggestions`).then(r => setSuggestions(r.data.suggestions)).catch(() => {});
    axios.get(`${API}/health`).then(r => setHealth(r.data)).catch(() => {});
    axios.get(`${API}/api/schema`).then(r => setSchema(r.data)).catch(() => {});
  }, []);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const sendMessage = useCallback(async (text) => {
    const q = text || input.trim();
    if (!q || loading) return;
    setInput('');

    const userMsg = { id: Date.now() + 'u', role: 'user', content: q };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    const history = messages
      .filter(m => m.role !== 'assistant' || !m.result)
      .map(m => ({ role: m.role, content: m.content }));

    try {
      const { data } = await axios.post(`${API}/api/chat`, { message: q, history });
      setMessages(prev => [...prev, {
        id: Date.now() + 'a',
        role: 'assistant',
        content: data.narrative || 'Here are the results:',
        result: data,
      }]);
    } catch (err) {
      setMessages(prev => [...prev, {
        id: Date.now() + 'e',
        role: 'assistant',
        content: 'Something went wrong processing your query.',
        error: err.response?.data?.detail || err.message,
      }]);
    } finally {
      setLoading(false);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [input, loading, messages]);

  const onKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  const queryHistory = messages.filter(m => m.role === 'user').map(m => m.content);

  return (
    <>
      <style>{styles}</style>
      <GridBg />

      <div style={{ position: 'relative', zIndex: 1, display: 'flex', flexDirection: 'column', height: '100vh' }}>

        {/* ── Header ── */}
        <header style={{
          padding: '14px 24px', display: 'flex', alignItems: 'center',
          justifyContent: 'space-between', borderBottom: `1px solid ${PALETTE.border}`,
          background: `${PALETTE.surface}cc`, backdropFilter: 'blur(12px)',
          position: 'sticky', top: 0, zIndex: 10,
        }}>
          <Logo />
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            {['chat', 'schema'].map(tab => (
              <button key={tab} onClick={() => setActiveTab(tab)} style={{
                background: 'none', border: 'none', cursor: 'pointer', padding: '4px 12px',
                borderRadius: 6, fontSize: 12, fontFamily: 'Space Mono, monospace',
                color: activeTab === tab ? PALETTE.emerald : PALETTE.textMuted,
                background: activeTab === tab ? `${PALETTE.emerald}15` : 'none',
                textTransform: 'uppercase', letterSpacing: 0.5,
              }}>{tab}</button>
            ))}
            {health && (
              <div style={{ fontSize: 11, fontFamily: 'Space Mono, monospace', color: PALETTE.textMuted, display: 'flex', gap: 10 }}>
                <span><StatusDot ok={health.supabase_connected} />DB</span>
                <span><StatusDot ok={health.llm_available} />LLM</span>
              </div>
            )}
          </div>
        </header>

        <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

          {/* ── Sidebar: History ── */}
          <aside style={{
            width: historyOpen ? 240 : 0, overflow: 'hidden', transition: 'width 0.25s ease',
            borderRight: historyOpen ? `1px solid ${PALETTE.border}` : 'none',
            background: PALETTE.surface, display: 'flex', flexDirection: 'column',
          }}>
            {historyOpen && (
              <div style={{ padding: 16 }}>
                <div style={{ fontSize: 11, fontFamily: 'Space Mono, monospace', color: PALETTE.emerald, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 12 }}>
                  Query History
                </div>
                {queryHistory.length === 0 && (
                  <div style={{ color: PALETTE.textMuted, fontSize: 12 }}>No queries yet</div>
                )}
                {queryHistory.map((q, i) => (
                  <button key={i} onClick={() => sendMessage(q)} style={{
                    display: 'block', width: '100%', textAlign: 'left', background: 'none',
                    border: `1px solid ${PALETTE.border}`, borderRadius: 6, padding: '8px 10px',
                    color: PALETTE.text, fontSize: 12, cursor: 'pointer', marginBottom: 6,
                    fontFamily: 'Sora, sans-serif', transition: 'all 0.15s',
                  }}
                    onMouseEnter={e => { e.currentTarget.style.borderColor = PALETTE.emerald; e.currentTarget.style.color = PALETTE.emerald; }}
                    onMouseLeave={e => { e.currentTarget.style.borderColor = PALETTE.border; e.currentTarget.style.color = PALETTE.text; }}
                  >
                    {q.length > 50 ? q.slice(0, 50) + '…' : q}
                  </button>
                ))}
              </div>
            )}
          </aside>

          {/* ── Main content ── */}
          <main style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>

            {activeTab === 'schema' ? (
              /* Schema view */
              <div style={{ flex: 1, overflowY: 'auto', padding: 24 }}>
                <div style={{ maxWidth: 800, margin: '0 auto' }}>
                  <h2 style={{ fontSize: 18, fontFamily: 'Space Mono, monospace', color: PALETTE.emerald, marginBottom: 20 }}>
                    Database Schema
                  </h2>
                  {schema?.tables?.map(t => (
                    <Card key={t.name} style={{ marginBottom: 14 }}>
                      <div style={{ fontSize: 14, fontFamily: 'Space Mono, monospace', color: PALETTE.sapphire, marginBottom: 10 }}>
                        📋 {t.name}
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                        {t.columns.map(c => (
                          <Tag key={c} color={PALETTE.textMuted}>{c}</Tag>
                        ))}
                      </div>
                    </Card>
                  ))}
                </div>
              </div>
            ) : (
              /* Chat view */
              <>
                {/* Messages */}
                <div style={{ flex: 1, overflowY: 'auto', padding: '24px', paddingBottom: 8 }}>
                  <div style={{ maxWidth: 820, margin: '0 auto' }}>
                    {messages.map(msg => <Message key={msg.id} msg={msg} />)}
                    {loading && (
                      <div style={{ display: 'flex', gap: 12, marginBottom: 20, alignItems: 'flex-start' }}>
                        <div style={{
                          width: 32, height: 32, borderRadius: 8, flexShrink: 0,
                          background: `linear-gradient(135deg, ${PALETTE.emerald}, ${PALETTE.sapphire})`,
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontSize: 12, fontWeight: 700, color: '#fff', fontFamily: 'Space Mono, monospace',
                        }}>AI</div>
                        <Card><Spinner /></Card>
                      </div>
                    )}
                    <div ref={bottomRef} />
                  </div>
                </div>

                {/* Suggestions */}
                {suggestions.length > 0 && messages.length <= 1 && (
                  <div style={{ padding: '0 24px 16px', maxWidth: 820, margin: '0 auto', width: '100%' }}>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      {suggestions.slice(0, 4).map((s, i) => (
                        <button key={i} onClick={() => sendMessage(s)} style={{
                          background: PALETTE.surfaceHigh, border: `1px solid ${PALETTE.border}`,
                          borderRadius: 8, padding: '7px 12px', color: PALETTE.textMuted,
                          fontSize: 12, cursor: 'pointer', fontFamily: 'Sora, sans-serif',
                          transition: 'all 0.15s',
                        }}
                          onMouseEnter={e => { e.currentTarget.style.borderColor = PALETTE.emerald; e.currentTarget.style.color = PALETTE.emerald; }}
                          onMouseLeave={e => { e.currentTarget.style.borderColor = PALETTE.border; e.currentTarget.style.color = PALETTE.textMuted; }}
                        >
                          {s}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Input */}
                <div style={{
                  padding: '16px 24px 20px', borderTop: `1px solid ${PALETTE.border}`,
                  background: `${PALETTE.surface}cc`, backdropFilter: 'blur(12px)',
                }}>
                  <div style={{ maxWidth: 820, margin: '0 auto', display: 'flex', gap: 10, alignItems: 'flex-end' }}>
                    {/* History toggle */}
                    <button onClick={() => setHistoryOpen(!historyOpen)} style={{
                      width: 42, height: 42, borderRadius: 8, flexShrink: 0,
                      background: historyOpen ? `${PALETTE.emerald}22` : PALETTE.surfaceHigh,
                      border: `1px solid ${historyOpen ? PALETTE.emerald : PALETTE.border}`,
                      cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 16, color: historyOpen ? PALETTE.emerald : PALETTE.textMuted,
                      transition: 'all 0.2s',
                    }}>☰</button>

                    {/* Textarea */}
                    <div style={{ flex: 1, position: 'relative' }}>
                      <textarea
                        ref={inputRef}
                        value={input}
                        onChange={e => setInput(e.target.value)}
                        onKeyDown={onKey}
                        placeholder="Ask anything about your blog analytics…"
                        rows={1}
                        style={{
                          width: '100%', background: PALETTE.surfaceHigh,
                          border: `1px solid ${input ? PALETTE.emerald + '66' : PALETTE.border}`,
                          borderRadius: 10, padding: '11px 16px', color: PALETTE.text,
                          fontSize: 14, fontFamily: 'Sora, sans-serif', resize: 'none',
                          outline: 'none', lineHeight: 1.5, transition: 'border-color 0.2s',
                          maxHeight: 120, overflowY: 'auto',
                        }}
                        onInput={e => {
                          e.target.style.height = 'auto';
                          e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
                        }}
                        onFocus={e => e.target.style.borderColor = `${PALETTE.emerald}66`}
                        onBlur={e => e.target.style.borderColor = PALETTE.border}
                        disabled={loading}
                      />
                    </div>

                    {/* Send */}
                    <button onClick={() => sendMessage()} disabled={!input.trim() || loading} style={{
                      width: 42, height: 42, borderRadius: 8, flexShrink: 0, border: 'none',
                      background: input.trim() && !loading
                        ? `linear-gradient(135deg, ${PALETTE.emerald}, ${PALETTE.sapphire})`
                        : PALETTE.surfaceHigh,
                      cursor: input.trim() && !loading ? 'pointer' : 'not-allowed',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 18, color: '#fff', transition: 'all 0.2s',
                      boxShadow: input.trim() && !loading ? `0 0 16px ${PALETTE.emerald}44` : 'none',
                    }}>↑</button>
                  </div>
                  <div style={{ maxWidth: 820, margin: '6px auto 0', fontSize: 11, color: PALETTE.textDim, fontFamily: 'Space Mono, monospace' }}>
                    Enter to send · Shift+Enter for newline · Demo mode {health?.supabase_connected ? '(DB connected)' : '(no DB — using demo data)'}
                  </div>
                </div>
              </>
            )}
          </main>
        </div>
      </div>
    </>
  );
}
