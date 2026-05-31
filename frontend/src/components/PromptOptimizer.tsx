import { useState } from 'react';
import { Sparkles, Copy, Check, Play, RefreshCw, X, Edit3, Eye } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface ChatQA {
  question: string;
  answer: string;
  resolved: boolean;
}

type OptimizerMode = 'standard' | 'sisyphus';

interface Props {
  onImport: (spec: string) => void;
  onClose: () => void;
}

export function PromptOptimizer({ onImport, onClose }: Props) {
  const [input, setInput] = useState('');
  const [mode, setMode] = useState<OptimizerMode>('sisyphus');
  const [spec, setSpec] = useState('');
  const [qaList, setQaList] = useState<ChatQA[]>([]);
  const [round, setRound] = useState(0);
  const [readinessScore, setReadinessScore] = useState(0);
  const [coverageSummary, setCoverageSummary] = useState('');
  const [isComplete, setIsComplete] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  const [showPreview, setShowPreview] = useState(true);
  const maxRounds = 8;

  const pendingQuestions = qaList.filter((qa) => !qa.resolved);
  const canContinueSisyphus = mode === 'sisyphus' && !!spec && pendingQuestions.length === 0;

  async function handleOptimize() {
    if (!input.trim() || loading) return;
    setLoading(true);
    setError('');
    try {
      const res = await fetch('/api/prompt/optimize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: input.trim(), mode, max_rounds: maxRounds }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || '请求失败');
      const data = await res.json();
      setSpec(data.spec);
      setQaList((data.questions || []).map((q: string) => ({ question: q, answer: '', resolved: false })));
      setRound(data.round || 1);
      setReadinessScore(data.readiness_score || 0);
      setCoverageSummary(data.coverage_summary || '');
      setIsComplete(!!data.is_complete);
    } catch (e: any) {
      setError(e.message || '生成失败');
    } finally {
      setLoading(false);
    }
  }

  async function handleRefine(forceQuestions = false) {
    const unresolved = qaList.filter((qa) => !qa.resolved && qa.answer.trim());
    if (unresolved.length === 0 && !forceQuestions) return;
    if (loading) return;
    setLoading(true);
    setError('');
    try {
      const res = await fetch('/api/prompt/refine', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          spec,
          answers: unresolved.map((qa) => qa.answer),
          questions: unresolved.map((qa) => qa.question),
          mode,
          round,
          max_rounds: maxRounds,
          force_questions: forceQuestions,
          qa_history: qaList
            .filter((qa) => qa.resolved && qa.answer.trim())
            .map((qa) => ({ question: qa.question, answer: qa.answer })),
        }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || '完善失败');
      const data = await res.json();
      setSpec(data.spec);
      // Mark resolved questions and add new ones
      const newQaList = qaList.map((qa) =>
        qa.answer.trim() ? { ...qa, resolved: true } : qa
      );
      (data.questions || []).forEach((q: string) => {
        newQaList.push({ question: q, answer: '', resolved: false });
      });
      setQaList(newQaList);
      setRound(data.round || round + 1);
      setReadinessScore(data.readiness_score || 0);
      setCoverageSummary(data.coverage_summary || '');
      setIsComplete(!!data.is_complete);
    } catch (e: any) {
      setError(e.message || '完善失败');
    } finally {
      setLoading(false);
    }
  }

  function handleCopy() {
    navigator.clipboard.writeText(spec);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal-content animate-in">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b" style={{ borderColor: 'var(--border)' }}>
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5" style={{ color: 'var(--accent)' }} />
            <h2 className="text-lg font-semibold">启发式生成产品规格说明书</h2>
          </div>
          <button onClick={onClose} className="p-1 rounded-md hover:bg-gray-800 transition">
            <X className="w-5 h-5" style={{ color: 'var(--text-secondary)' }} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4" style={{ maxHeight: '60vh' }}>
          {/* Input area */}
          <div>
            <label className="text-sm font-medium mb-2 block" style={{ color: 'var(--text-secondary)' }}>
              用一句话描述你想要开发的应用
            </label>
            <div className="flex mb-3 rounded-lg p-0.5" style={{ background: 'var(--main-secondary)' }}>
              <button
                onClick={() => setMode('standard')}
                className={`flex-1 py-2 text-sm font-medium rounded-md transition ${mode === 'standard' ? 'card shadow-sm' : ''}`}
                style={{ color: mode === 'standard' ? 'var(--text-primary)' : 'var(--text-muted)' }}
                disabled={loading}
              >
                标准模式
              </button>
              <button
                onClick={() => setMode('sisyphus')}
                className={`flex-1 py-2 text-sm font-medium rounded-md transition ${mode === 'sisyphus' ? 'card shadow-sm' : ''}`}
                style={{ color: mode === 'sisyphus' ? 'var(--text-primary)' : 'var(--text-muted)' }}
                disabled={loading}
              >
                西西弗斯模式
              </button>
            </div>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="例如：我想做一个员工临时车辆预约系统，支持多园区、车牌识别和提前缴费..."
              className="input resize-none"
              rows={3}
              disabled={loading}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                  handleOptimize();
                }
              }}
            />
            <button
              onClick={handleOptimize}
              disabled={!input.trim() || loading}
              className="btn btn-primary mt-3 w-full"
            >
              {loading ? (
                <>
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  生成规格说明书
                </>
              )}
            </button>
          </div>

          {error && (
            <div className="p-3 rounded-lg text-sm" style={{ background: 'rgba(239,68,68,0.12)', color: '#f87171', border: '1px solid rgba(239,68,68,0.25)' }}>
              {error}
            </div>
          )}

          {/* Spec preview */}
          {spec && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
                  生成结果
                </span>
                <div className="flex gap-1">
                  <button
                    onClick={() => setShowPreview(!showPreview)}
                    className="p-1.5 rounded-md hover:bg-gray-800 transition text-xs flex items-center gap-1"
                    style={{ color: 'var(--text-secondary)' }}
                  >
                    {showPreview ? <><Edit3 className="w-3.5 h-3.5" /> 编辑</> : <><Eye className="w-3.5 h-3.5" /> 预览</>}
                  </button>
                  <button
                    onClick={handleCopy}
                    className="p-1.5 rounded-md hover:bg-gray-800 transition text-xs flex items-center gap-1"
                    style={{ color: copied ? 'var(--accent)' : 'var(--text-secondary)' }}
                  >
                    {copied ? <><Check className="w-3.5 h-3.5" /> 已复制</> : <><Copy className="w-3.5 h-3.5" /> 复制</>}
                  </button>
                </div>
              </div>
              {showPreview ? (
                <div
                  className="markdown-body overflow-y-auto"
                  style={{
                    background: '#1e1e2e',
                    border: '1px solid #2d2d3d',
                    borderRadius: '8px',
                    padding: '16px',
                    maxHeight: '300px',
                  }}
                >
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{spec}</ReactMarkdown>
                </div>
              ) : (
                <textarea
                  value={spec}
                  onChange={(e) => setSpec(e.target.value)}
                  className="input resize-none"
                  rows={12}
                  style={{ fontFamily: 'monospace', fontSize: '13px', maxHeight: '300px' }}
                />
              )}
            </div>
          )}

          {spec && mode === 'sisyphus' && (
            <div className="grid grid-cols-3 gap-2">
              <div className="p-3 rounded-lg" style={{ background: 'var(--main-secondary)', border: '1px solid var(--border)' }}>
                <div className="text-xs" style={{ color: 'var(--text-muted)' }}>轮次</div>
                <div className="text-lg font-semibold">{round}/{maxRounds}</div>
              </div>
              <div className="p-3 rounded-lg" style={{ background: 'var(--main-secondary)', border: '1px solid var(--border)' }}>
                <div className="text-xs" style={{ color: 'var(--text-muted)' }}>准备度</div>
                <div className="text-lg font-semibold">{readinessScore}%</div>
              </div>
              <div className="p-3 rounded-lg" style={{ background: 'var(--main-secondary)', border: '1px solid var(--border)' }}>
                <div className="text-xs" style={{ color: 'var(--text-muted)' }}>状态</div>
                <div className="text-sm font-semibold">{isComplete ? '可进入流水线' : '继续澄清'}</div>
              </div>
              {coverageSummary && (
                <div className="col-span-3 p-3 rounded-lg text-sm" style={{ background: 'rgba(16,163,127,0.08)', border: '1px solid rgba(16,163,127,0.18)', color: 'var(--text-secondary)' }}>
                  {coverageSummary}
                </div>
              )}
            </div>
          )}

          {/* Follow-up questions */}
          {(qaList.length > 0 || canContinueSisyphus) && (
            <div className="space-y-3">
              <span className="text-sm font-medium block" style={{ color: 'var(--text-secondary)' }}>
                帮我完善需求
              </span>
              {qaList.map((qa, idx) => (
                <div key={idx} className={`p-3 rounded-lg ${qa.resolved ? 'opacity-50' : ''}`} style={{ background: 'var(--main-secondary)', border: '1px solid var(--border)' }}>
                  <div className="flex items-start gap-2 mb-2">
                    <div
                      className="w-6 h-6 rounded-full flex items-center justify-center text-xs text-white flex-shrink-0"
                      style={{ background: 'var(--accent)' }}
                    >
                      AI
                    </div>
                    <span className="text-sm">{qa.question}</span>
                  </div>
                  <div className="flex items-start gap-2">
                    <div
                      className="w-6 h-6 rounded-full flex items-center justify-center text-xs text-white flex-shrink-0"
                      style={{ background: '#6b6b6b' }}
                    >
                      你
                    </div>
                    <input
                      type="text"
                      value={qa.answer}
                      onChange={(e) => {
                        const updated = [...qaList];
                        updated[idx] = { ...updated[idx], answer: e.target.value };
                        setQaList(updated);
                      }}
                      placeholder={qa.resolved ? '已回答' : '输入你的回答...'}
                      disabled={qa.resolved || loading}
                      className="input py-2 text-sm"
                    />
                  </div>
                </div>
              ))}
              {qaList.some((qa) => !qa.resolved && qa.answer.trim()) && (
                <button
                  onClick={() => handleRefine(false)}
                  disabled={loading}
                  className="btn btn-primary w-full"
                >
                  {loading ? (
                    <>
                      <span className="typing-dot" />
                      <span className="typing-dot" />
                      <span className="typing-dot" />
                    </>
                  ) : (
                    <>
                      <RefreshCw className="w-4 h-4" />
                      更新规格说明书
                    </>
                  )}
                </button>
              )}
              {canContinueSisyphus && (
                <button
                  onClick={() => handleRefine(true)}
                  disabled={loading || round >= maxRounds}
                  className="btn w-full"
                >
                  {loading ? (
                    <>
                      <span className="typing-dot" />
                      <span className="typing-dot" />
                      <span className="typing-dot" />
                    </>
                  ) : (
                    <>
                      <RefreshCw className="w-4 h-4" />
                      继续启发式追问
                    </>
                  )}
                </button>
              )}
            </div>
          )}
        </div>

        {/* Footer actions */}
        {spec && (
          <div className="flex gap-3 p-5 border-t" style={{ borderColor: 'var(--border)' }}>
            <button onClick={handleCopy} className="btn flex-1">
              <Copy className="w-4 h-4" />
              复制内容
            </button>
            <button onClick={() => onImport(spec)} className="btn btn-primary flex-1">
              <Play className="w-4 h-4" />
              直接导入并开始流程
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
