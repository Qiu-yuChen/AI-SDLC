import { useState, useEffect } from 'react';
import { Plus, Search, PanelLeftClose, PanelLeft, Sparkles, Sun, Moon, Trash2, Archive } from 'lucide-react';
import { ChatView } from './components/ChatView';
import { PromptOptimizer } from './components/PromptOptimizer';
import { listBatches, deleteBatch } from './api/client';
import type { BatchListItem } from './types';

export default function App() {
  const [batches, setBatches] = useState<BatchListItem[]>([]);
  const [activeBatchId, setActiveBatchId] = useState<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [batchSearch, setBatchSearch] = useState('');
  const [showOptimizer, setShowOptimizer] = useState(false);
  const [importSpec, setImportSpec] = useState<string | null>(null);

  type Theme = 'light' | 'dark';
  const [theme, setTheme] = useState<Theme>(() => {
    const stored = localStorage.getItem('theme');
    if (stored === 'light' || stored === 'dark') return stored;
    return 'dark';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  useEffect(() => {
    loadBatches();
    const interval = setInterval(loadBatches, 5000);
    return () => clearInterval(interval);
  }, []);

  async function loadBatches() {
    try {
      const list = await listBatches();
      setBatches(list);
    } catch { /* backend not ready */ }
  }

  function handleSelectBatch(batchId: string) {
    setActiveBatchId(batchId);
  }

  function handleBatchCreated(batchId: string) {
    setActiveBatchId(batchId);
    loadBatches();
  }

  function handleNewChat() {
    setActiveBatchId(null);
    setImportSpec(null);
  }

  function handleImportSpec(spec: string) {
    setImportSpec(spec);
    setShowOptimizer(false);
  }

  const filteredBatches = batches.filter((b) => {
    if (!batchSearch) return true;
    const s = batchSearch.toLowerCase();
    return b.project_name.toLowerCase().includes(s) || b.batch_id.toLowerCase().includes(s);
  });

  return (
    <div className="flex h-screen" style={{ background: 'var(--main-secondary)' }}>
      {/* Sidebar */}
      {!sidebarCollapsed && (
        <div className="sidebar flex-shrink-0">
        <div className="p-4 border-b" style={{ borderColor: 'var(--sidebar-hover)' }}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <svg className="w-5 h-5" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg" style={{ color: 'var(--accent)' }}>
                <path d="M469.333333 42.666667v42.666666H298.666667a128 128 0 0 0-128 128v128a213.333333 213.333333 0 0 0 213.333333 213.333334h256a213.333333 213.333333 0 0 0 213.333333-213.333334V213.333333a128 128 0 0 0-128-128h-170.666666V42.666667h-85.333334zM256 213.333333a42.666667 42.666667 0 0 1 42.666667-42.666666h426.666666a42.666667 42.666667 0 0 1 42.666667 42.666666v128a128 128 0 0 1-128 128H384a128 128 0 0 1-128-128V213.333333z m149.333333 170.666667a64 64 0 1 0 0-128 64 64 0 0 0 0 128z m213.333334 0a64 64 0 1 0 0-128 64 64 0 0 0 0 128zM256 938.666667a256 256 0 0 1 512 0h85.333333a341.333333 341.333333 0 1 0-682.666666 0h85.333333z" fill="currentColor" />
              </svg>
              <h1
                className="text-base font-bold tracking-widest"
                style={{
                  fontFamily: 'Orbitron, sans-serif',
                  letterSpacing: '0.15em',
                  textShadow: '0 0 10px rgba(16, 163, 127, 0.35)',
                }}
              >
                SDLC
              </h1>
            </div>
            <button
              onClick={() => setTheme(t => t === 'light' ? 'dark' : 'light')}
              className="p-1 rounded hover:bg-[var(--sidebar-hover)] transition"
              title={theme === 'light' ? '切换暗色模式' : '切换亮色模式'}
          >
            {theme === 'light' ? <Moon className="w-4 h-4" style={{ color: 'var(--text-muted)' }} /> : <Sun className="w-4 h-4" style={{ color: 'var(--text-muted)' }} />}
            </button>
            <button
              onClick={() => setSidebarCollapsed(true)}
              className="p-1 rounded hover:bg-[var(--sidebar-hover)] transition"
            >
              <PanelLeftClose className="w-4 h-4" style={{ color: 'var(--text-muted)' }} />
            </button>
          </div>
        </div>

        <div className="p-3">
          <button
            onClick={handleNewChat}
            className="btn w-full mb-2 text-sm"
            style={{
              background: 'var(--sidebar-hover)',
              color: '#ececec',
              border: '1px solid var(--sidebar-active)',
            }}
          >
            <Plus className="w-4 h-4" />
            新建对话
          </button>
          <button
            onClick={() => setShowOptimizer(true)}
            className="btn w-full mb-3 text-sm"
            style={{
              background: 'transparent',
              color: 'var(--accent)',
              border: '1px solid var(--accent)',
            }}
          >
            <Sparkles className="w-4 h-4" />
            一句话生成规格书
          </button>

          <div className="relative mb-3">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2" style={{ color: '#808080' }} />
            <input
              type="text"
              value={batchSearch}
              onChange={(e) => setBatchSearch(e.target.value)}
              placeholder="搜索批次..."
              className="input text-sm pl-8 py-2"
              style={{ background: 'var(--sidebar-hover)', border: '1px solid var(--sidebar-active)', color: '#ececec' }}
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-2 sidebar-scroll">
          <div className="px-3 py-2">
            <span className="text-xs font-medium uppercase tracking-wider" style={{ color: '#808080' }}>历史会话</span>
          </div>
          <div className="space-y-0.5">
            {(() => {
              const now = Date.now();
              const DAY = 86400000;
              const WEEK = 7 * DAY;
              const MONTH = 30 * DAY;

              const groups: { label: string; batches: typeof filteredBatches }[] = [
                { label: '今天', batches: [] },
                { label: '本周', batches: [] },
                { label: '本月', batches: [] },
                { label: '更早', batches: [] },
              ];

              filteredBatches.forEach((b) => {
                const age = now - new Date(b.created_at).getTime();
                if (age < DAY) groups[0].batches.push(b);
                else if (age < WEEK) groups[1].batches.push(b);
                else if (age < MONTH) groups[2].batches.push(b);
                else groups[3].batches.push(b);
              });

              return groups.filter(g => g.batches.length > 0).map((group) => (
                <div key={group.label}>
                  <div className="px-3 pt-3 pb-1 font-semibold uppercase opacity-70 sidebar-group-header" style={{ letterSpacing: '0.05em' }}>
                    {group.label}
                  </div>
                  {group.batches.map((b) => (
                  <div key={b.batch_id} className="group relative">
                <button
                  onClick={() => handleSelectBatch(b.batch_id)}
                  className="w-full text-left px-3 py-2.5 rounded-lg transition text-sm"
                  style={{
                    background: activeBatchId === b.batch_id ? 'var(--sidebar-active)' : 'transparent',
                    color: activeBatchId === b.batch_id ? '#fff' : '#c0c0c0',
                  }}
                >
                  <div className="truncate font-medium">{b.project_name}</div>
                  <div className="flex items-center justify-between mt-0.5">
                    <span className="text-xs truncate max-w-[120px]" style={{ color: '#707070' }}>
                      {new Date(b.created_at).toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })}
                    </span>
                    <span className="text-xs px-1.5 py-0.5 rounded-full" style={{
                      background: b.status === 'completed' ? 'rgba(16,163,127,0.2)' : b.status === 'running' ? 'rgba(59,130,246,0.2)' :
                        b.status === 'stopped' ? 'rgba(245,158,11,0.2)' : b.status === 'failed' ? 'rgba(239,68,68,0.2)' : 'rgba(128,128,128,0.2)',
                      color: b.status === 'completed' ? '#10a37f' : b.status === 'running' ? '#3b82f6' :
                        b.status === 'stopped' ? '#f59e0b' : b.status === 'failed' ? '#ef4444' : '#a0a0a0',
                    }}>{b.status}</span>
                  </div>
                </button>
                <button
                  onClick={async (e) => { e.stopPropagation(); await deleteBatch(b.batch_id); loadBatches(); }}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded opacity-0 group-hover:opacity-100 transition"
                  style={{ color: 'var(--text-muted)' }}
                  title="删除"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
                  ))}
                </div>
              ));
            })()}
        </div>
      </div>
      </div>
      )}

      {/* Collapsed sidebar toggle */}
      {sidebarCollapsed && (
        <div className="flex-shrink-0 flex flex-col items-center py-3 gap-2" style={{ background: 'var(--sidebar-bg)', width: 48 }}>
          <button
            onClick={() => setSidebarCollapsed(false)}
            className="p-2 rounded hover:bg-[var(--sidebar-hover)] transition"
          >
            <PanelLeft className="w-4 h-4" style={{ color: '#a0a0a0' }} />
          </button>
        </div>
      )}

      {/* Chat Main */}
      <div className="flex-1 flex flex-col min-w-0">
        <ChatView batchId={activeBatchId} onBatchCreated={handleBatchCreated} importSpec={importSpec} onSpecConsumed={() => setImportSpec(null)} />
      </div>

      {showOptimizer && (
        <PromptOptimizer onImport={handleImportSpec} onClose={() => setShowOptimizer(false)} />
      )}
    </div>
  );
}
