"""
Coleta de dados do Banco Central do Brasil (SGS - Sistema Gerenciador de Séries Temporais).

API pública, sem necessidade de chave: https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados

Séries utilizadas neste projeto:
- 432   : Taxa de juros - Livre - Referencial (% a.a.), diária
- 21084 : Inadimplência da carteira de crédito - Pessoas físicas - Total (%), mensal
- 433   : IPCA - Variação mensal (%), mensal
- 29037 : Endividamento das famílias com o SFN em relação à renda acumulada
          nos últimos 12 meses (%), mensal
"""
from __future__ import annotations

import datetime as dt
import time
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"

SERIES = {
    "taxa_juros": 432,      # Taxa de juros - Livre - Referencial (% a.a.)
    "inadimplencia_pf": 21084,  # Inadimplência PF - Total (%)
    "ipca": 433,            # IPCA - Variação mensal (%)
    "endividamento_familias": 29037,  # Endividamento das famílias (% da renda)
}

# Como cada série é resumida quando agregada ao mês.
# A taxa de juros é diária e vira média do mês; as demais já são mensais.
AGREGACAO_MENSAL = {
    "taxa_juros": "mean",
    "inadimplencia_pf": "last",
    "ipca": "last",
    "endividamento_familias": "last",
}

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
PROCESSED_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"


def _intervalos_consulta(inicio: dt.date, fim: dt.date):
    """Divide consultas em blocos de dois anos, abaixo do limite de 10 anos do SGS."""
    cursor = inicio
    while cursor <= fim:
        limite = min(cursor + dt.timedelta(days=2 * 365 - 1), fim)
        yield cursor, limite
        cursor = limite + dt.timedelta(days=1)


def _requisitar_json(url: str, params: dict, tentativas: int = 5, pausa: float = 2.0):
    """Consulta a API com retentativas; o SGS falha de forma intermitente (502/HTML).

    Retorna a lista de observações ou `[]` quando o período não tem dados.
    """
    ultimo_erro = "sem resposta"
    for tentativa in range(tentativas):
        resp = requests.get(url, params=params, timeout=60)

        if resp.status_code == 404:
            try:
                detalhe = resp.json().get("erro", {}).get("detail", "")
            except ValueError:
                detalhe = ""
            if detalhe.endswith("Value(s) not found"):
                return []

        if resp.status_code == 200 and resp.text.lstrip().startswith("["):
            return resp.json()

        ultimo_erro = f"HTTP {resp.status_code}"
        if tentativa < tentativas - 1:
            time.sleep(pausa * (2 ** tentativa))

    raise RuntimeError(f"Falha ao consultar {url}: {ultimo_erro}")


def fetch_series(codigo: int, data_inicial: str, data_final: str) -> pd.DataFrame:
    """Busca uma série do SGS/BCB entre datas dd/mm/aaaa, em blocos de até 9 anos.

    Retorna um DataFrame com colunas data (datetime) e valor (float).
    """
    url = BASE_URL.format(codigo=codigo) + "?formato=json"
    inicio = dt.datetime.strptime(data_inicial, "%d/%m/%Y").date()
    fim = dt.datetime.strptime(data_final, "%d/%m/%Y").date()
    if inicio > fim:
        raise ValueError("data_inicial deve ser anterior ou igual a data_final")

    blocos = []
    for inicio_bloco, fim_bloco in _intervalos_consulta(inicio, fim):
        params = {
            "dataInicial": inicio_bloco.strftime("%d/%m/%Y"),
            "dataFinal": fim_bloco.strftime("%d/%m/%Y"),
        }
        dados = _requisitar_json(url, params)
        if dados:
            blocos.append(pd.DataFrame(dados))

    if not blocos:
        return pd.DataFrame(columns=["data", "valor"])

    df = pd.concat(blocos, ignore_index=True).drop_duplicates(subset="data")
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
    df["valor"] = df["valor"].astype(float)
    return df.sort_values("data").reset_index(drop=True)


def baixar_todas_as_series(
    anos: int | None = None,
    data_inicial: str = "01/01/2000",
    data_final: str | None = None,
) -> dict[str, pd.DataFrame]:
    """Baixa o histórico comum ou uma janela móvel e salva os CSVs brutos.

    `anos=None` consulta desde data_inicial; um inteiro define janela móvel.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    hoje = dt.date.today()
    fim = dt.datetime.strptime(data_final, "%d/%m/%Y").date() if data_final else hoje
    inicio = (
        fim - dt.timedelta(days=365 * anos)
        if anos is not None
        else dt.datetime.strptime(data_inicial, "%d/%m/%Y").date()
    )
    data_final_formatada = fim.strftime("%d/%m/%Y")
    data_inicial_formatada = inicio.strftime("%d/%m/%Y")

    resultados = {}
    for nome, codigo in SERIES.items():
        print(
            f"Baixando série '{nome}' (código {codigo}) de "
            f"{data_inicial_formatada} até {data_final_formatada}..."
        )
        df = fetch_series(codigo, data_inicial_formatada, data_final_formatada)
        if df.empty:
            raise ValueError(f"A série SGS {codigo} não retornou observações no período")
        df = df.rename(columns={"valor": nome})
        caminho = RAW_DIR / f"{nome}.csv"
        df.to_csv(caminho, index=False)
        print(f"  -> {len(df)} registros salvos em {caminho}")
        resultados[nome] = df

    return resultados


def montar_dataset_consolidado(series: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
    """Alinha as séries por mês sem interpolar observações mensais ausentes."""
    if series is None:
        series = {
            nome: pd.read_csv(RAW_DIR / f"{nome}.csv", parse_dates=["data"])
            for nome in SERIES
        }

    df_final = None
    for nome, df in series.items():
        df = df[["data", nome]].copy()
        df["mes"] = df["data"].dt.to_period("M")
        agregacao = AGREGACAO_MENSAL[nome]
        if agregacao == "mean":
            df = df.groupby("mes", as_index=False)[nome].mean()
        else:
            df = df.groupby("mes", as_index=False)[nome].last()
        df_final = df if df_final is None else pd.merge(df_final, df, on="mes", how="inner")

    df_final["data"] = df_final["mes"].dt.to_timestamp()
    df_final = (
        df_final.drop(columns="mes")
        [["data", *SERIES.keys()]]
        .sort_values("data")
        .reset_index(drop=True)
    )

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    caminho = PROCESSED_DIR / "dataset_consolidado.csv"
    df_final.to_csv(caminho, index=False)
    print(f"Dataset consolidado salvo em {caminho} ({len(df_final)} registros).")
    return df_final


if __name__ == "__main__":
    series = baixar_todas_as_series()
    montar_dataset_consolidado(series)
