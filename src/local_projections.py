"""Projeções locais (Jordà) para estimar respostas a impulso.

Cada horizonte `h` é estimado por uma regressão separada:

    y_{t+h} = alpha_h + beta_h * choque_t + Gamma * controles_t
              + soma_{j=1..p} phi_j * Z_{t-j} + erro_{t+h}

em que `Z` reúne a resposta, o choque e os controles defasados. Os erros-padrão
são de Newey–West (HAC), com largura de banda `h + p` por padrão. O coeficiente
`beta_h` é a resposta de `y` no horizonte `h` a uma mudança contemporânea no
choque. Não é, por si só, uma estimativa causal: depende do desenho e dos
controles incluídos.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import statsmodels.api as sm
from scipy.stats import norm


@dataclass(frozen=True)
class LocalProjectionResult:
    horizon: int
    coefficient: float
    std_error: float
    t_statistic: float
    p_value: float
    ci_lower: float
    ci_upper: float
    n_observations: int


def local_projection(
    data: pd.DataFrame,
    response: str,
    shock: str,
    horizons: int = 24,
    lags: int = 6,
    controls: list[str] | None = None,
    maxlags_hac: int | None = None,
    confidence: float = 0.95,
) -> list[LocalProjectionResult]:
    """Estima projeções locais de `response` a um choque em `shock`.

    `data` deve conter as colunas necessárias já no formato desejado (por
    exemplo, em primeira diferença). `controls` entra de forma contemporânea e
    defasada, junto com `response` e `shock`.
    """
    controls = list(controls or [])
    required = [response, shock, *controls]
    missing = [name for name in required if name not in data.columns]
    if missing:
        raise ValueError(f"Colunas ausentes em data: {missing}")
    if response == shock:
        raise ValueError("response e shock devem ser diferentes")
    if horizons < 0 or lags < 0:
        raise ValueError("horizons e lags devem ser >= 0")
    if not 0 < confidence < 1:
        raise ValueError("confidence deve estar em (0, 1)")

    base = data[required].astype(float).reset_index(drop=True)
    n_total = len(base)

    lagged = []
    for lag in range(1, lags + 1):
        for variable in required:
            column = base[variable].shift(lag).rename(f"{variable}_lag{lag}")
            lagged.append(column)

    regressors = [base[shock].rename(shock)]
    regressors += [base[name].rename(name) for name in controls]
    regressors += lagged
    design = pd.concat(regressors, axis=1)
    n_regressors = design.shape[1] + 1  # + intercepto

    if n_total <= n_regressors + lags:
        raise ValueError("Observações insuficientes para estimar as projeções locais")

    z_value = norm.ppf(1 - (1 - confidence) / 2)

    results = []
    for horizon in range(horizons + 1):
        outcome = base[response].shift(-horizon).rename("_outcome")
        aligned = pd.concat([outcome, design], axis=1).dropna()
        if len(aligned) <= n_regressors:
            raise ValueError(
                f"Observações insuficientes no horizonte {horizon}: "
                f"{len(aligned)} para {n_regressors} regressores"
            )

        y = aligned["_outcome"].to_numpy(dtype=float)
        x = sm.add_constant(
            aligned.drop(columns="_outcome"), has_constant="add"
        ).to_numpy(dtype=float)

        bandwidth = maxlags_hac if maxlags_hac is not None else (horizon + lags)
        fit = sm.OLS(y, x).fit(cov_type="HAC", cov_kwds={"maxlags": bandwidth})

        coefficient = float(fit.params[1])
        std_error = float(fit.bse[1])
        results.append(
            LocalProjectionResult(
                horizon=horizon,
                coefficient=coefficient,
                std_error=std_error,
                t_statistic=coefficient / std_error,
                p_value=float(fit.pvalues[1]),
                ci_lower=coefficient - z_value * std_error,
                ci_upper=coefficient + z_value * std_error,
                n_observations=int(fit.nobs),
            )
        )

    return results


def resultados_para_dataframe(
    results: list[LocalProjectionResult],
) -> pd.DataFrame:
    """Converte a lista de resultados em um DataFrame indexado pelo horizonte."""
    return pd.DataFrame(
        [
            {
                "horizonte": r.horizon,
                "coeficiente": r.coefficient,
                "erro_padrao": r.std_error,
                "t": r.t_statistic,
                "p_valor": r.p_value,
                "ic_inferior": r.ci_lower,
                "ic_superior": r.ci_upper,
                "n": r.n_observations,
            }
            for r in results
        ]
    ).set_index("horizonte")
