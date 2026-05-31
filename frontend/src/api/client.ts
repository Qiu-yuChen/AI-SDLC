/** API client — REST + WebSocket */

import type { BatchStatus, BatchListItem, WsEvent, ScoringReport } from '../types';

const BASE = '/api';

// ── REST ─────────────────────────────────────────────

export async function uploadSpec(file: File): Promise<{
  filename: string;
  size: number;
  path?: string;
  file_type?: string;
  preprocessed?: boolean;
  original_filename?: string;
  parsed_info?: Record<string, unknown>;
}> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${BASE}/upload-spec`, { method: 'POST', body: form });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function createBatch(specFilename: string, projectName: string): Promise<{ batch_id: string }> {
  const res = await fetch(`${BASE}/batches`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ spec_filename: specFilename, project_name: projectName }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listBatches(): Promise<BatchListItem[]> {
  const res = await fetch(`${BASE}/batches`);
  return res.json();
}

export async function getBatch(batchId: string): Promise<BatchStatus> {
  const res = await fetch(`${BASE}/batches/${batchId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function startBatch(batchId: string): Promise<void> {
  const res = await fetch(`${BASE}/batches/${batchId}/start`, { method: 'POST' });
  if (!res.ok) throw new Error(await res.text());
}

export async function stopBatch(batchId: string): Promise<void> {
  const res = await fetch(`${BASE}/batches/${batchId}/stop`, { method: 'POST' });
  if (!res.ok) throw new Error(await res.text());
}

export async function resumeBatch(batchId: string, guidance = ''): Promise<void> {
  const res = await fetch(`${BASE}/batches/${batchId}/resume`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ guidance }),
  });
  if (!res.ok) throw new Error(await res.text());
}

export async function deleteBatch(batchId: string): Promise<void> {
  const res = await fetch(`${BASE}/batches/${batchId}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(await res.text());
}

export async function executeNext(batchId: string): Promise<void> {
  const res = await fetch(`${BASE}/batches/${batchId}/next`, { method: 'POST' });
  if (!res.ok) throw new Error(await res.text());
}

export async function retryNode(batchId: string, nodeId: string): Promise<void> {
  const res = await fetch(`${BASE}/batches/${batchId}/retry/${nodeId}`, { method: 'POST' });
  if (!res.ok) throw new Error(await res.text());
}

export async function rollbackNode(batchId: string, nodeId: string): Promise<void> {
  const res = await fetch(`${BASE}/batches/${batchId}/rollback/${nodeId}`, { method: 'POST' });
  if (!res.ok) throw new Error(await res.text());
}

export async function fetchScoringReport(batchId: string): Promise<ScoringReport> {
  const res = await fetch(`/workspace/docs/已生成/${batchId}/质量评分/scoring_report.json`);
  if (!res.ok) throw new Error('Report not found');
  return res.json();
}

// ── WebSocket ────────────────────────────────────────

export function connectWs(
  batchId: string,
  onEvent: (event: WsEvent) => void,
  onClose?: () => void
): WebSocket {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const host = window.location.host;
  const url = `${protocol}://${host}/ws/batch/${batchId}/stream`;
  const ws = new WebSocket(url);

  let closed = false;

  ws.onopen = () => {
    // Keep-alive ping
    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send('ping');
      } else {
        clearInterval(pingInterval);
      }
    }, 30000);

    ws.addEventListener('close', () => clearInterval(pingInterval));
  };

  ws.onmessage = (msg) => {
    try {
      const event: WsEvent = JSON.parse(msg.data);
      onEvent(event);
    } catch {
      // ignore malformed messages
    }
  };

  ws.onclose = () => {
    if (!closed) {
      closed = true;
      onClose?.();
    }
  };

  ws.onerror = () => {
    // Error events are followed by close events, handled above
  };

  return ws;
}
