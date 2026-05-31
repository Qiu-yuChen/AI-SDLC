import { useState, useEffect, useRef, useCallback } from 'react';
import { Zap } from 'lucide-react';
import { ChatInput } from './ChatInput';
import { ChatMessage } from './ChatMessage';
import { uploadSpec, createBatch, startBatch, getBatch, fetchScoringReport, connectWs } from '../api/client';
import type { ChatMessage as ChatMsg, PipelineNodeStatus, ReactLogEntry } from '../types/chat';
import type { BatchStatus, WsEvent } from '../types';

interface Props {
  batchId: string | null;
  onBatchCreated: (batchId: string) => void;
  importSpec?: string | null;
  onSpecConsumed?: () => void;
}

const NODE_ORDER = ['\u6982\u8981\u8BBE\u8BA1', '\u4EE3\u7801\u751F\u6210', '\u5355\u5143\u6D4B\u8BD5', '\u8D28\u91CF\u8BC4\u5206'];

let msgId = 0;
function nextId() { return `msg_${++msgId}_${Date.now()}`; }
function now() { return new Date().toLocaleTimeString(); }

export function ChatView({ batchId, onBatchCreated, importSpec, onSpecConsumed }: Props) {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [processing, setProcessing] = useState(false);
  const [currentBatchId, setCurrentBatchId] = useState<string | null>(batchId);
  const [pipelineNodes, setPipelineNodes] = useState<PipelineNodeStatus[]>([]);
  const [reactLogMsgId, setReactLogMsgId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => { mountedRef.current = true; return () => { mountedRef.current = false; }; }, []);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  useEffect(() => { setCurrentBatchId(batchId); }, [batchId]);

  useEffect(() => {
    if (!importSpec) return;
    handleImportSpec(importSpec);
  }, [importSpec]);

  const addMsg = useCallback((msg: ChatMsg) => {
    if (!mountedRef.current) return;
    setMessages((prev) => [...prev, msg]);
  }, []);

  const updateMsg = useCallback((id: string, updater: (m: ChatMsg) => ChatMsg) => {
    if (!mountedRef.current) return;
    setMessages((prev) => prev.map((m) => m.id === id ? updater(m) : m));
  }, []);

  async function handleImportSpec(spec: string) {
    setProcessing(true);
    try {
      const blob = new Blob([spec], { type: 'text/markdown' });
      const file = new File([blob], 'generated_spec.md', { type: 'text/markdown' });

      addMsg({
        id: nextId(), role: 'user', type: 'file_upload',
        content: '通过一句话生成规格书',
        file: { name: file.name, size: file.size },
        timestamp: now(),
      });

      const loadingId = nextId();
      addMsg({
        id: loadingId, role: 'assistant', type: 'text',
        content: '⏳ 正在导入AI生成的规格书并启动开发流水线...',
        timestamp: now(), loading: true,
      });

      const uploadResult = await uploadSpec(file);
      const batch = await createBatch(uploadResult.filename, 'AI生成项目');

      const nodes: PipelineNodeStatus[] = NODE_ORDER.map((nid) => ({
        node_id: nid, name: nid, status: 'pending' as const,
        duration_seconds: null, output_files: [], quality_score: null,
      }));
      setPipelineNodes(nodes);

      updateMsg(loadingId, (m) => ({
        ...m,
        content: `✅ 已收到AI生成的规格说明书，正在启动开发流水线...\n\n🔄 概要设计 → 代码生成 → 单元测试 → 质量评分`,
        loading: false,
      }));

      setCurrentBatchId(batch.batch_id);
      onBatchCreated(batch.batch_id);
      await startBatch(batch.batch_id);
    } catch (e: any) {
      addMsg({
        id: nextId(), role: 'assistant', type: 'text',
        content: `❌ 导入失败: ${e.message || '未知错误'}`,
        timestamp: now(),
      });
    } finally {
      setProcessing(false);
      onSpecConsumed?.();
    }
  }

  async function handleFilePreview(msgId: string, batchId: string, filePath: string) {
    setMessages((prev) => prev.map((m) =>
      m.id === msgId ? { ...m, selectedFile: filePath, fileLoading: true, fileContent: '' } : m
    ));
    try {
      const url = `/workspace/docs/已生成/${batchId}/${filePath}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error('File not found');
      const text = await res.text();
      setMessages((prev) => prev.map((m) =>
        m.id === msgId ? { ...m, fileContent: text, fileLoading: false } : m
      ));
    } catch {
      setMessages((prev) => prev.map((m) =>
        m.id === msgId ? { ...m, fileContent: '无法加载文件内容', fileLoading: false } : m
      ));
    }
  }

  useEffect(() => {
    if (!currentBatchId) { setMessages([]); setPipelineNodes([]); return; }
    let loaded = false;
    const bid = currentBatchId;

    async function loadExisting() {
      try {
        const batch: BatchStatus = await getBatch(bid);
        if (!mountedRef.current || loaded) return;
        loaded = true;

        const initMsgs: ChatMsg[] = [];
        initMsgs.push({
          id: nextId(), role: 'user', type: 'text',
          content: `\u4E0A\u4F20\u4E86\u89C4\u683C\u8BF4\u660E\u4E66: ${batch.spec_file}`,
          timestamp: batch.created_at,
        });
        initMsgs.push({
          id: nextId(), role: 'assistant', type: 'text',
          content: `\u5DF2\u6536\u5230\u89C4\u683C\u8BF4\u660E\u4E66\u300A${batch.spec_file}\u300B\uFF0C\u6B63\u5728\u6267\u884C\u5F00\u53D1\u6D41\u6C34\u7EBF...`,
          timestamp: batch.created_at,
        });

        const nodes: PipelineNodeStatus[] = NODE_ORDER.map((nid) => {
          const n = batch.nodes[nid];
          return {
            node_id: nid,
            name: nid,
            status: n?.status || 'pending',
            duration_seconds: n?.duration_seconds ?? null,
            output_files: n?.output_files ?? [],
            quality_score: n?.quality_score ?? null,
          };
        });

        const pipelineMsg: ChatMsg = {
          id: nextId(), role: 'assistant', type: 'pipeline_status',
          content: '', pipelineNodes: nodes, timestamp: now(),
        };
        initMsgs.push(pipelineMsg);

        if (batch.status === 'completed' || batch.status === 'failed') {
          const allFiles: string[] = [];
          for (const n of Object.values(batch.nodes)) {
            if (n.output_files) allFiles.push(...n.output_files);
          }
          if (allFiles.length > 0) {
            initMsgs.push({
              id: nextId(), role: 'assistant', type: 'file_list',
              content: '\u2705 \u6D41\u6C34\u7EBF\u6267\u884C\u5B8C\u6210\uFF0C\u4EE5\u4E0B\u662F\u751F\u6210\u7684\u6587\u4EF6:',
              outputFiles: allFiles, timestamp: now(),
            });
          }
        }

        setMessages(initMsgs);
        setPipelineNodes(nodes);

        const scoringNode = batch.nodes['\u8D28\u91CF\u8BC4\u5206'];
        if (scoringNode?.status === 'completed') {
          try {
            const report = await fetchScoringReport(bid);
            if (mountedRef.current) {
              initMsgs.push({
                id: nextId(), role: 'assistant', type: 'scoring_report',
                content: '\u2705 \u8D28\u91CF\u8BC4\u5206\u5DF2\u5B8C\u6210',
                scoring: {
                  composite_score: Math.round(report.composite_score),
                  stars: '',
                  design_score: Math.round(report.design_score?.total_score ?? 0),
                  code_score: Math.round(report.code_score?.total_score ?? 0),
                  test_score: Math.round(report.test_score?.total_score ?? 0),
                  repozero_score: Math.round(report.repozero_score?.total_score ?? 0),
                },
                timestamp: now(),
              });
              setMessages([...initMsgs]);
            }
          } catch { /* no scoring report */ }
        }
      } catch { /* batch not found */ }
    }

    loadExisting();

    return () => { loaded = true; };
  }, [currentBatchId]);

  useEffect(() => {
    if (!currentBatchId) return;
    if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }

    const isActive = true;

    function connect() {
      if (!mountedRef.current) return;
      const ws = connectWs(currentBatchId!, (event: WsEvent) => {
        if (!mountedRef.current) return;
        setPipelineNodes((prev) => {
          const idx = prev.findIndex((n) => n.node_id === event.node_id);
          if (idx === -1) return prev;
          const updated = [...prev];
          const node = { ...updated[idx] };

          switch (event.type) {
            case 'node_start':
              node.status = 'running';
              break;
            case 'node_completed':
              node.status = 'completed';
              node.duration_seconds = event.duration_seconds ?? null;
              node.output_files = event.output_files ?? [];
              break;
            case 'node_failed':
              node.status = 'failed';
              break;
          }
          updated[idx] = node;

          addMsg({
            id: nextId(), role: 'assistant', type: 'pipeline_status',
            content: '', pipelineNodes: updated, timestamp: now(),
          });

          if (event.type === 'react_step' && event.step) {
            const entries: ReactLogEntry[] = [];
            if (event.step.thought) {
              entries.push({ type: 'thought', agent: event.name, content: event.step.thought });
            }
            if (event.step.action) {
              entries.push({ type: 'action', agent: event.name, content: `调用: ${event.step.action}(${event.step.action_input || ''})` });
            }
            if (event.step.observation) {
              const obs = event.step.observation;
              entries.push({ type: 'observation', agent: event.name, content: obs.length > 300 ? obs.substring(0, 300) + '...' : obs });
            }
            if (entries.length > 0) {
              if (!reactLogMsgId) {
                const msgId = nextId();
                setReactLogMsgId(msgId);
                addMsg({
                  id: msgId, role: 'assistant', type: 'react_log',
                  content: '', reactLogs: entries, timestamp: now(),
                });
              } else {
                setMessages((prev) => prev.map((m) =>
                  m.id === reactLogMsgId ? { ...m, reactLogs: [...(m.reactLogs || []), ...entries] } : m
                ));
              }
            }
          } else if (event.type === 'node_start' || event.type === 'node_completed' || event.type === 'node_failed') {
            setReactLogMsgId(null);
          }

          if (event.type === 'node_completed' && event.node_id === '\u8D28\u91CF\u8BC4\u5206') {
            fetchScoringReport(currentBatchId!)
              .then((report) => {
                if (!mountedRef.current) return;
                addMsg({
                  id: nextId(), role: 'assistant', type: 'scoring_report',
                  content: '\u2705 \u8D28\u91CF\u8BC4\u5206\u5DF2\u5B8C\u6210',
                  scoring: {
                    composite_score: Math.round(report.composite_score),
                    stars: '',
                    design_score: Math.round(report.design_score?.total_score ?? 0),
                    code_score: Math.round(report.code_score?.total_score ?? 0),
                    test_score: Math.round(report.test_score?.total_score ?? 0),
                    repozero_score: Math.round(report.repozero_score?.total_score ?? 0),
                  },
                  timestamp: now(),
                });

                const allFiles: string[] = [];
                updated.forEach((n) => { allFiles.push(...n.output_files); });
                if (allFiles.length > 0) {
                  addMsg({
                    id: nextId(), role: 'assistant', type: 'file_list',
                    content: '\u2705 \u6D41\u6C34\u7EBF\u6267\u884C\u5B8C\u6210\uFF0C\u4EE5\u4E0B\u662F\u751F\u6210\u7684\u6587\u4EF6:',
                    outputFiles: allFiles, timestamp: now(),
                  });
                }
              })
              .catch(() => {});
          }

          return updated;
        });
      }, () => {
        if (isActive && mountedRef.current) {
          setTimeout(connect, 3000);
        }
      });
      wsRef.current = ws;
    }

    connect();
    return () => { wsRef.current?.close(); wsRef.current = null; };
  }, [currentBatchId, addMsg]);

  async function handleSend(text: string, file?: File) {
    if (!file && !text.trim()) return;
    setProcessing(true);

    try {
      if (file) {
        addMsg({
          id: nextId(), role: 'user', type: 'file_upload',
          content: text || `\u4E0A\u4F20\u4E86\u89C4\u683C\u8BF4\u660E\u4E66`,
          file: { name: file.name, size: file.size },
          timestamp: now(),
        });

        const loadingId = nextId();
        addMsg({
          id: loadingId, role: 'assistant', type: 'text',
          content: '\u23F3 \u6B63\u5728\u4E0A\u4F20\u5E76\u542F\u52A8\u5F00\u53D1\u6D41\u6C34\u7EBF...',
          timestamp: now(), loading: true,
        });

        const uploadResult = await uploadSpec(file);
        const batch = await createBatch(uploadResult.filename, file.name.replace('.md', ''));

        const nodes: PipelineNodeStatus[] = NODE_ORDER.map((nid) => ({
          node_id: nid, name: nid, status: 'pending' as const,
          duration_seconds: null, output_files: [], quality_score: null,
        }));
        setPipelineNodes(nodes);

        updateMsg(loadingId, (m) => ({
          ...m,
          content: `\u2705 \u5DF2\u6536\u5230\u89C4\u683C\u8BF4\u660E\u4E66\u300A${file.name}\u300B\uFF0C\u6B63\u5728\u542F\u52A8\u5F00\u53D1\u6D41\u6C34\u7EBF...\n\n\uD83D\uDD04 \u6982\u8981\u8BBE\u8BA1 \u2192 \u4EE3\u7801\u751F\u6210 \u2192 \u5355\u5143\u6D4B\u8BD5 \u2192 \u8D28\u91CF\u8BC4\u5206`,
          loading: false,
        }));

        setCurrentBatchId(batch.batch_id);
        onBatchCreated(batch.batch_id);

        await startBatch(batch.batch_id);
      } else {
        addMsg({
          id: nextId(), role: 'user', type: 'text',
          content: text, timestamp: now(),
        });
        addMsg({
          id: nextId(), role: 'assistant', type: 'text',
          content: '\u8BF7\u4E0A\u4F20 .md \u89C4\u683C\u8BF4\u660E\u4E66\u4EE5\u542F\u52A8\u5F00\u53D1\u6D41\u6C34\u7EBF\u3002\u70B9\u51FB\u5DE6\u4FA7 \uD83D\uDCCE \u6309\u94AE\u9009\u62E9\u6587\u4EF6\u3002',
          timestamp: now(),
        });
      }
    } catch (e: any) {
      addMsg({
        id: nextId(), role: 'assistant', type: 'text',
        content: `\u274C \u64CD\u4F5C\u5931\u8D25: ${e.message || '\u672A\u77E5\u9519\u8BEF'}`,
        timestamp: now(),
      });
    } finally {
      setProcessing(false);
    }
  }

  const isEmpty = messages.length === 0;

  return (
    <div className="chat-view">
      <div className="chat-messages">
        {isEmpty ? (
          <div className="chat-empty">
            <div className="chat-empty-icon">
              <Zap className="w-8 h-8" style={{ color: 'var(--accent)' }} />
            </div>
            <h2 className="text-xl font-bold mb-2">AI-SDLC</h2>
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
              \u4E0A\u4F20\u4EA7\u54C1\u89C4\u683C\u8BF4\u660E\u4E66\uFF08.md\uFF09\uFF0CAI \u81EA\u52A8\u5B8C\u6210\u8BBE\u8BA1\u3001\u7F16\u7801\u3001\u6D4B\u8BD5
            </p>
          </div>
        ) : (
          messages.map((msg) => (
            <ChatMessage key={msg.id} message={msg} batchId={currentBatchId ?? undefined} onFilePreview={(fp) => {
              if (!fp) {
                setMessages((prev) => prev.map((m) => m.id === msg.id ? { ...m, selectedFile: null, fileContent: undefined, fileLoading: undefined } : m));
              } else if (currentBatchId) {
                handleFilePreview(msg.id, currentBatchId, fp);
              }
            }} />
          ))
        )}
        <div ref={messagesEndRef} />
      </div>
      <ChatInput onSend={handleSend} disabled={processing} />
    </div>
  );
}
