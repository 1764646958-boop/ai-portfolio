import { defineStore } from 'pinia';
import api from '@/utils/api';
import type {
  QuoteComparison,
  QuoteComparisonListItem,
  StandardListVersion,
} from '@/types/procurement';

const errorMessage = (error: any, fallback: string) =>
  error?.response?.data?.detail || error?.message || fallback;

export const useProcurementStore = defineStore('procurement', {
  state: () => ({
    standards: [] as StandardListVersion[],
    comparisons: [] as QuoteComparisonListItem[],
    activeComparison: null as QuoteComparison | null,
    loading: false,
    uploadingStandard: false,
    comparing: false,
    downloading: false,
  }),

  actions: {
    async loadStandards() {
      try {
        const response = await api.get<StandardListVersion[]>('/procurement/standards');
        this.standards = response.data;
      } catch (error: any) {
        throw new Error(errorMessage(error, '加载标准清单失败'));
      }
    },

    async loadComparisons() {
      try {
        const response = await api.get<QuoteComparisonListItem[]>('/procurement/comparisons');
        this.comparisons = response.data;
      } catch (error: any) {
        throw new Error(errorMessage(error, '加载报价对比历史失败'));
      }
    },

    async loadWorkspace() {
      this.loading = true;
      try {
        await Promise.all([this.loadStandards(), this.loadComparisons()]);
        if (!this.activeComparison && this.comparisons.length) {
          await this.loadComparison(this.comparisons[0].id);
        }
      } finally {
        this.loading = false;
      }
    },

    async uploadStandard(versionName: string, file: File) {
      this.uploadingStandard = true;
      try {
        const form = new FormData();
        form.append('version_name', versionName);
        form.append('file', file);
        const response = await api.post<StandardListVersion>('/procurement/standards', form);
        this.standards.unshift(response.data);
        return response.data;
      } catch (error: any) {
        throw new Error(errorMessage(error, '上传标准清单失败'));
      } finally {
        this.uploadingStandard = false;
      }
    },

    async createComparison(standardVersionId: number, file: File) {
      this.comparing = true;
      try {
        const form = new FormData();
        form.append('standard_version_id', String(standardVersionId));
        form.append('file', file);
        const response = await api.post<QuoteComparison>('/procurement/comparisons', form, {
          timeout: 120000,
        });
        this.activeComparison = response.data;
        await this.loadComparisons();
        return response.data;
      } catch (error: any) {
        throw new Error(errorMessage(error, '生成报价对比失败'));
      } finally {
        this.comparing = false;
      }
    },

    async loadComparison(comparisonId: number) {
      try {
        const response = await api.get<QuoteComparison>(`/procurement/comparisons/${comparisonId}`);
        this.activeComparison = response.data;
      } catch (error: any) {
        throw new Error(errorMessage(error, '加载报价对比报告失败'));
      }
    },

    async downloadReport(comparisonId: number) {
      this.downloading = true;
      try {
        const response = await api.get(`/procurement/comparisons/${comparisonId}/report`, {
          responseType: 'blob',
        });
        const url = URL.createObjectURL(response.data);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = `报价对比报告-${comparisonId}.xlsx`;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        URL.revokeObjectURL(url);
      } catch (error: any) {
        throw new Error(errorMessage(error, '下载报价对比报告失败'));
      } finally {
        this.downloading = false;
      }
    },
  },
});
