export type Cell = string | number | boolean | null;
export interface Column {
  key: string; name: string; type: 'category'|'boolean'|'number'|'date'|'text'|'identifier';
  coverage: number; distinctCount: number; missingCount: number; sensitive: boolean; queryable: boolean;
  privacyReason: string; distribution: { label: string; count: number }[];
  trueCount?: number; falseCount?: number; min?: number; max?: number; mean?: number;
}
export interface DashboardCard { id: string; title: string; source: string; sql: string; messages: unknown[] }
export interface Dataset {
  id: string; name: string; filename: string; rowCount: number; columnCount: number; inputColumnCount: number;
  excludedCount: number; sizeBytes: number; createdAt: string; sheetName: string|null; isDemo?: boolean;
  columns: Column[]; warnings: string[]; dashboard: DashboardCard[];
}
export interface Result { columns: string[]; rows: Cell[][]; truncated: boolean; elapsedMs: number }
export interface Answer {
  id: string; question: string; kind: 'answer'|'clarification'; title: string; summary: string; choices: string[];
  sql: string|null; result: Result|null; messages: unknown[]; pinned: boolean; attempts: number; plan: string; createdAt: string;
}
export interface Status { authenticated: boolean; passwordRequired: boolean; aiConfigured: boolean; model: string; localMode: boolean; directUploads?: boolean }
export interface Preview { columns: Pick<Column,'key'|'name'|'type'|'sensitive'>[]; rows: Record<string,Cell>[]; total: number; offset: number }
