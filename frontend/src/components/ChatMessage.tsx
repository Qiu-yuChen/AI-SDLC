import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { FileText, CheckCircle, Loader, Circle, AlertCircle, Brain, Wrench, Eye, X } from 'lucide-react';
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
    default: return <Circle className="w-4 h-4" style={{ color: '#6b7280' }} />;
  }
}

function PipelineCard({ nodes }: { nodes: PipelineNodeStatus[] }) {
  return (
    <div className="pipeline-card">
      {nodes.map((node) => (
        <div key={node.node_id} className="pipeline-card-node">
          <span className="text-sm">{NODE_ICONS[node.node_id] || '📋'}</span>
          <span className="text-sm font-medium" style={{ color: '#e0e0e0' }}>{node.node_id}</span>
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
    </div>
  );
}

function ScoringCard({ scoring }: { scoring: ChatMsg['scoring'] }) {
  if (!scoring) return null;
  const s = scoring;
  return (
    <div className="scoring-card">
      <div className="scoring-card-header">
        <span className="text-lg font-bold" style={{ color: '#e0e0e0' }}>{s.composite_score}/100</span>
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
        <span className="text-sm font-semibold" style={{ color: '#e0e0e0' }}>ReAct 思考日志</span>
        <span className="text-xs" style={{ color: '#6b7280' }}>({logs.length})</span>
      </div>
      <div className="react-log-entries">
        {logs.slice(-40).map((entry, idx) => (
          <div key={idx} className="react-entry">
            <span className="shrink-0 mt-0.5">{entryIcon(entry.type)}</span>
            {entry.agent && <span className="text-xs mr-1" style={{ color: '#9ca3af' }}>[{entry.agent}]</span>}
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
        <span className="text-xs font-mono truncate" style={{ color: '#9ca3af' }}>{fileName || '预览'}</span>
        <button onClick={onClose} className="file-chip-remove"><X className="w-3.5 h-3.5" /></button>
      </div>
      <div className="file-preview-body">
        {loading ? (
          <p className="text-center py-4" style={{ color: 'var(--text-muted)' }}>加载中...</p>
        ) : isMarkdown ? (
          <div className="markdown-body text-sm" style={{ color: '#e0e0e0' }}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content.substring(0, 30000)}</ReactMarkdown>
          </div>
        ) : (
          <pre className="text-xs whitespace-pre-wrap break-all font-mono" style={{ color: '#4ade80' }}>
            {content.substring(0, 10000)}
            {content.length > 10000 && '\n\n... (内容过长，已截断)'}
          </pre>
        )}
      </div>
    </div>
  );
}

function FileListCard({ files, onFileClick, selectedFile }: { files: string[]; onFileClick: (f: string) => void; selectedFile?: string | null }) {
  return (
    <div className="file-list-card">
      <div className="flex items-center gap-2 mb-2">
        <FileText className="w-4 h-4" style={{ color: 'var(--accent)' }} />
        <span className="text-sm font-semibold" style={{ color: '#e0e0e0' }}>产出物文件 ({files.length})</span>
      </div>
      <div className="space-y-1">
        {files.slice(0, 10).map((f) => (
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
        {files.length > 10 && <span className="text-xs" style={{ color: 'var(--text-muted)' }}>... 及其他 {files.length - 10} 个文件</span>}
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
            <span className="text-xs" style={{ color: '#c0c0c0' }}>{message.file.name}</span>
            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>({(message.file.size / 1024).toFixed(1)} KB)</span>
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

        {message.pipelineNodes && message.pipelineNodes.length > 0 && <PipelineCard nodes={message.pipelineNodes} />}
        {message.scoring && <ScoringCard scoring={message.scoring} />}
        {message.type === 'file_list' && message.outputFiles && batchId && (
          <FileListCard files={message.outputFiles} onFileClick={(f) => onFilePreview?.(f)} selectedFile={message.selectedFile} />
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
