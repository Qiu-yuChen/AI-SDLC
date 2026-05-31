/** Shared types for API and WebSocket events */

export type NodeStatus = 'pending' | 'running' | 'completed' | 'failed' | 'stopped';
export type BatchState = 'created' | 'running' | 'completed' | 'failed' | 'stopped';

export interface NodeInfo {
  node_id: string;
  name: string;
  status: NodeStatus;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  error: string | null;
  quality_score: number | null;
  output_files: string[];
}

export interface BatchStatus {
  batch_id: string;
  project_name: string;
  spec_file: string;
  status: BatchState;
  current_node: string | null;
  mode: 'auto' | 'manual';
  created_at: string;
  updated_at: string;
  nodes: Record<string, NodeInfo>;
}

export interface ScoringReport {
  composite_score: number;
  stars: string;
  design_score: { total_score: number; max_score: number };
  code_score: { total_score: number; max_score: number };
  test_score: { total_score: number; max_score: number };
  repozero_score: { total_score: number; max_score: number };
}

export interface BatchListItem {
  batch_id: string;
  project_name: string;
  status: string;
  current_node: string | null;
  created_at: string;
}

export interface ReActStep {
  thought?: string;
  action?: string;
  action_input?: string;
  observation?: string;
}

// WebSocket events
export type WsEventType =
  | 'node_start'
  | 'node_completed'
  | 'node_failed'
  | 'node_stopped'
  | 'batch_stopped'
  | 'batch_resumed'
  | 'react_step'
  | 'log';

export interface WsEvent {
  type: WsEventType;
  batch_id: string;
  node_id?: string;
  name?: string;
  duration_seconds?: number;
  output_files?: string[];
  error?: string;
  step?: ReActStep;
  message?: string;
  timestamp?: string;
}
