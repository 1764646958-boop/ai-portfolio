<template>
  <div class="procurement-page">
    <header class="procurement-header">
      <div>
        <span class="panel-eyebrow">采购核价</span>
        <h1>报价对比</h1>
        <p>以已发布的标准清单为基准，核对“装饰直接费”明细项的单价变化。</p>
      </div>
      <button class="secondary-btn" type="button" :disabled="store.loading" @click="refreshWorkspace">
        <i class="fa-solid fa-rotate" :class="{ 'fa-spin': store.loading }"></i>
        刷新
      </button>
    </header>

    <section class="workflow-grid" :class="{ 'single-column': !authStore.isAdmin }">
      <article v-if="authStore.isAdmin" class="workflow-card standard-card">
        <div class="card-heading">
          <span class="step-mark">01</span>
          <div>
            <h2>发布标准清单</h2>
            <p>管理员维护不可变的甲方核定价版本。</p>
          </div>
        </div>
        <label class="field-label">
          <span>版本名称</span>
          <input v-model="versionName" type="text" maxlength="120" placeholder="例如：2026-Q3 建店标准价" />
        </label>
        <label class="file-drop" :class="{ selected: standardFile }">
          <input type="file" accept=".xlsx" @change="onStandardFileChange" />
          <i class="fa-regular fa-file-excel"></i>
          <span>
            <strong>{{ standardFile?.name || '选择标准采购清单' }}</strong>
            <small>仅支持 .xlsx，读取“装饰直接费”F列</small>
          </span>
        </label>
        <button
          class="primary-btn"
          type="button"
          :disabled="!versionName.trim() || !standardFile || store.uploadingStandard"
          @click="uploadStandard"
        >
          <i :class="store.uploadingStandard ? 'fa-solid fa-spinner fa-spin' : 'fa-solid fa-cloud-arrow-up'"></i>
          {{ store.uploadingStandard ? '正在解析…' : '发布标准版本' }}
        </button>
      </article>

      <article class="workflow-card quote-card">
        <div class="card-heading">
          <span class="step-mark">{{ authStore.isAdmin ? '02' : '01' }}</span>
          <div>
            <h2>上传供应商报价</h2>
            <p>选择对应标准版本，立即生成确定性价格报告。</p>
          </div>
        </div>
        <label class="field-label">
          <span>标准清单版本</span>
          <select v-model.number="selectedStandardId" :disabled="!store.standards.length">
            <option :value="null" disabled>{{ store.standards.length ? '请选择版本' : '暂无可用标准版本' }}</option>
            <option v-for="standard in store.standards" :key="standard.id" :value="standard.id">
              {{ standard.version_name }} · {{ standard.item_count }} 项
            </option>
          </select>
        </label>
        <label class="file-drop" :class="{ selected: quoteFile }">
          <input type="file" accept=".xlsx" @change="onQuoteFileChange" />
          <i class="fa-solid fa-file-invoice-dollar"></i>
          <span>
            <strong>{{ quoteFile?.name || '选择供应商报价单' }}</strong>
            <small>供应商应只覆盖既有明细项的 F 列价格</small>
          </span>
        </label>
        <button
          class="primary-btn"
          type="button"
          :disabled="!selectedStandardId || !quoteFile || store.comparing"
          @click="createComparison"
        >
          <i :class="store.comparing ? 'fa-solid fa-spinner fa-spin' : 'fa-solid fa-code-compare'"></i>
          {{ store.comparing ? '正在逐项核对…' : '生成对比报告' }}
        </button>
      </article>
    </section>

    <section v-if="store.activeComparison" class="report-section">
      <div class="report-toolbar">
        <div>
          <span class="report-kicker">REPORT #{{ store.activeComparison.id }}</span>
          <h2>{{ store.activeComparison.original_filename }}</h2>
          <p>
            基准：{{ store.activeComparison.standard_version_name }}
            · {{ formatDate(store.activeComparison.created_at) }}
          </p>
        </div>
        <button
          class="download-btn"
          type="button"
          :disabled="store.downloading"
          @click="downloadActiveReport"
        >
          <i :class="store.downloading ? 'fa-solid fa-spinner fa-spin' : 'fa-solid fa-download'"></i>
          下载完整 Excel
        </button>
      </div>

      <div class="summary-grid">
        <button type="button" :class="['summary-card', 'changed', { active: activeFilter === 'all' }]" @click="activeFilter = 'all'">
          <span>价格变动</span>
          <strong>{{ store.activeComparison.summary.changed }}</strong>
          <small>涨价与降价合计</small>
        </button>
        <button type="button" :class="['summary-card', 'increase', { active: activeFilter === 'increase' }]" @click="activeFilter = 'increase'">
          <span>涨价</span>
          <strong>{{ store.activeComparison.summary.increase }}</strong>
          <small>报价高于核定价</small>
        </button>
        <button type="button" :class="['summary-card', 'decrease', { active: activeFilter === 'decrease' }]" @click="activeFilter = 'decrease'">
          <span>降价</span>
          <strong>{{ store.activeComparison.summary.decrease }}</strong>
          <small>报价低于核定价</small>
        </button>
        <button type="button" :class="['summary-card', 'pending', { active: activeFilter === 'pending_baseline' }]" @click="activeFilter = 'pending_baseline'">
          <span>待核定价</span>
          <strong>{{ store.activeComparison.summary.pending_baseline }}</strong>
          <small>甲方暂无有效基准</small>
        </button>
        <button type="button" :class="['summary-card', 'new-item', { active: activeFilter === 'new_item' }]" @click="activeFilter = 'new_item'">
          <span>新增项目</span>
          <strong>{{ store.activeComparison.summary.new_item }}</strong>
          <small>标准清单末尾新增</small>
        </button>
      </div>

      <div class="report-table-card">
        <div class="table-heading">
          <div>
            <h3>{{ filterTitle }}</h3>
            <p>网页仅展示变化和异常项目；未变化项目保留在下载报告中。</p>
          </div>
          <span>{{ visibleItems.length }} 项</span>
        </div>
        <div v-if="visibleItems.length" class="table-scroll">
          <table>
            <thead>
              <tr>
                <th>状态</th>
                <th>序号</th>
                <th>项目名称</th>
                <th>单位</th>
                <th>甲方核定价</th>
                <th>供应商报价</th>
                <th>差额</th>
                <th>涨跌幅</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in visibleItems" :key="`${item.row}-${item.status}`">
                <td><span :class="['status-pill', item.status]">{{ item.status_label }}</span></td>
                <td>{{ item.sequence || '—' }}</td>
                <td>
                  <strong>{{ item.name }}</strong>
                  <small v-if="item.description">{{ item.description }}</small>
                </td>
                <td>{{ item.unit || '—' }}</td>
                <td>{{ formatMoney(item.baseline_price) }}</td>
                <td>{{ formatMoney(item.quoted_price) }}</td>
                <td :class="differenceClass(item.difference)">{{ formatSignedMoney(item.difference) }}</td>
                <td :class="differenceClass(item.percentage)">{{ formatPercentage(item.percentage) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="empty-report">
          <i class="fa-solid fa-circle-check"></i>
          <strong>当前分类没有项目</strong>
          <p>切换上方分类查看其他结果。</p>
        </div>
      </div>
    </section>

    <section class="history-section">
      <div class="section-heading">
        <div>
          <span class="panel-eyebrow">历史记录</span>
          <h2>最近报价对比</h2>
        </div>
        <span>{{ store.comparisons.length }} 份报告</span>
      </div>
      <div v-if="store.comparisons.length" class="history-list">
        <button
          v-for="comparison in store.comparisons"
          :key="comparison.id"
          type="button"
          :class="['history-row', { active: comparison.id === store.activeComparison?.id }]"
          @click="openComparison(comparison.id)"
        >
          <span class="history-icon"><i class="fa-regular fa-file-lines"></i></span>
          <span class="history-copy">
            <strong>{{ comparison.original_filename }}</strong>
            <small>{{ comparison.standard_version_name }} · {{ formatDate(comparison.created_at) }}</small>
          </span>
          <span class="history-metrics">
            <b class="up">↑ {{ comparison.summary.increase }}</b>
            <b class="down">↓ {{ comparison.summary.decrease }}</b>
          </span>
          <i class="fa-solid fa-chevron-right"></i>
        </button>
      </div>
      <div v-else class="history-empty">尚未生成报价对比报告。</div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { useProcurementStore } from '@/stores/procurement';
import type { ComparisonStatus } from '@/types/procurement';

const authStore = useAuthStore();
const store = useProcurementStore();
const versionName = ref('');
const standardFile = ref<File | null>(null);
const quoteFile = ref<File | null>(null);
const selectedStandardId = ref<number | null>(null);
const activeFilter = ref<'all' | ComparisonStatus>('all');

const visibleItems = computed(() => {
  const items = store.activeComparison?.items || [];
  if (activeFilter.value === 'all') return items.filter((item) => item.status !== 'unchanged');
  return items.filter((item) => item.status === activeFilter.value);
});

const filterTitle = computed(() => ({
  all: '全部变化与异常',
  increase: '涨价项目',
  decrease: '降价项目',
  pending_baseline: '待核定价项目',
  new_item: '新增采购项目',
  missing_quote: '报价缺失项目',
  unchanged: '未变化项目',
}[activeFilter.value]));

watch(
  () => store.standards,
  (standards) => {
    if (!selectedStandardId.value && standards.length) selectedStandardId.value = standards[0].id;
  },
  { deep: true }
);

const onStandardFileChange = (event: Event) => {
  standardFile.value = (event.target as HTMLInputElement).files?.[0] || null;
};

const onQuoteFileChange = (event: Event) => {
  quoteFile.value = (event.target as HTMLInputElement).files?.[0] || null;
};

const uploadStandard = async () => {
  if (!standardFile.value || !versionName.value.trim()) return;
  try {
    const standard = await store.uploadStandard(versionName.value.trim(), standardFile.value);
    selectedStandardId.value = standard.id;
    versionName.value = '';
    standardFile.value = null;
  } catch (error: any) {
    alert(error.message);
  }
};

const createComparison = async () => {
  if (!selectedStandardId.value || !quoteFile.value) return;
  try {
    await store.createComparison(selectedStandardId.value, quoteFile.value);
    activeFilter.value = 'all';
    quoteFile.value = null;
  } catch (error: any) {
    alert(error.message);
  }
};

const refreshWorkspace = async () => {
  try {
    await store.loadWorkspace();
  } catch (error: any) {
    alert(error.message);
  }
};

const openComparison = async (comparisonId: number) => {
  try {
    await store.loadComparison(comparisonId);
    activeFilter.value = 'all';
  } catch (error: any) {
    alert(error.message);
  }
};

const downloadActiveReport = async () => {
  if (!store.activeComparison) return;
  try {
    await store.downloadReport(store.activeComparison.id);
  } catch (error: any) {
    alert(error.message);
  }
};

const formatDate = (value: string) => new Date(value).toLocaleString('zh-CN', {
  year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
});

const formatMoney = (value: string | null) => value === null ? '—' : `¥${Number(value).toFixed(2)}`;
const formatSignedMoney = (value: string | null) => {
  if (value === null) return '—';
  const amount = Number(value);
  return `${amount > 0 ? '+' : ''}¥${amount.toFixed(2)}`;
};
const formatPercentage = (value: string | null) => {
  if (value === null) return '—';
  const amount = Number(value);
  return `${amount > 0 ? '+' : ''}${amount.toFixed(2)}%`;
};
const differenceClass = (value: string | null) => {
  const amount = Number(value || 0);
  return amount > 0 ? 'value-up' : amount < 0 ? 'value-down' : '';
};

onMounted(refreshWorkspace);
</script>

<style scoped>
.procurement-page { height: 100%; overflow-y: auto; padding: 34px 38px 56px; background: var(--surface-soft); }
.procurement-header, .report-toolbar, .section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; }
.panel-eyebrow, .report-kicker { display: block; margin-bottom: 8px; color: var(--mint-strong); font-size: 10px; font-weight: 800; letter-spacing: .16em; text-transform: uppercase; }
.procurement-header h1 { font-size: 30px; letter-spacing: -.04em; }
.procurement-header p, .report-toolbar p, .card-heading p, .table-heading p { margin-top: 7px; color: var(--muted); font-size: 13px; }
.secondary-btn, .download-btn, .primary-btn { display: inline-flex; align-items: center; justify-content: center; gap: 8px; border-radius: 10px; cursor: pointer; font-weight: 700; }
.secondary-btn { padding: 10px 15px; border: 1px solid var(--line); color: var(--text); background: var(--surface); }
.workflow-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-top: 26px; }
.workflow-grid.single-column { grid-template-columns: minmax(0, 680px); }
.workflow-card { padding: 22px; border: 1px solid var(--line); border-radius: 16px; background: var(--surface); box-shadow: var(--card-shadow); }
.card-heading { display: flex; gap: 14px; align-items: flex-start; margin-bottom: 20px; }
.card-heading h2 { font-size: 17px; }
.step-mark { display: grid; width: 38px; height: 38px; flex: 0 0 38px; place-items: center; border-radius: 10px; color: #fff; background: var(--text); font-size: 11px; font-weight: 800; letter-spacing: .08em; }
.field-label { display: grid; gap: 7px; margin-bottom: 14px; color: var(--text-soft); font-size: 12px; font-weight: 700; }
.field-label input, .field-label select { width: 100%; height: 42px; padding: 0 12px; border: 1px solid var(--line); border-radius: 9px; color: var(--text); background: var(--surface-soft); }
.file-drop { position: relative; display: flex; min-height: 82px; align-items: center; gap: 14px; padding: 15px; border: 1px dashed var(--line-strong); border-radius: 12px; cursor: pointer; background: var(--surface-soft); }
.file-drop.selected { border-color: var(--mint); background: #f6f2e9; }
.file-drop input { position: absolute; width: 1px; height: 1px; opacity: 0; }
.file-drop > i { color: var(--mint-strong); font-size: 24px; }
.file-drop span { display: grid; gap: 4px; min-width: 0; }
.file-drop strong { overflow: hidden; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.file-drop small { color: var(--muted); font-size: 11px; }
.primary-btn { width: 100%; min-height: 42px; margin-top: 14px; color: #fff; background: var(--text); }
.report-section, .history-section { margin-top: 22px; padding: 24px; border: 1px solid var(--line); border-radius: 16px; background: var(--surface); box-shadow: var(--card-shadow); }
.report-toolbar h2 { font-size: 20px; }
.download-btn { padding: 11px 16px; color: #fff; background: var(--mint-strong); }
.summary-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin-top: 22px; }
.summary-card { display: grid; gap: 4px; padding: 15px; border: 1px solid var(--line); border-radius: 12px; text-align: left; cursor: pointer; background: var(--surface-soft); }
.summary-card:hover, .summary-card.active { border-color: var(--mint); transform: translateY(-1px); }
.summary-card span { color: var(--muted); font-size: 11px; font-weight: 700; }
.summary-card strong { font-size: 24px; }
.summary-card small { color: var(--muted); font-size: 10px; }
.summary-card.increase strong, .value-up, .history-metrics .up { color: #b4493f; }
.summary-card.decrease strong, .value-down, .history-metrics .down { color: #4d7658; }
.summary-card.pending strong { color: #9a6b2f; }
.summary-card.new-item strong { color: #4f64a5; }
.report-table-card { margin-top: 18px; overflow: hidden; border: 1px solid var(--line); border-radius: 13px; }
.table-heading { display: flex; align-items: center; justify-content: space-between; padding: 16px 18px; border-bottom: 1px solid var(--line); }
.table-heading h3 { font-size: 15px; }
.table-heading > span { color: var(--muted); font-size: 12px; }
.table-scroll { overflow-x: auto; }
table { width: 100%; min-width: 920px; border-collapse: collapse; }
th, td { padding: 13px 12px; border-bottom: 1px solid var(--line); text-align: left; font-size: 12px; vertical-align: top; }
th { color: var(--muted); background: var(--surface-soft); font-size: 10px; letter-spacing: .04em; }
td:nth-child(n+5) { font-variant-numeric: tabular-nums; white-space: nowrap; }
td strong { display: block; max-width: 280px; font-size: 12px; }
td small { display: -webkit-box; max-width: 320px; margin-top: 4px; overflow: hidden; color: var(--muted); font-size: 10px; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.status-pill { display: inline-flex; padding: 4px 8px; border-radius: 999px; font-size: 10px; font-weight: 800; white-space: nowrap; }
.status-pill.increase { color: #9f382f; background: #fce8e6; }
.status-pill.decrease { color: #356641; background: #e6f4ea; }
.status-pill.pending_baseline { color: #855919; background: #fff4ce; }
.status-pill.new_item { color: #40578f; background: #e8f0fe; }
.status-pill.missing_quote { color: #75458d; background: #f3e8fd; }
.empty-report { display: grid; place-items: center; gap: 7px; padding: 42px; color: var(--muted); text-align: center; }
.empty-report i { color: var(--success); font-size: 27px; }
.empty-report strong { color: var(--text); }
.section-heading { align-items: center; margin-bottom: 14px; }
.section-heading h2 { font-size: 18px; }
.section-heading > span { color: var(--muted); font-size: 12px; }
.history-list { display: grid; gap: 8px; }
.history-row { display: grid; grid-template-columns: 38px minmax(0, 1fr) auto 14px; align-items: center; gap: 12px; padding: 12px; border: 1px solid transparent; border-radius: 10px; cursor: pointer; text-align: left; background: var(--surface-soft); }
.history-row:hover, .history-row.active { border-color: var(--line-strong); background: var(--surface-hover); }
.history-icon { display: grid; width: 38px; height: 38px; place-items: center; border-radius: 9px; color: var(--mint-strong); background: var(--surface); }
.history-copy { display: grid; gap: 4px; min-width: 0; }
.history-copy strong { overflow: hidden; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.history-copy small { color: var(--muted); font-size: 10px; }
.history-metrics { display: flex; gap: 10px; font-size: 11px; }
.history-empty { padding: 26px; color: var(--muted); text-align: center; background: var(--surface-soft); border-radius: 10px; }
@media (max-width: 1080px) { .workflow-grid { grid-template-columns: 1fr; } .summary-grid { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 720px) { .procurement-page { padding: 24px 18px 40px; } .procurement-header, .report-toolbar { flex-direction: column; } .summary-grid { grid-template-columns: repeat(2, 1fr); } .download-btn { width: 100%; } }
</style>
