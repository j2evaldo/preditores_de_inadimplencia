#### **Impacto da Taxa de Juros na Inadimplência**

Projeto de séries temporais para investigar uma pergunta econômica concreta:
**quando os juros cobrados no crédito sobem, a inadimplência das famílias tende a
subir depois?**

Usamos dados públicos do **Banco Central do Brasil (SGS)** e métodos econométricos
para descrever padrões e testar se o passado de uma série ajuda a prever a outra.
Isso é diferente de provar que juros causam inadimplência: renda, emprego, inflação,
endividamento e decisões dos bancos também podem influenciar o resultado.

#### **Dados utilizados**

| Série | Código SGS | Descrição |
|---|---|---|
| `taxa_juros` | 432 | Taxa de juros - Livre - Referencial (% a.a.), diária |
| `inadimplencia_pf` | 21084 | Inadimplência da carteira de crédito - Pessoas Físicas - Total (%), mensal |

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
│   └── analise_econometrica.ipynb   # análise principal
├── src/
│   └── coleta_dados_bcb.py          # script de coleta via API do BCB
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

   Isso gera `data/raw/taxa_juros.csv`, `data/raw/inadimplencia_pf.csv` e o dataset
   consolidado em `data/processed/dataset_consolidado.csv`. Os juros diários são
   agregados pela média mensal; a inadimplência mensal é preservada como observada.
   O conjunto final contém somente meses comuns às duas séries e **não interpola**
   inadimplência.

   Para limitar a coleta a uma janela móvel, por exemplo cinco anos:

   ```python
   from src.coleta_dados_bcb import baixar_todas_as_series, montar_dataset_consolidado

   series = baixar_todas_as_series(anos=5)
   montar_dataset_consolidado(series)
   ```

3. Abra e execute `notebooks/analise_econometrica.ipynb`.

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
   causal. A alternativa VECM está apenas como exemplo comentado, não é estimada pelo
   notebook atualmente.

Em cada etapa, a pergunta é: **o que este resultado mostra e qual é o limite da
interpretação?** Essa disciplina é parte importante de uma análise de dados confiável.

#### **Resultados da execução atual**

Com 185 observações mensais comuns (mar/2011–jul/2026), o AIC selecionou `k=7` e o
ADF indicou `dmax=2`, levando ao VAR aumentado com 9 defasagens. O teste de
Toda–Yamamoto não rejeitou a hipótese nula ao nível de 5% em nenhum dos sentidos:

| Hipótese nula | Wald | gl | p-valor |
|---|---:|---:|---:|
| Juros não causam (Toda–Yamamoto) inadimplência | 8,098 | 7 | 0,324 |
| Inadimplência não causa (Toda–Yamamoto) juros | 4,800 | 7 | 0,684 |

Portanto, esta especificação ampliada **não encontrou evidência de precedência
preditiva** entre as séries. A ordem da inadimplência merece cautela: o ADF na primeira
diferença ficou próximo do limiar de 5% (p=0,073), enquanto o KPSS também traz
evidência limítrofe. Recomenda-se testar robustez de `dmax`, defasagens e quebras
estruturais. A causalidade de Toda–Yamamoto é preditiva/condicional e não prova
causalidade estrutural; não rejeitar a hipótese nula tampouco prova ausência de efeito.

Em linguagem direta: **nesta amostra, o teste não conseguiu mostrar que os juros
ajudam a antecipar a inadimplência**. Isso não quer dizer que o efeito não exista; quer
dizer que ainda precisamos de especificações e variáveis que ajudem a separar os
diversos fatores que afetam as famílias.
