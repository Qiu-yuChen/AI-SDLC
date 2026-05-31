import { useState, useRef } from 'react';
import { Upload, Play, FileText, Sparkles, Zap, FileType } from 'lucide-react';
import { uploadSpec, createBatch, startBatch } from '../api/client';
import type { BatchListItem } from '../types';

interface Props {
  onCreated: (batchId: string) => void;
  batches: BatchListItem[];
  onSelectBatch: (batchId: string) => void;
  onOpenOptimizer: () => void;
  importedSpec: string;
  onClearImportedSpec: () => void;
}

export function BatchCreator({ onCreated, batches, onSelectBatch, onOpenOptimizer, importedSpec, onClearImportedSpec }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [projectName, setProjectName] = useState('');
  const [specText, setSpecText] = useState('');
  const [uploading, setUploading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');
  const [mode, setMode] = useState<'upload' | 'text'>('upload');
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleSubmit() {
    setCreating(true);
    setError('');
    try {
      let specFilename = '';

      if (mode === 'upload' && file) {
        const uploadResult = await uploadSpec(file);
        specFilename = uploadResult.filename;
        if (!projectName) {
          // Strip extension for default project name
          const baseName = file.name.replace(/\.[^.]+$/, '');
          setProjectName(baseName);
        }
      } else if (mode === 'text' && specText.trim()) {
        const blob = new Blob([specText], { type: 'text/markdown' });
        const textFile = new File([blob], `spec_${Date.now()}.md`, { type: 'text/markdown' });
        const uploadResult = await uploadSpec(textFile);
        specFilename = uploadResult.filename;
        if (!projectName) setProjectName('手动输入规格书');
      }

      if (!specFilename) {
        setError('请上传规格说明书或输入内容');
        setCreating(false);
        return;
      }

      const batch = await createBatch(specFilename, projectName || '未命名项目');
      await startBatch(batch.batch_id);
      onCreated(batch.batch_id);
    } catch (e: any) {
      setError(e.message || '创建失败');
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto animate-in">
      {/* Prompt optimizer CTA */}
      <div
        onClick={onOpenOptimizer}
        className="card p-5 mb-6 cursor-pointer hover:border-[var(--accent)] transition card-interactive"
        style={{ borderColor: 'rgba(16,163,127,0.3)' }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-full flex items-center justify-center"
            style={{ background: 'rgba(16,163,127,0.1)' }}
          >
            <Sparkles className="w-5 h-5" style={{ color: 'var(--accent)' }} />
          </div>
          <div className="flex-1">
            <h3 className="font-semibold">一句话生成产品规格说明书</h3>
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
              用一句话描述需求，AI 自动生成完整的产品规格说明书
            </p>
          </div>
          <Zap className="w-4 h-4" style={{ color: 'var(--accent)' }} />
        </div>
      </div>

      {/* Main form */}
      <div className="card p-8">
        <h2 className="text-xl font-bold mb-1">新建开发批次</h2>
        <p className="text-sm mb-6" style={{ color: 'var(--text-muted)' }}>
          上传规格说明书或直接输入内容，AI Agent 将自动完成：概要设计 → 代码生成 → 单元测试
        </p>

        {/* Mode toggle */}
        <div className="flex mb-6 rounded-lg p-0.5" style={{ background: 'var(--main-secondary)' }}>
          <button
            onClick={() => setMode('upload')}
            className={`flex-1 py-2 text-sm font-medium rounded-md transition ${
              mode === 'upload' ? 'card shadow-sm' : ''
            }`}
            style={{ color: mode === 'upload' ? 'var(--text-primary)' : 'var(--text-muted)' }}
          >
            <Upload className="w-3.5 h-3.5 inline mr-1" />
            上传文件
          </button>
          <button
            onClick={() => setMode('text')}
            className={`flex-1 py-2 text-sm font-medium rounded-md transition ${
              mode === 'text' ? 'card shadow-sm' : ''
            }`}
            style={{ color: mode === 'text' ? 'var(--text-primary)' : 'var(--text-muted)' }}
          >
            <FileText className="w-3.5 h-3.5 inline mr-1" />
            输入内容
          </button>
        </div>

        {/* Upload mode */}
        {mode === 'upload' && (
          <div
            onClick={() => fileInputRef.current?.click()}
            className="border-2 border-dashed rounded-xl p-10 text-center cursor-pointer
              hover:border-[var(--accent)] transition mb-6"
            style={{ borderColor: 'var(--border)' }}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".md,.docx,.pptx,.pdf,.xlsx,.csv,.txt,.html,.htm,.json,.xml,.yaml,.yml,.rst,.org,.adoc,.log"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) {
                  setFile(f);
                  const baseName = f.name.replace(/\.[^.]+$/, '');
                  setProjectName(baseName);
                  setError('');
                }
              }}
            />
            {file ? (
              <div>
                {file.name.endsWith('.docx') ? (
                  <FileText className="w-10 h-10 mx-auto mb-2" style={{ color: '#3b82f6' }} />
                ) : file.name.endsWith('.pptx') ? (
                  <FileType className="w-10 h-10 mx-auto mb-2" style={{ color: '#f59e0b' }} />
                ) : file.name.endsWith('.pdf') ? (
                  <FileText className="w-10 h-10 mx-auto mb-2" style={{ color: '#ef4444' }} />
                ) : file.name.endsWith('.xlsx') || file.name.endsWith('.csv') ? (
                  <FileText className="w-10 h-10 mx-auto mb-2" style={{ color: '#10b981' }} />
                ) : file.name.endsWith('.html') || file.name.endsWith('.htm') ? (
                  <FileText className="w-10 h-10 mx-auto mb-2" style={{ color: '#8b5cf6' }} />
                ) : file.name.endsWith('.json') || file.name.endsWith('.xml') || file.name.endsWith('.yaml') || file.name.endsWith('.yml') ? (
                  <FileText className="w-10 h-10 mx-auto mb-2" style={{ color: '#06b6d4' }} />
                ) : (
                  <FileText className="w-10 h-10 mx-auto mb-2" style={{ color: 'var(--accent)' }} />
                )}
                <p className="text-base font-medium">{file.name}</p>
                <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                  {(file.size / 1024).toFixed(1)} KB
                  {!file.name.endsWith('.md') && (
                    <span className="ml-2 px-1.5 py-0.5 rounded text-xs"
                      style={{ background: 'rgba(16,163,127,0.1)', color: 'var(--accent)' }}>
                      AI 自动解析
                    </span>
                  )}
                </p>
              </div>
            ) : (
              <div>
                <Upload className="w-10 h-10 mx-auto mb-2" style={{ color: 'var(--text-muted)' }} />
                <p style={{ color: 'var(--text-muted)' }}>拖拽或点击上传规格说明书</p>
                <p className="text-xs mt-2 leading-relaxed" style={{ color: 'var(--text-secondary)', maxWidth: 400, margin: '0 auto' }}>
                  支持格式：Markdown (.md) · Word (.docx) · PPT (.pptx) · PDF (.pdf)<br />
                  Excel (.xlsx) · CSV · TXT · HTML · JSON · XML · YAML · RST · Org · AsciiDoc
                </p>
                <p className="text-xs mt-1" style={{ color: 'var(--accent)', opacity: 0.8 }}>
                  Office / PDF 等非 Markdown 文件将自动由 AI 转为结构化规格书
                </p>
              </div>
            )}
          </div>
        )}

        {/* Text mode */}
        {mode === 'text' && (
          <div className="mb-6">
            <textarea
              value={specText}
              onChange={(e) => setSpecText(e.target.value)}
              placeholder="在这里粘贴或输入产品规格说明书内容（Markdown 格式）..."
              className="input resize-none"
              rows={10}
            />
          </div>
        )}

        {/* Project name */}
        <div className="mb-6">
          <label className="text-sm font-medium mb-2 block" style={{ color: 'var(--text-secondary)' }}>
            项目名称
          </label>
          <input
            type="text"
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            placeholder="输入项目名称..."
            className="input"
          />
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 p-3 rounded-lg text-sm" style={{ background: 'rgba(239,68,68,0.12)', color: '#f87171', border: '1px solid rgba(239,68,68,0.25)' }}>
            {error}
          </div>
        )}

        {/* Submit */}
        <button
          onClick={handleSubmit}
          disabled={creating || (mode === 'upload' && !file) || (mode === 'text' && !specText.trim())}
          className="btn btn-primary w-full py-3 text-base"
          style={{ opacity: creating ? 0.6 : 1 }}
        >
          <Play className="w-4 h-4" />
          {creating ? '创建并启动中...' : '创建并启动'}
        </button>
      </div>

      {/* Recent batches */}
      {batches.length > 0 && (
        <div className="mt-8">
          <h3 className="text-base font-semibold mb-3">最近批次</h3>
          <div className="space-y-2">
            {batches.slice(0, 5).map((b) => (
              <button
                key={b.batch_id}
                onClick={() => onSelectBatch(b.batch_id)}
                className="w-full text-left p-3 rounded-lg card card-interactive flex justify-between items-center"
              >
                <div>
                  <span className="font-medium text-sm">{b.project_name}</span>
                  <span className="text-xs ml-2 font-mono" style={{ color: 'var(--text-muted)' }}>
                    {b.batch_id.split('_').slice(-1)}
                  </span>
                </div>
                <span
                  className="text-xs px-2 py-0.5 rounded-full"
                  style={{
                    background:
                      b.status === 'completed' ? 'rgba(16,163,127,0.1)' :
                      b.status === 'running' ? 'rgba(59,130,246,0.1)' :
                      b.status === 'failed' ? 'rgba(239,68,68,0.1)' :
                      'var(--main-secondary)',
                    color:
                      b.status === 'completed' ? '#10a37f' :
                      b.status === 'running' ? '#3b82f6' :
                      b.status === 'failed' ? '#ef4444' :
                      'var(--text-muted)',
                  }}
                >
                  {b.status}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
