import { useState, useRef } from 'react';
import { Send, Paperclip, X, FileText } from 'lucide-react';

interface Props {
  onSend: (text: string, file?: File) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: Props) {
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function handleSubmit() {
    if (disabled) return;
    if (!text.trim() && !file) return;
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
          <span className="text-xs truncate" style={{ color: '#c0c0c0' }}>{file.name}</span>
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
          accept=".md"
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
          title="上传 Markdown 文件"
        >
          <Paperclip className="w-5 h-5" />
        </button>
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入消息，或上传 .md 规格说明书..."
          className="chat-text-input"
          disabled={disabled}
        />
        <button
          onClick={handleSubmit}
          disabled={disabled || (!text.trim() && !file)}
          className="chat-send-btn"
        >
          <Send className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
