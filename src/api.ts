import type { WorkflowState } from './types';

const DEFAULT_BASE_URL = 'https://silver-refinement-agent-mkqutd4koq-uc.a.run.app';

export const apiConfig = {
  baseUrl: import.meta.env.VITE_SILVER_API_URL ?? DEFAULT_BASE_URL,
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiConfig.baseUrl}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Backend ${response.status}: ${detail}`);
  }

  return response.json() as Promise<T>;
}

export const silverApi = {
  health: () => request<{ status: string; module: string; version: string }>('/health'),

  createWorkflow: (payload: unknown) =>
    request<unknown>('/silver-workflows', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  generateMapping: (workflowId: string, payload: unknown) =>
    request<unknown>(`/silver-workflows/${workflowId}/mapping-recommendations`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  submitDataproc: (executionId: string) =>
    request<unknown>(`/executions/${executionId}/submit`, {
      method: 'POST',
    }),
};

export function demoWorkflowPatch(action: string): Partial<WorkflowState> {
  const now = new Date().toISOString().slice(11, 19);
  return { lastAction: `${action} · ${now}`, error: undefined };
}

