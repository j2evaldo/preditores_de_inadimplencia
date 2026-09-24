"""Modified Wald causality test of Toda–Yamamoto for a bivariate VAR."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import chi2


@dataclass(frozen=True)
class TodaYamamotoResult:
    cause: str
    effect: str
    selected_lags: int
    max_integration_order: int
    estimated_lags: int
    wald_statistic: float
    degrees_of_freedom: int
    p_value: float


def toda_yamamoto_causality(
    data: pd.DataFrame,
    cause: str,
    effect: str,
    selected_lags: int,
    max_integration_order: int,
) -> TodaYamamotoResult:
    """Test non-causality using a VAR(k+dmax) and restrictions on only lags 1..k.

    The VAR includes an intercept. The returned asymptotic modified Wald statistic
    has a chi-square distribution with `selected_lags` degrees of freedom.
    """
    if cause == effect:
        raise ValueError("cause e effect devem ser variáveis diferentes")
    if cause not in data.columns or effect not in data.columns:
        raise ValueError("cause e effect devem existir nas colunas de data")
    if selected_lags < 1 or max_integration_order < 0:
        raise ValueError("selected_lags deve ser >= 1 e max_integration_order >= 0")

    variables = [effect, cause]
    values = data[variables].dropna().to_numpy(dtype=float)
    estimated_lags = selected_lags + max_integration_order
    if len(values) <= estimated_lags + len(variables) + 1:
        raise ValueError("Observações insuficientes para estimar o VAR aumentado")

    n_observations = len(values) - estimated_lags
    regressors = [np.ones(n_observations)]
    for lag in range(1, estimated_lags + 1):
        regressors.extend(values[estimated_lags - lag : len(values) - lag].T)
    design = np.column_stack(regressors)
    outcomes = values[estimated_lags:]

    coefficients, _, _, _ = np.linalg.lstsq(design, outcomes, rcond=None)
    residuals = outcomes - design @ coefficients
    residual_df = n_observations - design.shape[1]
    if residual_df <= 0:
        raise ValueError("Graus de liberdade insuficientes para o teste")

    effect_index = 0
    cause_index = 1
    restrictions = np.array(
        [1 + (lag - 1) * len(variables) + cause_index for lag in range(1, selected_lags + 1)]
    )
    coefficient_covariance = (
        residuals[:, effect_index].dot(residuals[:, effect_index])
        / residual_df
        * np.linalg.inv(design.T @ design)
    )
    restricted_coefficients = coefficients[restrictions, effect_index]
    restricted_covariance = coefficient_covariance[np.ix_(restrictions, restrictions)]
    wald_statistic = float(
        restricted_coefficients.T
        @ np.linalg.solve(restricted_covariance, restricted_coefficients)
    )

    return TodaYamamotoResult(
        cause=cause,
        effect=effect,
        selected_lags=selected_lags,
        max_integration_order=max_integration_order,
        estimated_lags=estimated_lags,
        wald_statistic=wald_statistic,
        degrees_of_freedom=selected_lags,
        p_value=float(chi2.sf(wald_statistic, selected_lags)),
    )
