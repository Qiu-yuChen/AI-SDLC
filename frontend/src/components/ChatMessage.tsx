import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { FileText, CheckCircle, Loader, Circle, AlertCircle, Brain, Wrench, Eye, X, Download, Archive, Folder, Zap } from 'lucide-react';
import type { ChatMessage as ChatMsg, PipelineNodeStatus, ReactLogEntry } from '../types/chat';

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
    default: return <Circle className="w-4 h-4" style={{ color: 'var(--text-muted)' }} />;
  }
}

function PipelineCard({ nodes, currentActivity }: { nodes: PipelineNodeStatus[]; currentActivity?: string }) {
  return (
    <div className="pipeline-card">
      {nodes.map((node) => (
        <div key={node.node_id} className="pipeline-card-node">
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
          </span>
        </div>
      ))}
      {currentActivity && (
        <div className="pipeline-current-activity">
          <span className="pipeline-activity-dot" />
          <span>{currentActivity}</span>
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
      <div className="react-log-entries">
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
  return (
    <div className="file-preview-card">
      <div className="file-preview-header">
        <span className="text-xs font-mono truncate" style={{ color: 'var(--text-muted)' }}>{fileName || '预览'}</span>
        <button onClick={onClose} className="file-chip-remove"><X className="w-3.5 h-3.5" /></button>
      </div>
      <div className="file-preview-body">
        {loading ? (
          <p className="text-center py-4" style={{ color: 'var(--text-muted)' }}>加载中...</p>
        ) : isMarkdown ? (
          <div className="markdown-body text-sm" style={{ color: 'var(--text-primary)' }}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content.substring(0, 30000)}</ReactMarkdown>
          </div>
        ) : (
          <pre className="text-xs whitespace-pre-wrap break-all font-mono" style={{ color: 'var(--code-text)' }}>
            {content.substring(0, 10000)}
            {content.length > 10000 && '\n\n... (内容过长，已截断)'}
          </pre>
        )}
      </div>
    </div>
  );
}

function uniqueFiles(files: string[]) {
  return Array.from(new Set(files)).sort((a, b) => a.localeCompare(b, 'zh-CN'));
}

function classifyArtifact(file: string) {
  const lower = file.toLowerCase();
  if (lower.includes('test') || lower.includes('测试') || lower.endsWith('.spec.ts') || lower.endsWith('.test.ts')) return '测试';
  if (lower.endsWith('.py') || lower.endsWith('.ts') || lower.endsWith('.tsx') || lower.endsWith('.js') || lower.endsWith('.html') || lower.endsWith('.css')) return '代码';
  if (lower.endsWith('.json') || lower.endsWith('.csv') || lower.endsWith('.yaml') || lower.endsWith('.yml')) return '数据';
  if (lower.includes('评分') || lower.includes('report')) return '报告';
  return '文档';
}

function fileTypeCounts(files: string[]) {
  return files.reduce<Record<string, number>>((acc, file) => {
    const type = classifyArtifact(file);
    acc[type] = (acc[type] || 0) + 1;
    return acc;
  }, {});
}

function groupByNode(files: string[]) {
  return files.reduce<Record<string, string[]>>((acc, file) => {
    const [node = '产物'] = file.split('/');
    if (!acc[node]) acc[node] = [];
    acc[node].push(file);
    return acc;
  }, {});
}

function FileListCard({
  files,
  batchId,
  onFileClick,
  selectedFile,
}: {
  files: string[];
  batchId: string;
  onFileClick: (f: string) => void;
  selectedFile?: string | null;
}) {
  const visibleFiles = uniqueFiles(files);
  const counts = fileTypeCounts(visibleFiles);
  const groups = groupByNode(visibleFiles);
  const exportUrl = `/api/batches/${batchId}/export`;

  return (
    <div className="file-list-card">
      <div className="artifact-card-header">
        <div className="flex items-center gap-2">
          <Archive className="w-4 h-4" style={{ color: 'var(--accent)' }} />
          <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>产出物文件 ({visibleFiles.length})</span>
        </div>
        <a href={exportUrl} className="artifact-download-btn" title="下载全部产物 ZIP">
          <Download className="w-3.5 h-3.5" />
          下载 ZIP
        </a>
      </div>

      <div className="artifact-summary">
        <div className="artifact-summary-main">
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>已生成</span>
          <strong>{visibleFiles.length}</strong>
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>个文件</span>
        </div>
        <div className="artifact-type-grid">
          {Object.entries(counts).map(([type, count]) => (
            <span key={type} className="artifact-type-pill">{type} {count}</span>
          ))}
        </div>
      </div>

      <div className="space-y-1">
        {Object.entries(groups).slice(0, 4).map(([node, nodeFiles]) => (
          <div key={node} className="artifact-node-group">
            <div className="artifact-node-title">
              <Folder className="w-3.5 h-3.5" />
              <span>{node}</span>
              <span>{nodeFiles.length}</span>
            </div>
            {nodeFiles.slice(0, 4).map((f) => (
              <button
                key={f}
                onClick={() => onFileClick(f)}
                className="file-list-item"
                style={{
                  background: selectedFile === f ? 'rgba(16,163,127,0.08)' : 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  width: '100%',
                  textAlign: 'left',
                }}
              >
                <FileText className="w-3.5 h-3.5 shrink-0" style={{ color: 'var(--accent)' }} />
                <span className="text-xs truncate">{f.split('/').pop()}</span>
                <Eye className="w-3 h-3 shrink-0 ml-auto" style={{ color: 'var(--text-muted)' }} />
              </button>
            ))}
            {nodeFiles.length > 4 && (
              <span className="artifact-more">还有 {nodeFiles.length - 4} 个文件会打包到 ZIP</span>
            )}
          </div>
        ))}
        {Object.keys(groups).length > 4 && (
          <span className="artifact-more">还有 {Object.keys(groups).length - 4} 个阶段会打包到 ZIP</span>
        )}
      </div>
    </div>
  );
}

export function ChatMessage({ message, batchId, onFilePreview }: { message: ChatMsg; batchId?: string; onFilePreview?: (filePath: string) => void }) {
  const isUser = message.role === 'user';

  return (
    <div className={`chat-msg-row ${isUser ? 'chat-msg-user' : 'chat-msg-assistant'}`}>
      {!isUser && <div className="chat-avatar"><Zap className="w-4 h-4" /></div>}
      <div className={`chat-bubble ${isUser ? 'chat-bubble-user' : 'chat-bubble-assistant'}`}>
        {message.type === 'file_upload' && message.file && (
          <div className="msg-file-chip">
            <FileText className="w-4 h-4 shrink-0" style={{ color: 'var(--accent)' }} />
            <span className="msg-file-chip-name">{message.file.name}</span>
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

        {message.pipelineNodes && message.pipelineNodes.length > 0 && (
          <PipelineCard nodes={message.pipelineNodes} currentActivity={message.currentActivity} />
        )}
        {message.scoring && <ScoringCard scoring={message.scoring} />}
        {message.type === 'file_list' && message.outputFiles && batchId && (
          <FileListCard files={message.outputFiles} batchId={batchId} onFileClick={(f) => onFilePreview?.(f)} selectedFile={message.selectedFile} />
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
      </div>
    </div>
  );
}
