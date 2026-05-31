import { useState, useEffect, useRef } from 'react';
import { Brain, Wrench, Eye, Terminal, Activity } from 'lucide-react';
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
  batchStatus?: string;
}

export function ReActLog({ batchId, batchStatus }: Props) {
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [collapsed, setCollapsed] = useState(false);
  const [connected, setConnected] = useState(false);
  const [retryCount, setRetryCount] = useState(0);
  const logEndRef = useRef<HTMLDivElement>(null);
  const idCounter = useRef(0);
  const mountedRef = useRef(true);
  const retryRef = useRef(0);

  const isActive = batchStatus === 'created' || batchStatus === 'running';

  useEffect(() => {
    mountedRef.current = true;
    retryRef.current = 0;
    setRetryCount(0);
    setConnected(false);
    let reconnectTimer: ReturnType<typeof setTimeout>;
    let ws: WebSocket;
    let reconnectScheduled = false;

    function scheduleReconnect() {
      if (!isActive || !mountedRef.current || reconnectScheduled) return;
      reconnectScheduled = true;
      const delay = Math.min(1000 * Math.pow(2, retryRef.current), 30000);
      retryRef.current += 1;
      setRetryCount(retryRef.current);
      reconnectTimer = setTimeout(() => {
        reconnectScheduled = false;
        connect();
      }, delay);
    }

    function connect() {
      if (!mountedRef.current) return;

      ws = connectWs(
        batchId,
        (event: WsEvent) => {
          if (!mountedRef.current) return;
          retryRef.current = 0;
          idCounter.current += 1;
          const now = new Date().toLocaleTimeString();

          switch (event.type) {
            case 'node_start':
              setEntries((prev) => [
                ...prev,
                { id: idCounter.current, type: 'system', agent: event.name,
                  content: `开始执行: ${event.name}`, timestamp: now },
              ]);
              break;

            case 'react_step':
              if (event.step?.thought) {
                setEntries((prev) => [
                  ...prev,
                  { id: idCounter.current, type: 'thought', agent: event.name,
                    content: event.step!.thought!, timestamp: now },
                ]);
              }
              if (event.step?.action) {
                setEntries((prev) => [
                  ...prev,
                  { id: idCounter.current, type: 'action', agent: event.name,
                    content: `调用: ${event.step!.action}(${event.step!.action_input || ''})`, timestamp: now },
                ]);
              }
              if (event.step?.observation) {
                const obs = event.step!.observation!;
                setEntries((prev) => [
                  ...prev,
                  { id: idCounter.current, type: 'observation', agent: event.name,
                    content: obs.length > 300 ? obs.substring(0, 300) + '...' : obs, timestamp: now },
                ]);
              }
              break;

            case 'node_completed':
              setEntries((prev) => [
                ...prev,
                { id: idCounter.current, type: 'system', agent: event.name,
                  content: `完成: ${event.name} (${event.duration_seconds?.toFixed(1)}s)`, timestamp: now },
              ]);
              break;

            case 'node_failed':
              setEntries((prev) => [
                ...prev,
                { id: idCounter.current, type: 'system', agent: event.name,
                  content: `失败: ${event.name} — ${event.error || '未知错误'}`, timestamp: now },
              ]);
              break;
          }
        },
        () => {
          if (!mountedRef.current) return;
          setConnected(false);
          if (isActive) {
            scheduleReconnect();
          }
        }
      );

      ws.addEventListener('open', () => {
        if (mountedRef.current) {
          setConnected(true);
          setRetryCount(0);
          retryRef.current = 0;
        }
      });
    }

    connect();

    return () => {
      mountedRef.current = false;
      clearTimeout(reconnectTimer);
      if (ws) ws.close();
    };
  }, [batchId, isActive]);

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

  const activeEntryCount = entries.filter(e => e.type !== 'system').length;

  return (
    <div className="card overflow-hidden" style={{ background: '#1f1f1f', borderColor: '#2a2a2a' }}>
      <div
        className="flex items-center justify-between px-4 py-3 cursor-pointer"
        style={{ background: '#171717' }}
        onClick={() => setCollapsed(!collapsed)}
      >
        <div className="flex items-center gap-2">
          <Brain className="w-4 h-4" style={{ color: '#8b5cf6' }} />
          <h3 className="font-semibold text-sm" style={{ color: '#e0e0e0' }}>
            ReAct 思考日志
          </h3>
          {connected && isActive && (
            <Activity className="w-3.5 h-3.5" style={{ color: '#10a37f' }} />
          )}
          {activeEntryCount > 0 && (
            <span className="text-xs" style={{ color: '#6b7280' }}>
              ({activeEntryCount})
            </span>
          )}
          {!isActive && entries.length === 0 && (
            <span className="text-xs" style={{ color: '#6b7280' }}>(已结束)</span>
          )}
        </div>
        <span className="text-xs" style={{ color: '#6b7280' }}>
          {collapsed ? '展开' : '收起'}
        </span>
      </div>

      {!collapsed && (
        <div className="p-4 max-h-96 overflow-y-auto font-mono text-sm leading-relaxed">
          {!isActive && entries.length === 0 && (
            <div className="text-center py-8">
              <p style={{ color: '#6b7280', marginBottom: '8px' }}>
                该批次已完成，无实时日志
              </p>
              <p style={{ color: '#4b5563', fontSize: '12px' }}>
                新建批次后可在执行过程中查看 Agent 思考过程
              </p>
            </div>
          )}

          {isActive && entries.length === 0 && (
            <p className="text-center py-8" style={{ color: '#6b7280' }}>
              {connected ? '等待 Agent 开始执行...' : '连接中...'}
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
