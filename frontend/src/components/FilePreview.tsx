import { useState } from 'react';
import { FileCode, FileText, Folder, ExternalLink } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { NodeInfo } from '../types';

interface Props {
  batchId: string;
  nodes: Record<string, NodeInfo>;
  wsHost: string;
}

const NODE_NAMES: Record<string, string> = {
  概要设计: '📐 概要设计',
  代码生成: '💻 代码生成',
  单元测试: '🧪 单元测试',
};

export function FilePreview({ batchId, nodes }: Props) {
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string>('');
  const [loading, setLoading] = useState(false);

  const allFiles: { nodeId: string; nodeName: string; files: string[] }[] = [];
  for (const [nodeId, node] of Object.entries(nodes)) {
    if (node.output_files?.length > 0) {
      allFiles.push({
        nodeId,
        nodeName: NODE_NAMES[nodeId] || nodeId,
        files: node.output_files,
      });
    }
  }

  async function loadFile(path: string) {
    setSelectedFile(path);
    setLoading(true);
    try {
      const url = `/workspace/docs/已生成/${batchId}/${path}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error('File not found');
      const text = await res.text();
      setFileContent(text);
    } catch {
      setFileContent('无法加载文件内容');
    } finally {
      setLoading(false);
    }
  }

  const isMarkdown = selectedFile?.endsWith('.md');
  const isCode = selectedFile?.endsWith('.py') || selectedFile?.endsWith('.ts') ||
    selectedFile?.endsWith('.js') || selectedFile?.endsWith('.html') ||
    selectedFile?.endsWith('.css') || selectedFile?.endsWith('.json');

  return (
    <div className="card p-6">
      <h3 className="text-lg font-semibold mb-4">产出物文件</h3>

      {allFiles.length === 0 ? (
        <p className="text-center py-8" style={{ color: 'var(--text-muted)' }}>
          暂无产出物，等待 Agent 执行完成...
        </p>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="space-y-4">
            {allFiles.map(({ nodeId, nodeName, files }) => (
              <div key={nodeId}>
                <h4 className="text-sm font-semibold mb-2 flex items-center gap-1" style={{ color: 'var(--text-secondary)' }}>
                  <Folder className="w-4 h-4" />
                  {nodeName}
                </h4>
                <div className="space-y-1">
                  {files.map((file) => (
                    <button
                      key={file}
                      onClick={() => loadFile(file)}
                      className="w-full text-left px-3 py-2 rounded-lg text-sm transition flex items-center gap-2"
                      style={{
                        background: selectedFile === file ? 'rgba(16,163,127,0.08)' : 'transparent',
                        color: selectedFile === file ? 'var(--accent)' : 'var(--text-secondary)',
                        border: selectedFile === file ? '1px solid rgba(16,163,127,0.2)' : '1px solid transparent',
                      }}
                    >
                      {file.endsWith('.md') ? (
                        <FileText className="w-4 h-4 shrink-0" />
                      ) : (
                        <FileCode className="w-4 h-4 shrink-0" />
                      )}
                      <span className="truncate">{file.split('/').pop()}</span>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div className="rounded-lg overflow-hidden" style={{ background: '#1e1e2e', border: '1px solid #2d2d3d' }}>
            <div className="flex items-center justify-between px-4 py-2 border-b" style={{ background: '#16162a', borderColor: '#2d2d3d' }}>
              <span className="text-xs font-mono truncate" style={{ color: '#9ca3af' }}>
                {selectedFile || '选择文件预览'}
              </span>
              {selectedFile && (
                <a
                  href={`/workspace/docs/已生成/${batchId}/${selectedFile}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: 'var(--accent)' }}
                >
                  <ExternalLink className="w-4 h-4" />
                </a>
              )}
            </div>
            <div className="p-4 max-h-96 overflow-auto">
              {loading ? (
                <p className="text-center py-8" style={{ color: 'var(--text-muted)' }}>加载中...</p>
              ) : selectedFile ? (
                isMarkdown ? (
                  <div className="prose prose-invert max-w-none text-sm markdown-body" style={{ color: '#e0e0e0' }}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{fileContent.substring(0, 30000)}</ReactMarkdown>
                  </div>
                ) : (
                  <pre className="text-sm whitespace-pre-wrap break-all font-mono" style={{ color: '#4ade80' }}>
                    {fileContent.substring(0, 10000)}
                    {fileContent.length > 10000 && '\n\n... (内容过长，已截断)'}
                  </pre>
                )
              ) : (
                <p className="text-center py-8" style={{ color: 'var(--text-muted)' }}>
                  选择左侧文件进行预览
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
