import { useState, useEffect } from 'react';
import { Sparkles, Play, StepForward, RefreshCw, FolderOpen, Plus, Search, PanelLeftClose, PanelLeft, Zap } from 'lucide-react';
import { BatchCreator } from './components/BatchCreator';
import { PipelineView } from './components/PipelineView';
import { ReActLog } from './components/ReActLog';
import { FilePreview } from './components/FilePreview';
import { PromptOptimizer } from './components/PromptOptimizer';
import { listBatches, getBatch, createBatch, uploadSpec, startBatch } from './api/client';
import type { BatchListItem, BatchStatus } from './types';

type View = 'create' | 'monitor';

export default function App() {
  const [view, setView] = useState<View>('create');
  const [batches, setBatches] = useState<BatchListItem[]>([]);
  const [activeBatchId, setActiveBatchId] = useState<string | null>(null);
  const [activeBatch, setActiveBatch] = useState<BatchStatus | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [batchSearch, setBatchSearch] = useState('');
  const [showPromptOptimizer, setShowPromptOptimizer] = useState(false);

  useEffect(() => {
    loadBatches();
    const interval = setInterval(loadBatches, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!activeBatchId) return;
    refreshBatch();
    const interval = setInterval(refreshBatch, 2000);
    return () => clearInterval(interval);
  }, [activeBatchId]);

  async function loadBatches() {
    try {
      const list = await listBatches();
      setBatches(list);
    } catch { /* backend not ready */ }
  }

  async function refreshBatch() {
    if (!activeBatchId) return;
    try {
      const batch = await getBatch(activeBatchId);
      setActiveBatch(batch);
    } catch { /* ignore */ }
  }

  function handleBatchCreated(batchId: string) {
    setActiveBatchId(batchId);
    setView('monitor');
    loadBatches();
  }

  function handleSelectBatch(batchId: string) {
    setActiveBatchId(batchId);
    setView('monitor');
  }

  const [importingSpec, setImportingSpec] = useState(false);

  async function handleImportSpec(spec: string) {
    setShowPromptOptimizer(false);
    setImportingSpec(true);
    try {
      const blob = new Blob([spec], { type: 'text/markdown' });
      const textFile = new File([blob], `ai_spec_${Date.now()}.md`, { type: 'text/markdown' });
      const uploadResult = await uploadSpec(textFile);
      const batch = await createBatch(uploadResult.filename, 'AI 生成规格书');
      await startBatch(batch.batch_id);
      handleBatchCreated(batch.batch_id);
    } catch (e: any) {
      console.error('Import failed:', e);
    } finally {
      setImportingSpec(false);
    }
  }

  const filteredBatches = batches.filter((b) => {
    if (!batchSearch) return true;
    const s = batchSearch.toLowerCase();
    return b.project_name.toLowerCase().includes(s) || b.batch_id.toLowerCase().includes(s);
  });

  return (
    <div className="flex h-screen" style={{ background: 'var(--main-secondary)' }}>
      {/* Sidebar */}
      <div className={`sidebar flex-shrink-0 ${sidebarCollapsed ? 'hidden' : ''}`}>
        <div className="p-4 border-b" style={{ borderColor: 'var(--sidebar-hover)' }}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Zap className="w-5 h-5" style={{ color: 'var(--accent)' }} />
              <h1 className="text-base font-bold tracking-tight">
                AI-<span style={{ color: 'var(--accent)' }}>SDLC</span>
              </h1>
            </div>
            <button
              onClick={() => setSidebarCollapsed(true)}
              className="p-1 rounded hover:bg-[var(--sidebar-hover)] transition"
            >
              <PanelLeftClose className="w-4 h-4" style={{ color: '#a0a0a0' }} />
            </button>
          </div>
        </div>

        <div className="p-3">
          <button
            onClick={() => { setView('create'); setActiveBatchId(null); }}
            className="btn w-full mb-3 text-sm"
            style={{
              background: 'var(--sidebar-hover)',
              color: '#ececec',
              border: '1px solid var(--sidebar-active)',
            }}
          >
            <Plus className="w-4 h-4" />
            新建批次
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

        <div className="flex-1 overflow-y-auto px-2">
          <div className="px-3 py-2">
            <span className="text-xs font-medium uppercase tracking-wider" style={{ color: '#808080' }}>历史批次</span>
          </div>
          <div className="space-y-0.5">
            {filteredBatches.map((b) => (
              <button
                key={b.batch_id}
                onClick={() => handleSelectBatch(b.batch_id)}
                className="w-full text-left px-3 py-2.5 rounded-lg transition text-sm"
                style={{
                  background: activeBatchId === b.batch_id ? 'var(--sidebar-active)' : 'transparent',
                  color: activeBatchId === b.batch_id ? '#fff' : '#c0c0c0',
                }}
              >
                <div className="truncate font-medium">{b.project_name}</div>
                <div className="flex items-center justify-between mt-0.5">
                  <span className="text-xs truncate max-w-[140px]" style={{ color: '#707070' }}>
                    {b.batch_id.split('_').slice(-1)}
                  </span>
                  <span
                    className="text-xs px-1.5 py-0.5 rounded-full"
                    style={{
                      background:
                        b.status === 'completed' ? 'rgba(16,163,127,0.2)' :
                        b.status === 'running' ? 'rgba(59,130,246,0.2)' :
                        b.status === 'failed' ? 'rgba(239,68,68,0.2)' :
                        'rgba(128,128,128,0.2)',
                      color:
                        b.status === 'completed' ? '#10a37f' :
                        b.status === 'running' ? '#3b82f6' :
                        b.status === 'failed' ? '#ef4444' :
                        '#a0a0a0',
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
        <div className="flex-shrink-0 p-3" style={{ background: 'var(--sidebar-bg)' }}>
          <button
            onClick={() => setSidebarCollapsed(false)}
            className="p-2 rounded hover:bg-[var(--sidebar-hover)] transition"
          >
            <PanelLeft className="w-4 h-4" style={{ color: '#a0a0a0' }} />
          </button>
        </div>
      )}

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Bar */}
        {activeBatch && view === 'monitor' && (
          <div
            className="px-6 py-3 border-b flex items-center justify-between"
            style={{ background: 'var(--main-bg)', borderColor: 'var(--border)' }}
          >
            <div>
              <h2 className="font-semibold">
                {activeBatch.project_name}
                <span className="ml-2 text-xs px-2 py-0.5 rounded-full font-mono" style={{ background: 'var(--main-secondary)', color: 'var(--text-muted)' }}>
                  {activeBatch.batch_id}
                </span>
              </h2>
              <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
                规格书: {activeBatch.spec_file} · 状态: {activeBatch.status}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => { setActiveBatchId(null); setView('create'); }}
                className="btn text-sm"
              >
                <Plus className="w-3.5 h-3.5" />
                新建
              </button>
              {activeBatch.status === 'completed' && (
                <span className="text-sm font-medium" style={{ color: 'var(--accent)' }}>全部完成</span>
              )}
              {activeBatch.status === 'failed' && (
                <span className="text-sm font-medium" style={{ color: '#ef4444' }}>执行失败</span>
              )}
              {activeBatch.status === 'running' && (
                <span className="text-sm font-medium animate-pulse" style={{ color: 'var(--accent)' }}>运行中</span>
              )}
            </div>
          </div>
        )}

        {/* Main Content Area */}
        <main className="flex-1 overflow-y-auto p-6">
          {view === 'create' && (
            <BatchCreator
              onCreated={handleBatchCreated}
              batches={batches}
              onSelectBatch={handleSelectBatch}
              onOpenOptimizer={() => setShowPromptOptimizer(true)}
              importedSpec={''}
              onClearImportedSpec={() => {}}
            />
          )}

          {view === 'monitor' && activeBatchId && activeBatch && (
            <div className="space-y-6">
              <PipelineView
                nodes={activeBatch.nodes}
                currentNode={activeBatch.current_node}
                batchId={activeBatchId}
                mode={activeBatch.mode}
                onRefresh={refreshBatch}
              />
              <ReActLog batchId={activeBatchId} batchStatus={activeBatch.status} />
              <FilePreview
                batchId={activeBatchId}
                nodes={activeBatch.nodes}
                wsHost={window.location.host}
              />
            </div>
          )}

          {view === 'monitor' && !activeBatchId && (
            <div className="text-center py-20">
              <FolderOpen className="w-16 h-16 mx-auto mb-4" style={{ color: '#d1d5db' }} />
              <h3 className="text-xl font-semibold mb-2" style={{ color: 'var(--text-secondary)' }}>选择一个批次</h3>
              <p style={{ color: 'var(--text-muted)' }}>从左侧列表中选择已创建的批次查看执行详情</p>
            </div>
          )}
        </main>
      </div>

      {/* Prompt Optimizer Modal */}
      {showPromptOptimizer && (
        <PromptOptimizer
          onImport={handleImportSpec}
          onClose={() => setShowPromptOptimizer(false)}
        />
      )}
    </div>
  );
}
