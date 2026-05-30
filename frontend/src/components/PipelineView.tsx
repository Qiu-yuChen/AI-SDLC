import { useState } from 'react';
import { CheckCircle, Loader, Circle, AlertCircle, Clock, RotateCcw, ChevronRight, Play } from 'lucide-react';
import { retryNode, executeNext } from '../api/client';
import type { NodeInfo, NodeStatus } from '../types';

interface Props {
  nodes: Record<string, NodeInfo>;
  currentNode: string | null;
  batchId: string;
  mode: 'auto' | 'manual';
  onRefresh: () => void;
}

const NODE_ORDER = ['概要设计', '代码生成', '单元测试'];
const NODE_ICONS: Record<string, string> = {
  概要设计: '📐',
  代码生成: '💻',
  单元测试: '🧪',
};

function StatusIcon({ status }: { status: NodeStatus }) {
  switch (status) {
    case 'completed':
      return <CheckCircle className="w-5 h-5" style={{ color: 'var(--accent)' }} />;
    case 'running':
      return <Loader className="w-5 h-5 animate-spin" style={{ color: 'var(--accent)' }} />;
    case 'failed':
      return <AlertCircle className="w-5 h-5" style={{ color: '#ef4444' }} />;
    default:
      return <Circle className="w-5 h-5" style={{ color: '#d1d5db' }} />;
  }
}

function QualityBar({ score }: { score: number | null }) {
  if (score === null || score === undefined) return null;
  const level = score >= 80 ? '#10a37f' : score >= 60 ? '#f59e0b' : '#ef4444';
  return (
    <div className="mt-2 w-full">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>质量</span>
        <span className="text-xs font-semibold" style={{ color: level }}>{Math.round(score)}/100</span>
      </div>
      <div className="quality-bar">
        <div className="quality-bar-fill" style={{ width: `${Math.min(score, 100)}%`, background: `linear-gradient(90deg, ${level}, ${level}88)` }} />
      </div>
    </div>
  );
}

export function PipelineView({ nodes, currentNode, batchId, mode, onRefresh }: Props) {
  const [retrying, setRetrying] = useState<string | null>(null);
  const [stepping, setStepping] = useState(false);

  async function handleRetry(nodeId: string) {
    setRetrying(nodeId);
    try {
      await retryNode(batchId, nodeId);
      onRefresh();
    } catch (e) {
      console.error('Retry failed:', e);
    } finally {
      setRetrying(null);
    }
  }

  async function handleNextStep() {
    setStepping(true);
    try {
      await executeNext(batchId);
      onRefresh();
    } catch (e) {
      console.error('Next step failed:', e);
    } finally {
      setStepping(false);
    }
  }

  const allCompleted = NODE_ORDER.every((n) => nodes[n]?.status === 'completed');
  const hasFailed = NODE_ORDER.some((n) => nodes[n]?.status === 'failed');

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold">执行流水线</h3>
        <div className="flex items-center gap-3">
          {mode === 'manual' && !allCompleted && (
            <button
              onClick={handleNextStep}
              disabled={stepping}
              className="btn btn-primary text-sm"
            >
              <Play className="w-4 h-4" />
              {stepping ? '执行中...' : '执行下一步'}
            </button>
          )}
          <span className="text-xs px-2 py-0.5 rounded-full" style={{
            background: mode === 'auto' ? '#d1fae5' : '#fef3c7',
            color: mode === 'auto' ? '#065f46' : '#92400e',
          }}>
            {mode === 'auto' ? '自动模式' : '手动模式'}
          </span>
        </div>
      </div>

      <div className="flex items-start justify-center gap-0 flex-wrap">
        {NODE_ORDER.map((nodeId, idx) => {
          const node = nodes[nodeId];
          const isRunning = node?.status === 'running';
          const isCompleted = node?.status === 'completed';
          const isFailed = node?.status === 'failed';

          return (
            <div key={nodeId} className="flex items-start relative">
              <div
                className={`relative flex flex-col items-center p-5 rounded-xl border-2 min-w-[200px] transition-all card-interactive ${
                  isRunning
                    ? 'node-running bg-green-50/30'
                    : isCompleted
                    ? 'border-green-200 bg-green-50/10'
                    : isFailed
                    ? 'border-red-300 bg-red-50/30'
                    : 'border-gray-700 bg-gray-900/50'
                }`}
              >
                <span className="text-2xl mb-2">{NODE_ICONS[nodeId]}</span>
                <span className="font-semibold text-sm">{nodeId}</span>

                <div className="mt-2">
                  <StatusIcon status={node?.status || 'pending'} />
                </div>

                <span className="text-xs mt-2 font-medium" style={{
                  color: isRunning ? 'var(--accent)' :
                    isCompleted ? '#059669' :
                    isFailed ? '#ef4444' :
                    'var(--text-muted)',
                }}>
                  {isRunning ? '执行中...' :
                   isCompleted ? `完成 (${node?.duration_seconds?.toFixed(1)}s)` :
                   isFailed ? '失败' :
                   '等待中'}
                </span>

                <QualityBar score={node?.quality_score ?? null} />

                {isCompleted && node?.output_files?.length > 0 && (
                  <span className="text-xs mt-2" style={{ color: 'var(--text-muted)' }}>
                    {node.output_files.length} 个文件
                  </span>
                )}

                {isFailed && (
                  <div className="mt-2 space-y-2 w-full">
                    {node?.error && (
                      <div
                        className="p-2 rounded text-xs truncate max-w-[180px]"
                        style={{ background: 'rgba(239,68,68,0.12)', color: '#f87171', border: '1px solid rgba(239,68,68,0.25)' }}
                        title={node.error}
                      >
                        {node.error.substring(0, 60)}
                      </div>
                    )}
                    <button
                      onClick={() => handleRetry(nodeId)}
                      disabled={retrying === nodeId}
                      className="btn btn-danger text-xs w-full py-1.5"
                    >
                      <RotateCcw className={`w-3 h-3 ${retrying === nodeId ? 'animate-spin' : ''}`} />
                      {retrying === nodeId ? '重试中...' : '重试'}
                    </button>
                  </div>
                )}
              </div>

              {idx < NODE_ORDER.length - 1 && (
                <div className="flex items-center mx-1 pt-8">
                  <div
                    className="h-0.5 w-10 rounded"
                    style={{ background: isCompleted ? 'var(--accent)' : '#e5e5e5' }}
                  />
                  <ChevronRight
                    className="w-4 h-4"
                    style={{ color: isCompleted ? 'var(--accent)' : '#d1d5db' }}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {allCompleted && (
        <div className="mt-6 p-4 rounded-lg text-center animate-in" style={{ background: 'rgba(16,163,127,0.15)', color: '#6ee7b7' }}>
          <CheckCircle className="w-6 h-6 mx-auto mb-2" />
          <span className="font-semibold">全部节点已完成</span>
        </div>
      )}
    </div>
  );
}
