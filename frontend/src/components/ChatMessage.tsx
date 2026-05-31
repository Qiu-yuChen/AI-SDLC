import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useState, useRef, useEffect } from 'react';
import { Light as SyntaxHighlighter } from 'react-syntax-highlighter';
import { atomOneDark } from 'react-syntax-highlighter/dist/esm/styles/hljs';
import python from 'react-syntax-highlighter/dist/esm/languages/hljs/python';
import javascript from 'react-syntax-highlighter/dist/esm/languages/hljs/javascript';
import typescript from 'react-syntax-highlighter/dist/esm/languages/hljs/typescript';
import bash from 'react-syntax-highlighter/dist/esm/languages/hljs/bash';
import json from 'react-syntax-highlighter/dist/esm/languages/hljs/json';
import css from 'react-syntax-highlighter/dist/esm/languages/hljs/css';
import xml from 'react-syntax-highlighter/dist/esm/languages/hljs/xml';
import yaml from 'react-syntax-highlighter/dist/esm/languages/hljs/yaml';
import markdown from 'react-syntax-highlighter/dist/esm/languages/hljs/markdown';
import { FileText, CheckCircle, Loader, Circle, AlertCircle, Brain, Wrench, Eye, X, Download, Archive, Folder, Zap, RotateCcw, ChevronDown, ChevronRight, ChevronUp, MoreHorizontal } from 'lucide-react';
import type { ChatMessage as ChatMsg, PipelineNodeStatus, ReactLogEntry } from '../types/chat';
import { retryNode } from '../api/client';

SyntaxHighlighter.registerLanguage('python', python);
SyntaxHighlighter.registerLanguage('javascript', javascript);
SyntaxHighlighter.registerLanguage('typescript', typescript);
SyntaxHighlighter.registerLanguage('bash', bash);
SyntaxHighlighter.registerLanguage('json', json);
SyntaxHighlighter.registerLanguage('css', css);
SyntaxHighlighter.registerLanguage('xml', xml);
SyntaxHighlighter.registerLanguage('yaml', yaml);
SyntaxHighlighter.registerLanguage('markdown', markdown);

const EXT_TO_LANG: Record<string, string> = {
  '.py': 'python', '.pyw': 'python',
  '.js': 'javascript', '.mjs': 'javascript', '.cjs': 'javascript',
  '.ts': 'typescript', '.tsx': 'typescript',
  '.sh': 'bash', '.bash': 'bash', '.zsh': 'bash',
  '.json': 'json',
  '.css': 'css', '.scss': 'css', '.less': 'css',
  '.html': 'xml', '.htm': 'xml', '.svg': 'xml', '.xml': 'xml',
  '.yaml': 'yaml', '.yml': 'yaml',
  '.md': 'markdown',
  '.txt': 'bash',
};

function getLang(fileName: string): string {
  const ext = '.' + (fileName.split('.').pop()?.toLowerCase() || '');
  return EXT_TO_LANG[ext] || '';
}

const NODE_ICONS: Record<string, string> = {
  '概要设计': '📐',
  '代码生成': '💻',
  '单元测试': '🧪',
  '质量评分': '🏆',
};

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'completed': return <CheckCircle className="w-4 h-4" style={{ color: 'var(--accent)' }} />;
    case 'running': return <Loader className="w-4 h-4 animate-spin" style={{ color: 'var(--accent)' }} />;
    case 'failed': return <AlertCircle className="w-4 h-4" style={{ color: '#ef4444' }} />;
    case 'stopped': return <Circle className="w-4 h-4" style={{ color: '#f59e0b' }} />;
    default: return <Circle className="w-4 h-4" style={{ color: '#6b7280' }} />;
  }
}

function PipelineCard({ nodes, currentActivity, batchId }: { nodes: PipelineNodeStatus[]; currentActivity?: string; batchId?: string }) {
  const handleRetry = (nodeId: string) => {
    if (!batchId) return;
    retryNode(batchId, nodeId);
  };
  return (
    <div className="pipeline-card">
      {nodes.map((node) => (
        <div key={node.node_id} className={`pipeline-card-node ${node.status}`}>
          <span className="text-sm">{NODE_ICONS[node.node_id] || '📋'}</span>
          <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{node.node_id}</span>
          <StatusIcon status={node.status} />
          <span className="text-xs" style={{
            color: node.status === 'completed' ? '#059669' :
              node.status === 'running' ? 'var(--accent)' :
              node.status === 'stopped' ? '#f59e0b' :
              node.status === 'failed' ? '#ef4444' : 'var(--text-muted)',
          }}>
            {node.status === 'completed' ? `完成 (${node.duration_seconds?.toFixed(1)}s)` :
              node.status === 'running' ? '执行中...' :
              node.status === 'stopped' ? '已停止' :
              node.status === 'failed' ? '失败' : '等待中'}
            {(node.status === 'failed' || node.status === 'stopped') && batchId && (
              <button onClick={() => handleRetry(node.node_id)} className="ml-2 px-1.5 py-0.5 rounded text-xs" style={{ background: 'rgba(16,163,127,0.1)', color: 'var(--accent)' }}>
                <RotateCcw className="w-3 h-3 inline mr-0.5" />重试
              </button>
            )}
          </span>
        </div>
      ))}
      {currentActivity && (
        <div className="pipeline-current-activity">
          <span className="pipeline-activity-dot" />
          <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{currentActivity}</span>
        </div>
      )}
    </div>
  );
}

function ScoringCard({ scoring }: { scoring: ChatMsg['scoring'] }) {
  if (!scoring) return null;
  const s = scoring;
  return (
    <div className="scoring-card">
      <div className="scoring-card-header">
        <span className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{s.composite_score}/100</span>
        <span className="text-sm" style={{ color: 'var(--text-muted)' }}>
          {'★'.repeat(Math.min(5, Math.max(1, Math.floor(s.composite_score / 20))))}
          {'☆'.repeat(5 - Math.min(5, Math.max(1, Math.floor(s.composite_score / 20))))}
        </span>
      </div>
      <div className="scoring-card-grid">
        {[
          ['📐 概要设计', s.design_score],
          ['💻 代码生成', s.code_score],
          ['🧪 单元测试', s.test_score],
          ['🏆 RepoZero', s.repozero_score],
        ].map(([label, score]) => (
          <div className="scoring-card-item" key={label as string}>
            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{label}</span>
            <span className="text-sm font-semibold" style={{ color: (score as number) >= 80 ? '#10a37f' : (score as number) >= 60 ? '#f59e0b' : '#ef4444' }}>
              {score}/100
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ReActLogCard({ logs }: { logs: ReactLogEntry[] }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  function entryIcon(type: string) {
    switch (type) {
      case 'thought': return <Brain className="w-3.5 h-3.5" style={{ color: '#8b5cf6' }} />;
      case 'action': return <Wrench className="w-3.5 h-3.5" style={{ color: '#f59e0b' }} />;
      case 'observation': return <Eye className="w-3.5 h-3.5" style={{ color: '#06b6d4' }} />;
      default: return null;
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
    <div className="react-log-card">
      <div className="flex items-center gap-2 mb-2">
        <Brain className="w-4 h-4" style={{ color: '#8b5cf6' }} />
        <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>ReAct 思考日志</span>
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>({logs.length})</span>
      </div>
      <div className="react-log-entries" ref={scrollRef}>
        {logs.slice(-40).map((entry, idx) => (
          <div key={idx} className="react-entry">
            <span className="shrink-0 mt-0.5">{entryIcon(entry.type)}</span>
            {entry.agent && <span className="text-xs mr-1" style={{ color: 'var(--text-muted)' }}>[{entry.agent}]</span>}
            <span className="text-xs" style={{ color: entryColor(entry.type) }}>{entry.content}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function FilePreviewCard({ content, loading, fileName, onClose }: { content: string; loading: boolean; fileName: string | null; onClose: () => void }) {
  const isMarkdown = fileName?.endsWith('.md');
  const lang = fileName ? getLang(fileName) : '';
  const truncated = content.length > 30000 ? content.substring(0, 30000) : content;
  const truncatedMsg = content.length > 30000 ? '\n\n... (内容过长，已截断)' : '';

  return (
    <div className="file-preview-card">
      <div className="file-preview-header">
        <span className="text-xs font-mono truncate" style={{ color: 'var(--text-muted)' }}>
          {fileName || '预览'}
          {lang && <span className="ml-1" style={{ color: 'var(--accent)' }}>{lang}</span>}
        </span>
        <button onClick={onClose} className="file-chip-remove"><X className="w-3.5 h-3.5" /></button>
      </div>
      <div className="file-preview-body">
        {loading ? (
          <p className="text-center py-4" style={{ color: 'var(--text-muted)' }}>加载中...</p>
        ) : isMarkdown ? (
          <div className="markdown-body text-sm" style={{ color: 'var(--text-primary)' }}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{truncated}</ReactMarkdown>
          </div>
        ) : lang ? (
          <SyntaxHighlighter
            language={lang}
            style={atomOneDark}
            showLineNumbers={content.split('\n').length > 3}
            customStyle={{
              background: '#1a1a2e',
              margin: 0,
              borderRadius: 0,
              fontSize: '12px',
              maxHeight: '400px',
            }}
          >
            {truncated + truncatedMsg}
          </SyntaxHighlighter>
        ) : (
          <pre className="text-xs whitespace-pre-wrap break-all font-mono" style={{ color: 'var(--text-secondary)' }}>
            {content.substring(0, 10000)}
            {content.length > 10000 && '\n\n... (内容过长，已截断)'}
          </pre>
        )}
      </div>
    </div>
  );
}

function FileListCard({ files, onFileClick: _onFileClick, selectedFile: _sel, batchId }: { files: string[]; onFileClick: (f: string) => void; selectedFile?: string | null; batchId?: string }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [previews, setPreviews] = useState<Record<string, string>>({});
  const [showAll, setShowAll] = useState(false);

  const PREVIEW_COUNT = 10;
  const visibleFiles = showAll ? files : files.slice(0, PREVIEW_COUNT);
  const hasMore = files.length > PREVIEW_COUNT;

  async function toggle(filePath: string) {
    if (expanded === filePath) { setExpanded(null); return; }
    setExpanded(filePath);
    if (!previews[filePath]) {
      try {
        const res = await fetch(`/workspace/docs/已生成/${batchId}/${filePath}`);
        if (res.ok) {
          const text = await res.text();
          setPreviews((p) => ({ ...p, [filePath]: text }));
        } else {
          setPreviews((p) => ({ ...p, [filePath]: '无法加载' }));
        }
      } catch {
        setPreviews((p) => ({ ...p, [filePath]: '加载失败' }));
      }
    }
  }

  const isMarkdown = (f: string) => f.endsWith('.md');

  return (
    <div className="file-list-card">
      <div className="flex items-center gap-2 mb-2">
        <FileText className="w-4 h-4" style={{ color: 'var(--accent)' }} />
        <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>产出物文件 ({files.length})</span>
        {batchId && (
          <a href={`/api/batches/${batchId}/export`} className="ml-auto flex items-center gap-1 px-2 py-1 rounded text-xs" style={{ background: 'rgba(16,163,127,0.1)', color: 'var(--accent)', textDecoration: 'none' }}>
            <Download className="w-3 h-3" /> ZIP
          </a>
        )}
      </div>
      <div className="space-y-0.5">
        {visibleFiles.map((f) => (
          <div key={f}>
            <button
              onClick={() => toggle(f)}
              className="file-list-item"
              style={{ width: '100%', textAlign: 'left' }}
            >
              {expanded === f ? <ChevronDown className="w-3.5 h-3.5 shrink-0" style={{ color: 'var(--accent)' }} /> : <ChevronRight className="w-3.5 h-3.5 shrink-0" style={{ color: 'var(--text-muted)' }} />}
              <FileText className="w-3.5 h-3.5 shrink-0" style={{ color: 'var(--accent)' }} />
              <span className="text-xs truncate">{f.split('/').pop()}</span>
            </button>
            {expanded === f && (
              <div className="mx-4 mb-2 rounded-lg overflow-hidden" style={{ border: '1px solid var(--border)' }}>
                <div className="max-h-48 overflow-auto p-2 text-xs" style={{ background: 'var(--main-secondary)' }}>
                  {!previews[f] ? (
                    <span style={{ color: 'var(--text-muted)' }}>加载中...</span>
                  ) : previews[f] === '无法加载' || previews[f] === '加载失败' ? (
                    <span style={{ color: 'var(--text-muted)' }}>{previews[f]}</span>
                  ) : isMarkdown(f) ? (
                    <div className="markdown-body" style={{ color: 'var(--text-primary)' }}>
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{previews[f].substring(0, 5000)}</ReactMarkdown>
                    </div>
                  ) : (
                    <SyntaxHighlighter
                      language={getLang(f)}
                      style={atomOneDark}
                      customStyle={{ margin: 0, padding: '8px', fontSize: '11px', background: 'transparent', maxHeight: '12rem', overflow: 'auto' }}
                      wrapLongLines
                    >
                      {previews[f].substring(0, 3000)}
                    </SyntaxHighlighter>
                  )}
                </div>
              </div>
            )}
          </div>
        ))}
        {hasMore && !showAll && (
          <button
            onClick={() => setShowAll(true)}
            className="file-list-item"
            style={{ width: '100%', textAlign: 'left', color: 'var(--accent)', fontStyle: 'italic' }}
          >
            <ChevronDown className="w-3.5 h-3.5 shrink-0" style={{ color: 'var(--accent)' }} />
            <span className="text-xs">还有 {files.length - PREVIEW_COUNT} 个文件，点击展开全部</span>
          </button>
        )}
        {showAll && hasMore && (
          <button
            onClick={() => { setShowAll(false); setExpanded(null); }}
            className="file-list-item"
            style={{ width: '100%', textAlign: 'left', color: 'var(--accent)', fontStyle: 'italic' }}
          >
            <ChevronUp className="w-3.5 h-3.5 shrink-0" style={{ color: 'var(--accent)' }} />
            <span className="text-xs">收起，仅显示前 {PREVIEW_COUNT} 个文件</span>
          </button>
        )}
      </div>
    </div>
  );
}

export function ChatMessage({ message, batchId, onFilePreview }: { message: ChatMsg; batchId?: string; onFilePreview?: (filePath: string) => void }) {
  const isUser = message.role === 'user';

  return (
    <div className={`chat-msg-row ${isUser ? 'chat-msg-user' : 'chat-msg-assistant'}`}>
      {!isUser && <div className="chat-avatar">AI</div>}
      <div className={`chat-bubble ${isUser ? 'chat-bubble-user' : 'chat-bubble-assistant'}`}>
        {message.type === 'file_upload' && message.file && (
          <div className="file-chip mb-2">
            <FileText className="w-3.5 h-3.5" style={{ color: 'var(--accent)' }} />
            <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{message.file.name}</span>
            {message.file.size > 0 && <span className="text-xs" style={{ color: 'var(--text-muted)' }}>({(message.file.size / 1024).toFixed(1)} KB)</span>}
          </div>
        )}

        {message.content && (
          <div className={isUser ? '' : 'markdown-body'}>
            {isUser ? <p className="text-sm" style={{ margin: 0 }}>{message.content}</p> : <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>}
          </div>
        )}

        {message.loading && (
          <div className="flex items-center gap-1 mt-1">
            <span className="typing-dot" />
            <span className="typing-dot" />
            <span className="typing-dot" />
          </div>
        )}

        {message.pipelineNodes && message.pipelineNodes.length > 0 && <PipelineCard nodes={message.pipelineNodes} currentActivity={message.currentActivity} batchId={batchId} />}
        {message.scoring && <ScoringCard scoring={message.scoring} />}
        {message.type === 'file_list' && message.outputFiles && batchId && (
          <FileListCard files={message.outputFiles} onFileClick={(f) => onFilePreview?.(f)} selectedFile={message.selectedFile} batchId={batchId} />
        )}
        {message.type === 'react_log' && message.reactLogs && message.reactLogs.length > 0 && <ReActLogCard logs={message.reactLogs} />}
        {message.selectedFile && (
          <FilePreviewCard
            content={message.fileContent || ''}
            loading={!!message.fileLoading}
            fileName={message.selectedFile}
            onClose={() => onFilePreview?.('')}
          />
        )}
        {message.posterUrl && (
          <div className="my-2 rounded-lg overflow-hidden" style={{ border: '1px solid var(--border)' }}>
            <div className="flex items-center gap-1 px-3 py-2 text-xs" style={{ background: 'var(--main-secondary)', color: 'var(--text-muted)' }}>
              🖼️ 交付海报
              <a href={`/workspace/docs/已生成/${batchId}/${message.posterUrl}`} target="_blank" download className="ml-auto" style={{ color: 'var(--accent)' }}>下载</a>
            </div>
            <img src={`/workspace/docs/已生成/${batchId}/${message.posterUrl}`} alt="交付海报" style={{ width: '100%', display: 'block' }} />
          </div>
        )}
      </div>
    </div>
  );
}
