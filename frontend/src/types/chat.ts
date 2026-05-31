export type MessageRole = 'user' | 'assistant' | 'system';
export type MessageType = 'text' | 'file_upload' | 'pipeline_status' | 'react_log' | 'scoring_report' | 'file_list';

export interface FileAttachment {
  name: string;
  size: number;
}

export interface PipelineNodeStatus {
  node_id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'stopped';
  duration_seconds: number | null;
  output_files: string[];
  quality_score: number | null;
}

export interface ScoringData {
  composite_score: number;
  stars: string;
  design_score: number;
  code_score: number;
  test_score: number;
  repozero_score: number;
}

export interface ReactLogEntry {
  type: 'thought' | 'action' | 'observation';
  agent?: string;
  content: string;
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  type: MessageType;
  content: string;
  file?: FileAttachment;
  pipelineNodes?: PipelineNodeStatus[];
  scoring?: ScoringData;
  reactLogs?: ReactLogEntry[];
  outputFiles?: string[];
  timestamp: string;
  loading?: boolean;
  selectedFile?: string | null;
  fileContent?: string;
  fileLoading?: boolean;
}
