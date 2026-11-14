import fs from 'node:fs';
import vm from 'node:vm';


const [observationsPath, formatPath] = process.argv.slice(2);
if (!observationsPath || !formatPath) {
  throw new Error('Expected observations.js and format.js paths');
}

const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const sandbox = {
  console,
  Intl,
  Date,
  Math,
  Number,
  String,
  Set,
  Map,
  URLSearchParams,
  document: { querySelector: () => ({}) },
  ClearSpendApi: {},
  ClearSpendObservationClient: { loadObservationPayload: () => {} },
};
sandbox.globalThis = sandbox;
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(formatPath, 'utf8'), sandbox, { filename: formatPath });
vm.runInContext('const money=ClearSpendFormat.money;', sandbox);

const marker = 'function renderObservationCards(){';
const source = fs.readFileSync(observationsPath, 'utf8');
if (!source.includes(marker)) throw new Error('Could not locate browser observation seam');
const instrumented = source.replace(
  marker,
  `globalThis.__observationReference={analyzeMonth,analyzeHistoricalPatterns,groupFindings};return;\n${marker}`,
);
vm.runInContext(instrumented, sandbox, { filename: observationsPath });

const { analyzeMonth, analyzeHistoricalPatterns, groupFindings } = sandbox.__observationReference;
const targetMonths = input.targetMonths || [];
const historyMonths = input.historyMonths || [];
const recurringMonths = input.recurringMonths || [];
const transactionsByMonth = new Map(historyMonths.map(month => [
  month,
  (input.transactionsByMonth?.[month] || []).map(item => ({ ...item, _month: month })),
]));
const recurringPayloads = recurringMonths.map(month => input.recurringByMonth?.[month] || {});
const categoryHistory = new Map([...transactionsByMonth].map(([month, transactions]) => {
  const routine = transactions.filter(item => !item.event_id);
  const grouped = new Map();
  routine.forEach(item => {
    const amount = Number(item.personal_amount ?? item.amount) || 0;
    if (amount > 0) {
      const category = item.category || 'Needs review';
      grouped.set(category, (grouped.get(category) || 0) + amount);
    }
  });
  return [month, {
    total: routine.reduce(
      (sum, item) => sum + Math.max(0, Number(item.personal_amount ?? item.amount) || 0),
      0,
    ),
    categories: [...grouped].map(([category, amount]) => ({ category, amount })),
  }];
}));
const householdHistory = new Map(Object.entries(input.householdHistory || {}));
const context = {
  categoryHistory,
  householdHistory,
  partialMonth: input.partialMonth || '',
  incomeVisible: Boolean(input.incomeVisible),
  period: input.period,
  recurringMonths,
};
const allTransactions = [...transactionsByMonth.values()].flat();
let findings = [];
if (input.period === 'month') {
  targetMonths.forEach(month => findings.push(...analyzeMonth(
    month,
    transactionsByMonth.get(month) || [],
    allTransactions,
    recurringPayloads[recurringMonths.indexOf(month)] || {},
    context,
  )));
} else {
  findings = analyzeHistoricalPatterns(
    targetMonths, transactionsByMonth, recurringPayloads, context,
  );
}
const reviewed = new Set(input.reviewedFindingKeys || []);
const active = findings.filter(item => !item.findingKey || !reviewed.has(item.findingKey));
process.stdout.write(JSON.stringify({ findings: active, groups: groupFindings(active) }));
