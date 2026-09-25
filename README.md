#### **Impacto da Taxa de Juros na Inadimplência**

Projeto de séries temporais para investigar uma pergunta econômica concreta:
**quando os juros cobrados no crédito sobem, a inadimplência das famílias tende a
subir depois?**

Usamos dados públicos do **Banco Central do Brasil (SGS)** e métodos econométricos
para descrever padrões e testar se o passado de uma série ajuda a prever a outra.
Isso é diferente de provar que juros causam inadimplência: renda, emprego, inflação,
endividamento e decisões dos bancos também podem influenciar o resultado.

O projeto tem duas etapas. A **v1** (`notebooks/analise_econometrica.ipynb`) compara
apenas juros e inadimplência. A **v2** (`notebooks/analise_com_controles.ipynb`)
acrescenta controles macroeconômicos (IPCA e endividamento das famílias) e corrige a
base estatística: reavalia a ordem de integração com mais testes, trata a
cointegração explicitamente e estima a resposta ao longo do tempo por projeções
locais.

#### **Dados utilizados**

| Série | Código SGS | Descrição |
|---|---|---|
| `taxa_juros` | 432 | Taxa de juros - Livre - Referencial (% a.a.), diária |
| `inadimplencia_pf` | 21084 | Inadimplência da carteira de crédito - Pessoas Físicas - Total (%), mensal |
| `ipca` | 433 | IPCA - Variação mensal (%), mensal |
| `endividamento_familias` | 29037 | Endividamento das famílias com o SFN em relação à renda acumulada nos últimos 12 meses (%) |

Fonte: API pública do BCB — `https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados`
(não requer chave de acesso).

Período coletado: todo o histórico comum disponível, limitado pela série que começa
mais tarde. A série diária é consultada em blocos de dois anos por causa dos limites
da API; períodos sem observações são tratados como ausência de dados.

#### **Estrutura do projeto**

```
.
├── data/
│   ├── raw/            # séries brutas baixadas do BCB (CSV, uma por série)
│   └── processed/      # dataset_consolidado.csv (séries unidas por data)
├── notebooks/
│   ├── analise_econometrica.ipynb    # v1: análise bivariada
│   └── analise_com_controles.ipynb   # v2: controles + cointegração + projeções locais
├── src/
│   ├── coleta_dados_bcb.py           # coleta via API do BCB
│   ├── toda_yamamoto.py              # teste de Wald modificado
│   └── local_projections.py          # projeções locais de Jordà com erros HAC
├── reports/            # (reservado para saídas/figuras exportadas)
├── requirements.txt
└── README.md
```

#### **Como rodar**

1. Crie o ambiente virtual e instale as dependências (este projeto usa `uv`, mas
   `pip`/`venv` padrão também funcionam se disponíveis no seu sistema):

   ```bash
   uv venv .venv
   source .venv/bin/activate
   uv pip install -r requirements.txt
   ```

2. Baixe os dados do BCB:

   ```bash
   python src/coleta_dados_bcb.py
   ```

   Isso gera os CSVs brutos em `data/raw/` (uma por série) e o dataset consolidado
   em `data/processed/dataset_consolidado.csv`. Os juros diários são agregados pela
   média mensal; as séries mensais são preservadas como observadas. O conjunto final
   contém somente meses comuns a todas as séries e **não interpola** inadimplência.
   A API do BCB falha de forma intermitente e o coletor faz retentativas automáticas.

   Para limitar a coleta a uma janela móvel, por exemplo cinco anos:

   ```python
   from src.coleta_dados_bcb import baixar_todas_as_series, montar_dataset_consolidado

   series = baixar_todas_as_series(anos=5)
   montar_dataset_consolidado(series)
   ```

3. Abra e execute os notebooks:
   - `notebooks/analise_econometrica.ipynb` (v1, análise bivariada);
   - `notebooks/analise_com_controles.ipynb` (v2, controles e projeções locais).

#### **Metodologia da análise**

O notebook conta a análise passo a passo — de uma forma que permite acompanhar as
decisões, em vez de apenas apresentar tabelas:

1. **Conhecer os dados**: gráficos e estatísticas descritivas mostram tendências,
   variações e valores fora do padrão. São pistas para investigar, não conclusões.
2. **Verificar estacionariedade**: ADF e KPSS ajudam a entender se as propriedades das
   séries mudam ao longo do tempo. Como partem de hipóteses nulas diferentes, resultados
   que não combinam ou ficam perto do limite pedem cautela.
3. **Investigar uma relação de longo prazo**: o teste de Johansen procura combinações
   estáveis entre séries com tendência. A interpretação depende de as séries terem uma
   ordem de integração compatível.
4. **Perguntar se uma série ajuda a prever a outra**: Granger olha para o conteúdo
   preditivo de valores passados. O teste aparece nos dois sentidos e não deve ser
   confundido com prova de causalidade econômica.
5. **Testar robustez com Toda–Yamamoto**: o notebook seleciona `k`, estima um VAR
   aumentado com `k + dmax` defasagens e aplica o teste de Wald às primeiras `k`.
   Comparamos juros → inadimplência e inadimplência → juros. A rotina está em
   `src/toda_yamamoto.py`.
6. **Visualizar a dinâmica com VAR/IRF**: o VAR nas primeiras diferenças e sua resposta
   ao impulso servem como exploração de como o modelo propaga mudanças. A IRF
   ortogonalizada depende da ordem das variáveis; não é, sozinha, uma estimativa
   causal. A alternativa VECM está comentada na v1; a v2 a estima explicitamente.

Em cada etapa, a pergunta é: **o que este resultado mostra e qual é o limite da
interpretação?** Essa disciplina é parte importante de uma análise de dados confiável.

#### **Extensão da v2: controles e correção da base estatística**

A v2 parte da mesma pergunta, mas com quatro séries (juros, inadimplência, IPCA e
endividamento) e três mudanças de método:

1. **Ordem de integração mais bem fundamentada**: além de ADF e KPSS, usa-se o teste
   de Zivot–Andrews, que admite uma quebra estrutural (relevante por causa da
   pandemia). A taxa de juros e a inadimplência são tratadas como I(1); o IPCA é
   I(0); o endividamento é tratado como I(1) por prudência. Assim, `dmax = 1`, e não
   2 como na v1.
2. **Cointegração tratada explicitamente**: o teste de Johansen aponta uma relação de
   cointegração. O notebook estima um VECM e reporta os coeficientes de carga
   (ajuste ao equilíbrio de longo prazo) e o teste de Granger via mecanismo de
   correção de erro.
3. **Projeções locais de Jordà**: a resposta da inadimplência a um choque nos juros é
   estimada horizonte a horizonte, com controles e erros-padrão HAC (Newey–West) e
   bandas de confiança. Isso evita a sobreparametrização de um VAR grande e permite
   comparar com e sem controles.

#### **Resultados da v1 (bivariada)**

Com 185 observações mensais comuns (mar/2011–jul/2026), o AIC selecionou `k=7` e o
ADF indicou `dmax=2`, levando ao VAR aumentado com 9 defasagens. O teste de
Toda–Yamamoto não rejeitou a hipótese nula ao nível de 5% em nenhum dos sentidos:

| Hipótese nula | Wald | gl | p-valor |
|---|---|---:|---:|
| Juros não causam (Toda–Yamamoto) inadimplência | 8,098 | 7 | 0,324 |
| Inadimplência não causa (Toda–Yamamoto) juros | 4,800 | 7 | 0,684 |

Nesta especificação bivariada **não houve evidência de precedência preditiva** entre
as séries. A ordem da inadimplência merecia cautela: o ADF na primeira diferença
ficava próximo do limiar de 5%.

#### **Resultados da v2 (com controles)**

Com 184 observações mensais comuns (mar/2011–jun/2026), quatro séries, `k=6` pelo
AIC e `dmax=1`:

- **Cointegração**: o teste de Johansen e a seleção de posto indicam **uma** relação
  de cointegração a 5%. No VECM, o coeficiente de carga da inadimplência é positivo e
  significativo, enquanto o dos juros não é — só a inadimplência se ajusta ao
  equilíbrio de longo prazo.
- **Toda–Yamamoto corrigido**: com `dmax=1` (VAR(7)) o teste **rejeita** a
  não-causalidade juros → inadimplência a 5%; com `dmax=2` (VAR(8)) não rejeita.

| dmax | Hipótese nula | Wald | gl | p-valor |
|---:|---|---:|---:|---:|
| 1 | Juros não causam (Toda–Yamamoto) inadimplência | 13,859 | 6 | 0,031 |
| 1 | Inadimplência não causa (Toda–Yamamoto) juros | 4,144 | 6 | 0,657 |
| 2 | Juros não causam (Toda–Yamamoto) inadimplência | 10,740 | 6 | 0,097 |
| 2 | Inadimplência não causa (Toda–Yamamoto) juros | 4,583 | 6 | 0,598 |

- **VECM / Granger via correção de erro**: a direção juros → inadimplência fica em
  p ≈ 0,098 (limítrofe); a inversa, em p ≈ 0,134.
- **Projeções locais** (resposta a um choque de 1 desvio-padrão em Δjuros, com
  controles): resposta em forma de morro, positiva e significativa em parte do médio
  prazo (horizontes 8–14 meses), com bandas alargando nos horizontes maiores. Sem os
  meses da pandemia, o padrão qualitativo se mantém.

Em linguagem direta: **ao segurar IPCA e endividamento constantes e corrigir a
especificação, os juros passam a ter mais conteúdo preditivo sobre a inadimplência do
que a v1 sugeria**. Mas a evidência ainda **depende de `dmax`** e o teste do VECM é
limítrofe. Isso é precedência preditiva condicional, não uma estimativa causal; a
sensibilidade mostra que a conclusão não é robusta o bastante para afirmar um efeito.
