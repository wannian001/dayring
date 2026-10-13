// Overview (#project): what Proactive Health AIO is, who it is for, the problem it answers and how, then the
// comparison with what people use now, the trade-offs, what comes next and who made it (each opening on a click).
// The same facts as the README's "Why it exists", shorter. The server only names the page (modules/docs.py).
import { esc } from "../charts.js";
import { getLang, t } from "../i18n.js";

const REPO = "https://github.com/wannian001/proactive-health-aio";

const PROJECT = {
  zh: {
    title: "项目说明", sub: "它是什么、为谁做、和现有的有什么不同",
    note: "在线演示里的人叫 Sam，是虚构的研究生，数字都是编的。代码开源（MIT），装到自己电脑上就能看自己的数据。",
    lede: "把睡眠、运动、饮食、体重、屏幕和日程放进同一天，每一项都和你自己最近 28 天比；每天早上说出今天该调整的最多三件事，每件都写明依据。",
    facts: ["跑在你自己的电脑上", "和你自己比，不和人群比", "每条规则都写明", "中文 / English"],
    cards: [
      { h: "为谁做", items: ["戴手表、用好几个健康 App，数据多却散的人", "作息常被 deadline 和屏幕打乱的学生和知识工作者", "想自己定目标、看得到每条规则的人"] },
      { h: "要解决的问题", items: ["数据分在手表、饮食记录、屏幕使用时间、日历几个 App 里", "各打各的分：和人群比，或者给一个看不到公式的分数", "往往是不舒服了才去翻"] },
      { h: "它怎么做", items: ["读你已经有的导出数据，不用买新设备", "每一项和你自己的平常比", "每天最多三件该调整的：训练、睡眠、饮食各一件"] },
    ],
    loopTitle: "每天怎么转",
    loop: [["量", "导入设备已经记下的", "data", "数据来源"], ["比", "和你的平常、你的目标比", "today", "今天"],
      ["调", "今天该调整的，最多三件", "today", "今天"], ["记", "每个目标做到了几天", "goals", "目标"], ["看", "这一周和前四周并排", "review", "每周复盘"]],
    folds: [
      { h: "和现在常用的比", table: { head: ["现在用的", "管什么", "这里多做的"], rows: [
        ["手表 App（Oura、WHOOP、Garmin Connect）", "自己设备的恢复分", "把恢复和饮食、屏幕、日程放在同一天"],
        ["饮食记录（MyFitnessPal、Cronometer）", "吃了什么", "吃得晚不晚，和第二天的恢复对照"],
        ["屏幕使用时间", "用了多久", "和睡眠、专注、第二天放在一起"],
        ["Apple 健康", "几乎什么都存", "说出今天该改什么、为什么"],
        ["跨 App 找关联（Exist.io、Bearable）", "找相关", "只在本机，规则写明，落到今天的事"]] },
        after: "现在的代价：好几个 App，常常好几份订阅，历史散在几处云上，分数的公式看不到，最后还得自己把它们拼起来。" },
      { h: "有意的取舍", items: [
        "<b>不实时同步：</b>导入 Apple 健康的导出包。换来的是数据只在你的电脑上。",
        "<b>规则，不是模型：</b>建议来自几条写明的固定规则，能解释、能检查，但不会自己“学”。",
        "<b>和自己比：</b>刚开始的 28 天还没有“平常”，回答会少。",
        "<b>不是医疗建议：</b>只看行为和身体信号，不诊断，不打总分，不算连胜。"] },
      { h: "接下来", items: [
        "<b>目标直接在页面上设：</b>这一版已加。每次改动记在 goals.jsonl 里，一条不删。",
        "<b>接 AI 助手：</b>助手读每一页的数据，提出调整目标的建议；你在目标页点了采纳才生效。接口已经留好：<code>healthaio goal propose</code>。",
        "<b>iPhone 伴侣 App：</b>省掉手动导出。"] },
      { h: "谁做的、怎么做的", items: [
        "分工：需求、取舍和验收是我；代码由 AI 编程工具（Claude Code、Codex）写。",
        "它来自我自己用了一年的个人系统，四代迭代见“迭代记录”。",
        "Python 标准库，不用装别的包；颜色、组件和图表是一套带版本号的设计套件；每条规则都有测试。"] },
    ],
    links: [[REPO, "GitHub 仓库"], ["#guide", "使用说明"], ["#history", "迭代记录"], ["#kit", "设计套件"]],
  },
  en: {
    title: "Overview", sub: "What it is, who it is for, and how it differs from what people use now",
    note: "The person in the online demo, Sam, is a made-up graduate student, and every number is invented. The code is open source (MIT): install it on your computer to see your own data.",
    lede: "Sleep, exercise, food, weight, screens and your calendar on one day, each compared with your own last 28 days; every morning, at most three things to adjust today, each with the numbers behind it.",
    facts: ["Runs on your own computer", "You against you, not a population", "Every rule written down", "English / 中文"],
    cards: [
      { h: "Who it is for", items: ["People with a watch and several health apps: plenty of data, all in pieces", "Students and knowledge workers whose sleep gets pushed around by deadlines and screens", "People who want to set their own goals and see every rule"] },
      { h: "The problem", items: ["The data sits in separate apps: the watch, a food log, Screen Time, the calendar", "Each scores on its own: against a population, or with a formula you cannot see", "Most people only look after they already feel bad"] },
      { h: "What it does", items: ["Reads the exports you already have; no new device", "Compares every signal with your own normal", "At most three things to adjust each day: one each for training, sleep and food"] },
    ],
    loopTitle: "The daily loop",
    loop: [["Measure", "Import what your devices recorded", "data", "Data sources"], ["Compare", "Against your normal and your goals", "today", "Today"],
      ["Adjust", "At most three things today", "today", "Today"], ["Keep track", "On how many days each goal was kept", "goals", "Goals"], ["Review", "This week next to the four before it", "review", "Weekly review"]],
    folds: [
      { h: "Next to what people use now", table: { head: ["What people use", "What it covers", "What this adds"], rows: [
        ["Watch apps (Oura, WHOOP, Garmin Connect)", "A recovery score from their own device", "Recovery on the same day as food, screens and the calendar"],
        ["Food logs (MyFitnessPal, Cronometer)", "What you ate", "How late you ate, next to the next morning's recovery"],
        ["Screen Time", "How long", "Next to sleep, focus and the next day"],
        ["Apple Health", "Stores almost everything", "Says what to change today, and why"],
        ["Cross-app trackers (Exist.io, Bearable)", "Correlations", "On this computer only, rules written down, turned into today's to-dos"]] },
        after: "What that costs now: several apps, often several subscriptions, your history in several clouds, scores whose formula you cannot check, and you still do the joining-up yourself." },
      { h: "Trade-offs, on purpose", items: [
        "<b>No live sync:</b> you import an Apple Health export. In return, the data never leaves your computer.",
        "<b>Rules, not a model:</b> the advice comes from a few fixed rules, written down, explainable and checkable, but it does not “learn”.",
        "<b>You against you:</b> in the first 28 days there is no normal yet, so there are fewer answers.",
        "<b>Not medical advice:</b> behaviour and body signals only; no diagnosis, no total score, no streaks."] },
      { h: "What comes next", items: [
        "<b>Goals set on the page:</b> added in this version. Every change is a line in goals.jsonl; none is deleted.",
        "<b>An AI assistant:</b> it reads every page's data and proposes changes to your goals; nothing changes until you accept on the Goals page. The way in is ready: <code>healthaio goal propose</code>.",
        "<b>An iPhone companion:</b> no more manual exports."] },
      { h: "Who made it, and how", items: [
        "Who did what: the needs, the trade-offs and the acceptance checks are mine; the code was written by AI coding tools (Claude Code, Codex).",
        "It comes from the personal system I have used for a year; its four generations are in History.",
        "Python's standard library, nothing else to install; colours, components and charts are one versioned design kit; every rule has tests."] },
    ],
    links: [[REPO, "GitHub repository"], ["#guide", "Guide"], ["#history", "History"], ["#kit", "Design kit"]],
  },
};

function fold(f, i) {
  const table = f.table ? `<div class="table-wrap"><table class="doc-table"><thead><tr>${f.table.head.map((h) => `<th>${h}</th>`).join("")}</tr></thead>
    <tbody>${f.table.rows.map((r) => `<tr>${r.map((c, k) => (k === 0 ? `<th scope="row">${esc(c)}</th>` : `<td>${esc(c)}</td>`)).join("")}</tr>`).join("")}</tbody></table></div>` : "";
  const items = f.items ? `<ul class="doc-list">${f.items.map((x) => `<li>${x}</li>`).join("")}</ul>` : "";
  return `<li><details${i === 0 ? " open" : ""}><summary><span class="doc-n">${i + 1}</span>${f.h}</summary>${table}${items}${f.after ? `<p>${f.after}</p>` : ""}</details></li>`;
}

export default {
  render() {
    const c = PROJECT[getLang()] || PROJECT.en;
    const cards = c.cards.map((card, i) => `<section class="card doc-card"><h3><span class="doc-n">${"ABC"[i]}</span>${card.h}</h3>
      <ul>${card.items.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></section>`).join("");
    const loop = c.loop.map(([name, what, page, label]) => `<li><b>${name}</b><span>${what}</span><a href="#${page}">${label} ›</a></li>`).join("");
    const links = c.links.map(([href, label]) => `<a href="${href}"${href.startsWith("http") ? ' target="_blank" rel="noopener"' : ""}>${label} ›</a>`).join("");
    return `<div class="head"><div><h1>${c.title}</h1><div class="sub">${c.sub}</div></div></div>
      <div class="doc">
        <div class="doc-note"><p>${c.note}</p><button type="button" class="doc-link" id="doc-lang">${t("doc.other_lang")}</button></div>
        <section class="card"><p class="doc-lede">${c.lede}</p><div class="doc-facts">${c.facts.map((f) => `<span class="chip">${f}</span>`).join("")}</div></section>
        <div class="doc-brief">${cards}</div>
        <h2 class="doc-section">${c.loopTitle}</h2>
        <ol class="doc-loop">${loop}</ol>
        <section class="card"><ol class="doc-folds">${c.folds.map(fold).join("")}</ol></section>
        <p class="doc-try">${links}</p>
      </div>`;
  },
  mount(el) {
    const lang = el.querySelector("#doc-lang");
    if (lang) lang.onclick = () => document.querySelector("#lang")?.click();
  },
};
