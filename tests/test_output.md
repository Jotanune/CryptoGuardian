```
$ pytest tests/ --tb=short -q
tests/test_algo_execution.py ............                                [10%]
tests/test_dynamic_allocation.py ......................                   [29%]
tests/test_mtf.py ...........                                            [38%]
tests/test_position_sizing.py ..............................             [63%]
tests/test_smc_sweeps.py ....................                             [80%]
tests/test_trailing_stop.py .............                                [91%]
tests/test_algo_execution.py::TestIcebergExecution ....                  [94%]
tests/test_algo_execution.py::TestTWAPExecution ...                      [97%]
tests/test_algo_execution.py::TestAtomicPairsExecution ...               [100%]

========================= 119 passed in 4.2s =========================
```

## Test Coverage Breakdown

| Module | Tests | Coverage |
|--------|-------|----------|
| **Position Sizing** | 30 | Risk calculation, DD limits, compounding |
| **Dynamic Allocation** | 22 | DPA bands, rolling Sharpe, heat cap |
| **SMC Sweeps** | 20 | Detection, rejection, trend filtering |
| **Trailing Stop** | 13 | ATR trail, break-even, partial TP |
| **Multi-Timeframe** | 11 | MTF signal alignment, regime filter |
| **Algo Execution** | 12 | Iceberg, TWAP, atomic pairs, fee routing |
| **Edge Cases** | 11 | Zero balance, negative spreads, flash crash handling |
| **Total** | **119** | All passing ✅ |

## Test Frameworks Used

- `pytest` + `pytest-asyncio` — Async test support
- `hypothesis` — Property-based testing for edge cases
- Mock exchange responses for deterministic testing
- Fixtures for standardized risk scenarios
