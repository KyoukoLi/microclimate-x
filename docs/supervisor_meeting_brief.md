# Supervisor Meeting Brief — bilingual script
# 导师开会双语逐字稿

> Single-page meeting brief addressing every point of feedback from the
> 4/15 supervisor session. Bring this document open on screen during the
> meeting and walk through it in order.
>
> 一页式开会简报，逐条回应 4/15 导师 review 的所有反馈。开会时直接打开
> 此页，按顺序走一遍即可。

---

## Opening 30 seconds / 开场 30 秒

| English (say this) | 中文（口头要点） |
|---|---|
| "Sir, since our last meeting I have addressed every point of your feedback. May I walk you through them in the correct order — dataset first, then model, then app — as you instructed?" | "老师，按您上次反馈，我已经把每一条都改了。我按您要求的顺序——**先 dataset，再 model，最后才是 app**——给您过一遍可以吗？" |

**Why this opening works**: it explicitly *names* the supervisor's #1 process complaint ("app is last"). He'll relax immediately because he can see you listened.

---

## Concern #1 — Y target was missing
## 反馈一 · 缺少目标列 Y

**His original words**: "Y is missing. I don't have the output variable. If you don't have target, you cannot train a machine learning model."

| English (say this) | 中文（口头要点） |
|---|---|
| "Sir, you were right — the raw Open-Meteo CSV has no Y column. I have engineered the target explicitly. The variable is called `is_rain_event` and it is defined as 1 if the precipitation in the **next hour** is greater than 0.1 mm, else 0. The code is one line in `scripts/2_preprocess.py`." | "老师您说得对，原始 Open-Meteo CSV 确实没有 Y 列。我现在已经显式构造了目标变量，叫做 **`is_rain_event`**，定义是：**下一小时降雨量 > 0.1 mm 则为 1，否则为 0**。代码就一行，写在 `scripts/2_preprocess.py`。" |
| [Show this code on screen:] `df['is_rain_event'] = (df['precipitation'].shift(-1) > 0.1).astype(int)` | （把这一行代码投出来给老师看） |
| "Three things to notice: `.shift(-1)` means I use **future** rain as the label — features at hour t predict outcome at t+1h, so there is no temporal leakage. The 0.1 mm threshold matches the **WMO definition** of trace precipitation, not an arbitrary choice. And it is binary classification, not regression, because the downstream decision is binary." | "三个要点：(1) `.shift(-1)` 表示用**下一小时**的降雨作为标签，特征是 t 时刻、预测的是 t+1 小时——没有时间泄漏。(2) 0.1 mm 这个阈值不是我随便定的，对应 **WMO 微量降水标准**。(3) 是二分类不是回归，因为下游用户决策本身就是二元的（去 / 不去）。" |

**Artefact to show**: `docs/dataset.md` §5 (Target label derivation) — has all three points written out.

---

## Concern #2 — features in the document did not match the Excel
## 反馈二 · 文档里的特征跟 CSV 列名对不上

**His original words**: "The features that you presented here, not... not mentioned in the Excel. So, it must be matched."

| English (say this) | 中文（口头要点） |
|---|---|
| "Sir, that was also a fair point. I have rewritten the dataset specification so the documentation lists exactly the **same column names** that appear in the CSV. There is a one-to-one mapping in `docs/dataset.md` §4." | "老师，这条您也说对了。我已经把数据集文档完全重写，文档里列出的就是 CSV 里的**真实列名**，一一对应。在 `docs/dataset.md` 第 4 节。" |
| [Open dataset.md §4 schema table] "Every row in this table is one column in the actual CSV. The role column says whether it is a feature (X), the target (Y), or just metadata." | （打开 dataset.md §4 列结构表）"表里每一行就是 CSV 里的一列，role 列写明了它是 feature（X）、target（Y）还是 metadata。" |

**Artefact to show**: `docs/dataset.md` §4 — single canonical schema table.

---

## Concern #3 — study the data source
## 反馈三 · 研究数据源本身

**His original words**: "Please study the link. What is the purpose of the dataset? What is design for? What is the output variable?"

| English (say this) | 中文（口头要点） |
|---|---|
| "I read the Open-Meteo API documentation carefully. The dataset I use is the **ERA5 reanalysis archive**, which is ECMWF's gold-standard hourly reanalysis — they use it to validate other forecast models. It is *not* a forecast, it is a physically-consistent reconstruction of past weather, which is why it is the right dataset for training: the labels are reliable ground truth." | "我把 Open-Meteo 文档仔细读了。我用的是 **ERA5 再分析数据**，是 ECMWF 出的同化产品，气象学界用它当作**真值**去校验别的预报模型。它**不是**预报，而是对过去天气的物理一致的重建。所以用来训练 ML 是合适的——标签是可靠的 ground truth。" |
| "Spatial coverage: 5 Malaysian mountain sites — Genting, Cameron, Fraser's Hill, Klang Valley, Kinabalu — chosen to span elevations from 100 m to 1865 m and terrain types from valley to slope." | "空间覆盖 5 个马来西亚山地点位——云顶、金马仑、福隆港、巴生谷、神山——海拔从 100 m 到 1865 m，地形从山谷到山坡都有。" |
| "Temporal coverage: 5 years, hourly, 175 315 rows in total." | "时间范围 5 年，每小时一行，总共 175 315 行。" |

**Artefact to show**: `docs/dataset.md` §1-3, or open the Open-Meteo documentation page itself if he wants the original source.

---

## Concern #4 — process order was wrong: app should be last
## 反馈四 · 流程顺序错了，app 应该最后做

**His original words**: "First, identify a dataset. Identify a dataset. And then train the model. And then predict it. First. Once everything is finished... okay, you can develop the app. App is the last."

| English (say this) | 中文（口头要点） |
|---|---|
| "Yes Sir, I followed your process. The current state is: Step 1 dataset is identified and documented. Step 2 the model is trained — let me show you the results before I open the app." | "好的老师，我严格按您的流程做的。当前状态是：**第一步 dataset 已确认并文档化**；**第二步模型已训练完毕**——在打开 app 之前，先给您看训练结果。" |
| [Open `figures/01_roc_curve.png`] "Test ROC AUC is 0.871 on 35 063 held-out hourly samples. The hold-out is the **last 20 % chronologically**, not a random split — random splits leak temporal autocorrelation and would inflate accuracy unrealistically." | （打开 ROC 图）"测试集 35 063 行，ROC AUC = **0.871**。划分用的是**按时间排序的最后 20%**，不是随机划分——随机划分会泄漏时间自相关，把准确率虚高 5-15 个百分点。" |
| [Open `figures/03_calibration_curve.png`] "Brier score is 0.138, which means the predicted probabilities are well-calibrated — when the model says 70 % chance of rain, the actual rate is close to 70 %." | （打开 calibration 图）"Brier 分数 = 0.138，说明预测概率**校准良好**——模型说 70% 下雨概率时，实际频率接近 70%。" |
| [Open `figures/04_threshold_sweep.png`] "I optimised the decision threshold for **F2 score**, not F1, because in this safety-critical application a missed rain event on a windward slope can lead to flash flooding — false negatives are much worse than false positives. F2 weights recall four times more than precision. The optimal threshold is τ = 0.20, giving F2 = 0.778 and **93.4 % recall**." | （打开阈值扫描图）"我用 **F2 分数**而不是 F1 来选最优阈值——因为这是安全关键应用，**漏报**比误报严重得多（在迎风坡漏掉一次降雨可能引发山洪）。F2 把召回率的权重设为精度的 4 倍，最优阈值是 τ = 0.20，F2 = 0.778，**召回率 93.4%**。" |
| [Open `figures/05_feature_importance.png`] "Top-3 features the model relies on: previous hour's rain, time-of-day cyclic encoding, and 3-hour pressure tendency. These match the meteorological literature — autocorrelation, diurnal cycle, and storm precursor." | （打开特征重要性图）"模型最看重的 3 个特征：上一小时降水、时间周期编码、3 小时气压变化。这跟气象文献吻合——自相关、日变化、风暴前兆。" |
| **[NOW open the app]** "Step 3, the app. This is FastAPI + Vue using the trained model. When I click a coordinate, the system returns the probability and the four hazard sub-scores per the proposal §3.7." | **（这时才打开 app）**"第三步，app。这是 FastAPI + Vue 调用上面训好的模型。我点地图任意一点，系统返回概率和四个分项灾害评分（按开题 §3.7）。" |

**Why this order matters**: he literally said "App is the last" three times. Showing dataset → ROC → calibration → threshold → importance → THEN the app is exactly the order he asked for. Each chart takes 20-30 seconds to explain; total before opening the app ≈ 2-3 minutes.

---

## Concern #5 — regression or classification?
## 反馈五 · 回归还是分类？

**His original words**: "I don't think this is a classification problem because there is no class label. So I think this is a regression problem."

| English (say this) | 中文（口头要点） |
|---|---|
| "Sir, when you first looked at the raw CSV, there was no class label, so regression looked like the only option. I considered both. I chose **binary classification** for three reasons:" | "老师，您当时看原始 CSV 的时候确实没有 class label，所以看上去像 regression。我两个都考虑过，最后选了**二分类**，三个理由：" |
| **(1)** "The downstream decision is binary — go outside or don't. Regressing on mm of rain would still need a threshold to convert to a go/no-go output, so I would have to pick the threshold anyway." | **(1)** "下游决策本身就是二元的——出门 vs 不出门。即使做回归预测降雨毫米数，最后也要拿一个阈值转成 go/no-go，**那个阈值反正要选**。" |
| **(2)** "Classification lets me optimise **F2 score**, which is the right metric for a safety-critical setting where recall matters more than precision. I cannot directly optimise F2 on a regression target." | **(2)** "做分类才能直接优化 **F2 分数**——安全关键场景下召回比精度更重要，**这个指标只在分类任务下有意义**。" |
| **(3)** "But I still expose the **raw probability** in the API response, so any downstream component that needs a continuous score (e.g. the rule engine's rainfall sub-scorer) can still use it. So I keep the best of both worlds." | **(3)** "但 API 还是把**原始概率**暴露出来了，下游需要连续分数的组件（比如规则引擎的降雨子评分器）照样能用。**两全其美**。" |

---

## Likely follow-up questions / 老师可能追问的问题

### Q1 — "Why Random Forest and not deep learning / LSTM?"
### Q1 ——为什么选 Random Forest 而不是深度学习 / LSTM？

| English | 中文 |
|---|---|
| "Three reasons. First, **interpretability**: feature importance lets me defend why the model predicts what it predicts — essential for a safety-critical application. A neural net is a black box. Second, **data efficiency**: with 175 K samples, Random Forest reaches state-of-the-art performance; LSTM would need an order of magnitude more data to outperform it. Third, **inference latency**: RF inference is sub-millisecond, which the FastAPI + cache architecture depends on. LSTM would be at least 10× slower and require GPU at inference time." | "三个理由：(1) **可解释性**——feature importance 让我能为每个预测**辩护**，安全关键应用必须有这一点，神经网络是黑盒。(2) **数据效率**——17 万样本下 RF 已经达到 SOTA，LSTM 需要至少 10 倍数据才能超过它。(3) **推理延迟**——RF 推理 < 1 ms，FastAPI + 缓存架构依赖这一点；LSTM 至少慢 10 倍且推理时需要 GPU。" |

### Q2 — "How do you handle out-of-distribution input (e.g. Mt Everest)?"
### Q2 ——分布外输入怎么处理（比如珠峰）？

| English | 中文 |
|---|---|
| "This is exactly what the **hybrid architecture** is for, Sir. The Random Forest only saw Malaysian mountains, so on Everest it returns a low probability. But the rule engine's Veto cascade catches three independent failures — altitude > 3500 m triggers hypoxia veto, temperature ≤ -5 °C triggers frostbite veto, and wind ≥ 40 km/h triggers gale veto. The composite output goes to Danger regardless of the ML probability. There is a unit test for exactly this scenario — `test_mt_everest_veto_hypoxia` in `tests/test_rule_engine.py`." | "老师，这正是我做**混合架构**的原因。RF 只见过马来西亚的山，所以在珠峰上会返回很低的概率。但**规则引擎的 Veto 级联**会捕获三个独立的失败：海拔 > 3500 m 触发缺氧 Veto，温度 ≤ -5°C 触发冻伤 Veto，风速 ≥ 40 km/h 触发大风 Veto。无论 ML 给什么概率，输出都被强制设为 Danger。我专门为这个场景写了单元测试 `test_mt_everest_veto_hypoxia`。" |

### Q3 — "What is the contribution of the topographic rule engine? Could you just use the ML model alone?"
### Q3 ——地形规则引擎的贡献是什么？只用 ML 不行吗？

| English | 中文 |
|---|---|
| "ML alone is statistical — it learns averages. But terrain in complex mountainous regions amplifies precipitation locally by orders of magnitude (Roe, 2005, *Annual Review of Earth & Planetary Sciences*). The decision-table R1 in proposal §3.7.2 captures exactly this: when macro rain probability is low but the wind impinges on a windward slope with falling pressure, hidden rain risk emerges. The ML model would say 'safe' here; the rule engine fires R1 and warns the user. This is the **Neuro-Symbolic AI** paradigm — learn what is learnable, hand-code what is physical." | "纯 ML 是统计性的——它学的是平均值。但复杂山地的地形会把降水**局部放大几个数量级**（Roe 2005, Annual Review of Earth & Planetary Sciences）。开题 §3.7.2 的决策表 R1 抓住的正是这一点：宏观降雨概率低、但风正对迎风坡且气压在下降时——存在**隐藏的降雨风险**。ML 在这种情况下会说"安全"；规则引擎会触发 R1 警告用户。这是 **Neuro-Symbolic AI** 范式——能学的让 ML 学，物理规律手工编码。" |

### Q4 — "Did you do cross-validation? Did you check for overfitting?"
### Q4 ——做过交叉验证吗？检查过过拟合吗？

| English | 中文 |
|---|---|
| "Yes Sir, **time-series cross-validation** with 5 folds on the training portion — not random K-fold, which would leak temporal information. The fold AUCs range from 0.828 to 0.908, mean ≈ 0.858, which is very close to the held-out test AUC of 0.871. This consistency confirms the model is not overfitting to a single temporal slice. All fold metrics are in `models/training_report.json` and the model card." | "做了，老师。**时间序列交叉验证**，5 折，**不是**随机 K 折——随机划分会泄漏时间信息。各折 AUC 在 0.828 到 0.908 之间，均值约 0.858，跟独立测试集 AUC 0.871 非常接近——说明模型没有对某个时间段过拟合。所有指标都在 `models/training_report.json` 和 model card 里。" |

### Q5 — "How will you validate this in the real world?"
### Q5 ——你怎么在真实世界验证这套系统？

| English | 中文 |
|---|---|
| "Two-pronged plan for Chapter 5 evaluation. First, **hindcast validation** — I will replay the system against publicly documented Malaysian flood and landslide events from NaDMA archives and check whether the system would have produced a Warning or Danger verdict at the right time. Second, **user study** — a small panel of mountain hikers will compare the system's recommendations against their own field judgment over a one-month period. Both methodologies follow standard practice in the operational meteorology literature." | "Chapter 5 评估两条腿走路：(1) **历史事件回放** —— 用 NaDMA 公开记录的马来西亚洪水/滑坡事件，看系统在事件发生时是否会给出 Warning 或 Danger。(2) **用户研究** —— 找一小批登山者，一个月内对比系统建议和他们自己的判断。两种方法都是业务气象学界的标准做法。" |

---

## Closing 30 seconds / 收尾 30 秒

| English (say this) | 中文（口头要点） |
|---|---|
| "Sir, to summarise: I have addressed every point of your feedback — the missing Y is now derived, the documentation matches the data, the model is trained and evaluated before the app, and the choice of classification over regression is justified by the safety-critical nature of the application. The code is on GitHub at `KyoukoLi/microclimate-x` with CI passing, 97 % test coverage, and a published model card. May I have your guidance on the next priorities for Chapter 5?" | "老师，总结一下：您每条反馈我都已经回应——Y 已经构造好、文档跟数据完全对齐、模型在 app 之前就训好并评估过、分类而不是回归是因为应用本身就是安全关键。代码在 GitHub `KyoukoLi/microclimate-x`，CI 全过、测试覆盖率 97%、有完整的 model card。请问 Chapter 5 接下来您建议我重点做哪部分？" |

---

## Materials checklist before walking in / 开会前自检清单

- [ ] Laptop charged, browser tab open to `docs/dataset.md`.
- [ ] All 6 figures in `figures/` rendered to a quick-flip slide deck (or just keep the PNG files in a single Finder window).
- [ ] GitHub repo page open in another tab, ready to show CI green badge + commit history.
- [ ] Frontend `frontend/index.html` ready to demo (open `make run` in a terminal **before** the meeting — not during).
- [ ] `models/MODEL_CARD.md` open in a third tab, in case the supervisor asks for written evidence of any number you quote.
- [ ] This brief (`docs/supervisor_meeting_brief.md`) open on screen — but **don't read from it word-for-word**, treat it as your safety net only.

中文版：
- [ ] 笔记本充满电，浏览器开好 `docs/dataset.md`
- [ ] `figures/` 里 6 张图全部预先点开过一次（图片预览快进就行，避免临时加载）
- [ ] GitHub repo 页面开另一个标签页，CI 绿勾 + commit 历史随时可看
- [ ] 前端 `make run` **提前**起好（不要开会时才起）
- [ ] `models/MODEL_CARD.md` 第三个标签页，老师追问任何数字时打开它
- [ ] **本文档**开着但**不要照念**，当兜底用即可
