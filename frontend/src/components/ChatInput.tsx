import { useState, useRef, useCallback } from 'react';
import { Play, Send, Square, Paperclip, X, FileText, Mic, MicOff } from 'lucide-react';
import { useVoiceInput } from '../hooks/useVoiceInput';

interface Props {
  onSend: (text: string, file?: File) => void;
  onStop?: () => void;
  disabled?: boolean;
  canStop?: boolean;
  canResume?: boolean;
}

export function ChatInput({ onSend, onStop, disabled, canStop, canResume }: Props) {
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleVoiceResult = useCallback((transcript: string) => {
    setText((prev) => {
      const withoutPrevInterim = prev.replace(/[🎙️🔴🟢].*$/, '').trim();
      return withoutPrevInterim ? `${withoutPrevInterim} ${transcript}` : transcript;
    });
  }, []);

  const { isListening, isSupported, toggleListening } = useVoiceInput(handleVoiceResult);

  function handleSubmit() {
    if (disabled) return;
    if (!text.trim() && !file && !canResume) return;
    onSend(text.trim(), file || undefined);
    setText('');
    setFile(null);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }

  return (
    <div className="chat-input-bar">
      {file && (
        <div className="file-chip">
          <FileText className="w-3.5 h-3.5" style={{ color: 'var(--accent)' }} />
          <span className="text-xs truncate" style={{ color: 'var(--text-secondary)' }}>{file.name}</span>
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            ({(file.size / 1024).toFixed(1)} KB)
          </span>
          <button onClick={() => setFile(null)} className="file-chip-remove">
            <X className="w-3 h-3" />
          </button>
        </div>
      )}
      <div className="chat-input-row">
        <input
          ref={fileInputRef}
          type="file"
            accept=".md,.docx,.pptx,.pdf,.xlsx,.csv,.txt,.html,.htm,.json,.xml,.yaml,.yml,.rst,.org,.adoc,.log"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) setFile(f);
            e.target.value = '';
          }}
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          className="chat-attach-btn"
          title="上传文件"
          disabled={disabled || canStop}
        >
          <Paperclip className="w-5 h-5" />
        </button>
        {isSupported && (
          <button
            onClick={toggleListening}
            className="chat-attach-btn"
            title={isListening ? '停止录音' : '语音输入'}
            disabled={disabled || canStop}
            style={isListening ? { color: '#ef4444' } : {}}
          >
            {isListening ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
          </button>
        )}
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            isListening ? '🎙️ 正在聆听...' :
            canResume ? '输入补充指引后继续，或直接点击继续' :
            '输入消息，或上传文件（支持 15+ 格式）...'
          }
          className="chat-text-input"
          disabled={disabled || canStop}
        />
        {canStop && (
          <button
            onClick={onStop}
            className="chat-stop-btn"
            title="停止当前生成"
            type="button"
          >
            <Square className="w-4 h-4" />
          </button>
        )}
        <button
          onClick={handleSubmit}
          disabled={disabled || canStop || (!text.trim() && !file && !canResume)}
          className="chat-send-btn"
          title={canResume ? '继续运行' : '发送'}
        >
          {canResume ? <Play className="w-4 h-4" /> : <Send className="w-4 h-4" />}
        </button>
      </div>
    </div>
  );
}
