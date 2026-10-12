// Words live here, numbers come from the server. Add a language by adding one more dictionary.
const DICT = {
  en: {
    "nav.today": "Today", "nav.week": "Week", "nav.body": "Body", "nav.sleep": "Sleep",
    "nav.review": "Review", "nav.data": "Data", "nav.time": "Time",
    "ui.demo": "Demo data", "ui.lang": "中文", "ui.mode": "Light / dark",
    "ui.prev_day": "Previous day", "ui.next_day": "Next day", "ui.back_today": "Back to today",
    "ui.how": "How this is worked out", "ui.list_sep": ", ", "ui.loading": "Loading…", "ui.error": "Could not load this page",
    "ui.error_hint": "Check that the server is running and the data folder is readable.",
    "ui.computed": "Computed {time}", "ui.static_gap": "The demo site does not go back this far", "ui.static_gap_hint": "The online demo has the last two weeks pre-rendered. Run dayring on your computer to browse any date.", "ui.back_latest": "Back to the latest", "ui.no_data": "No data yet",

    "today.title": "Today", "today.looking_back": "Looking back at {day}",
    "today.agenda": "On today", "today.nothing": "Nothing on the calendar.",
    "today.due": "Due {when}", "today.days_left.0": "today", "today.days_left.1": "tomorrow",
    "today.days_left.n": "in {n} days", "today.graded": "{pct}% of grade", "today.ungraded": "not graded",
    "today.training": "Training", "today.rest": "No training planned",
    "today.tonight": "Tonight", "today.phone_away": "Phone away", "today.asleep_by": "Asleep by", "today.alarm": "Alarm",
    "today.last_morning": "This morning: woke {woke}, alarm {alarm} — {result}.",
    "today.on_time": "on time, so the alarm moves earlier", "today.late": "late, so the alarm stays",
    "today.unknown_morning": "no wake time recorded, so the alarm stays",

    "ring.label": "Day ring: last night's sleep, the day's calendar and workouts, and screen time by hour",
    "ring.sleep": "Sleep", "ring.events": "Today's calendar", "ring.screen": "Screen, {day}",
    "ring.now": "now",

    "recovery.title": "Body recovery", "recovery.eyebrow": "Recovery",
    "recovery.good": "Recovered better than usual", "recovery.normal": "Recovered as usual",
    "recovery.low": "Recovery below your normal", "recovery.unknown": "Not enough data to judge recovery",
    "recovery.as_of": "From the night ending {day}", "recovery.behind": "Body data stops {n} days ago — this describes {day}, not last night.",
    "recovery.rule": "Sleep, HRV and resting heart rate are each compared with the middle half of your previous 28 days. Two or more worse than normal reads as below normal; two or more better and none worse reads as better than usual. HRV falling and resting heart rate rising are signs the nervous system has recovered less.",
    "metric.sleep": "Sleep", "metric.hrv": "HRV", "metric.resting_hr": "Resting heart rate",
    "metric.steps": "Steps", "metric.exercise": "Exercise ring", "metric.training": "Training, last 7 days",
    "metric.focus": "Focused work", "metric.longest_focus": "Longest focus stretch",
    "metric.fun": "Entertainment & social", "metric.fun_before_sleep": "Entertainment in the hour before sleep",
    "state.high": "above normal", "state.low": "below normal", "state.normal": "within normal",
    "state.partial": "day not over", "state.none": "no normal yet",
    "band": "normal {low}–{high}", "band_one": "normal {low}", "slept_from": "{start}–{end}",
    "self.title": "Self-rated", "self.prompt": "Add a line to self_report.csv (energy and focus, 0–5) and it shows here.",
    "self.energy": "energy {v}/5", "self.focus": "focus {v}/5",
    "activity.partial": "Counted until the last sync; not compared with normal.",
    "training.days": "{n} of {k} days", "training.last": "Last: {type}, {min}", "training.none": "No workouts in the last 7 days.",

    "screens.title": "Screens, {day}", "screens.more": "Where your time went →", "screens.stale": "Screen time stops {n} days ago; numbers shown without comparison.",
    "screens.total": "{total} on screens", "screens.rule": "Screen time from all your devices, counted once when they overlap. Focused work = work + learning apps; a stretch survives interruptions of up to 3 minutes. Entertainment & social = video, games and feeds. Each is compared with your previous 28 days.",
    "target.focus": "Focused work ≥ {limit}", "target.fun": "Entertainment ≤ {limit}",
    "target.met": "met", "target.missed": "missed", "target.week": "{n} of last {k} days",
    "cat.work": "Work", "cat.learning": "Learning", "cat.communication": "Communication", "cat.entertainment": "Entertainment",
    "cat.social": "Social", "cat.other": "Other", "cat.focus": "Focus", "cat.fun": "Entertainment & social",

    "week.title": "This week's load", "week.strain": "Short sleep and hard training stacked up this week",
    "week.ok": "No stack-up of short sleep and hard training",
    "week.nights": "{short} of {n} nights under {h} h", "week.train": "Trained {n} of 7 days",
    "week.hrv": "HRV {dir} {pct} vs the 4 weeks before", "week.up": "up", "week.down": "down",
    "week.rule": "Flags a week with at least 3 nights under 7 hours and at least 3 training days. The thresholds are a starting point, not a diagnosis.",

    "effects.title": "What has tended to help the next day", "effects.outcome": "Next day's", "effects.col.what": "On the day…", "effects.col.worse": "← next day worse", "effects.col.better": "next day better →", "effects.col.diff": "Difference",
    "out.hrv": "HRV", "out.resting_hr": "Resting HR", "out.energy": "Self-rated energy",
    "eff.trained": "Logged a workout that day", "eff.steps": "Walked {min}+ steps that day", "eff.exercise": "{min}+ exercise-ring minutes that day",
    "eff.slept": "Slept {hours}+ hours that night", "eff.in_bed": "{hours}+ hours in bed that night", "eff.asleep_by": "Asleep by {clock} that night",
    "eff.days": "{yes} days yes · {no} days no", "eff.read.hrv.higher": "HRV {v}% higher", "eff.read.hrv.lower": "HRV {v}% lower", "eff.read.resting_hr.higher": "resting HR {v} bpm higher", "eff.read.resting_hr.lower": "resting HR {v} bpm lower", "eff.read.energy.higher": "energy {v} points higher", "eff.read.energy.lower": "energy {v} points lower", "eff.range": "95% interval {low} to {high}", "eff.too_few": "Too few days to compare",
    "eff.detected": "Significant effect", "eff.not_detected": "No significant effect",
    "eff.read": "Days after: {diff} ({low} to {high})",
    "effects.rule": "Each row is one condition, such as \"logged a workout that day\". Days that met it and days that did not are split into two groups, and the next day is compared: HRV and resting heart rate against the median of your previous 28 days, self-rated energy as the score itself. The dot is the difference between the two groups and the line its 95% interval; further right always means a better next day (lower resting heart rate is better, so that one is flipped). Each condition is compared on its own, the whole list is corrected with Benjamini–Hochberg, and only what survives counts as a significant effect and gets a colour. Exercise minutes are the Activity ring's exercise minutes in the Health app, not only logged workouts. These are associations in your own history, not causes: you may train more on days you already feel good.",
    "unit.min": "min", "unit.ms": "ms", "unit.bpm": "bpm", "unit.steps": "steps", "unit.pct": "%", "unit.points": "pts",
  },
  zh: {
    "nav.today": "今天", "nav.week": "本周", "nav.body": "身体", "nav.sleep": "作息",
    "nav.review": "复盘", "nav.data": "数据", "nav.time": "时间",
    "ui.demo": "演示数据", "ui.lang": "EN", "ui.mode": "浅色 / 深色",
    "ui.prev_day": "前一天", "ui.next_day": "后一天", "ui.back_today": "回到今天",
    "ui.how": "怎么算的", "ui.list_sep": "、", "ui.loading": "正在读取…", "ui.error": "这一页没读出来",
    "ui.error_hint": "看一下服务有没有在跑、数据目录能不能读。",
    "ui.computed": "{time} 算的", "ui.static_gap": "演示站没有这么早的日子", "ui.static_gap_hint": "在线演示只预先算好了最近两周。在自己电脑上运行 dayring 可以看任意一天。", "ui.back_latest": "回到最近", "ui.no_data": "还没有数据",

    "today.title": "今天", "today.looking_back": "回看 {day}",
    "today.agenda": "今天要做的", "today.nothing": "日历上没有安排。",
    "today.due": "{when}截止", "today.days_left.0": "今天", "today.days_left.1": "明天",
    "today.days_left.n": "{n} 天后", "today.graded": "占成绩 {pct}%", "today.ungraded": "不计分",
    "today.training": "训练", "today.rest": "今天没排训练",
    "today.tonight": "今晚", "today.phone_away": "手机放远", "today.asleep_by": "睡着", "today.alarm": "闹钟",
    "today.last_morning": "今早 {woke} 醒，闹钟 {alarm}，{result}。",
    "today.on_time": "按时，闹钟往前挪一步", "today.late": "没按时，闹钟不动",
    "today.unknown_morning": "没有醒来记录，闹钟不动",

    "ring.label": "一天的环：昨晚的睡眠、当天的日程和训练、每小时的屏幕时间",
    "ring.sleep": "睡眠", "ring.events": "今天的日程", "ring.screen": "屏幕 · {day}",
    "ring.now": "现在",

    "recovery.title": "身体恢复", "recovery.eyebrow": "恢复",
    "recovery.good": "恢复得比平常好", "recovery.normal": "恢复平常",
    "recovery.low": "恢复低于平常", "recovery.unknown": "数据不够，判断不了恢复",
    "recovery.as_of": "按 {day} 早上醒来那一觉", "recovery.behind": "身体数据停在 {n} 天前，下面说的是 {day}，不是昨晚。",
    "recovery.rule": "睡眠、HRV、静息心率各自跟你之前 28 天的中间 50% 比。两项以上变差算低于平常，两项以上变好且没有变差算比平常好。HRV 降、静息心率升是神经系统恢复变差的信号。",
    "metric.sleep": "睡眠", "metric.hrv": "HRV", "metric.resting_hr": "静息心率",
    "metric.steps": "步数", "metric.exercise": "锻炼圆环", "metric.training": "近 7 天训练",
    "metric.focus": "专注做事", "metric.longest_focus": "最长一段专注",
    "metric.fun": "娱乐和社交", "metric.fun_before_sleep": "睡前一小时娱乐",
    "state.high": "高于平常", "state.low": "低于平常", "state.normal": "在平常范围",
    "state.partial": "这天还没过完", "state.none": "还没有平常值",
    "band": "平常 {low}–{high}", "band_one": "平常 {low}", "slept_from": "{start}–{end}",
    "self.title": "自评", "self.prompt": "在 self_report.csv 里记一行（精力、专注，0–5 分），就会显示在这里。",
    "self.energy": "精力 {v}/5", "self.focus": "专注 {v}/5",
    "activity.partial": "只算到最近一次同步，不跟平常比。",
    "training.days": "{k} 天里练了 {n} 天", "training.last": "上次：{type}，{min}", "training.none": "近 7 天没有训练。",

    "screens.title": "屏幕 · {day}", "screens.more": "看时间去向 →", "screens.stale": "屏幕记录停在 {n} 天前，下面的数照写但不跟平常比。",
    "screens.total": "屏幕共 {total}", "screens.rule": "几台设备的屏幕时间合起来，同一时刻只算一次。专注做事 = 工作和学习类应用，中间 3 分钟以内的打断不算断开。娱乐和社交 = 视频、游戏、信息流。各自跟你之前 28 天比。",
    "target.focus": "专注做事 ≥ {limit}", "target.fun": "娱乐 ≤ {limit}",
    "target.met": "做到", "target.missed": "没做到", "target.week": "近 {k} 天做到 {n} 天",
    "cat.work": "工作", "cat.learning": "学习", "cat.communication": "沟通", "cat.entertainment": "娱乐",
    "cat.social": "社交", "cat.other": "其他", "cat.focus": "专注", "cat.fun": "娱乐和社交",

    "week.title": "这一周的负荷", "week.strain": "这一周睡眠不足和高强度训练叠在一起了",
    "week.ok": "这一周没有出现睡眠不足叠加高强度训练",
    "week.nights": "{n} 晚里 {short} 晚不到 {h} 小时", "week.train": "7 天里练了 {n} 天",
    "week.hrv": "HRV 比之前 4 周{dir} {pct}", "week.up": "高", "week.down": "低",
    "week.rule": "7 天里至少 3 晚睡不到 7 小时、而且至少练了 3 天，就提示负荷叠加。阈值只是起点，不是诊断。",

    "effects.title": "做什么第二天会更好", "effects.outcome": "看第二天的", "effects.col.what": "这一天……", "effects.col.worse": "← 第二天更差", "effects.col.better": "第二天更好 →", "effects.col.diff": "差多少",
    "out.hrv": "HRV", "out.resting_hr": "静息心率", "out.energy": "自评精力",
    "eff.trained": "当天有训练记录", "eff.steps": "当天走了 {min} 步以上", "eff.exercise": "当天锻炼圆环满 {min} 分钟",
    "eff.slept": "当晚睡了 {hours} 小时以上", "eff.in_bed": "当晚在床上躺了 {hours} 小时以上", "eff.asleep_by": "当晚 {clock} 前睡着",
    "eff.days": "符合 {yes} 天 · 不符合 {no} 天", "eff.read.hrv.higher": "第二天 HRV 高 {v}%", "eff.read.hrv.lower": "第二天 HRV 低 {v}%", "eff.read.resting_hr.higher": "第二天静息心率高 {v} 次/分", "eff.read.resting_hr.lower": "第二天静息心率低 {v} 次/分", "eff.read.energy.higher": "第二天自评精力高 {v} 分", "eff.read.energy.lower": "第二天自评精力低 {v} 分", "eff.range": "95% 区间 {low} 到 {high}", "eff.too_few": "天数太少，比不了",
    "eff.detected": "有显著影响", "eff.not_detected": "没有显著影响",
    "eff.read": "第二天：{diff}（{low} 到 {high}）",
    "effects.rule": "每一行是一个条件，比如“当天有训练记录”。把符合的日子和不符合的日子分成两组，比它们第二天的指标：HRV 和静息心率跟你自己之前 28 天的中位数比，自评精力直接比分数。点是两组的平均差，横线是 95% 区间；图上越往右，第二天越好（静息心率越低越好，已经把方向翻过来画）。每个条件单独比，整张表一起做 Benjamini–Hochberg 校正，校正后仍然成立的才算“有显著影响”、才上颜色。锻炼分钟取的是健康 App 活动圆环里的锻炼时间，不只是训练记录。这是你自己历史里的关联，不是因果：状态好的日子本来就更可能去练。",
    "unit.min": "分钟", "unit.ms": "ms", "unit.bpm": "次/分", "unit.steps": "步", "unit.pct": "%", "unit.points": "分",
  },
};

// ---- pages beyond Today ----
Object.assign(DICT.en, {
  "status.todo": "to do", "status.submitted": "submitted", "status.done": "done",
  "chart.avg7": "7-day average", "chart.series": "Chart",
  "week.title_range": "{from} – {to}", "week.sub": "Calendar, deadlines and training for the week",
  "week.prev": "Previous week", "week.next": "Next week", "week.current": "This week",
  "week.free": "Nothing scheduled", "week.planned": "Planned: {what}", "week.planned_missed": "Planned: {what} · not done", "today.trained": "Done: {what}, {d} ({time})", "week.slept": "slept {d}", "week.trained": "{what} {d}", "week.rested": "rest day",
  "week.load": "How heavy the coming weeks are", "week.load_note": "Block height = share of the grade · amber = due within 3 days · grey = not graded",
  "week.this": "This week", "week.in_weeks": "+{n} wk", "week.upcoming": "Next 3 weeks", "week.later": "Later this term",
  "week.overdue": "Past due date, still marked to do — check whether it was handed in", "week.none_soon": "Nothing due in the next 3 weeks.",
  "week.none_later": "Nothing further out.", "week.days_ago": "{n} days ago",
  "body.sub": "Weight against your plan", "body.empty": "No weights yet. Add weight_kg to body_daily.csv, or import Apple Health.",
  "body.weight": "Weight", "body.avg7_on": "7-day average on {day}", "body.no_plan": "No weight plan in dayring.toml",
  "body.status.on_track": "Within the planned pace", "body.status.faster": "Faster than planned", "body.status.slower": "Slower than planned", "body.status.reached": "Target reached",
  "body.rate": "Per week (last 3 weeks)", "body.since_start": "Since {day}", "body.to_go": "To {target}", "body.eta": "At this pace, around",
  "body.weighed": "Weighed", "body.weighed_n": "{n} of the last 14 days",
  "body.chart": "Last 120 days", "body.daily": "Each weigh-in", "body.corridor": "Planned pace {lo}–{hi}% a week", "body.target": "Target {kg} kg",
  "body.rule": "Dots are single weigh-ins; the line is the average of the last 7 days (at least 3 weigh-ins). The shaded corridor is the plan: losing between the two weekly percentages from the start weight. A weigh-in more than 15% away from all your others is ignored as a typo.",
  "body.long": "The long view", "body.long_note": "Median of each month", "body.waist": "Waist", "body.no_waist": "No waist measurements yet.",
  "sleep.sub": "Target {h} hours a night", "sleep.no_plan": "Add [plan.sleep] or [plan.wake_shift] to dayring.toml to get tonight's times.",
  "sleep.moved": "Alarm moved {moved} of {total}", "sleep.shift_rule": "After each on-time morning (awake within {grace} minutes of the alarm) the next alarm is {step} minutes earlier. A late or missing morning keeps it where it is; it never moves later.",
  "sleep.compare": "Last 7 nights vs the 7 before", "sleep.asleep": "Fell asleep, average", "sleep.woke": "Woke, average", "sleep.duration": "Slept, average", "sleep.spread": "Bedtime spread",
  "sleep.last_week": "before: {v}", "sleep.windows": "Last 21 nights", "sleep.alarm_at": "alarm {alarm}", "sleep.woke_at": "woke {woke}", "sleep.no_record": "no record",
  "sleep.final": "goal {alarm}", "sleep.ladder": "The alarm ladder", "sleep.on_time": "woke on time", "sleep.late": "woke late",
  "sleep.checks": "This week's checks",
  "sleep.check.woke_on_time": "Up with the alarm", "sleep.check.asleep_in_time": "Asleep in time", "sleep.check.slept_enough": "Slept enough", "sleep.check.screen_before_sleep_ok": "Calm last hour",
  "sleep.checks_rule": "Up with the alarm: awake within the grace minutes. Asleep in time: early enough for the target hours before the alarm (or by the planned bedtime). Slept enough: within {slack} minutes of the target. Calm last hour: no more than {min} minutes of entertainment or social apps in the hour before falling asleep. – means no record.",
  "review.title": "Week of {from} – {to}", "review.sub": "This week next to the four before it. Facts only.", "review.partial": "This week is not over yet; numbers so far.",
  "review.prev": "Previous week", "review.next": "Next week", "review.facts": "The week in numbers", "review.this": "This week", "review.before": "4 weeks before", "review.change": "Change",
  "review.sec.sleep": "Sleep", "review.sec.recovery": "Recovery", "review.sec.activity": "Activity", "review.sec.screens": "Screens", "review.sec.self": "Self-rated",
  "review.m.sleep_min": "Sleep per night", "review.m.onset": "Fell asleep", "review.m.wake": "Woke", "review.m.hrv_ms": "HRV (median)", "review.m.resting_hr": "Resting HR (median)",
  "review.m.steps": "Steps per day", "review.m.workout_min": "Exercise per day", "review.m.workout_days": "Training days", "review.m.focus": "Focused work per day", "review.m.fun": "Entertainment per day",
  "review.m.energy": "Energy, self-rated (0–5)", "review.m.focus_self": "Focus, self-rated (0–5)", "review.planned": "{n} planned", "review.days": "{n} d",
  "review.later": "later", "review.earlier": "earlier", "review.same": "about the same", "review.gaps": "No body data on {days}.", "review.weight": "Weight this week",
  "review.weight_change": "{v} vs the week before", "review.weight_days": "{n} weigh-ins", "review.due_this": "Due this week", "review.due_next": "Due next week", "review.none": "Nothing.",
  "review.rule": "Averages per day with data (HRV and resting heart rate use the median). The comparison is the four weeks before this one. Green and red only mark the direction that is usually better or worse; small changes stay grey.",
  "data.sub": "What arrived over the last {n} days", "data.ok": "Data is flowing", "data.attention": "Something stopped",
  "data.arrivals": "Arrivals", "data.s.sleep": "Sleep", "data.s.hrv": "HRV", "data.s.steps": "Steps", "data.s.weight": "Weight", "data.s.screen": "Screen time", "data.s.self": "Self-report",
  "data.status.ok": "up to date", "data.status.stale": "stopped", "data.status.missing": "never arrived",
  "data.last": "last {day} ({n} d ago)", "data.last_today": "arrived today", "data.never": "no data", "data.days": "{n} of {k} days",
  "data.mark.1": "has data", "data.mark.p": "partial", "data.mark.0": "nothing",
  "data.honest": "A missing day stays missing: pages never fill it in or treat it as zero. When a stream stops, pages say how old their numbers are.",
  "data.files": "Files", "data.file": "File", "data.rows": "Rows", "data.modified": "Changed", "data.absent": "not there (optional)",
  "data.problems": "{n} unreadable rows", "data.clean": "readable", "data.problem_line": "line {line}, {column}",
  "data.import": "Bring data in", "data.import_lede": "Everything lives in plain CSV files in your data folder. Importers write them; you can also edit them by hand.",
  "data.import_note": "Nothing is uploaded anywhere. The server listens on this computer only.",
});
Object.assign(DICT.zh, {
  "status.todo": "待办", "status.submitted": "已提交", "status.done": "完成",
  "chart.avg7": "7 天平均", "chart.series": "图",
  "week.title_range": "{from} – {to}", "week.sub": "这一周的日程、截止和训练",
  "week.prev": "上一周", "week.next": "下一周", "week.current": "回到本周",
  "week.free": "没有安排", "week.planned": "计划：{what}", "week.planned_missed": "计划：{what} · 没练", "today.trained": "已练：{what}，{d}（{time}）", "week.slept": "睡了 {d}", "week.trained": "{what} {d}", "week.rested": "休息",
  "week.load": "接下来几周有多重", "week.load_note": "块高 = 占成绩的比例 · 琥珀色 = 3 天内截止 · 灰色 = 不计分",
  "week.this": "本周", "week.in_weeks": "+{n} 周", "week.upcoming": "接下来 3 周", "week.later": "本学期更晚的",
  "week.overdue": "日期已过、还标着待办——核对一下交了没有", "week.none_soon": "接下来 3 周没有截止。",
  "week.none_later": "再往后没有了。", "week.days_ago": "{n} 天前",
  "body.sub": "体重对照计划", "body.empty": "还没有体重。在 body_daily.csv 里填 weight_kg，或者导入 Apple 健康。",
  "body.weight": "体重", "body.avg7_on": "{day} 的 7 天平均", "body.no_plan": "dayring.toml 里没有体重计划",
  "body.status.on_track": "在计划速度内", "body.status.faster": "比计划快", "body.status.slower": "比计划慢", "body.status.reached": "到目标了",
  "body.rate": "每周（近 3 周）", "body.since_start": "{day} 以来", "body.to_go": "离 {target}", "body.eta": "照这个速度，大约",
  "body.weighed": "称重", "body.weighed_n": "近 14 天称了 {n} 天",
  "body.chart": "最近 120 天", "body.daily": "每次称重", "body.corridor": "计划速度每周 {lo}–{hi}%", "body.target": "目标 {kg} kg",
  "body.rule": "点是每次称的，线是最近 7 天的平均（至少 3 次）。阴影走廊是计划：从起点体重每周降两个百分比之间。和你所有体重相差超过 15% 的一次当作输错，不算。",
  "body.long": "长期", "body.long_note": "每月中位数", "body.waist": "腰围", "body.no_waist": "还没有腰围记录。",
  "sleep.sub": "每晚目标 {h} 小时", "sleep.no_plan": "在 dayring.toml 里加 [plan.sleep] 或 [plan.wake_shift]，就能算出今晚的时间。",
  "sleep.moved": "闹钟已经往前挪了 {moved}，一共要挪 {total}", "sleep.shift_rule": "每按时起一天（闹钟后 {grace} 分钟内醒），第二天闹钟早 {step} 分钟；没按时或没记录就停在原地，绝不往后挪。",
  "sleep.compare": "最近 7 晚和再往前 7 晚", "sleep.asleep": "平均睡着", "sleep.woke": "平均醒来", "sleep.duration": "平均睡了", "sleep.spread": "入睡时间波动",
  "sleep.last_week": "之前：{v}", "sleep.windows": "最近 21 晚", "sleep.alarm_at": "闹钟 {alarm}", "sleep.woke_at": "{woke} 醒", "sleep.no_record": "没有记录",
  "sleep.final": "目标 {alarm}", "sleep.ladder": "闹钟台阶", "sleep.on_time": "按时醒", "sleep.late": "没按时",
  "sleep.checks": "这一周的打勾",
  "sleep.check.woke_on_time": "跟着闹钟起", "sleep.check.asleep_in_time": "按时睡着", "sleep.check.slept_enough": "睡够了", "sleep.check.screen_before_sleep_ok": "睡前一小时没刷",
  "sleep.checks_rule": "跟着闹钟起：闹钟后宽限分钟内醒。按时睡着：睡着的时间够在闹钟前睡满目标时长（或在计划关灯前）。睡够了：和目标差不超过 {slack} 分钟。睡前一小时没刷：睡着前一小时娱乐和社交不超过 {min} 分钟。– 是没有记录。",
  "review.title": "{from} – {to} 这一周", "review.sub": "这一周和之前 4 周并排，只摆事实。", "review.partial": "这一周还没过完，数字只算到现在。",
  "review.prev": "上一周", "review.next": "下一周", "review.facts": "这一周的数", "review.this": "这一周", "review.before": "之前 4 周", "review.change": "变化",
  "review.sec.sleep": "睡眠", "review.sec.recovery": "恢复", "review.sec.activity": "活动", "review.sec.screens": "屏幕", "review.sec.self": "自评",
  "review.m.sleep_min": "每晚睡眠", "review.m.onset": "睡着", "review.m.wake": "醒来", "review.m.hrv_ms": "HRV（中位数）", "review.m.resting_hr": "静息心率（中位数）",
  "review.m.steps": "每天步数", "review.m.workout_min": "每天运动", "review.m.workout_days": "训练天数", "review.m.focus": "每天专注做事", "review.m.fun": "每天娱乐",
  "review.m.energy": "自评精力（0–5）", "review.m.focus_self": "自评专注（0–5）", "review.planned": "计划 {n} 天", "review.days": "{n} 天",
  "review.later": "晚", "review.earlier": "早", "review.same": "差不多", "review.gaps": "{days} 没有身体数据。", "review.weight": "这一周的体重",
  "review.weight_change": "比上一周 {v}", "review.weight_days": "称了 {n} 次", "review.due_this": "这一周截止", "review.due_next": "下一周截止", "review.none": "没有。",
  "review.rule": "按有数据的日子取每天平均（HRV 和静息心率取中位数），对照的是这一周之前的 4 周。绿和红只标通常算好或坏的方向，变化很小的保持灰色。",
  "data.sub": "最近 {n} 天到了哪些数据", "data.ok": "数据都在进来", "data.attention": "有数据停了",
  "data.arrivals": "到达情况", "data.s.sleep": "睡眠", "data.s.hrv": "HRV", "data.s.steps": "步数", "data.s.weight": "体重", "data.s.screen": "屏幕时间", "data.s.self": "自评",
  "data.status.ok": "是新的", "data.status.stale": "停了", "data.status.missing": "从来没到过",
  "data.last": "最后一次 {day}（{n} 天前）", "data.last_today": "今天到过", "data.never": "没有数据", "data.days": "{k} 天里有 {n} 天",
  "data.mark.1": "有", "data.mark.p": "不全", "data.mark.0": "没有",
  "data.honest": "缺的日子就是缺：页面不补值、也不当成 0。某路数据停了，页面会写明数字是多久以前的。",
  "data.files": "文件", "data.file": "文件", "data.rows": "行数", "data.modified": "改动", "data.absent": "没有（可选）",
  "data.problems": "{n} 行读不出", "data.clean": "都能读", "data.problem_line": "第 {line} 行，{column}",
  "data.import": "导入数据", "data.import_lede": "所有数据都是数据目录里的普通 CSV 文件。导入工具写它们，你也可以直接手改。",
  "data.import_note": "不往任何地方上传。服务只在这台电脑上监听。",
});

Object.assign(DICT.en, {
  "act.sleep": "Sleep", "act.exercise": "Exercise", "act.calendar": "Calendar", "act.screen": "Screens", "act.not_recorded": "Not recorded",
  "act.fun": "Entertainment & social", "act.focus": "Focused work", "act.communication": "Communication",
  "chg.fun": "entertainment & social", "chg.focus": "focused work", "chg.communication": "communication", "chg.exercise": "exercise",
  "chg.calendar": "calendar time", "chg.sleep": "sleep",
  "chg.short.fun": "Entertainment", "chg.short.focus": "Focus", "chg.short.communication": "Communication", "chg.short.exercise": "Exercise",
  "chg.short.calendar": "Calendar", "chg.short.sleep": "Sleep",
  "chg.more": "more", "chg.less": "less", "chg.up": "up", "chg.down": "down",
  "time.title": "Where your time went", "time.hours": "{h}h", "chart.row_max": "top {v}", "time.span": "{from} – {to} · {n} days with records",
  "time.prev": "Earlier 7 days", "time.next": "Later 7 days", "time.latest": "Latest",
  "time.eyebrow": "What changed",
  "time.change_line": "Compared with your normal, the biggest change these {n} days: {what}, {d} {dir} a day",
  "time.change_sub": "{v} a day these days; your normal is {low}–{high}.",
  "time.change_sub_one": "{v} a day these days; your normal is {low}.", "time.change_sub_none": "{v} a day these days; usually none.",
  "time.band_none": "usually none", "time.slight_high": "just above normal", "time.slight_low": "just below normal",
  "time.also": "Also outside your normal:", "time.chip": "{what} {d} {dir}",
  "time.usual_line": "These {n} days look like your normal", "time.usual_sub": "All within your normal: {list}.",
  "time.usual_sub_slight": "Nothing is clearly outside your normal (only just past its edge: {list}).",
  "time.not_compared": "Not compared (no record, or too few days with one): {list}.",
  "time.no_normal_line": "Not enough days yet to know your normal",
  "time.no_normal_sub": "A normal needs at least {min} days with that record in the {n} days before.",
  "time.day_label": "{what} {dir}", "time.day_usual": "Usual day", "time.day_no_normal": "No normal yet",
  "time.foot_screen": "Screens {v}", "time.foot_ex": "Exercise {v}", "time.foot_rest": "No workout",
  "time.per_day": "Daily average", "time.vs_normal": "each against your normal: the middle half of your 7-day averages in the {n} days before",
  "time.few": "too few days",
  "time.exercise_days": "worked out on {n} of {k} days", "time.sleep_note": "falling asleep to waking, within the day",
  "time.known": "{n} of {k} days have a record", "time.no_record": "no record these days",
  "time.nr_known": "{n} of {k} days have both a night and screen time",
  "time.stale": "{what}: the last whole day on record is {day}, so averages use only the days with one.",
  "time.stale_none": "{what}: no record yet.",
  "time.typical": "A typical day (average of these days; a full bar is 60 minutes in that hour)", "time.history": "Last 30 days",
  "time.history_note": "Each row has its own scale (its top value is under its name); shaded = the days above; × = no record",
  "time.fun_limit": "entertainment limit {v}", "time.limit_short": "limit {v}", "time.focus_goal": "focus goal {v}",
  "time.apps": "On screens, most used", "time.apps_note": "per day", "time.devices": "Devices", "time.no_screens": "No screen time these days.",
  "time.workouts": "Workouts", "time.workouts_note": "from workouts.csv (Apple Fitness via Apple Health, or any CSV)",
  "time.no_workouts": "No workouts these days.", "time.untimed": "Workout minutes are known only as daily totals here, so they are counted but not placed in the hours.",
  "time.empty": "Nothing recorded yet. Import Apple Health (sleep and workouts), a calendar, or Screen Time.",
  "time.restart": "This page has changed and the server still runs the older version. Restart dayring serve to see it.",
  "time.rule": "Every activity is measured from its own record, minute by minute: sleep from your watch (falling asleep to waking), exercise from logged workouts (the minutes moving, pauses left out), calendar from your calendar blocks (planned training is left out, the workout counts instead), screens from app sessions counted once across devices. A minute can belong to two activities, such as a lecture with the laptop open, so the activities can add up to more than the day. Waking minutes that no record covers are shown as not recorded, never guessed. A day without the record an activity needs shows \"—\" for it and is left out of its average and of its normal, never counted as zero: a night with the watch off, Screen Time not imported yet, workouts on the day an Apple Health export was made. Not recorded is only worked out for days with both a night and screen time. On the days the clocks change, the day is 23 or 25 hours long. What changed: entertainment & social, focused work, communication, exercise, calendar time and sleep are each compared with your own normal. The screen total is not one of them: it is the biggest almost every day, which says nothing, and its parts say what moved. A single day is compared with the middle half (25th to 75th percentile) of that activity's daily minutes in the {n} days before it (at least {min} days with that record). The 7 days are compared by their daily average with the middle half of your 7-day averages: one average for the 7 days ending on each of the {n} days before the first of them (each needs 4 days with the record, and at least {min} of them are needed). An average moves far less than a single day, so a week with no exercise or no classes at all stands out even though single days with none are common; the tiles show the 7-day averages against this normal. An average resting on fewer than half of the shown days is shown but not compared. A value counts as a change only when it lies at least one width of its normal outside it; the width counts as at least 30 minutes for a single day and 15 minutes a day for the 7-day average, or a tenth of the usual value when that is larger. Of those changes, the one furthest in minutes from the middle of its normal is named, a tie going to the order above. A value only just past its normal is called just above or just below and is not coloured. Green and red only show the direction: less entertainment, more focused work, more exercise and more sleep count as better; communication and calendar time have no better direction. There is no comparison with the 7 days before: one normal for the whole page.",
  "dev.phone": "phone", "dev.tablet": "tablet", "dev.laptop": "laptop", "dev.desktop": "desktop", "dev.mac": "Mac", "dev.other": "other",
  "wtype.hiit": "HIIT",
});
Object.assign(DICT.zh, {
  "act.sleep": "睡眠", "act.exercise": "运动", "act.calendar": "日程", "act.screen": "屏幕", "act.not_recorded": "没有记录",
  "act.fun": "娱乐和社交", "act.focus": "专注做事", "act.communication": "沟通",
  "chg.fun": "娱乐和社交", "chg.focus": "专注做事", "chg.communication": "沟通", "chg.exercise": "运动", "chg.calendar": "日程", "chg.sleep": "睡眠",
  "chg.short.fun": "娱乐社交", "chg.short.focus": "专注", "chg.short.communication": "沟通", "chg.short.exercise": "运动",
  "chg.short.calendar": "日程", "chg.short.sleep": "睡眠",
  "chg.more": "多", "chg.less": "少", "chg.up": "多", "chg.down": "少",
  "time.title": "时间去向", "time.hours": "{h} 小时", "chart.row_max": "最高 {v}", "time.span": "{from} – {to} · {n} 个有记录的日子",
  "time.prev": "往前 7 天", "time.next": "往后 7 天", "time.latest": "最近",
  "time.eyebrow": "变了什么",
  "time.change_line": "和平常比，这 {n} 天变化最大的是|{what}：每天{dir} {d}",
  "time.change_sub": "这几天每天 {v}，平常 {low}–{high}。",
  "time.change_sub_one": "这几天每天 {v}，平常是 {low}。", "time.change_sub_none": "这几天每天 {v}，平常没有。",
  "time.band_none": "平常没有", "time.slight_high": "略高于平常", "time.slight_low": "略低于平常",
  "time.also": "也和平常不一样：", "time.chip": "{what}{dir} {d}",
  "time.usual_line": "这 {n} 天和平常差不多", "time.usual_sub": "{list}都在平常范围里。",
  "time.usual_sub_slight": "没有哪一项明显超出平常（{list}只是略微超出）。",
  "time.not_compared": "没比（缺记录，或有记录的日子太少）：{list}。",
  "time.no_normal_line": "还没有足够的日子算出平常值",
  "time.no_normal_sub": "平常值要之前 {n} 天里至少 {min} 天有这项记录。",
  "time.day_label": "{what} {dir}", "time.day_usual": "和平常差不多", "time.day_no_normal": "还没有平常值",
  "time.foot_screen": "屏幕 {v}", "time.foot_ex": "运动 {v}", "time.foot_rest": "没运动",
  "time.per_day": "每天平均", "time.vs_normal": "都和你的平常比：之前 {n} 天里 7 天平均的中间一半",
  "time.few": "记录太少",
  "time.exercise_days": "{k} 天里练了 {n} 天", "time.sleep_note": "从睡着到醒来，按当天的钟点算",
  "time.known": "{k} 天里 {n} 天有记录", "time.no_record": "这几天没有记录",
  "time.nr_known": "{k} 天里 {n} 天睡眠和屏幕都有记录",
  "time.stale": "{what}的完整记录最晚到 {day}，平均只算有记录的那几天。",
  "time.stale_none": "{what}还没有记录。",
  "time.typical": "典型的一天（这几天的平均；满格 = 那个小时 60\u00a0分钟）", "time.history": "最近 30 天",
  "time.history_note": "每一行各用自己的刻度（最高值写在名字下面）；灰底 = 上面那几天；× = 没有记录",
  "time.fun_limit": "娱乐上限 {v}", "time.limit_short": "上限 {v}", "time.focus_goal": "专注目标 {v}",
  "time.apps": "屏幕上用得最多", "time.apps_note": "每天平均", "time.devices": "设备", "time.no_screens": "这几天没有屏幕时间。",
  "time.workouts": "训练", "time.workouts_note": "来自 workouts.csv（Apple 健康里的 Fitness 记录，或任意 CSV）",
  "time.no_workouts": "这几天没有训练。", "time.untimed": "这里的训练只有每天的总分钟，没有开始时间，所以算进总数，但画不进每小时。",
  "time.empty": "还没有记录。导入 Apple 健康（睡眠和训练）、日历或屏幕使用时间。",
  "time.restart": "这一页改过了，服务还在跑旧版本。重启 dayring serve 就能看到。",
  "time.rule": "每一项都按它自己的记录一分钟一分钟地算：睡眠看手表（从睡着到醒来），运动看记下的训练（只算在动的分钟，暂停不算），日程看日历（计划里的训练不算，算实际练的那次），屏幕看几台设备的应用使用、同一时刻只算一次。一分钟可以同时算两项，比如开着电脑上课，所以各项加起来可能超过一天。醒着却哪一项都没记到的时间写成“没有记录”，不去猜。哪天缺了某一项需要的记录，那一项就写“—”，也不算进它的平均和平常值，绝不当成 0：比如手表那晚没戴、屏幕使用时间还没导入、导出 Apple 健康那天的训练。“没有记录”只算睡眠和屏幕都有记录的日子。调时钟（夏令时）那两天，一天是 23 或 25 小时。变了什么：娱乐和社交、专注做事、沟通、运动、日程、睡眠这六项，各自和你自己的平常比。屏幕总时间不参与：它几乎每天都最多，说明不了什么，变的是它里面的几项。单独一天的平常 = 这一项在它之前 {n} 天里每天分钟数的中间一半（第 25 到第 75 百分位，至少要 {min} 天有这项记录）。这 7 天用每天平均来比，平常 = 你的 7 天平均的中间一半：第一天之前的 {n} 天里，以每一天结尾的 7 天各算一个平均（每个平均至少要 4 天有记录，这样的平均至少要 {min} 个）。7 天平均比单独一天稳得多，所以一整周没运动、没课也能看出来，哪怕单独几天是 0 很常见；下面的小卡片就是 7 天平均和这个平常比。有记录的日子不到一半的，照样显示，但不比。超出平常至少“一个平常范围的宽度”才算变化；宽度至少按 30 分钟算（7 天平均按每天 15 分钟），平常值的十分之一更大时按它算。这些变化里，离平常中间值的分钟数最多的那项写出来；一样多时按上面的顺序。只超出一点的写“略高于平常”或“略低于平常”，不上颜色。绿和红只表示方向：娱乐少、专注多、运动多、睡得多算好；沟通和日程没有好坏方向。不和再往前的 7 天比：整页只用一个平常值。",
  "dev.phone": "手机", "dev.tablet": "平板", "dev.laptop": "笔记本", "dev.desktop": "台式机", "dev.mac": "Mac", "dev.other": "其他设备",
  "wtype.workout": "训练", "wtype.other": "其他训练", "wtype.strength training": "力量训练", "wtype.functional strength training": "功能性力量训练",
  "wtype.hiit": "高强度间歇训练", "wtype.mixed cardio": "混合有氧", "wtype.cross training": "交叉训练", "wtype.mind and body": "身心训练",
  "wtype.core training": "核心训练", "wtype.flexibility": "柔韧训练", "wtype.cooldown": "放松整理",
  "wtype.running": "跑步", "wtype.walking": "步行", "wtype.hiking": "徒步", "wtype.cycling": "骑行", "wtype.swimming": "游泳",
  "wtype.rowing": "划船", "wtype.elliptical": "椭圆机", "wtype.stair climbing": "爬楼梯", "wtype.stairs": "爬楼梯",
  "wtype.yoga": "瑜伽", "wtype.pilates": "普拉提", "wtype.dance": "舞蹈", "wtype.boxing": "拳击", "wtype.kickboxing": "搏击操",
  "wtype.martial arts": "武术", "wtype.climbing": "攀岩", "wtype.badminton": "羽毛球", "wtype.tennis": "网球", "wtype.table tennis": "乒乓球",
  "wtype.basketball": "篮球", "wtype.soccer": "足球", "wtype.football": "足球", "wtype.volleyball": "排球", "wtype.skating": "滑冰",
  "wtype.snow sports": "雪上运动", "wtype.jump rope": "跳绳", "wtype.water sports": "水上运动", "wtype.surfing sports": "冲浪",
});

// ---- Drain page and the grouped menu ----
Object.assign(DICT.en, {
  "nav.drain": "Drain", "nav.weight": "Weight", "nav.sleep_tab": "Sleep",
  "drain.title": "Drain", "drain.sub": "{from} – {to}, against the 28 days before",
  "drain.prev": "Earlier 7 days", "drain.next": "Later 7 days", "drain.latest": "Latest",
  "drain.eyebrow": "What is quietly wearing you down", "drain.sep": ", ",
  "drain.worse_none": "Against your normal, nothing got worse", "drain.worse_some": "Against your normal, {n} got worse: {list}",
  "drain.plan_none": "Everything with a plan is within it.", "drain.plan_some": "Against your plan: {list}.",
  "drain.plan_unset": "No plans set for these yet (plan.sleep.bedtime, plan.screen.entertainment_max_hours).",
  "drain.items": "Seven signals", "drain.weeks": "Last 8 weeks", "drain.week_to": "week to {day}",
  "drain.key.normal": "your normal", "drain.key.now": "last 7 days", "drain.key.plan": "plan",
  "drain.item.resting_hr": "Resting heart rate", "drain.item.hrv": "HRV", "drain.item.asleep": "Falling asleep",
  "drain.item.spread": "Sleep-timing spread", "drain.item.before_sleep": "Screens in the hour before sleep",
  "drain.item.fun": "Entertainment & social", "drain.item.switches": "App switching",
  "drain.why.resting_hr": "Staying high: the stress side of the nervous system is winning, recovery is worse.",
  "drain.why.hrv": "Staying low: less vagal tone. Watch HRV jumps around daily, so read the weekly direction.",
  "drain.why.asleep": "Later pushes the body clock back; enough hours does not fully make up for it.",
  "drain.why.spread": "How much the middle of your sleep moves night to night; large = the body clock never lines up.",
  "drain.why.before_sleep": "Light holds back melatonin and stimulating content keeps you alert, so sleep comes later.",
  "drain.why.fun": "Dense, high-reward input. The evidence here is softer than for the signals above.",
  "drain.why.switches": "The more often you switch apps, the more scattered attention gets; each switch leaves residue.",
  "drain.state.bad": "worse than normal", "drain.state.good": "better than normal", "drain.state.neutral": "within normal",
  "drain.no_window": "too few records in the last 7 days", "drain.no_baseline": "no normal yet",
  "drain.usual": "normal {a}–{b}", "drain.per_hour": "{v} an hour",
  "drain.plan.bedtime": "plan: asleep by {clock}", "drain.plan.limit": "limit {v}", "drain.plan.ok": "within plan",
  "drain.plan.over.asleep": " later than planned by {d}", "drain.plan.over.fun": " over the limit by {d}",
  "drain.rule": "Against your normal: the average of the last {w} days against the middle half of the {b} days before (sleep-timing spread: against the range of the four 7-night blocks before). Outside that band in the worse direction counts as worse; if your normal was already bad, it will say within normal, which is why the plan comparison is separate. Against your plan: falling asleep against plan.sleep.bedtime, entertainment & social against plan.screen.entertainment_max_hours in dayring.toml. Each signal uses only days its own record covers. There is no total score: the signals have different units and different strength of evidence.",
  "today.drain": "Drain, last 7 days", "today.drain_more": "See what is wearing you down →",
});
Object.assign(DICT.zh, {
  "nav.drain": "消耗", "nav.weight": "体重", "nav.sleep_tab": "作息",
  "drain.title": "消耗", "drain.sub": "{from} – {to}，和之前 28 天比",
  "drain.prev": "往前 7 天", "drain.next": "往后 7 天", "drain.latest": "最近",
  "drain.eyebrow": "哪些东西在悄悄耗你", "drain.sep": "、",
  "drain.worse_none": "跟自己的平常比，没有哪项变差", "drain.worse_some": "跟自己的平常比，有 {n} 项变差：{list}",
  "drain.plan_none": "定了计划的几项都在计划内。", "drain.plan_some": "跟计划比：{list}。",
  "drain.plan_unset": "这几项还没定计划（plan.sleep.bedtime、plan.screen.entertainment_max_hours）。",
  "drain.items": "七个信号", "drain.weeks": "最近 8 周", "drain.week_to": "到 {day} 的一周",
  "drain.key.normal": "你的平常", "drain.key.now": "最近 7 天", "drain.key.plan": "计划",
  "drain.item.resting_hr": "静息心率", "drain.item.hrv": "HRV", "drain.item.asleep": "入睡时刻",
  "drain.item.spread": "作息波动", "drain.item.before_sleep": "睡前一小时屏幕",
  "drain.item.fun": "娱乐和社交", "drain.item.switches": "应用切换",
  "drain.why.resting_hr": "持续偏高：交感神经占上风，恢复变差。",
  "drain.why.hrv": "持续偏低：副交感（迷走）张力下降。手表的 HRV 每天波动大，看几周的方向。",
  "drain.why.asleep": "越晚，生物钟越往后推；时长睡够了也补不全。",
  "drain.why.spread": "每晚睡眠中点差多少；大 = 生物钟每天对不齐。",
  "drain.why.before_sleep": "光抑制褪黑素，内容让人更清醒，都会推迟入睡。",
  "drain.why.fun": "奖励密集的高刺激输入。这一条的证据比上面几条软。",
  "drain.why.switches": "切得越勤，注意力越碎，每次切换都会留下残留。",
  "drain.state.bad": "比平常差", "drain.state.good": "比平常好", "drain.state.neutral": "在平常范围",
  "drain.no_window": "最近 7 天记录不够", "drain.no_baseline": "还定不出平常",
  "drain.usual": "平常 {a}–{b}", "drain.per_hour": "每小时 {v} 次",
  "drain.plan.bedtime": "计划 {clock} 前睡着", "drain.plan.limit": "上限 {v}", "drain.plan.ok": "在计划内",
  "drain.plan.over.asleep": "比计划晚 {d}", "drain.plan.over.fun": "比上限多 {d}",
  "drain.rule": "跟平常比：最近 {w} 天的平均，对之前 {b} 天每天的中间一半（作息波动对之前 4 段、每段 7 晚的范围），往坏的方向出界算变差；平常本来就差时这里会说在平常范围，所以跟计划比单独写。跟计划比：入睡对 dayring.toml 里的 plan.sleep.bedtime，娱乐和社交对 plan.screen.entertainment_max_hours。每个信号只用它自己的记录覆盖到的日子。不打总分：几项的单位不同，证据强弱也不同。",
  "today.drain": "消耗 · 最近 7 天", "today.drain_more": "看哪些在耗你 →",
});

const WEEKDAY = { en: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"], zh: ["周日", "周一", "周二", "周三", "周四", "周五", "周六"] };
const MONTH = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

let lang = "en";
export const getLang = () => lang;
export function setLang(next) { lang = DICT[next] ? next : "en"; document.documentElement.lang = lang === "zh" ? "zh-CN" : "en"; }

export function t(key, vars = {}) {
  const text = (DICT[lang] && DICT[lang][key]) ?? DICT.en[key] ?? key;
  return text.replace(/\{(\w+)\}/g, (_, name) => (vars[name] ?? `{${name}}`));
}

// a workout type as the importer writes it ("strength training"), in the page's language
export function wtype(name) {
  if (!name) return "—";
  const hit = DICT[lang] && DICT[lang][`wtype.${String(name).toLowerCase()}`];
  if (hit) return hit;
  return lang === "en" ? String(name).charAt(0).toUpperCase() + String(name).slice(1) : String(name);
}

// a device name from screen_sessions ("phone", "laptop-2"), in the page's language; other names stay as typed
export function device(name) {
  const m = /^(phone|tablet|laptop|desktop|mac|other)(-\d+)?$/.exec(String(name || ""));
  return m ? `${DICT[lang][`dev.${m[1]}`] ?? DICT.en[`dev.${m[1]}`]}${m[2] || ""}` : String(name ?? "");
}

const parse = (iso) => {
  const [d, time = "00:00"] = String(iso).split("T");
  const [y, m, day] = d.split("-").map(Number);
  const [hh, mm] = time.split(":").map(Number);
  return new Date(y, m - 1, day, hh || 0, mm || 0);
};
export const toDate = parse;

export function dur(minutes, { short = false } = {}) {
  if (minutes === null || minutes === undefined || Number.isNaN(minutes)) return "—";
  const total = Math.round(Math.abs(minutes));
  const h = Math.floor(total / 60), m = total % 60;
  if (lang === "zh") {
    if (h === 0) return `${m} 分`;
    return m || !short ? `${h} 小时 ${m} 分`.replace(/ 0 分$/, "") : `${h} 小时`;
  }
  if (h === 0) return `${m}m`;
  return m ? `${h}h ${m}m` : `${h}h`;
}

export function clock(iso) {
  if (!iso) return "—";
  const d = parse(iso);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export function day(iso, { weekday = true } = {}) {
  if (!iso) return "—";
  const d = parse(iso);
  if (lang === "zh") return `${d.getMonth() + 1}月${d.getDate()}日${weekday ? " " + WEEKDAY.zh[d.getDay()] : ""}`;
  return `${weekday ? WEEKDAY.en[d.getDay()] + " " : ""}${d.getDate()} ${MONTH[d.getMonth()]}`;
}

export function shortDay(iso) {
  const d = parse(iso);
  return lang === "zh" ? `${d.getMonth() + 1}/${d.getDate()}` : `${d.getDate()} ${MONTH[d.getMonth()]}`;
}

export function weekdayShort(iso) { return WEEKDAY[lang][parse(iso).getDay()]; }

export function num(value, digits = 0) {
  if (value === null || value === undefined) return "—";
  return Number(value).toLocaleString(lang === "zh" ? "zh-CN" : "en-AU", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

export function signed(value, digits = 1, unit = "") {
  if (value === null || value === undefined) return "—";
  const s = value > 0 ? "+" : value < 0 ? "−" : "±";
  return `${s}${num(Math.abs(value), digits)}${unit}`;
}

export function pct(fraction, digits = 0) { return `${num(Math.abs(fraction) * 100, digits)}%`; }

// value in a metric's own unit, as text with its unit
export function measure(value, unit) {
  if (value === null || value === undefined) return "—";
  if (unit === "min") return dur(value);
  if (unit === "steps") return lang === "zh" ? `${num(value)} 步` : `${num(value)}`;
  if (unit === "ms") return `${num(value)} ms`;
  if (unit === "bpm") return lang === "zh" ? `${num(value)} 次/分` : `${num(value)} bpm`;
  return num(value);
}
