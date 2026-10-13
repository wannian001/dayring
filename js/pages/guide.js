// Guide (#guide): how to use Proactive Health AIO, from the demo to your own data to a normal day with it.
// Numbered steps in the order you meet them, in one card, each opening on a click; commands are the ones in the README's Quick start. The server only
// names the page (modules/docs.py).
import { esc } from "../charts.js?v=260bf4b694";
import { getLang, t } from "../i18n.js?v=260bf4b694";

const CODE = {
  install: ["git clone https://github.com/wannian001/proactive-health-aio.git", "cd proactive-health-aio", "python3 -m healthaio serve --demo"],
  import: ["cp examples/healthaio.example.toml healthaio.toml", "python3 -m healthaio import apple-health ~/Downloads/export.zip"],
  more: ["python3 -m healthaio import ics ~/Downloads/timetable.ics --kind class", "python3 -m healthaio import macos-screentime",
    "python3 -m healthaio import ai-logs", "python3 -m healthaio check"],
  serve: ["python3 -m healthaio serve"],
};

const GUIDE = {
  zh: {
    title: "使用说明", sub: "从看演示，到用上你自己的数据，再到每天怎么看",
    note: "在线演示里的人叫 Sam，是虚构的研究生，数字都是编的。想看你自己的，按下面第 2 到 4 步装到你自己的电脑上；数据只留在那台电脑里。",
    steps: [
      { h: "先看看演示", body: [
        "左边的菜单（手机上在底部）按管理健康的顺序排：<b>今天 → 身体数据 → 时间与精力 → 目标与日程 → 每周复盘 → 数据来源</b>。点有子页的一项，子页才展开。",
        "从“今天”开始：恢复得怎样、今天该调整什么、今天有什么安排、今晚几点该睡着。",
        "菜单旁边的两个按钮可以切换中英文和深浅色。"] },
      { h: "装到你的电脑上", body: ["需要 Python 3.9 以上，不用装别的包。先用演示数据确认能跑，然后打开 <b>http://localhost:8790</b>："], code: "install" },
      { h: "导入你的数据", body: [
        "在 iPhone 的“健康” App 里点右上角的头像，选“导出所有健康数据”，把得到的 <b>export.zip</b> 传到电脑上。",
        "一个导出包就能带进来大部分：睡眠、HRV、静息心率、步数、体重、每次训练，以及记饮食的 App 写进健康里的每一餐。"], code: "import",
        after: "下面这些是可选的：课表或日历（.ics）、Mac 的屏幕使用时间（试验性）、Claude Code 和 Codex 的使用记录（只读时刻和条数）；最后一行检查哪些行读不出：", code2: "more" },
      { h: "打开，设你的目标", body: [
        "在 <b>healthaio.toml</b> 里改一下时区，然后运行下面这行。",
        "目标在“目标”页直接设、随时改：几点睡着、每周练几次、饮食和屏幕的上限。每一项都可以不设，没设的页面照样显示事实，只是没有目标可比。"], code: "serve" },
      { h: "每天怎么用", body: [
        "<b>早上</b>打开“今天”：先看恢复（和你自己最近 28 天比），再看“今天该调整的”：训练、睡眠、饮食各最多一件，每件都写明依据的数字。",
        "想细看某一项，去“身体数据”（作息、运动、饮食、体重）或“时间与精力”（时间去向、AI 干活量、消耗）。",
        "<b>周末</b>看“每周复盘”：这一周和前四周并排放，不打分。",
        "某项很久没更新，去“数据来源”页看是哪一路断了。它不实时同步：想看新数据时，再导出一次 Apple 健康，重新导入。"] },
      { h: "怎么读这些数", body: [
        "<b>和你自己比，</b>不和人群比：“平常”是你自己前 28 天的中间一半。",
        "<b>缺的就是缺：</b>没记的一天不算成 0，记得少，回答就少，不会编。",
        "<b>关联不是因果：</b>“做什么第二天会更好”只说哪些事常和更好的第二天一起出现。",
        "<b>不是医疗建议：</b>建议都是日常习惯（早点睡、早点吃、练轻一点）；健康问题请找专业人士。"] },
      { h: "你的数据", body: [
        "数据是你电脑上一个文件夹里的普通 CSV 文件，导入工具写它们，看板只读。",
        "服务只在本机（127.0.0.1）运行，不往任何地方发数据。它唯一会写的，是你在目标页设的目标：每次一行，记在 healthaio.toml 旁边的 goals.jsonl 里。"] },
    ],
    history: "这个项目是怎么来的？看迭代记录（在作者的网站上）",
  },
  en: {
    title: "Guide", sub: "From the demo, to your own data, to a normal day with it",
    note: "The person in the online demo, Sam, is a made-up graduate student, and every number is invented. To see your own, install it on your computer with steps 2 to 4 below; your data stays on that computer.",
    steps: [
      { h: "Look around the demo", body: [
        "The menu on the left (at the bottom on a phone) follows the loop of managing your health: <b>Today → Body → Time & energy → Goals & schedule → Weekly review → Data sources</b>. An item with pages opens them with a click.",
        "Start with Today: how you recovered, what to adjust today, what is on, and when to be asleep tonight.",
        "The two buttons by the menu switch the language and light / dark."] },
      { h: "Install it on your computer", body: ["Needs Python 3.9 or newer, no other packages. Check it runs with the demo data first, then open <b>http://localhost:8790</b>:"], code: "install" },
      { h: "Bring in your data", body: [
        "On your iPhone, open the Health app, tap your picture at the top right and choose Export All Health Data; copy the <b>export.zip</b> to your computer.",
        "One export brings in most of it: sleep, HRV, resting heart rate, steps, weight, every workout, and the meals that food-logging apps write into Health."], code: "import",
        after: "These are optional: a timetable or calendar (.ics), Screen Time on a Mac (experimental), Claude Code and Codex logs (times and counts only); the last line checks which rows could not be read:", code2: "more" },
      { h: "Open it, set your goals", body: [
        "Set your timezone in <b>healthaio.toml</b>, then run the line below.",
        "Set goals right on the Goals page and change them any time: when to be asleep, how often to train, limits for food and screens. Each is optional; a page without its goal still shows the facts, just without a goal to compare with."], code: "serve" },
      { h: "A normal day with it", body: [
        "<b>In the morning</b>, open Today: first recovery (against your own last 28 days), then what to adjust today: at most one thing each for training, sleep and food, each with the numbers behind it.",
        "For a closer look, go to Body (sleep, exercise, food, weight) or Time & energy (where the time went, AI work, drain).",
        "<b>At the weekend</b>, open Weekly review: this week next to the four before it, with no scores.",
        "If something has not updated for a while, Data sources shows which stream stopped. Nothing syncs live: for fresh data, export from Apple Health again and import it."] },
      { h: "How to read the numbers", body: [
        "<b>You against you,</b> never a population: “normal” is the middle half of your own previous 28 days.",
        "<b>Missing stays missing:</b> a day you did not log is not a zero; a sparse log gives fewer answers, not made-up ones.",
        "<b>Associations, not causes:</b> “What has tended to help the next day” only says what has gone with a better next day.",
        "<b>Not medical advice:</b> the suggestions are everyday habits (sleep earlier, eat earlier, train lighter); for anything about your health, talk to a professional."] },
      { h: "Your data", body: [
        "Your data is plain CSV files in a folder on your computer. The importers write them; the dashboard only reads them.",
        "The server listens only on this computer (127.0.0.1) and sends nothing anywhere. The one thing it writes is a goal you set on the Goals page: one line each, in goals.jsonl next to healthaio.toml."] },
    ],
    history: "Where did this project come from? Read its history (on the author's site)",
  },
};

const code = (key) => `<pre class="doc-code"><code>${CODE[key].map(esc).join("\n")}</code></pre>`;

export default {
  render() {
    const c = GUIDE[getLang()] || GUIDE.en;
    // one card: every step's title in view, its text one click away; the first step is open
    const steps = c.steps.map((s, i) => `<li><details${i === 0 ? " open" : ""}><summary><span class="doc-n">${i + 1}</span>${s.h}</summary>
      ${s.body.map((p) => `<p>${p}</p>`).join("")}${s.code ? code(s.code) : ""}${s.after ? `<p>${s.after}</p>${code(s.code2)}` : ""}</details></li>`).join("");
    return `<div class="head"><div><h1>${c.title}</h1><div class="sub">${c.sub}</div></div></div>
      <div class="doc">
        <div class="doc-note"><p>${c.note}</p><button type="button" class="doc-link" id="doc-lang">${t("doc.other_lang")}</button></div>
        <section class="card"><ol class="doc-folds doc-guide-steps">${steps}</ol></section>
        <p class="doc-try"><a href="${esc(t("doc.history_url"))}" target="_blank" rel="noopener">${c.history} ↗</a></p>
      </div>`;
  },
  mount(el) {
    const lang = el.querySelector("#doc-lang");
    if (lang) lang.onclick = () => document.querySelector("#lang")?.click();
  },
};
