import { useState, useEffect } from 'react';
import { Plus, Search, PanelLeftClose, PanelLeft, Zap, Sparkles, Sun, Moon } from 'lucide-react';
import { ChatView } from './components/ChatView';
import { PromptOptimizer } from './components/PromptOptimizer';
import { listBatches } from './api/client';
import type { BatchListItem } from './types';

type Theme = 'light' | 'dark';

function getInitialTheme(): Theme {
  const stored = localStorage.getItem('theme');
  if (stored === 'light' || stored === 'dark') return stored;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export default function App() {
  const [batches, setBatches] = useState<BatchListItem[]>([]);
  const [activeBatchId, setActiveBatchId] = useState<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [batchSearch, setBatchSearch] = useState('');
  const [showOptimizer, setShowOptimizer] = useState(false);
  const [importSpec, setImportSpec] = useState<string | null>(null);
  const [theme, setTheme] = useState<Theme>(getInitialTheme);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  function toggleTheme() {
    setTheme((t) => t === 'light' ? 'dark' : 'light');
  }

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
    <div className="flex h-screen" style={{ background: 'var(--main-bg)' }}>
      {/* Sidebar */}
      <div className={`sidebar flex-shrink-0 ${sidebarCollapsed ? 'hidden' : ''}`}>
        <div className="p-4 border-b" style={{ borderColor: 'var(--border)' }}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Zap className="w-5 h-5" style={{ color: 'var(--accent)' }} />
              <h1 className="text-base font-semibold tracking-tight" style={{ color: 'var(--text-primary)' }}>
                AI-<span style={{ color: 'var(--accent)' }}>SDLC</span>
              </h1>
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={toggleTheme}
                className="sidebar-icon-btn"
                title={theme === 'light' ? '切换暗色模式' : '切换亮色模式'}
              >
                {theme === 'light' ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
              </button>
              <button
                onClick={() => setSidebarCollapsed(true)}
                className="sidebar-icon-btn"
                title="收起侧边栏"
              >
                <PanelLeftClose className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        <div className="p-3">
          <button
            onClick={handleNewChat}
            className="btn w-full mb-2 text-sm"
            style={{
              background: 'transparent',
              color: 'var(--text-primary)',
              border: 'none',
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
              border: 'none',
            }}
          >
            <Sparkles className="w-4 h-4" />
            一句话生成规格书
          </button>

          <div className="relative mb-3">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-muted)' }} />
            <input
              type="text"
              value={batchSearch}
              onChange={(e) => setBatchSearch(e.target.value)}
              placeholder="搜索批次..."
              className="input text-sm pl-8 py-2"
              style={{ background: 'var(--sidebar-hover)', border: 'none', color: 'var(--text-primary)' }}
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-2">
          <div className="px-3 py-2">
            <span className="text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>历史会话</span>
          </div>
          <div className="space-y-0.5">
            {filteredBatches.map((b) => (
              <button
                key={b.batch_id}
                onClick={() => handleSelectBatch(b.batch_id)}
                className="w-full text-left px-3 py-2.5 rounded-lg transition text-sm"
                style={{
                  background: activeBatchId === b.batch_id ? 'var(--sidebar-active)' : 'transparent',
                  color: activeBatchId === b.batch_id ? 'var(--text-primary)' : 'var(--text-secondary)',
                }}
              >
                <div className="truncate font-medium">{b.project_name}</div>
                <div className="flex items-center justify-between mt-0.5">
                  <span className="text-xs truncate max-w-[140px]" style={{ color: 'var(--text-muted)' }}>
                    {b.batch_id.split('_').slice(-1)}
                  </span>
                  <span
                    className="text-xs px-1.5 py-0.5 rounded-full"
                    style={{
                      background:
                        b.status === 'completed' ? 'rgba(16,163,127,0.2)' :
                        b.status === 'running' ? 'rgba(59,130,246,0.2)' :
                        b.status === 'stopped' ? 'rgba(245,158,11,0.2)' :
                        b.status === 'failed' ? 'rgba(239,68,68,0.2)' :
                        'rgba(128,128,128,0.2)',
                      color:
                        b.status === 'completed' ? '#10a37f' :
                        b.status === 'running' ? '#3b82f6' :
                        b.status === 'stopped' ? '#f59e0b' :
                        b.status === 'failed' ? '#ef4444' :
                        '#888',
                    }}
                  >
                    {b.status}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Collapsed sidebar toggle */}
      {sidebarCollapsed && (
        <div className="flex-shrink-0 p-2 flex flex-col items-center gap-2" style={{ background: 'var(--sidebar-bg)', borderRight: '1px solid var(--border)' }}>
          <button
            onClick={() => setSidebarCollapsed(false)}
            className="sidebar-icon-btn"
            title="展开侧边栏"
          >
            <PanelLeft className="w-4 h-4" />
          </button>
          <button
            onClick={toggleTheme}
            className="sidebar-icon-btn"
            title={theme === 'light' ? '切换暗色模式' : '切换亮色模式'}
          >
            {theme === 'light' ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
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
