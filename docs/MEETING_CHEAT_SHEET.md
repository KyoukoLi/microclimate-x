# 📋 Supervisor Meeting Cheat Sheet
# 📋 导师开会一页通

> **Open this on your laptop during the meeting.** Print it if you prefer paper.
> Everything you need is in this single document.
>
> **开会时电脑屏幕开着这一页就够。** 想要纸质版直接打印。
> 所有内容都在这一份文档里。

---

## 🔧 0. Before the meeting (10 minutes before)
## 🔧 0. 会前 10 分钟准备

Run these in a terminal, in order. **Do not skip any.**
在终端按顺序执行，**一条都不能少**：

```bash
cd ~/Projects/microclimate-x

# 1. Pull latest + verify clean working tree
git pull && git status        # should print "working tree clean"

# 2. Start the backend (leave running in this terminal)
make run                      # uvicorn boots on http://localhost:8000

# 3. In a NEW terminal: verify the API is alive + model is loaded
curl -s http://localhost:8000/api/health | python3 -m json.tool
# expect: "status": "ok", "ml_loaded": true
```

If `ml_loaded` is **false**, run `make train` first — but this should already be done.
如果 `ml_loaded` 显示 **false**，先跑 `make train` —— 但理论上之前已经训好了。

### Browser tabs to open in this exact order / 浏览器按顺序开好这几个标签页

| # | URL | Purpose |
|---|---|---|
| 1 | `file:///…/microclimate-x/docs/MEETING_CHEAT_SHEET.md` (this file) | Your safety net |
| 2 | `https://github.com/KyoukoLi/microclimate-x` | Show CI green badge |
| 3 | `file:///…/microclimate-x/docs/dataset.md` | For Concern #1 + #2 |
| 4 | `file:///…/microclimate-x/figures/01_roc_curve.png` | For Concern #4 step 2 |
| 5 | `file:///…/microclimate-x/figures/03_calibration_curve.png` | |
| 6 | `file:///…/microclimate-x/figures/04_threshold_sweep.png` | |
| 7 | `file:///…/microclimate-x/figures/05_feature_importance.png` | |
| 8 | `file:///…/microclimate-x/docs/architecture.md` | For rule engine section |
| 9 | `http://localhost:8000/app/` | **The actual app — OPEN LAST** |
| 10 | `file:///…/microclimate-x/models/MODEL_CARD.md` | Q&A backup |

🚨 **Tab 9 (the app) MUST be opened LAST.** If you accidentally show the app first the supervisor will remember last meeting's complaint ("app is last") and you lose credibility.

🚨 **标签 9（app）一定要最后打开。** 不小心先打开 app 老师就会立刻想起上次 "app is last" 的批评。

---

## 🎬 1. Opening (30 seconds)
## 🎬 1. 开场（30 秒）

> **EN**: "Sir, since our last meeting I have addressed every point of your feedback. May I walk you through them in the correct order — **dataset first, then model, then app** — as you instructed?"
>
> **ZH**: "老师，按您上次反馈，我已经把每一条都改了。我按您要求的顺序——**先 dataset，再 model，最后才是 app**——给您过一遍可以吗？"

**Why this works**: directly quotes his words back to him. He relaxes immediately.
**为什么有效**：直接复述了他自己的话，他会立刻放松。

---

## 📊 2. Concern #1 — "Y is missing"
## 📊 2. 反馈一 —— Y 列缺失

**His original words / 老师原话**: *"Y is missing. I don't have the output variable. If you don't have target, you cannot train a machine learning model."*

### What to do on screen / 屏幕操作

1. Switch to Tab 3 (`docs/dataset.md`)
2. Scroll to **§5 Target label derivation**
3. Point to the highlighted code line:

```python
df['is_rain_event'] = (df['precipitation'].shift(-1) > 0.1).astype(int)
```

### What to say / 怎么说

| 🇬🇧 EN | 🇨🇳 ZH |
|---|---|
| "Sir, you were right — the raw Open-Meteo CSV has no Y column. I have engineered the target explicitly. The variable is called `is_rain_event` and it is defined as **1 if the precipitation in the next hour is greater than 0.1 mm, else 0**." | "老师您说得对，原始 CSV 没有 Y 列。我现在已经显式构造了目标变量 **`is_rain_event`**——**下一小时降雨量 > 0.1 mm 则为 1，否则为 0**。" |
| "Three things to notice. First, `.shift(-1)` means I use **future** rain as the label — features at hour t predict outcome at t+1h, so there is no temporal data leakage." | "三个要点：(1) `.shift(-1)` 表示用**下一小时**的降雨作标签，特征是 t 时刻、预测的是 t+1 小时——**无时间泄漏**。" |
| "Second, the 0.1 mm threshold matches the **WMO definition of trace precipitation** — it is not an arbitrary choice." | "(2) 0.1 mm 这个阈值不是我随便定的，对应 **WMO 微量降水标准**。" |
| "Third, it is **binary classification**, not regression, because the downstream user decision is binary — go or no-go." | "(3) 是**二分类**不是回归，因为下游用户决策本身就是二元的——去 / 不去。" |

---

## 📊 3. Concern #2 — "Features in document don't match Excel"
## 📊 3. 反馈二 —— 文档里的特征和 CSV 列名对不上

**His original words / 老师原话**: *"The features that you presented here, not... not mentioned in the Excel. So, it must be matched."*

### What to do on screen / 屏幕操作

Stay on Tab 3 (`docs/dataset.md`). Scroll **up** to **§4 Schema**. Show the column table.

### What to say / 怎么说

| 🇬🇧 EN | 🇨🇳 ZH |
|---|---|
| "Sir, that was also a fair point. I have rewritten the dataset specification so the documentation lists **exactly the same column names** that appear in the CSV. There is a one-to-one mapping right here in §4." | "老师，这条您也说得对。我已经重写了数据集文档，文档里列出的就是 CSV 里的**真实列名**，一一对应，就在第 4 节这里。" |
| "Every row in this table is one column in the actual CSV. The 'role' column says whether it is a feature (**X**), the target (**Y**), or just metadata." | "表里每一行就是 CSV 里的一列，role 列写明了它是 feature（**X**）、target（**Y**）还是 metadata。" |

---

## 📊 4. Concern #3 — "Study the data source"
## 📊 4. 反馈三 —— 研究数据源本身

**His original words / 老师原话**: *"Please study the link. What is the purpose of the dataset? What is design for? What is the output variable?"*

### What to do on screen / 屏幕操作

Stay on Tab 3 (`docs/dataset.md`). Scroll back **up** to **§1-3** (Source / Spatial coverage / Temporal coverage).

### What to say / 怎么说

| 🇬🇧 EN | 🇨🇳 ZH |
|---|---|
| "I read the Open-Meteo API documentation carefully. The dataset I use is the **ERA5 reanalysis archive**, which is ECMWF's gold-standard hourly reanalysis." | "我把 Open-Meteo 文档仔细读了。我用的是 **ERA5 再分析数据**，是 ECMWF 出的金标准同化产品。" |
| "It is *not* a forecast — it is a physically-consistent reconstruction of past weather. ECMWF themselves use ERA5 to **validate other forecast models**. That is why it is the right dataset for training ML: the labels are reliable ground truth." | "它**不是**预报，是对过去天气的物理一致的重建。ECMWF 自己用 ERA5 去**校验别的预报模型**——所以拿来训练 ML 是合适的，**标签是可靠的 ground truth**。" |
| "Spatial coverage: 5 Malaysian mountain sites — Genting, Cameron, Fraser's Hill, Klang Valley, Kinabalu — chosen to span elevations from 100 m to 1865 m and terrain from valley to slope." | "空间覆盖 5 个马来西亚山地点位——云顶、金马仑、福隆港、巴生谷、神山——海拔 100 m 到 1865 m，地形从山谷到山坡都有。" |
| "Temporal coverage: 5 years, hourly, 175 315 rows total." | "时间范围 5 年，每小时一行，总共 175 315 行。" |

---

## 📊 5. Concern #4 — "App is the last"
## 📊 5. 反馈四 —— App 放在最后做

**His original words / 老师原话**: *"First, identify a dataset. And then train the model. And then predict it. Once everything is finished, you can develop the app. App is the last."*

🚨 **This is the most important section.** Pace yourself — about 2-3 minutes total. **Don't open the app until the very end.**
🚨 **这是最重要的一节。** 控制节奏，总共大约 2-3 分钟。**不要提前打开 app。**

### Step-by-step on-screen demo / 逐步演示

#### Step 2a — ROC curve / 第二步 a：ROC 曲线
→ Switch to **Tab 4** (`figures/01_roc_curve.png`)

| 🇬🇧 EN | 🇨🇳 ZH |
|---|---|
| "Step 2, model training. Test ROC AUC is **0.871** on 35 063 held-out hourly samples. The hold-out is the **last 20 % chronologically**, not a random split — random splits leak temporal autocorrelation and would inflate accuracy unrealistically by 5-15 percentage points." | "第二步，模型训练。测试集 35 063 行，**ROC AUC = 0.871**。划分用的是**按时间排序的最后 20%**，不是随机划分——随机划分会泄漏时间自相关，把准确率虚高 5-15 个百分点。" |

#### Step 2b — Calibration / 第二步 b：校准度
→ Switch to **Tab 5** (`figures/03_calibration_curve.png`)

| 🇬🇧 EN | 🇨🇳 ZH |
|---|---|
| "Brier score is **0.138**, which means the predicted probabilities are well-calibrated — when the model says 70 % chance of rain, the actual rate is close to 70 %. So I do not need post-hoc calibration like Platt scaling or isotonic regression." | "Brier 分数 = **0.138**，说明预测概率**校准良好**——模型说 70% 概率时，实际频率接近 70%。**不需要额外做** Platt scaling 或 isotonic 校准。" |

#### Step 2c — Threshold choice / 第二步 c：阈值选择
→ Switch to **Tab 6** (`figures/04_threshold_sweep.png`)

| 🇬🇧 EN | 🇨🇳 ZH |
|---|---|
| "I optimised the decision threshold for **F2 score**, not F1, because in this safety-critical application a missed rain event on a windward slope can lead to flash flooding — false negatives are much worse than false positives." | "我用 **F2 分数**而不是 F1 来选最优阈值——因为这是安全关键应用，**漏报**比误报严重得多。" |
| "F2 weights recall four times more than precision. The optimal threshold is τ = **0.20**, giving F2 = 0.778 and **93.4 % recall**." | "F2 把召回率的权重设为精度的 4 倍。最优阈值是 τ = **0.20**，F2 = 0.778，**召回率 93.4%**。" |

#### Step 2d — What the model learned / 第二步 d：模型学到了什么
→ Switch to **Tab 7** (`figures/05_feature_importance.png`)

| 🇬🇧 EN | 🇨🇳 ZH |
|---|---|
| "Top three features: previous hour's rain, time-of-day cyclic encoding, and 3-hour pressure tendency. These match the meteorological literature — autocorrelation, diurnal cycle, and storm precursor. So the model has learned something physically meaningful." | "模型最看重的 3 个特征：上一小时降水、时间周期编码、3 小时气压变化。**跟气象文献吻合**——自相关、日变化、风暴前兆。模型学到的是**物理上有意义的信号**。" |

#### Step 3 — The app (last) / 第三步：App（最后）
→ Switch to **Tab 9** (`http://localhost:8000/app/`)

| 🇬🇧 EN | 🇨🇳 ZH |
|---|---|
| "**Now**, Step 3, the app. This is FastAPI plus Vue using the trained model from Step 2 — not a separate model, not a placeholder. When I click any coordinate, the system returns the probability and the four hazard sub-scores per proposal §3.7." | "**现在**第三步，app。这是 FastAPI + Vue 调用刚才**第二步训好的模型**——不是另一个模型、也不是占位符。点地图任意一点，系统返回概率和四个分项灾害评分（按开题 §3.7）。" |

### Demo scenario A — Genting Highlands (familiar territory)
### Demo 场景 A —— 云顶高原（训练数据内）

1. Click the **🇲🇾 Genting Highlands · slope** option in the scenario dropdown (top right)
2. Wait ~1 second for the loading spinner to finish
3. Point to the **risk gauge** (main number)
4. Point to the **4 mini-gauges** below (rainfall / fog / wind / thunderstorm)

| Say in EN | 用中文说 |
|---|---|
| "Genting is a slope at 1865 m. The model gives a moderate rain probability, the rule engine picks up orographic lift on the windward side, and the composite score reflects both. The 4 mini-gauges decompose the risk by hazard type so the user knows whether to worry about rain, fog, wind, or thunder specifically." | "云顶是 1865 m 的山坡，模型给出中等降雨概率，规则引擎检测到迎风坡的地形抬升，最终评分综合两者。4 个 mini-gauge 把风险按类型拆解——用户能看出该担心降雨、雾、风、还是雷暴。" |

### Demo scenario B — Mt Everest (out-of-distribution stress test)
### Demo 场景 B —— 珠穆朗玛峰（分布外压力测试）

1. Click the **🏔️ Mt Everest · 8 848 m (OOD)** option in the dropdown
2. Wait for the result
3. Point to the **Veto triggers** section (blinking red box)

| Say in EN | 用中文说 |
|---|---|
| "This is the critical test. The model was trained only on Malaysian mountains — it has never seen anything above 2000 m. A pure ML system would give a low probability here and falsely return 'safe', and a hiker could die." | "**这是关键测试**。模型只在马来西亚山地训练过——从未见过 2000 m 以上的地点。**纯 ML 系统**会给出低概率然后错误地返回"安全"——登山者可能因此遇难。" |
| "But the hybrid architecture intervenes: the Veto cascade fires three independent overrides — altitude > 3500 m triggers hypoxia veto, temperature ≤ −5 °C triggers frostbite veto, wind ≥ 40 km/h triggers gale veto. The composite is forced to 100 = Danger, regardless of the ML output. This is exactly the OOD safety net the rule engine provides." | "但混合架构介入了：**Veto 级联触发了三个独立否决**——海拔 > 3500 m（缺氧）、温度 ≤ −5°C（冻伤）、风速 ≥ 40 km/h（大风）。无论 ML 输出什么，综合评分被强制设为 100 = Danger。**这就是规则引擎对 OOD 输入的安全网作用**。" |

🎯 **The Mt Everest demo is your strongest defensive argument.** It's also pre-tested — see `tests/test_rule_engine.py::test_mt_everest_veto_hypoxia`.
🎯 **珠峰演示是你最强的辩护点**。也是有单元测试覆盖的——见 `test_mt_everest_veto_hypoxia`。

---

## 📊 6. Concern #5 — "Regression or classification?"
## 📊 6. 反馈五 —— 回归还是分类？

**His original words / 老师原话**: *"I don't think this is a classification problem because there is no class label. So I think this is a regression problem."*

| 🇬🇧 EN | 🇨🇳 ZH |
|---|---|
| "Sir, when you first looked at the raw CSV, there was no class label, so regression looked like the only option. I considered both. I chose **binary classification** for three reasons:" | "老师，您当时看 CSV 没有 class label，所以看上去像 regression。我两个都考虑过，最后选了**二分类**，三个理由：" |
| **(1)** "The downstream decision is binary — go outside or don't. Regressing on mm of rain would still need a threshold to convert to a go/no-go output, so I would have to pick the threshold anyway." | **(1)** "下游决策本身就是二元的——出门 vs 不出门。即使做回归预测降雨毫米数，最后也要拿一个阈值转成 go/no-go，**那个阈值反正要选**。" |
| **(2)** "Classification lets me optimise **F2 score** directly, which is the right metric for safety-critical recall. I cannot directly optimise F2 on a regression target." | **(2)** "做分类才能直接优化 **F2 分数**——安全关键场景下召回比精度更重要，**这个指标只在分类任务下有意义**。" |
| **(3)** "But I still expose the **raw probability** in the API response, so any downstream component that needs a continuous score — for example the rule engine's rainfall sub-scorer — can still use it. So I keep the best of both worlds." | **(3)** "但 API 还是把**原始概率**暴露出来了，下游需要连续分数的组件（比如规则引擎的降雨子评分器）照样能用。**两全其美**。" |

---

## 🛡️ 7. Anticipated follow-up Q&A
## 🛡️ 7. 老师可能追问的问题

### Q1 — "Why Random Forest and not deep learning / LSTM?"
### Q1 ——为什么选 Random Forest 而不是深度学习 / LSTM？

| 🇬🇧 EN | 🇨🇳 ZH |
|---|---|
| "Three reasons. First, **interpretability** — feature importance lets me defend why the model predicts what it predicts. Essential for safety-critical applications. A neural net is a black box." | "三个理由：(1) **可解释性**——feature importance 让我能为每个预测**辩护**，安全关键应用必须有这一点，神经网络是黑盒。" |
| "Second, **data efficiency** — with 175 K samples, Random Forest reaches state-of-the-art performance. LSTM would need an order of magnitude more data to outperform it." | "(2) **数据效率**——17 万样本下 RF 已经达到 SOTA，LSTM 需要至少 10 倍数据才能超过它。" |
| "Third, **inference latency** — RF inference is sub-millisecond, which the FastAPI plus cache architecture depends on. LSTM would be at least 10× slower and require GPU at inference time." | "(3) **推理延迟**——RF 推理 < 1 ms，FastAPI + 缓存架构依赖这一点；LSTM 至少慢 10 倍且推理时需要 GPU。" |

### Q2 — "How do you handle out-of-distribution input?"
### Q2 ——分布外输入怎么处理？

**Just show the Mt Everest demo from Section 5 — that IS the answer.**
**直接展示第 5 节的珠峰 demo —— 那就是答案。**

### Q3 — "What is the contribution of the topographic rule engine? Could you just use ML alone?"
### Q3 ——地形规则引擎的贡献是什么？只用 ML 不行吗？

| 🇬🇧 EN | 🇨🇳 ZH |
|---|---|
| "Pure ML is statistical — it learns averages. But terrain in complex mountainous regions amplifies precipitation locally by **orders of magnitude**, see Roe 2005, *Annual Review of Earth & Planetary Sciences*." | "纯 ML 是统计性的——它学的是平均值。但复杂山地的地形会把降水**局部放大几个数量级**（Roe 2005, Annual Review of Earth & Planetary Sciences）。" |
| "The R1 rule in our decision table captures exactly this: when macro rain probability is low **but** the wind impinges on a windward slope with falling pressure, hidden rain risk emerges. The ML model would say 'safe' here; the rule engine fires R1 and warns the user." | "我们决策表的 R1 规则抓住的正是这一点：宏观降雨概率低、但风正对迎风坡且气压下降时——**存在隐藏的降雨风险**。ML 在这种情况下会说"安全"；规则引擎会触发 R1 警告用户。" |
| "This is the **Neuro-Symbolic AI** paradigm — learn what is learnable, hand-code what is physical." | "这就是 **Neuro-Symbolic AI** 范式——能学的让 ML 学，物理规律手工编码。" |

### Q4 — "Did you do cross-validation? Did you check for overfitting?"
### Q4 ——做过交叉验证吗？检查过过拟合吗？

| 🇬🇧 EN | 🇨🇳 ZH |
|---|---|
| "Yes Sir, **time-series cross-validation** with 5 folds on the training portion — not random K-fold, which would leak temporal information." | "做了老师，**时间序列交叉验证**，5 折，**不是**随机 K 折——随机划分会泄漏时间信息。" |
| "The fold AUCs range from 0.828 to 0.908, mean approximately 0.858 — very close to the held-out test AUC of 0.871. This consistency confirms the model is not overfitting to a single temporal slice." | "各折 AUC 在 0.828 到 0.908 之间，均值约 0.858——跟独立测试集 AUC 0.871 非常接近。**说明模型没有对某个时间段过拟合**。" |
| "All fold metrics are in `models/training_report.json` and the model card." | "所有指标都在 `models/training_report.json` 和 model card 里。" |

### Q5 — "How will you validate this in the real world?"
### Q5 ——你怎么在真实世界验证这套系统？

| 🇬🇧 EN | 🇨🇳 ZH |
|---|---|
| "Two-pronged plan for Chapter 5 evaluation. First, **hindcast validation** — I will replay the system against publicly documented Malaysian flood and landslide events from NaDMA archives and check whether the system would have produced a Warning or Danger verdict at the right time." | "Chapter 5 评估两条腿走路：(1) **历史事件回放**——用 NaDMA 公开记录的马来西亚洪水/滑坡事件，看系统在事件发生时是否会给出 Warning 或 Danger。" |
| "Second, **user study** — a small panel of mountain hikers will compare the system's recommendations against their own field judgment over a one-month period. Both methodologies follow standard practice in operational meteorology." | "(2) **用户研究**——找一小批登山者，一个月内对比系统建议和他们自己的判断。**两种方法都是业务气象学界的标准做法**。" |

### Q6 — "What about the four risk levels — Safe, Caution, Warning, Danger?"
### Q6 ——四个风险等级（Safe / Caution / Warning / Danger）是怎么定的？

| 🇬🇧 EN | 🇨🇳 ZH |
|---|---|
| "The thresholds are 30 / 55 / 80 on the 0-100 composite score. They are calibrated so that the **mean output across all training data** falls in the middle of the Caution band — that way the system uses its full dynamic range. Each level maps to a different recommended action in the bilingual advice." | "阈值是 0-100 综合分上的 30 / 55 / 80。校准依据：**训练集平均输出**正好落在 Caution 区间中部——这样系统能用满整个动态范围。每个等级对应不同的双语建议行动。" |

### Q7 — "What if the API or model fails in production?"
### Q7 ——生产环境 API 或模型挂了怎么办？

| 🇬🇧 EN | 🇨🇳 ZH |
|---|---|
| "Three layers of graceful degradation. First, if the trained model fails to load, the engine falls back to a physics-motivated heuristic. Second, every internal exception is caught and surfaced as a typed `ErrorResponse` JSON document. Third, the rule engine's Veto cascade runs **independently** of the ML model — even if ML returns garbage, the safety thresholds still fire." | "三层降级：(1) 模型加载失败时回退到**物理启发式**。(2) 所有内部异常被捕获并返回**类型化的 `ErrorResponse` JSON**。(3) **规则引擎的 Veto 级联独立于 ML 模型**——即使 ML 返回乱码，安全阈值仍然会触发。" |

---

## 🎬 8. Closing (30 seconds)
## 🎬 8. 收尾（30 秒）

| 🇬🇧 EN | 🇨🇳 ZH |
|---|---|
| "Sir, to summarise: I have addressed every point of your feedback. The missing Y is now derived. The documentation matches the data. The model is trained and evaluated **before** the app. And the choice of classification over regression is justified by the safety-critical nature of the application." | "老师，总结一下：您每条反馈我都已经回应——Y 已经构造好、文档跟数据完全对齐、模型在 app **之前**就训好并评估过、分类而不是回归是因为应用本身就是安全关键。" |
| "The code is on GitHub at `KyoukoLi/microclimate-x` with CI passing, 97 % test coverage, and a published model card. May I have your guidance on the next priorities for Chapter 5?" | "代码在 GitHub `KyoukoLi/microclimate-x`，CI 全过、测试覆盖率 97%、有完整的 model card。请问 **Chapter 5 接下来您建议我重点做哪部分**？" |

---

## 🧠 9. Psychological reminders
## 🧠 9. 心理建设

From the meeting recordings, the supervisor cares about three things above all else:
从录音里可以听出来，老师**最在意三件事**：

1. **Did you LISTEN to him?** — He asked "Do you understand my English?" multiple times. Reassure him by **quoting his exact words back** ("as you instructed: dataset first, then model, then app").
   **你听进去他的话了吗？** —— 他反复问 "Understand my English?" 用**复述他原话**让他放心。

2. **Do you understand basic ML?** — He explained X/Y, rows/columns, "if-then is the target" — patiently, like a tutor. Don't open with hybrid / neuro-symbolic / TPI / CAPE. Start with: dataset, target, feature, train, predict. **Earn the right** to use fancier vocabulary by first speaking his language.
   **你懂 ML 基础吗？** —— 不要上来就抛 hybrid、neuro-symbolic、TPI、CAPE。**先用他的词汇**：dataset、target、feature、train、predict。**先证明你懂基础**再升级。

3. **Did you follow his process?** — "App is the last" three times. The visual order in which you open tabs IS the answer. **No app until the very end.**
   **你按他的流程做了吗？** —— "app is the last" 他说了三次。**你打开标签页的顺序就是答案**。**绝对不要提前打开 app**。

### Defensive lines if you get stuck / 答不出来时的兜底话术

| Situation | Say (EN) | 说（ZH） |
|---|---|---|
| Don't know the answer | "That is a good question, Sir. I haven't fully worked out the answer yet — may I prepare a written response by next meeting?" | "老师这是个好问题，我还没完全想清楚——能否下次开会前给您一份书面回复？" |
| He challenges a threshold | "Sir, the threshold is documented in `docs/thresholds.md` with the academic citation. Let me open it." | "老师，这个阈值的学术引用在 `docs/thresholds.md` 里，我打开给您看。" |
| He says "this doesn't match what I expected" | "Yes Sir — that is exactly what I want to confirm with you. Could you describe what you expected so I can align?" | "老师**这正是我想跟您确认的点**——能否说说您预期的样子？我好对齐。" |

---

## ⚙️ 10. Backup plan if technical issues
## ⚙️ 10. 设备出问题的备份方案

| Problem | Fallback |
|---|---|
| WiFi / network down | The synthetic dataset works offline — `make synth` already ran |
| `make run` fails | Show the GitHub repo with CI green badge instead — the same artefacts are visible there |
| Demo doesn't load (open-meteo / open-topo-data API blocked) | Use the cached responses — recent results survive in `cache.sqlite3` |
| Browser crashes | Open this cheat sheet on your phone — every key number / sentence is here |
| 网络挂了 | 合成数据集已经跑过，本地能演 |
| `make run` 起不来 | 直接给 GitHub repo 看 CI 绿勾，artefact 一样能看到 |
| Demo 加载失败 | 用缓存的结果——最近查询都在 `cache.sqlite3` 里 |
| 浏览器崩了 | 手机打开这份 cheat sheet —— 所有关键数字和句子都在里面 |

---

## 📐 11. Final pre-flight checklist (do this 60 seconds before walking in)
## 📐 11. 起飞前最后 60 秒自检

```
☐ Laptop ≥ 80% battery, charger in bag
☐ make run is running in a terminal (don't close it!)
☐ http://localhost:8000/api/health returns ml_loaded: true
☐ All 10 browser tabs open in the order above (#9 — the app — is LAST in the tab bar)
☐ This cheat sheet open on screen, but NOT to be read word-for-word
☐ Phone on silent
☐ Deep breath. You have done the work.
```

```
☐ 笔记本电池 ≥ 80%，充电器在包里
☐ make run 在另一个终端跑着（不要关掉！）
☐ http://localhost:8000/api/health 返回 ml_loaded: true
☐ 10 个浏览器标签页按上面顺序开好（第 9 个 app 在标签栏最后）
☐ 这份 cheat sheet 开着，但不要照念
☐ 手机静音
☐ 深呼吸。你已经做完了所有该做的工作。
```

---

## 📎 Cross-references / 相关文档索引

| Topic | File |
|---|---|
| Detailed dataset spec | [`docs/dataset.md`](dataset.md) |
| Architecture deep-dive | [`docs/architecture.md`](architecture.md) |
| Threshold citations | [`docs/thresholds.md`](thresholds.md) |
| Pipeline order ASCII chart | [`docs/pipeline_order.md`](pipeline_order.md) |
| Model card | [`../models/MODEL_CARD.md`](../models/MODEL_CARD.md) |
| Full thesis-defence brief | [`supervisor_meeting_brief.md`](supervisor_meeting_brief.md) |
| Evaluation summary JSON | [`../figures/evaluation_summary.json`](../figures/evaluation_summary.json) |

---

> *Generated 2026-05-11 for the MicroClimate-X final-year-project supervisor meeting at UKM.
> 此页为 2026-05-11 UKM 毕业设计 MicroClimate-X 导师答辩准备文档。*
