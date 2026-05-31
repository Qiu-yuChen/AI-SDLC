import { useState, useEffect, useRef, useCallback } from 'react';

import { ChatInput } from './ChatInput';
import { ChatMessage } from './ChatMessage';
import {
  uploadSpec,
  createBatch,
  startBatch,
  stopBatch,
  resumeBatch,
  getBatch,
  fetchScoringReport,
  connectWs,
} from '../api/client';
import type { ChatMessage as ChatMsg, PipelineNodeStatus, ReactLogEntry } from '../types/chat';
import type { BatchState, BatchStatus, WsEvent } from '../types';

interface Props {
  batchId: string | null;
  onBatchCreated: (batchId: string) => void;
  importSpec?: string | null;
  onSpecConsumed?: () => void;
}

const NODE_ORDER = ['概要设计', '代码生成', '单元测试', '质量评分'];

let msgId = 0;
function nextId() { return `msg_${++msgId}_${Date.now()}`; }
function now() { return new Date().toLocaleTimeString(); }

function emptyNodes(): PipelineNodeStatus[] {
  return NODE_ORDER.map((nid) => ({
    node_id: nid,
    name: nid,
    status: 'pending',
    duration_seconds: null,
    output_files: [],
    quality_score: null,
  }));
}

function nodesFromBatch(batch: BatchStatus): PipelineNodeStatus[] {
  return NODE_ORDER.map((nid) => {
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
}

function reactEntriesFromStep(event: WsEvent): ReactLogEntry[] {
  const step = event.step;
  if (!step) return [];
  const entries: ReactLogEntry[] = [];
  if (step.thought) entries.push({ type: 'thought', agent: event.name, content: step.thought });
  if (step.action) entries.push({ type: 'action', agent: event.name, content: `调用: ${step.action}${step.action_input ? `(${step.action_input})` : ''}` });
  if (step.observation) entries.push({ type: 'observation', agent: event.name, content: step.observation });
  return entries;
}

function activityFromStep(event: WsEvent): string {
  const step = event.step;
  if (!step) return '';
  if (step.action) {
    const action = step.action.toLowerCase();
    if (!action.includes('.') || action.includes('write_file') || action.includes('read_file')) {
      const input = step.action_input || '';
      if (action.includes('write_file')) {
        const match = input.match(/["']([^"']+\.(py|md|ts|tsx|json|csv|txt|yaml|yml|toml|cfg|html|css|js|go|rs|java|c|h))["']/i);
        if (match) return `正在写入 ${match[1].split(/[\\/]/).pop()}`;
        return '正在写入文件...';
      }
      if (action.includes('read_file')) return '正在读取文件...';
      if (action.includes('list_directory') || action.includes('list_dir')) return '正在浏览目录...';
      if (action.includes('syntax_check')) return '正在检查代码语法...';
      if (action.includes('format_code')) return '正在格式化代码...';
      if (action.includes('validate')) return '正在验证设计完整性...';
    }
  }
  if (step.thought) {
    const thought = step.thought.length > 40 ? `${step.thought.slice(0, 40)}...` : step.thought;
    return `思考: ${thought}`;
  }
  if (step.observation) {
    return step.observation.length > 40 ? `${step.observation.slice(0, 40)}...` : step.observation;
  }
  return '';
}

export function ChatView({ batchId, onBatchCreated, importSpec, onSpecConsumed }: Props) {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [processing, setProcessing] = useState(false);
  const [currentBatchId, setCurrentBatchId] = useState<string | null>(batchId);
  const [batchStatus, setBatchStatus] = useState<BatchState | null>(null);
  const [pipelineNodes, setPipelineNodes] = useState<PipelineNodeStatus[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const mountedRef = useRef(true);
  const pipelineMsgIdRef = useRef<string | null>(null);
  const reactLogMsgIdRef = useRef<string | null>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const [showScrollBtn, setShowScrollBtn] = useState(false);

  useEffect(() => { mountedRef.current = true; return () => { mountedRef.current = false; }; }, []);
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);
  useEffect(() => { setCurrentBatchId(batchId); }, [batchId]);

  // Scroll detection for "back to bottom" button
  const handleScroll = useCallback(() => {
    const el = chatContainerRef.current;
    if (!el) return;
    setShowScrollBtn(el.scrollHeight - el.scrollTop - el.clientHeight > 200);
  }, []);
  useEffect(() => {
    const el = chatContainerRef.current;
    if (!el) return;
    el.addEventListener('scroll', handleScroll, { passive: true });
    return () => el.removeEventListener('scroll', handleScroll);
  }, [handleScroll]);

  function scrollToBottom() {
    const el = chatContainerRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
  }

  const addMsg = useCallback((msg: ChatMsg) => {
    if (!mountedRef.current) return;
    setMessages((prev) => [...prev, msg]);
  }, []);

  const updateMsg = useCallback((id: string, updater: (m: ChatMsg) => ChatMsg) => {
    if (!mountedRef.current) return;
    setMessages((prev) => prev.map((m) => m.id === id ? updater(m) : m));
  }, []);

  const upsertPipelineMessage = useCallback((nodes: PipelineNodeStatus[]) => {
    if (!mountedRef.current) return;
    setMessages((prev) => {
      const existingIndex = prev.findIndex((m) => m.type === 'pipeline_status');
      if (existingIndex >= 0) {
        const next = prev.filter((m, idx) => m.type !== 'pipeline_status' || idx === existingIndex);
        const idx = next.findIndex((m) => m.type === 'pipeline_status');
        pipelineMsgIdRef.current = next[idx].id;
        next[idx] = { ...next[idx], pipelineNodes: nodes, timestamp: now() };
        return next;
      }
      const msg: ChatMsg = { id: nextId(), role: 'assistant', type: 'pipeline_status', content: '', pipelineNodes: nodes, timestamp: now() };
      pipelineMsgIdRef.current = msg.id;
      return [...prev, msg];
    });
  }, []);

  const upsertReactLogMessage = useCallback((entries: ReactLogEntry[]) => {
    if (!mountedRef.current || entries.length === 0) return;
    setMessages((prev) => {
      const id = reactLogMsgIdRef.current;
      const existingIndex = id ? prev.findIndex((m) => m.id === id) : prev.findIndex((m) => m.type === 'react_log');
      if (existingIndex >= 0) {
        const next = [...prev];
        const existing = next[existingIndex];
        reactLogMsgIdRef.current = existing.id;
        next[existingIndex] = { ...existing, reactLogs: [...(existing.reactLogs || []), ...entries], timestamp: now() };
        return next;
      }
      const msg: ChatMsg = { id: nextId(), role: 'assistant', type: 'react_log', content: '', reactLogs: entries, timestamp: now() };
      reactLogMsgIdRef.current = msg.id;
      return [...prev, msg];
    });
  }, []);

  const replaceReactLogMessage = useCallback((entries: ReactLogEntry[]) => {
    if (!mountedRef.current || entries.length === 0) return;
    setMessages((prev) => {
      const existingIndex = prev.findIndex((m) => m.type === 'react_log');
      if (existingIndex >= 0) {
        const next = [...prev];
        const existing = next[existingIndex];
        reactLogMsgIdRef.current = existing.id;
        next[existingIndex] = { ...existing, reactLogs: entries, timestamp: now() };
        return next;
      }
      const msg: ChatMsg = { id: nextId(), role: 'assistant', type: 'react_log', content: '', reactLogs: entries, timestamp: now() };
      reactLogMsgIdRef.current = msg.id;
      return [...prev, msg];
    });
  }, []);

  const upsertSingleMessage = useCallback((msg: ChatMsg, type: ChatMsg['type']) => {
    setMessages((prev) => {
      const existingIndex = prev.findIndex((m) => m.type === type);
      if (existingIndex < 0) return [...prev, msg];
      const next = [...prev];
      next[existingIndex] = { ...next[existingIndex], ...msg, id: next[existingIndex].id };
      return next;
    });
  }, []);

  const upsertFileListMessage = useCallback((files: string[]) => {
    if (!mountedRef.current || files.length === 0) return;
    const sortedFiles = Array.from(new Set(files)).sort((a, b) => a.localeCompare(b, 'zh-CN'));
    setMessages((prev) => {
      const existingIndex = prev.findIndex((m) => m.type === 'file_list');
      // 始终用合并后的完整列表替换（不累加，上游已负责合并）
      const next = [...prev];
      if (existingIndex < 0) {
        next.push({
          id: nextId(),
          role: 'assistant',
          type: 'file_list',
          content: '已生成以下产物，可预览或一键下载 ZIP:',
          outputFiles: sortedFiles,
          timestamp: now(),
        });
      } else {
        next[existingIndex] = {
          ...next[existingIndex],
          content: '已生成以下产物，可预览或一键下载 ZIP:',
          outputFiles: sortedFiles,
          timestamp: now(),
        };
      }
      return next;
    });
  }, []);

  async function handleFilePreview(msgId: string, batchId: string, filePath: string) {
    setMessages((prev) => prev.map((m) =>
      m.id === msgId ? { ...m, selectedFile: filePath, fileLoading: true, fileContent: '' } : m
    ));
    try {
      const res = await fetch(`/workspace/docs/已生成/${batchId}/${filePath}`);
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

  async function loadReactLogs(batchIdToLoad: string): Promise<{ logs: ReactLogEntry[]; lastActivity: string }> {
    try {
      const res = await fetch(`/workspace/docs/已生成/${batchIdToLoad}/execution_log.json`);
      if (!res.ok) return { logs: [], lastActivity: '' };
      const raw = await res.json();
      const stepEntries = raw.filter((entry: any) => entry.event === 'react_step' && entry.step);
      const logs = stepEntries.flatMap((entry: any) => reactEntriesFromStep({
        type: 'react_step',
        batch_id: batchIdToLoad,
        node_id: entry.node,
        name: entry.name,
        step: entry.step,
      }));
      const lastStep = stepEntries.length > 0 ? stepEntries[stepEntries.length - 1] : null;
      const lastActivity = lastStep ? activityFromStep({
        type: 'react_step',
        batch_id: batchIdToLoad,
        node_id: lastStep.node,
        name: lastStep.name,
        step: lastStep.step,
      }) : '';
      return { logs, lastActivity };
    } catch {
      return { logs: [], lastActivity: '' };
    }
  }

  async function beginBatchFromFile(file: File, projectName: string, loadingId?: string) {
    const uploadResult = await uploadSpec(file);
    const batch = await createBatch(uploadResult.filename, projectName);
    const nodes = emptyNodes();
    setPipelineNodes(nodes);
    upsertPipelineMessage(nodes);
    setCurrentBatchId(batch.batch_id);
    setBatchStatus('running');
    onBatchCreated(batch.batch_id);
    if (loadingId) {
      updateMsg(loadingId, (m) => ({ ...m, content: `已收到规格说明书《${file.name}》，正在启动开发流水线...`, loading: false }));
    }
    await startBatch(batch.batch_id);
  }

  async function handleImportSpec(spec: string) {
    setProcessing(true);
    try {
      const blob = new Blob([spec], { type: 'text/markdown' });
      const file = new File([blob], 'generated_spec.md', { type: 'text/markdown' });
      addMsg({ id: nextId(), role: 'user', type: 'file_upload', content: '通过一句话生成规格书', file: { name: file.name, size: file.size }, timestamp: now() });
      const loadingId = nextId();
      addMsg({ id: loadingId, role: 'assistant', type: 'text', content: '正在导入 AI 生成的规格书并启动开发流水线...', timestamp: now(), loading: true });
      await beginBatchFromFile(file, 'AI生成项目', loadingId);
    } catch (e: any) {
      addMsg({ id: nextId(), role: 'assistant', type: 'text', content: `导入失败: ${e.message || '未知错误'}`, timestamp: now() });
    } finally {
      setProcessing(false);
      onSpecConsumed?.();
    }
  }

  useEffect(() => {
    if (!importSpec) return;
    handleImportSpec(importSpec);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [importSpec]);

  useEffect(() => {
    if (!currentBatchId) {
      setMessages([]);
      setPipelineNodes([]);
      setBatchStatus(null);
      pipelineMsgIdRef.current = null;
      reactLogMsgIdRef.current = null;
      return;
    }

    let cancelled = false;
    const bid = currentBatchId;

    async function loadExisting() {
      try {
        const batch = await getBatch(bid);
        if (!mountedRef.current || cancelled) return;

        const nodes = nodesFromBatch(batch);
        const initMsgs: ChatMsg[] = [
          { id: nextId(), role: 'user', type: 'file_upload', content: '', file: { name: batch.spec_file, size: undefined as unknown as number }, timestamp: batch.created_at },
          { id: nextId(), role: 'assistant', type: 'text', content: batch.status === 'stopped' ? `生成已停止，可输入补充指引后继续执行。` : `已收到规格说明书《${batch.spec_file}》，正在执行开发流水线...`, timestamp: batch.created_at },
        ];

        const pipelineMsg: ChatMsg = { id: nextId(), role: 'assistant', type: 'pipeline_status', content: '', pipelineNodes: nodes, timestamp: now() };
        pipelineMsgIdRef.current = pipelineMsg.id;
        initMsgs.push(pipelineMsg);

        const { logs: reactLogs, lastActivity } = await loadReactLogs(bid);
        if (batch.status === 'running' && lastActivity) {
          pipelineMsg.currentActivity = lastActivity;
        }
        if (reactLogs.length) {
          const reactMsg: ChatMsg = { id: nextId(), role: 'assistant', type: 'react_log', content: '', reactLogs, timestamp: now() };
          reactLogMsgIdRef.current = reactMsg.id;
          initMsgs.push(reactMsg);
        }

        const allFiles = Object.values(batch.nodes).flatMap((n) => n.output_files || []);
        if ((batch.status === 'completed' || batch.status === 'failed') && allFiles.length > 0) {
          initMsgs.push({ id: nextId(), role: 'assistant', type: 'file_list', content: '已生成以下产物，可预览或一键下载 ZIP:', outputFiles: Array.from(new Set(allFiles)), timestamp: now() });
        }

        setMessages(initMsgs);
        setPipelineNodes(nodes);
        setBatchStatus((prev) => {
          if (prev === 'running') return 'running';
          return batch.status;
        });

        const scoringNode = batch.nodes['质量评分'];
        if (scoringNode?.status === 'completed') {
          try {
            const report = await fetchScoringReport(bid);
            const num = (v: unknown) => Math.round(typeof v === 'number' ? v : (v as Record<string, unknown>)?.total_score as number || 0);
            if (!cancelled && mountedRef.current) {
              upsertSingleMessage({
                id: nextId(),
                role: 'assistant',
                type: 'scoring_report',
                content: '质量评分已完成',
                scoring: {
                  composite_score: num(report.composite_score),
                  stars: '',
                  design_score: num(report.design_score),
                  code_score: num(report.code_score),
                  test_score: num(report.test_score),
                  repozero_score: num(report.repozero_score),
                },
                timestamp: now(),
              }, 'scoring_report');
            }
          } catch { /* no scoring report */ }

          if (batch.has_poster && !cancelled && mountedRef.current) {
            addMsg({
              id: nextId(), role: 'assistant', type: 'text',
              content: '',
              posterUrl: '交付海报/poster.png',
              timestamp: now(),
            });
          }
        }
      } catch { /* batch not found */ }
    }

    loadExisting();
    return () => { cancelled = true; };
  }, [currentBatchId, upsertSingleMessage]);

  useEffect(() => {
    if (!currentBatchId || !['created', 'running'].includes(batchStatus || '')) return;

    let cancelled = false;
    const bid = currentBatchId;

    async function refreshSnapshot() {
      try {
        const batch = await getBatch(bid);
        if (cancelled || !mountedRef.current) return;
        const nodes = nodesFromBatch(batch);
        setPipelineNodes(nodes);
        setBatchStatus(batch.status);
        upsertPipelineMessage(nodes);

        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
          const { logs: reactLogs, lastActivity } = await loadReactLogs(bid);
          if (!cancelled && mountedRef.current) {
            if (reactLogs.length) {
              replaceReactLogMessage(reactLogs);
            }
            if (batch.status === 'running' && lastActivity) {
              setMessages((prev) => prev.map((m) =>
                m.type === 'pipeline_status' ? { ...m, currentActivity: lastActivity } : m
              ));
            }
          }
        }
      } catch { /* keep the live websocket state */ }
    }

    refreshSnapshot();
    const timer = window.setInterval(refreshSnapshot, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [currentBatchId, batchStatus, upsertPipelineMessage, replaceReactLogMessage]);

  useEffect(() => {
    if (!currentBatchId) return;
    wsRef.current?.close();
    wsRef.current = null;
    let closed = false;

    function connect() {
      if (!mountedRef.current || closed || !currentBatchId) return;
      const ws = connectWs(currentBatchId, (event: WsEvent) => {
        if (!mountedRef.current) return;

        if (event.type === 'react_step') {
          upsertReactLogMessage(reactEntriesFromStep(event));
          const activity = activityFromStep(event);
          if (activity) {
            setMessages((prev) => prev.map((m) =>
              m.type === 'pipeline_status' ? { ...m, currentActivity: activity } : m
            ));
          }
          return;
        }

        if (event.type === 'batch_resumed') {
          setBatchStatus('running');
          addMsg({ id: nextId(), role: 'assistant', type: 'text', content: '已继续执行生成任务。', timestamp: now() });
          return;
        }

        if (event.type === 'batch_stopped') {
          setBatchStatus('stopped');
        }

        if (['node_start', 'node_completed', 'node_failed', 'node_stopped', 'batch_stopped'].includes(event.type)) {
          setPipelineNodes((prev) => {
            const next = prev.length ? [...prev] : emptyNodes();
            const idx = next.findIndex((n) => n.node_id === event.node_id);
            if (idx >= 0) {
              const node = { ...next[idx] };
              if (event.type === 'node_start') node.status = 'running';
              if (event.type === 'node_completed') {
                node.status = 'completed';
                node.duration_seconds = event.duration_seconds ?? null;
                node.output_files = event.output_files ?? [];
                if (event.output_files?.length) {
                  const allFiles = next.flatMap((n) => n.output_files || []);
                  upsertFileListMessage(allFiles);
                }
              }
              if (event.type === 'node_failed') node.status = 'failed';
              if (event.type === 'node_stopped' || event.type === 'batch_stopped') node.status = 'stopped';
              next[idx] = node;
            }
            upsertPipelineMessage(next);
            return next;
          });
        }

        if (event.type === 'node_start') {
          setBatchStatus('running');
          if (event.retry) {
            replaceReactLogMessage([]);
          }
          addMsg({ id: nextId(), role: 'assistant', type: 'text', content: `**${event.name || event.node_id || ''}** 已开始执行...`, timestamp: now() });
        }
        if (event.type === 'node_completed') {
          const dur = event.duration_seconds != null ? ` (耗时 ${event.duration_seconds.toFixed(1)}s)` : '';
          addMsg({ id: nextId(), role: 'assistant', type: 'text', content: `**${event.name || event.node_id || ''}** 完成${dur}`, timestamp: now() });
          setMessages((prev) => prev.map((m) =>
            m.type === 'pipeline_status' ? { ...m, currentActivity: undefined } : m
          ));
        }
        if (event.type === 'node_failed') {
          setBatchStatus('failed');
          addMsg({ id: nextId(), role: 'assistant', type: 'text', content: `**${event.name || event.node_id || ''}** 执行失败${event.error ? ': ' + event.error : ''}`, timestamp: now() });
          setMessages((prev) => prev.map((m) =>
            m.type === 'pipeline_status' ? { ...m, currentActivity: undefined } : m
          ));
        }
        if (event.type === 'node_stopped') setBatchStatus('stopped');

        if (event.type === 'rollback') {
          setBatchStatus('running');
          replaceReactLogMessage([]);
          addMsg({
            id: nextId(), role: 'assistant', type: 'text',
            content: `⏪ 回退到「${event.node_id}」，从该阶段重新执行`,
            timestamp: now(),
          });
        }

        if (event.type === 'node_completed' && event.node_id === '质量评分') {
                setBatchStatus('completed');
          getBatch(currentBatchId)
            .then((batch) => {
              const allFiles = Object.values(batch.nodes).flatMap((n) => n.output_files || []);
              upsertFileListMessage(allFiles);
            })
            .catch(() => {});
          fetchScoringReport(currentBatchId)
            .then((report) => {
              if (!mountedRef.current) return;
              const num = (v: unknown) => Math.round(typeof v === 'number' ? v : (v as Record<string, unknown>)?.total_score as number || 0);
              upsertSingleMessage({
                id: nextId(),
                role: 'assistant',
                type: 'scoring_report',
                content: '质量评分已完成',
                scoring: {
                  composite_score: num(report.composite_score),
                  stars: '',
                  design_score: num(report.design_score),
                  code_score: num(report.code_score),
                  test_score: num(report.test_score),
                  repozero_score: num(report.repozero_score),
                },
                timestamp: now(),
              }, 'scoring_report');
            })
            .catch(() => {});
        }

        if (event.type === 'poster_ready') {
          addMsg({
            id: nextId(), role: 'assistant', type: 'text',
            content: '',
            posterUrl: event.path || event.message,
            timestamp: now(),
          });
        }
      }, () => {
        if (!closed && mountedRef.current) setTimeout(connect, 3000);
      });
      wsRef.current = ws;
    }

    connect();
    return () => {
      closed = true;
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [currentBatchId, addMsg, upsertPipelineMessage, upsertReactLogMessage, upsertSingleMessage, upsertFileListMessage]);

  async function handleStop() {
    if (!currentBatchId) return;
    setProcessing(true);
    try {
      await stopBatch(currentBatchId);
      onBatchCreated(currentBatchId);
      setBatchStatus('stopped');
      setPipelineNodes((prev) => {
        const next = prev.map((node) => node.status === 'running' ? { ...node, status: 'stopped' as const } : node);
        upsertPipelineMessage(next);
        return next;
      });
      addMsg({ id: nextId(), role: 'assistant', type: 'text', content: '已停止当前生成。你可以补充指引后继续运行。', timestamp: now() });
    } catch (e: any) {
      addMsg({ id: nextId(), role: 'assistant', type: 'text', content: `停止失败: ${e.message || '未知错误'}`, timestamp: now() });
    } finally {
      setProcessing(false);
    }
  }

  async function handleSend(text: string, file?: File) {
    if (!file && !text.trim() && batchStatus !== 'stopped') return;
    setProcessing(true);

    try {
      if (batchStatus === 'stopped' && currentBatchId && !file) {
        if (text.trim()) addMsg({ id: nextId(), role: 'user', type: 'text', content: text, timestamp: now() });
        addMsg({ id: nextId(), role: 'assistant', type: 'text', content: text.trim() ? '已追加指引，继续从断点执行。' : '继续从断点执行。', timestamp: now() });
        setBatchStatus('running');
        await resumeBatch(currentBatchId, text.trim());
        onBatchCreated(currentBatchId);
        return;
      }

      if (file) {
        addMsg({ id: nextId(), role: 'user', type: 'file_upload', content: text || '上传了规格说明书', file: { name: file.name, size: file.size }, timestamp: now() });
        const loadingId = nextId();
        addMsg({ id: loadingId, role: 'assistant', type: 'text', content: '正在上传并启动开发流水线...', timestamp: now(), loading: true });
        await beginBatchFromFile(file, file.name.replace('.md', ''), loadingId);
      } else {
        addMsg({ id: nextId(), role: 'user', type: 'text', content: text, timestamp: now() });
        addMsg({ id: nextId(), role: 'assistant', type: 'text', content: '请上传 .md 规格说明书以启动开发流水线。', timestamp: now() });
      }
    } catch (e: any) {
      addMsg({ id: nextId(), role: 'assistant', type: 'text', content: `操作失败: ${e.message || '未知错误'}`, timestamp: now() });
    } finally {
      setProcessing(false);
    }
  }

  const isEmpty = messages.length === 0;
  const canStop = batchStatus === 'running' && !processing;
  const canResume = batchStatus === 'stopped' && !processing;

  return (
    <div className="chat-view">
       <div className="chat-messages" ref={chatContainerRef}>
        {isEmpty ? (
          <div className="chat-empty">
            <div className="chat-empty-icon">
              <svg className="w-8 h-8" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg" style={{ color: 'var(--accent)' }}>
                <path d="M469.333333 42.666667v42.666666H298.666667a128 128 0 0 0-128 128v128a213.333333 213.333333 0 0 0 213.333333 213.333334h256a213.333333 213.333333 0 0 0 213.333333-213.333334V213.333333a128 128 0 0 0-128-128h-170.666666V42.666667h-85.333334zM256 213.333333a42.666667 42.666667 0 0 1 42.666667-42.666666h426.666666a42.666667 42.666667 0 0 1 42.666667 42.666666v128a128 128 0 0 1-128 128H384a128 128 0 0 1-128-128V213.333333z m149.333333 170.666667a64 64 0 1 0 0-128 64 64 0 0 0 0 128z m213.333334 0a64 64 0 1 0 0-128 64 64 0 0 0 0 128zM256 938.666667a256 256 0 0 1 512 0h85.333333a341.333333 341.333333 0 1 0-682.666666 0h85.333333z" fill="currentColor" />
              </svg>
            </div>
            <h2 className="text-xl font-bold mb-2">AI-SDLC</h2>
            <p
              className="text-sm"
              style={{
                color: 'var(--text-muted)',
                fontFamily: 'Orbitron, -apple-system, BlinkMacSystemFont, sans-serif',
                letterSpacing: '0.05em',
              }}
            >
              Software Development Lightweight Counselor，轻量型软件开发智能助手
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
        {showScrollBtn && (
          <button onClick={scrollToBottom} className="scroll-to-bottom-btn" title="回到底部">
            ↓
          </button>
        )}
      </div>
      <ChatInput onSend={handleSend} onStop={handleStop} disabled={processing} canStop={canStop} canResume={canResume} />
    </div>
  );
}
