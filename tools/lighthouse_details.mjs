#!/usr/bin/env node
// Расшифровка отчёта Lighthouse для журнала GitHub Actions.
//
// Появилась 25.09.2026, когда взялись за скорость главной: в сводке видно
// только «LCP 4.2 s», а что именно тормозит — нет. Сами отчёты лежат в
// артефакте, но из песочницы агента артефакты не скачиваются (сеть закрыта),
// поэтому главное печатаем прямо в журнал.
//
//   node tools/lighthouse_details.mjs output/lighthouse-weekly/Главная.json
import fs from "node:fs";

const file = process.argv[2];
if (!file || !fs.existsSync(file)) {
  console.log(`Отчёт не найден: ${file}`);
  process.exit(0);
}
const report = JSON.parse(fs.readFileSync(file, "utf8"));
const audits = report.audits || {};
const kb = (bytes) => `${Math.round((bytes || 0) / 1024)} КБ`;
const ms = (value) => `${Math.round(value || 0)} мс`;
const short = (url) => String(url || "").replace(/^https?:\/\/[^/]+/, "").slice(0, 90);

console.log(`\n### ${report.finalDisplayedUrl || report.requestedUrl}`);
console.log(`Устройство: ${report.configSettings?.formFactor}, сеть: ${report.configSettings?.throttlingMethod}`);

for (const id of ["first-contentful-paint", "largest-contentful-paint", "speed-index",
                  "total-blocking-time", "cumulative-layout-shift"]) {
  const a = audits[id];
  if (a) console.log(`  ${a.title}: ${a.displayValue} (балл ${Math.round((a.score || 0) * 100)})`);
}

// Что считается главной картинкой и из чего складывается её время.
const lcpEl = audits["largest-contentful-paint-element"]?.details?.items || [];
for (const block of lcpEl) {
  for (const item of block.items || []) {
    if (item.node) console.log(`\nLCP-элемент: ${item.node.nodeLabel || ""}\n  ${String(item.node.snippet || "").slice(0, 300)}`);
    if (item.phase) console.log(`  фаза «${item.phase}»: ${ms(item.timing)} (${Math.round(item.percent || 0)}%)`);
  }
}
const lcpInsight = audits["lcp-breakdown-insight"]?.details?.items || [];
for (const block of lcpInsight) {
  for (const item of block.items || []) {
    if (item.subpart || item.label) console.log(`  ${item.label || item.subpart}: ${ms(item.duration)}`);
  }
}
const discovery = audits["lcp-discovery-insight"];
if (discovery?.details) console.log(`  обнаружение LCP: ${discovery.title} (балл ${discovery.score})`);

// Что блокирует первую отрисовку.
const blocking = audits["render-blocking-insight"]?.details?.items
  || audits["render-blocking-resources"]?.details?.items || [];
if (blocking.length) {
  console.log("\nБлокируют отрисовку:");
  for (const item of blocking.slice(0, 8)) {
    console.log(`  ${short(item.url)} — ${kb(item.totalBytes || item.transferSize)}, ${ms(item.wastedMs)}`);
  }
}

// Самые тяжёлые запросы и когда они стартуют.
const requests = audits["network-requests"]?.details?.items || [];
if (requests.length) {
  const total = requests.reduce((sum, r) => sum + (r.transferSize || 0), 0);
  console.log(`\nЗапросов: ${requests.length}, передано всего: ${kb(total)}. Самые тяжёлые:`);
  for (const r of [...requests].sort((a, b) => (b.transferSize || 0) - (a.transferSize || 0)).slice(0, 15)) {
    console.log(`  ${kb(r.transferSize).padStart(7)}  старт ${ms(r.networkRequestTime).padStart(7)}  ` +
      `${(r.resourceType || "").padEnd(10)} ${r.priority || ""}  ${short(r.url)}`);
  }
  const byType = {};
  for (const r of requests) byType[r.resourceType || "?"] = (byType[r.resourceType || "?"] || 0) + (r.transferSize || 0);
  console.log("  По типам: " + Object.entries(byType).sort((a, b) => b[1] - a[1])
    .map(([type, size]) => `${type} ${kb(size)}`).join(", "));
}

// Возможности ускорения по оценке самого Lighthouse.
const opportunities = Object.values(audits)
  .filter((a) => a.details && (a.details.overallSavingsMs > 0 || a.details.overallSavingsBytes > 0)
    && (a.score ?? 1) < 1)
  .sort((a, b) => (b.details.overallSavingsMs || 0) - (a.details.overallSavingsMs || 0));
if (opportunities.length) {
  console.log("\nВозможности ускорения:");
  for (const a of opportunities.slice(0, 12)) {
    console.log(`  ${a.title}: ~${ms(a.details.overallSavingsMs)}, ~${kb(a.details.overallSavingsBytes)}`);
    for (const item of (a.details.items || []).slice(0, 3)) {
      if (item.url) console.log(`      ${short(item.url)} — лишних ${kb(item.wastedBytes)}`);
    }
  }
}

// Кто занимает основной поток (скрипты).
const bootup = audits["bootup-time"]?.details?.items || [];
if (bootup.length) {
  console.log("\nСкрипты по времени выполнения:");
  for (const item of bootup.slice(0, 6)) console.log(`  ${ms(item.total).padStart(7)}  ${short(item.url)}`);
}
const thirdParty = audits["third-party-summary"]?.details?.items || [];
if (thirdParty.length) {
  console.log("\nСторонние сервисы:");
  for (const item of thirdParty.slice(0, 6)) {
    console.log(`  ${item.entity?.text || item.entity}: ${kb(item.transferSize)}, блокировка ${ms(item.blockingTime)}`);
  }
}
