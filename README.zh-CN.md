# dayring

一个本地优先的个人看板：睡眠、恢复、时间去向和截止日期，每一项都和你自己的平常比。

**[在线演示](https://wannian001.github.io/dayring/)**（一个虚构的学生，没有真实数据）· [English](README.md)

![今天页，青瓷主题](docs/images/today-zh-celadon.png)

最上面的环是 24 小时的一天：外圈是昨晚的睡眠，中圈是今天的日程（当天的训练用它自己的颜色画在上面），内圈是每小时的屏幕时间，按用途上色。
下面所有内容都在回答一个问题：和我自己最近四周比，今天怎么样？

## 每一页回答什么

| 页面 | 回答的问题 |
|---|---|
| **今天** | 恢复得怎么样（睡眠、HRV、静息心率，各自和你之前 28 天的中间 50% 比）？今天要做什么，今晚几点放手机、几点睡？昨天屏幕时间花在哪了？做什么第二天会更好？ |
| **本周** | 七天的课、截止和训练；接下来几周按占成绩的比例看有多重。 |
| **身体** | 体重 7 天平均是不是在计划允许的走廊里、每周降多少、长期走势。 |
| **作息** | 21 晚画在同一根轴上，这周和上周比；可选的起床前移计划：每按时起一天，闹钟往前挪一步。 |
| **时间** | 时间都去哪了，和平常比变了什么？睡眠、训练、日程和屏幕（手机、平板、电脑同一时刻只算一次）各按自己的记录算，各自和你的平常（之前 28 天的中间一半）比。最上面写的是离平常最远的那一项（比如娱乐社交多了），而不是占得最多的那一项；每天一个图标标出当天的变化，下面写当天的屏幕时间和运动分钟。哪项记录都没覆盖的时间写成“没有记录”。按小时、按应用、最近 30 天。 |
| **复盘** | 一周的事实和之前四周并排。不打分，不评价。 |
| **数据** | 90 天里每天到了什么数据、哪些文件有读不出的行、怎么继续导入。 |

<p>
  <img src="docs/images/week.png" width="49%" alt="本周页">
  <img src="docs/images/sleep-zh.png" width="49%" alt="作息页">
</p>

界面中英双语，三套主题（暮色、石墨、青瓷），深浅色都有，手机和电脑都能用。

## 它怎么判断

- **只和自己比。** “平常”是你自己之前 28 天的第 25–75 百分位，从不拿人群标准比。三项恢复指标里两项以上变差，就说“恢复低于平常”。
- **缺的就是缺。** 空格表示不知道，不当成 0。同步时还没过完的那天照样显示，但不跟平常比。某路数据停了，每一页都会写明数字是多久以前的。醒着却没有任何记录覆盖的时间写成“没有记录”，不摊到别的项目里。
- **是关联，不是因果。** “做什么第二天会更好”拿做了和没做的第二天比，给 95% 区间，整张表一起做 Benjamini–Hochberg 校正，只有校正后还成立的才上颜色；页面也写明为什么状态好的日子本来就更可能去练。
- **颜色有含义。** 数据颜色跟着被测的东西走（专注永远是蓝，娱乐永远是橙，运动永远是品红），做过色弱校验；绿和红只用来表示更好和更差，而且一定配文字。

## 快速开始

需要 Python 3.9 以上，不用装别的包。

```bash
git clone https://github.com/wannian001/dayring.git
cd dayring
python3 -m dayring serve --demo
```

打开 <http://localhost:8790>。换成你自己的数据：

```bash
cp examples/dayring.example.toml dayring.toml     # 时区、计划、设备
python3 -m dayring import apple-health ~/Downloads/export.zip
python3 -m dayring import ics ~/Downloads/timetable.ics --kind class
python3 -m dayring import macos-screentime        # 只限 macOS，试验性
python3 -m dayring check                           # 看哪些行读不出
python3 -m dayring serve
```

Apple 健康导出的数据里也有你的每次训练，带开始和结束时间（Apple Fitness 和“体能训练” App 记下的都在里面），所以时间页能把运动放进一天里，和睡眠、上课、屏幕排在一起。

截止日期、自评、别的 App 记的训练等其他数据都是普通 CSV，可以手改，也可以从别的导出文件映射过来
（`python3 -m dayring import csv deadlines my-tracker.csv --map "Due=due,Task=title,Course=group"`）。

## 数据只在你的电脑上

- 数据是你指定文件夹里的普通 CSV（[格式](docs/DATA_FORMAT.md)）。导入工具写它们（[每个导入工具怎么工作](docs/IMPORTERS.md)），看板只读。
- 服务只监听 `127.0.0.1`，没有写接口，不往任何地方发数据。
- `build-static`（演示站用的）遇到你自己的数据会拒绝运行，除非你加一个明确表示“我要公开”的参数。

## 怎么搭的

```
导入工具 ─▶ data/*.csv ─▶ 读取层（按 schema.py 检查）─▶ 各页计算 ─▶ JSON ─▶ 网页
Apple 健康、.ics、        一张表一个文件，              今天、本周、身体、      原生 JS，
屏幕使用时间、任意 CSV    坏行只报告、不中断            作息、时间……           手画 SVG
```

- `dayring/schema.py` 是所有表的唯一定义，`docs/DATA_FORMAT.md` 由它生成。
- 每页的计算只返回数字、单位、平常范围和状态，不返回句子；文字由浏览器写，所以同一份数据能切中英文（`dayring/web/js/i18n.js`）。
- `python3 -m dayring page today` 打出一页的 JSON，脚本或 AI 助手读到的数和页面上的一样。
- 演示站就是同一个网页加上预先算好的 JSON（`python3 -m dayring build-static --demo`），放在 GitHub Pages 上。
- 设计说明：[docs/DESIGN.md](docs/DESIGN.md)。

## 开发

```bash
python3 -m unittest discover -s tests      # Python 3.9–3.13 都能跑
python3 -m dayring page today --demo --today 2026-10-12
```

## 来历

dayring 是我每天在用的个人系统里抽出来的公开、通用的核心。私有版本读我自己的手表、手机和电脑数据，用的是同一套界面；这个仓库里没有任何那边的数据。

## 许可

[MIT](LICENSE)
