export type ComparisonStatus =
  | 'increase'
  | 'decrease'
  | 'unchanged'
  | 'pending_baseline'
  | 'new_item'
  | 'missing_quote';

export interface StandardListVersion {
  id: number;
  version_name: string;
  original_filename: string;
  file_hash: string;
  item_count: number;
  created_at: string;
}

export interface ComparisonSummary {
  total: number;
  changed: number;
  increase: number;
  decrease: number;
  unchanged: number;
  pending_baseline: number;
  new_item: number;
  missing_quote: number;
}

export interface ComparisonItem {
  row: number;
  sequence: string;
  name: string;
  description: string;
  unit: string;
  baseline_price: string | null;
  quoted_price: string | null;
  difference: string | null;
  percentage: string | null;
  status: ComparisonStatus;
  status_label: string;
}

export interface QuoteComparisonListItem {
  id: number;
  standard_version_id: number;
  standard_version_name: string;
  original_filename: string;
  summary: ComparisonSummary;
  created_at: string;
}

export interface QuoteComparison extends QuoteComparisonListItem {
  items: ComparisonItem[];
}
