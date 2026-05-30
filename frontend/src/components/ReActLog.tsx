import { useState, useEffect, useRef } from 'react';
import { Brain, Wrench, Eye, Terminal } from 'lucide-react';
import { connectWs } from '../api/client';
import type { ReActStep, WsEvent } from '../types';

interface LogEntry {
  id: number;
  type: 'thought' | 'action' | 'observation' | 'system';
  agent?: string;
  content: string;
  timestamp: string;
}

interface Props {
  batchId: string;
}

export function ReActLog({ batchId }: Props) {
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [collapsed, setCollapsed] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);
  const idCounter = useRef(0);

  useEffect(() => {
    const ws = connectWs(
      batchId,
      (event: WsEvent) => {
        idCounter.current += 1;
        const now = new Date().toLocaleTimeString();

        switch (event.type) {
          case 'node_start':
            setEntries((prev) => [
              ...prev,
              {
                id: idCounter.current,
                type: 'system',
                agent: event.name,
                content: `开始执行: ${event.name}`,
                timestamp: now,
              },
            ]);
            break;

          case 'react_step':
            if (event.step?.thought) {
              setEntries((prev) => [
                ...prev,
                {
                  id: idCounter.current,
                  type: 'thought',
                  agent: event.name,
                  content: event.step!.thought!,
                  timestamp: now,
                },
              ]);
            }
            if (event.step?.action) {
              setEntries((prev) => [
                ...prev,
                {
                  id: idCounter.current,
                  type: 'action',
                  agent: event.name,
                  content: `调用工具: ${event.step!.action}(${event.step!.action_input || ''})`,
                  timestamp: now,
                },
              ]);
            }
            if (event.step?.observation) {
              setEntries((prev) => [
                ...prev,
                {
                  id: idCounter.current,
                  type: 'observation',
                  agent: event.name,
                  content: event.step!.observation!,
                  timestamp: now,
                },
              ]);
            }
            break;

          case 'node_completed':
            setEntries((prev) => [
              ...prev,
              {
                id: idCounter.current,
                type: 'system',
                agent: event.name,
                content: `完成: ${event.name} (${event.duration_seconds?.toFixed(1)}s)`,
                timestamp: now,
              },
            ]);
            break;

          case 'node_failed':
            setEntries((prev) => [
              ...prev,
              {
                id: idCounter.current,
                type: 'system',
                agent: event.name,
                content: `失败: ${event.name} — ${event.error || '未知错误'}`,
                timestamp: now,
              },
            ]);
            break;
        }
      },
      () => {
        setEntries((prev) => [
          ...prev,
          {
            id: idCounter.current + 1,
            type: 'system',
            content: 'WebSocket 连接已关闭',
            timestamp: new Date().toLocaleTimeString(),
          },
        ]);
      }
    );

    return () => ws.close();
  }, [batchId]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [entries]);

  function entryIcon(type: string) {
    switch (type) {
      case 'thought': return <Brain className="w-4 h-4" style={{ color: '#8b5cf6' }} />;
      case 'action': return <Wrench className="w-4 h-4" style={{ color: '#f59e0b' }} />;
      case 'observation': return <Eye className="w-4 h-4" style={{ color: '#06b6d4' }} />;
      default: return <Terminal className="w-4 h-4" style={{ color: 'var(--text-muted)' }} />;
    }
  }

  function entryColor(type: string) {
    switch (type) {
      case 'thought': return '#7c3aed';
      case 'action': return '#d97706';
      case 'observation': return '#0891b2';
      default: return 'var(--text-secondary)';
    }
  }

  return (
    <div className="card overflow-hidden" style={{ background: '#1e1e2e', borderColor: '#2d2d3d' }}>
      <div
        className="flex items-center justify-between px-4 py-3 cursor-pointer"
        style={{ background: '#16162a' }}
        onClick={() => setCollapsed(!collapsed)}
      >
        <div className="flex items-center gap-2">
          <Brain className="w-4 h-4" style={{ color: '#8b5cf6' }} />
          <h3 className="font-semibold text-sm" style={{ color: '#e0e0e0' }}>ReAct 思考日志</h3>
          <span className="text-xs" style={{ color: '#6b7280' }}>({entries.length})</span>
        </div>
        <span className="text-xs" style={{ color: '#6b7280' }}>{collapsed ? '展开' : '收起'}</span>
      </div>

      {!collapsed && (
        <div className="p-4 max-h-96 overflow-y-auto font-mono text-sm leading-relaxed">
          {entries.length === 0 && (
            <p className="text-center py-8" style={{ color: '#6b7280' }}>
              等待 Agent 开始执行...
            </p>
          )}

          {entries.map((entry) => (
            <div key={entry.id} className="react-entry mb-2 flex gap-2">
              <span className="shrink-0 text-xs mt-0.5" style={{ color: '#6b7280' }}>
                {entry.timestamp}
              </span>
              <span className="shrink-0 mt-0.5">
                {entryIcon(entry.type)}
              </span>
              <span style={{ color: entryColor(entry.type) }}>
                {entry.agent && (
                  <span className="mr-1" style={{ color: '#9ca3af' }}>[{entry.agent}]</span>
                )}
                {entry.content}
              </span>
            </div>
          ))}
          <div ref={logEndRef} />
        </div>
      )}
    </div>
  );
}
