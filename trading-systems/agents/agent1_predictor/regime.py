import numpy as np

def calculate_hurst_exponent(series, max_lag=20):
    """
    Estimates the Hurst Exponent (H) using the Rescaled Range (R/S) / Variance method.
    H > 0.5: Trending (Persistent)
    H < 0.5: Mean Reverting (Anti-persistent)
    H = 0.5: Random Walk (Geometric Brownian Motion)
    """
    lags = range(2, max_lag)

    # We calculate the standard deviation of differenced series across various lags
    tau = [
        np.sqrt(np.std(series[lag:] - series[:-lag]))
        for lag in lags
    ]

    # Fit a line to the log-log plot to extract the slope (Hurst)
    poly = np.polyfit(np.log(lags), np.log(tau), 1)

    return poly[0] * 2.0


def classify_regime(df):
    """
    Uses the Hurst Exponent to identify the high-level market environment.
    This dictates which strategies gain higher confidence.
    """
    close_series = df['close'].values
    hurst = calculate_hurst_exponent(close_series)

    # Classification thresholds (standard quant values)
    if hurst > 0.55:
        regime = "trending"
    elif hurst < 0.45:
        regime = "mean_reverting"
    else:
        regime = "random"

    return regime, round(hurst, 3)