# 收益率计算算法说明

本文档详细记录 HolmFolio 中三种核心收益率计算的方法论：组合 TWR、标签加权价格收益率（用于 Tag Correlation 和 Tag Beta）、以及资产 Beta。

---

## 目录

1. [组合 TWR（时间加权收益率）](#1-组合-twr时间加权收益率)
2. [标签加权价格收益率](#2-标签加权价格收益率)
3. [统计指标：相关性与 Beta](#3-统计指标相关性与-beta)
4. [算法等价性证明](#4-算法等价性证明)

---

## 1. 组合 TWR（时间加权收益率）

**代码位置**：`backend/services/calculation.py` → `calculate_twr()`

### 1.1 问题

计算组合在时间段 $[t_0, t_N]$ 内的投资绩效。挑战在于：组合市值的变化有**两个来源**——

1. **资产价格波动**（投资收益）
2. **外部现金流**（存钱/取钱，改变本金）

TWR 的目的是剥离现金流的影响，只衡量投资决策本身的收益。

### 1.2 算法

采用基金净值法（NAV/share method）。

#### 符号

| 符号 | 含义 |
|------|------|
| $t$ | 第 $t$ 个交易日 |
| $V(t)$ | 第 $t$ 日末的组合总市值（基准货币） |
| $\Delta CF(t)$ | 第 $t$ 日的外部净现金流（流入为正，流出为负） |
| $NAV(t)$ | 第 $t$ 日末的单位净值 |
| $S(t)$ | 第 $t$ 日末的份额数 |

#### 初始化（$t_0$）

$$NAV(t_0) = 1.0$$
$$S(t_0) = \frac{V(t_0)}{NAV(t_0)}$$

#### 每日迭代（$t_1$ 到 $t_N$）

**Step 1** — 统计当日外部净现金流：

$$\Delta CF(t) = \sum cash\_in - \sum cash\_out$$

所有金额转换为基准货币。

**Step 2** — 计算当日净值（两种方法，交叉验证）：

方法一（从份额推净值）：
$$NAV(t) = \frac{V(t) - \Delta CF(t)}{S(t-1)}$$

方法二（从收益率推净值）：
$$r(t) = \frac{V(t) - \Delta CF(t)}{V(t-1)} - 1$$
$$NAV_{\text{ref}}(t) = NAV(t-1) \cdot (1 + r(t))$$

验证：$|NAV(t) - NAV_{\text{ref}}(t)| < 0.0001$

**Step 3** — 调整份额（现金流换份额）：

$$\Delta S(t) = \frac{\Delta CF(t)}{NAV(t)}$$
$$S(t) = S(t-1) + \Delta S(t)$$

#### 累计收益

$$TWR = \prod_{t=t_1}^{t_N} (1 + r(t)) - 1$$

#### 年化收益

$$\text{Annualized Return} = (1 + TWR)^{\frac{365}{\text{days}}} - 1$$

### 1.3 直觉

买入基金份额：现金 → 基金（份额增加，净值不变）  
赎回基金份额：基金 → 现金（份额减少，净值不变）

现金流的处理方式：假设现金流发生在每日**末尾**——先用昨日份额和今日市值算今日净值，再按今日净值增发/注销份额。这样每日收益率 $r(t)$ 只反映资产价格波动，不受资金进出影响。

---

## 2. 标签加权价格收益率

**代码位置**：`backend/services/portfolio.py` → `get_tag_daily_returns()`

### 2.1 问题

每个**标签**（Tag）是一个虚拟子组合，包含多个资产。标签的市值会因两个原因变化：

1. 底层资产的**价格波动**
2. 用户买卖导致的**持仓量变化**

如果直接使用标签市值变化率（$V(t)/V(t-1) - 1$），买卖操作会污染收益率——买入更多某标签下的资产会制造出一个虚假的"正收益"，而这并非投资表现。

### 2.2 算法

使用**加权价格收益率**：每个资产只考察其纯价格变化，然后按前一日市值占比加权。

#### 符号

| 符号 | 含义 |
|------|------|
| $n$ | 标签下资产数量 |
| $q_i(t)$ | 资产 $i$ 在第 $t$ 日末的持仓量 |
| $p_i(t)$ | 资产 $i$ 在第 $t$ 日的收盘价 |
| $mv_i(t) = q_i(t) \cdot p_i(t)$ | 资产 $i$ 在第 $t$ 日的市值 |
| $w_i^{\text{tag}}$ | 资产 $i$ 在此标签的权重（0–100，来自 AssetTag 表） |
| $\text{rate}_i(t)$ | 资产 $i$ 的币种对基准货币的汇率 |

#### 每日计算（对每个交易日 $t$）

**Step 1** — 计算各资产在前一日末的标签内权重：

$$mv_i^{\text{primary}}(t-1) = mv_i(t-1) \cdot \text{rate}_i(t-1) \cdot \frac{w_i^{\text{tag}}}{100}$$
$$total(t-1) = \sum_{j=1}^n mv_j^{\text{primary}}(t-1)$$
$$w_i(t-1) = \frac{mv_i^{\text{primary}}(t-1)}{total(t-1)}$$

**Step 2** — 计算各资产的纯价格收益率：

$$r_i^{\text{price}}(t) = \frac{p_i(t)}{p_i(t-1)} - 1$$

**Step 3** — 加权求和得到标签收益率：

$$R_{\text{tag}}(t) = \sum_{i=1}^n w_i(t-1) \cdot r_i^{\text{price}}(t)$$

### 2.3 直觉

- **权重用前一日市值**：今日的买卖只会影响明日之后的权重，不会污染今日的收益率。
- **收益率用纯价格变化**：$p_i(t)/p_i(t-1) - 1$ 与持仓量完全无关，只反映资产本身的市场表现。
- **多币种处理**：权重计算时将各资产的市值用汇率转换为基准货币，保证权重在同一币种下可比。价格收益率是无量纲比例，不需要汇率转换。

---

## 3. 统计指标：相关性与 Beta

### 3.1 Tag Correlation（标签相关性）

**代码位置**：`backend/services/portfolio.py` → `calculate_tag_correlation()`

#### 数据准备

对选定的标签类别，用 `get_tag_daily_returns()` 获取每个标签的日收益率序列。

#### 对齐

只保留**所有标签都有有效收益率**的交易日：

$$\text{aligned\_returns}[t] = \{R_1(t), R_2(t), \ldots, R_k(t)\}$$

其中 $\forall i,\ R_i(t) \neq \text{None}$。这种联合对齐保证了每个观测是同时的，Pearson 相关系数的成对比较才有意义。

#### 数据充足性

要求至少有 20 个对齐的交易日数据点。不足 20 个的标签被标记为 `insufficient_data_tags` 并排除。

#### Pearson 相关系数矩阵

对对齐后的收益率矩阵（$k$ 个标签 × $n$ 个交易日），计算 Pearson 相关系数矩阵：

$$\rho_{ij} = \frac{\text{Cov}(R_i, R_j)}{\sigma_i \cdot \sigma_j}$$

其中 $\text{Cov}$ 和 $\sigma$ 使用样本估计（`np.corrcoef`，自由度为 $n-1$）。零方差序列（如价格完全不变）会导致 NaN，被替换为 0。

### 3.2 Tag Beta（标签 Beta）

**代码位置**：`backend/services/calculation.py` → `calculate_tag_beta()`

#### 数据准备

同样使用 `get_tag_daily_returns()` 获取每个标签的日收益率序列，并获取基准（Benchmark）的同日收益率序列。

每个标签**独立**与基准对齐：只保留该标签和基准都有有效返回的交易日。不同标签不要求相互对齐。

#### 频率聚合

支持三种频率（通过 `_aggregate_returns_to_frequency()`）：

| 频率 | 聚合方式 | 最少数据点 |
|------|---------|-----------|
| `daily` | 原样使用 | 20 |
| `weekly` | 同 ISO 周内日收益连乘 | 4 |
| `monthly` | 同月内日收益连乘 | 2 |

聚合公式（周期内）：
$$R_{\text{period}} = \prod_{t \in \text{period}} (1 + r_t) - 1$$

#### Beta 计算

对每个标签独立计算：

$$\beta_{\text{tag}} = \frac{\text{Cov}(R_{\text{tag}}, R_{\text{bm}})}{\text{Var}(R_{\text{bm}})}$$

其中协方差和方差使用样本估计（`np.cov`，`ddof=1`）。

### 3.3 Asset Beta（资产 Beta）

**代码位置**：`backend/services/calculation.py` → `calculate_asset_beta()`

资产 Beta 与标签 Beta 的算法框架相同，但数据来源不同：

- 资产 Beta 使用 `get_asset_daily_prices()` 获取每个资产的**纯价格序列**（从 Price 表读取）
- 日收益率 = $(p_t - p_{t-1}) / p_{t-1}$

由于只依赖价格表、完全不涉及持仓量，天然隔离了买卖操作的干扰。

---

## 4. 算法等价性证明

本节证明：在**成交价等于收盘价**的理想条件下，标签层面的 TWR 方法与加权价格收益率方法等价。

### 4.1 假设

- 资产 $i$ 的每日成交价 $p_i^{\text{trade}}(t)$ 等于收盘价 $p_i(t)$
- 所有资产以收盘价计价

### 4.2 TWR 思路

将标签视为子组合，买入/卖出视为该子组合的外部现金流：

$$CF(t) = \sum_i \Delta q_i(t) \cdot p_i(t)$$

其中 $\Delta q_i(t) = q_i(t) - q_i(t-1)$（正 = 买入，负 = 卖出）。

TWR 日收益率：

$$R_{\text{TWR}}(t) = \frac{V(t) - CF(t)}{V(t-1)} - 1$$

展开分子：

$$V(t) - CF(t) = \sum_i q_i(t) \cdot p_i(t) - \sum_i \Delta q_i(t) \cdot p_i(t)$$
$$= \sum_i \big[q_i(t) - (q_i(t) - q_i(t-1))\big] \cdot p_i(t)$$
$$= \sum_i q_i(t-1) \cdot p_i(t)$$

因此：

$$R_{\text{TWR}}(t) = \frac{\sum_i q_i(t-1) \cdot p_i(t)}{\sum_i q_i(t-1) \cdot p_i(t-1)} - 1$$

### 4.3 加权价格收益率思路

每个资产的纯价格收益率：

$$r_i(t) = \frac{p_i(t)}{p_i(t-1)} - 1$$

权重为前一日市值占比（含标签权重）：

$$w_i(t-1) = \frac{q_i(t-1) \cdot p_i(t-1) \cdot w_i^{\text{tag}}}{\sum_j q_j(t-1) \cdot p_j(t-1) \cdot w_j^{\text{tag}}}$$

加权求和：

$$R_{\text{weighted}}(t) = \sum_i w_i(t-1) \cdot r_i(t)$$
$$= \sum_i w_i(t-1) \cdot \left(\frac{p_i(t)}{p_i(t-1)} - 1\right)$$
$$= \frac{\sum_i q_i(t-1) \cdot p_i(t) \cdot w_i^{\text{tag}}}{\sum_j q_j(t-1) \cdot p_j(t-1) \cdot w_j^{\text{tag}}} - 1$$

### 4.4 结论

两式化简结果**完全相同**（为简洁，取 $w_i^{\text{tag}} = 100\%$ 的特例）：

$$\boxed{R(t) = \frac{\sum_i q_i(t-1) \cdot p_i(t)}{\sum_i q_i(t-1) \cdot p_i(t-1)} - 1}$$

### 4.5 实际取舍

当成交价 ≠ 收盘价时，二者差一个**交易滑点项**：

$$R_{\text{TWR}} - R_{\text{weighted}} = \frac{\sum_i \Delta q_i(t) \cdot [p_i(t) - p_i^{\text{trade}}(t)]}{V(t-1)}$$

当前系统只存储收盘价，因此选择加权价格收益率法作为数据约束下的最优近似。日频分析中单日滑点通常远小于日波动幅度，对相关性和 Beta 估计的影响可忽略。

---

## 附：相关代码文件索引

| 算法 | 文件 |
|------|------|
| 组合 TWR | `backend/services/calculation.py` — `calculate_twr()` |
| 标签加权价格收益率 | `backend/services/portfolio.py` — `get_tag_daily_returns()` |
| 标签相关性 | `backend/services/portfolio.py` — `calculate_tag_correlation()` |
| 标签 Beta | `backend/services/calculation.py` — `calculate_tag_beta()` |
| 资产 Beta | `backend/services/calculation.py` — `calculate_asset_beta()` |
| 日收益 → 周/月聚合 | `backend/services/calculation.py` — `_aggregate_returns_to_frequency()` |
| Beta 静态方法 | `backend/services/calculation.py` — `calculate_beta()` |
