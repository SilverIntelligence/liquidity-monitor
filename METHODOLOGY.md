## Precious Metals Liquidity Monitor - Methodology

### Overview

The Precious Metals Liquidity Monitor computes a composite 0-100 "Liquidity Index" for gold (XAU) and silver (XAG) by combining normalized scores from multiple market indicators. Higher scores indicate tighter liquidity conditions, while lower scores indicate looser conditions.

### Conceptual Framework

**Liquidity** in precious metals markets refers to the ease of buying and selling without significantly affecting price. Tight liquidity conditions typically manifest as:

- Declining physical inventories
- ETF outflows (redemptions)
- Futures backwardation (spot premium over futures)
- Declining speculative positioning
- Rising retail premiums over spot

Our index quantifies these conditions on a standardized 0-100 scale.

---

## Data Components

### 1. Inventory Metrics

**Sources:**
- COMEX warehouse stocks (daily)
- LBMA vault holdings (monthly/quarterly)

**Measurement:** Total ounces in registered inventories

**Interpretation:**
- **Lower inventory = tighter liquidity**
- Declining stocks suggest physical scarcity
- Direction: **-1** (inverted scoring)

**Normalization Window:** 252 trading days (~1 year)

---

### 2. ETF Flows

**Sources:**
- GLD (SPDR Gold Shares)
- IAU (iShares Gold Trust)
- SLV (iShares Silver Trust)
- SIVR (Aberdeen Silver ETF)

**Measurement:** Daily holdings in troy ounces, computed as 1-day and 5-day net changes

**Interpretation:**
- **Outflows (negative) = tighter liquidity**
- Redemptions indicate physical delivery demand
- Inflows suggest investors prefer paper exposure
- Direction: **-1** (inverted scoring)

**Normalization Window:** 252 days

---

### 3. Futures Term Structure

**Source:** CME front-month settlement prices

**Measurement:** Basis = Front month price - Second month price

**Interpretation:**
- **Backwardation (positive basis) = tighter liquidity**
- Spot premium indicates immediate demand
- Contango (negative basis) suggests ample supply
- Direction: **+1** (normal scoring)

**Normalization Window:** 252 days

---

### 4. CFTC Commitments of Traders (CoT)

**Source:** CFTC weekly disaggregated futures reports

**Measurement:** Net Managed Money positioning (long - short contracts)

**Interpretation:**
- **Lower net length = tighter liquidity**
- Spec reduction often precedes price squeezes
- High spec length indicates crowded long positioning
- Direction: **-1** (inverted scoring)

**Normalization Window:** 156 weeks (~3 years of weekly data)

---

### 5. Dealer Retail Premiums

**Sources:** Scraped from 3-5 major bullion dealers (APMEX, JM Bullion, SD Bullion, etc.)

**Measurement:** Median premium over spot for 1 oz coins/bars (%)

**Interpretation:**
- **Higher premiums = tighter liquidity**
- Retail markup reflects dealer inventory stress
- Low premiums indicate ample retail supply
- Direction: **+1** (normal scoring)

**Normalization Window:** 252 days

**Scraping Compliance:**
- 60-second minimum delay between dealers
- Respect robots.txt
- User agent: "WallStreetSilver Liquidity Monitor"

---

## Normalization Method

### Z-Score to Percentile Transformation

For each component, we transform raw values to a 0-100 score:

1. **Collect rolling window:** Last N observations (window size varies by component)
2. **Compute statistics:**
   ```
   μ = mean(window)
   σ = std(window)
   σ_clamped = max(σ, 0.01)  # Prevent division by zero
   ```

3. **Calculate z-score:**
   ```
   z = (value - μ) / σ_clamped
   ```

4. **Apply direction:**
   ```
   z_adjusted = z × direction
   ```
   - If direction = +1: higher raw value → higher score
   - If direction = -1: higher raw value → lower score (inverted)

5. **Convert to percentile:**
   ```
   p = Φ(z_adjusted)  # Standard normal CDF
   ```

6. **Scale to 0-100:**
   ```
   score = round(p × 100)
   score_clamped = clamp(score, 0, 100)
   ```

### Example

**Component:** Dealer Premiums
**Direction:** +1 (higher premium = tighter)

```
Current premium: 8%
Rolling mean (252d): 5%
Rolling std (252d): 2%

z = (8 - 5) / 2 = 1.5
z_adjusted = 1.5 × 1 = 1.5
p = Φ(1.5) ≈ 0.933
score = round(0.933 × 100) = 93

Interpretation: Premium is 1.5 standard deviations above the mean,
indicating very tight retail liquidity (93/100).
```

---

## Composite Index Calculation

### Default Formula (v1)

The composite index is a weighted average of component scores:

```
Liquidity_Index = Σ(w_i × s_i)

where:
  w_i = weight for component i
  s_i = score for component i (0-100)
```

**Default Weights:**

| Component         | Weight | Rationale                                |
|-------------------|--------|------------------------------------------|
| Inventory         | 0.25   | Direct measure of physical availability  |
| ETF Flows         | 0.20   | Institutional demand signal              |
| Term Structure    | 0.20   | Forward market signal of spot scarcity   |
| CoT Positioning   | 0.20   | Speculative positioning and sentiment    |
| Dealer Premiums   | 0.15   | Retail market stress indicator           |

**Total:** 1.00

### Missing Data Handling

If one or more components are unavailable (e.g., delayed CFTC report):

1. Mark composite as **degraded**
2. Rescale remaining weights to sum to 1.0
3. Compute weighted average with available components
4. Store `degraded=true` flag in database

**Example:**

If CoT data is missing (weight 0.20):

```
Remaining weights: 0.25 + 0.20 + 0.20 + 0.15 = 0.80
Rescaled weights:
  - Inventory: 0.25 / 0.80 = 0.3125
  - ETF: 0.20 / 0.80 = 0.25
  - Term: 0.20 / 0.80 = 0.25
  - Premium: 0.15 / 0.80 = 0.1875
```

---

## Score Interpretation

| Range   | Label              | Interpretation                                    |
|---------|--------------------|---------------------------------------------------|
| 0-20    | Very Loose         | Abundant supply, low premiums, contango           |
| 21-40   | Loose              | Adequate liquidity, neutral conditions            |
| 41-60   | Neutral            | Balanced supply/demand                            |
| 61-80   | Tight              | Declining inventories, rising premiums            |
| 81-100  | Very Tight         | Scarcity signals across multiple indicators       |

### Actionable Insights

**High Scores (80+):**
- Physical demand exceeding available supply
- Potential for delivery squeezes
- Retail premiums elevated
- Consider: Price upside risk, supply chain constraints

**Low Scores (20-):**
- Ample physical supply
- Low retail demand
- Spec positioning may be crowded
- Consider: Price downside risk, mean reversion

**Rapidly Rising Scores:**
- Liquidity draining from market
- Early warning of potential price acceleration

**Rapidly Falling Scores:**
- Liquidity returning to market
- Easing of scarcity conditions

---

## Formula Versioning

All composite calculations are tagged with a `formula_id` to ensure reproducibility:

**Formula v1 (default):**
```json
{
  "description": "Default liquidity index formula v1",
  "weights": {
    "inventory": 0.25,
    "etf_flow": 0.20,
    "term": 0.20,
    "cot": 0.20,
    "premium": 0.15
  }
}
```

When weights are updated, a new `formula_id` is created. Historical scores remain tied to their original formula, enabling:
- Backtest of formula changes
- A/B testing of weight configurations
- Transparent version control

---

## Data Quality & Revisions

### Source Reliability

Each data source is tracked with:
- HTTP status codes
- Checksum of raw payload
- Parse success/failure rates
- Last successful update timestamp

### Revision Policy

- **Raw observations:** Store `source_revision_ts` if source republishes corrected data
- **Component scores:** Recompute if underlying data revised
- **Composite scores:** Recompute if components or formula change
- **Historical integrity:** Never delete; append with newer `formula_id` if methodology changes

### Staleness Thresholds

| Component    | Update Frequency | Stale After |
|--------------|------------------|-------------|
| Inventory    | Daily            | 48 hours    |
| ETF Flows    | Daily            | 48 hours    |
| Term         | Daily            | 24 hours    |
| CoT          | Weekly           | 10 days     |
| Premiums     | Hourly           | 6 hours     |

---

## Backtesting & Validation

### Historical Recomputation

To validate the methodology, recompute scores for past periods:

```python
from scoring.composite import recompute_historical_scores

result = await recompute_historical_scores(
    session=session,
    metal_id=1,  # Gold
    formula_id=1,
    start_date=datetime(2020, 1, 1),
    end_date=datetime(2024, 11, 18)
)
```

### Golden Tests

Key historical events to validate against:

1. **March 2020 COVID Panic:**
   - Expected: Very tight (80+) as physical markets dislocated

2. **August 2020 Gold Peak (~$2075):**
   - Expected: Moderately tight (60-75)

3. **Silver Squeeze (Feb 2021):**
   - Expected: Extremely tight (90+) for XAG

4. **2022 Fed Tightening:**
   - Expected: Loosening trend (60 → 40)

### Correlation Analysis

Compare index to:
- Spot price momentum (expected: positive correlation during squeezes)
- Realized volatility (expected: positive correlation)
- VVIX/MOVE (vol-of-vol proxies)

---

## Future Enhancements

### Potential Additional Components

1. **Lease Rates:** Gold/silver forward offered rates (GOFO/SIFO)
2. **Central Bank Purchases:** Monthly CB buying (LBMA/WGC data)
3. **Mine Production:** Quarterly supply metrics
4. **Refiners Spread:** Bid-ask on 400oz bars vs. small bars
5. **Vol-of-Vol:** Realized volatility or options skew

### Alternative Weighting Schemes

- **Equal weight:** All components = 0.20
- **PCA-derived:** Weights from principal component analysis
- **Regime-dependent:** Higher inventory weight during supply shocks
- **Machine learning:** Optimize weights for price prediction

### Sub-Indices

Decompose into:
- **Physical Liquidity Index:** Inventory + Premiums
- **Paper Liquidity Index:** ETF + Term + CoT
- **Sentiment Index:** CoT + Premium

---

## Caveats & Limitations

1. **Data Availability:**
   - Some sources require paid APIs (CME real-time futures)
   - LBMA publishes infrequently (monthly/quarterly)
   - Dealer scraping may break if websites change structure

2. **Lagging Indicators:**
   - CoT is published with 3-day lag (Friday for Tuesday data)
   - ETF holdings reflect T-1 or T-2 data
   - COMEX stocks updated once daily after close

3. **Structural Changes:**
   - ETF creation/redemption mechanics can change
   - Dealer premiums affected by mint production capacity
   - Futures term structure influenced by interest rates, storage costs

4. **Scoring Assumptions:**
   - Normal distribution assumption for z-scores (may not hold in fat-tailed events)
   - Fixed rolling windows (252 days) may not capture regime shifts
   - Equal treatment of all observations in window (no decay weighting)

5. **Not a Trading Signal:**
   - Index quantifies *current conditions*, not future price direction
   - High liquidity stress can persist (or intensify) before resolution
   - Should be combined with price action, technical analysis, fundamentals

---

## References

### Data Sources

- **COMEX:** https://www.cmegroup.com/delivery_reports/
- **LBMA:** https://www.lbma.org.uk/
- **CFTC CoT:** https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm
- **ETF Sponsors:** GLD, IAU, SLV, SIVR websites
- **CME Futures:** https://www.cmegroup.com/

### Academic Background

- Amihud, Y. (2002). "Illiquidity and stock returns."
- Brunnermeier, M. K., & Pedersen, L. H. (2009). "Market liquidity and funding liquidity."
- Erb, C., & Harvey, C. (2013). "The Golden Dilemma."

### Community

- **WallStreetSilver:** https://www.reddit.com/r/Wallstreetsilver/
- **Monetary Metals:** https://monetary-metals.com/ (basis analysis)

---

**Document Version:** 1.0
**Last Updated:** 2024-11-18
**Formula Version:** v1 (formula_id=1)
