import { useState, useRef, useCallback, useEffect } from 'react';

interface UseVoiceInputReturn {
  isListening: boolean;
  isSupported: boolean;
  toggleListening: () => void;
}

export function useVoiceInput(onResult: (text: string) => void): UseVoiceInputReturn {
  const [isListening, setIsListening] = useState(false);
  const listeningRef = useRef(false);
  const recognitionRef = useRef<any>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const resultCallbackRef = useRef(onResult);

  resultCallbackRef.current = onResult;

  // Check what's available
  const hasSpeechRecognition = typeof window !== 'undefined' &&
    !!(window as any).SpeechRecognition || !!(window as any).webkitSpeechRecognition;
  const hasMediaRecorder = typeof window !== 'undefined' &&
    typeof MediaRecorder !== 'undefined';

  const isSupported = hasSpeechRecognition || hasMediaRecorder;

  const stopAll = useCallback(() => {
    // Stop Web Speech API
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch { }
      recognitionRef.current = null;
    }
    // Stop MediaRecorder
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current = null;
    }
    listeningRef.current = false;
    setIsListening(false);
  }, []);

  // ── Chrome/Edge path: Web Speech API ──
  const startSpeechRecognition = useCallback(() => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) return;

    const recognition = new SR();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'zh-CN';
    let lastFinal = '';

    recognition.onresult = (event: any) => {
      let final = '';
      let interim = '';
      for (let i = 0; i < event.results.length; i++) {
        const r = event.results[i];
        if (r.isFinal) {
          final += r[0].transcript;
        } else {
          interim += r[0].transcript;
        }
      }
      lastFinal = final;
      resultCallbackRef.current(final + interim);
    };

    recognition.onerror = () => stopAll();
    recognition.onend = () => {
      if (listeningRef.current && lastFinal) {
        resultCallbackRef.current(lastFinal);
      }
      listeningRef.current = false;
      setIsListening(false);
      recognitionRef.current = null;
    };

    recognitionRef.current = recognition;
    recognition.start();
    listeningRef.current = true;
    setIsListening(true);
  }, [stopAll]);

  // ── Safari/Firefox path: MediaRecorder → /api/stt ──
  const startMediaRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus' : 'audio/webm';

      const recorder = new MediaRecorder(stream, { mimeType });
      const chunks: Blob[] = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.push(e.data);
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        if (chunks.length === 0) return;

        const blob = new Blob(chunks, { type: mimeType });
        try {
          const form = new FormData();
          form.append('file', blob, `recording.${mimeType.includes('opus') ? 'webm' : 'webm'}`);
          const res = await fetch('/api/stt', { method: 'POST', body: form });
          if (res.ok) {
            const data = await res.json();
            if (data.text) resultCallbackRef.current(data.text);
          }
        } catch {
          // STT server may not be ready yet
        } finally {
          mediaRecorderRef.current = null;
          listeningRef.current = false;
          setIsListening(false);
        }
      };

      mediaRecorderRef.current = recorder;
      recorder.start();
      listeningRef.current = true;
      setIsListening(true);
    } catch {
      // User denied microphone permission
    }
  }, []);

  const toggleListening = useCallback(() => {
    if (listeningRef.current) {
      stopAll();
      return;
    }

    if (hasSpeechRecognition) {
      startSpeechRecognition();
    } else if (hasMediaRecorder) {
      startMediaRecording();
    }
  }, [hasSpeechRecognition, hasMediaRecorder, startSpeechRecognition, startMediaRecording, stopAll]);

  useEffect(() => () => stopAll(), [stopAll]);

  return { isListening, isSupported, toggleListening };
}
