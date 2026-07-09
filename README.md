# JV Ads

Analisador de Google Ads da JV Truck Pneus. Programa local, de terminal, que:

1. **Conecta** na sua conta Google Ads (OAuth).
2. **Analisa** a conta inteira com regras objetivas (últimos 30 dias completos).
3. **Identifica** desperdícios e oportunidades, explicando cada recomendação com os dados da própria conta.
4. **Aplica** as alterações que você aprovar — **nada é modificado sem a sua confirmação, item por item**.

## Experimente sem credenciais (modo demo)

```bash
pip install -r requirements.txt
python -m jv_ads
```

Sem credenciais configuradas o programa entra automaticamente em **modo demo**,
com dados fictícios de uma loja de pneus. Nenhuma conta é tocada. Serve para
conhecer todas as telas antes de conectar a conta real.

## Conectar a conta real

Você vai precisar de três coisas (todas gratuitas):

### 1. Developer token
- Acesse sua conta de **administrador** (MCC) do Google Ads → Ferramentas → **Centro de API**.
- Copie o developer token. O nível "Acesso básico" é suficiente (15.000 operações/dia).
- Se você não tem MCC, crie uma em https://ads.google.com/home/tools/manager-accounts/ e vincule sua conta.

### 2. Cliente OAuth (Google Cloud)
- https://console.cloud.google.com → crie um projeto → **APIs e serviços** → ative a **Google Ads API**.
- **Credenciais** → Criar credenciais → **ID do cliente OAuth** → tipo **App para computador**.
- Guarde o `client_id` e o `client_secret`.

### 3. Refresh token
```bash
python setup_oauth.py
```
O script abre o navegador, você autoriza com a conta Google que acessa o Google Ads,
e ele imprime o `refresh_token`.

### Arquivos de configuração

```bash
cp google-ads.example.yaml google-ads.yaml   # preencha com os valores acima
cp config.example.yaml config.yaml           # preencha o customer_id da conta
```

> **Segurança:** `google-ads.yaml` e `config.yaml` estão no `.gitignore` e nunca
> devem ser versionados ou compartilhados — o refresh token dá acesso à conta.

### Executar

```bash
python -m jv_ads
```

## O que as regras analisam

| Regra | Dispara quando | Ação oferecida |
|---|---|---|
| Palavra sem conversão | gastou ≥ R$ 50 em 30 dias e 0 conversões | Pausar (reversível) |
| Termo de desperdício | termo pesquisado gastou ≥ R$ 30, ≥ 5 cliques, 0 conversões | Adicionar negativa exata |
| Orçamento limitado | campanha converte com CPA ≤ média da conta e perde ≥ 10% das impressões por orçamento | Aumentar orçamento +20% |
| Campanha sem retorno | gastou ≥ R$ 150 e 0 conversões | Alerta para revisão manual (sem ação automática) |
| Campanha saudável | CPA ≤ média da conta | "Não alterar" |

Todos os limiares são configuráveis no `config.yaml`. As regras exigem amostra
mínima de propósito: com poucos dados, a resposta certa é não mexer.

## Segurança das alterações

- Toda alteração exige confirmação individual (`s/n`) na hora de aplicar.
- Pausar palavra é **reversível** dentro do Google Ads.
- Orçamentos compartilhados nunca são alterados.
- Campanhas inteiras nunca são pausadas automaticamente — só alerta.
- Tudo que foi aplicado fica registrado em `jv_ads.db` (menu Histórico).

## Testes

```bash
python -m tests.test_rules
```

## Limitações conhecidas (por design da API do Google)

- Métricas de **hoje são parciais** — o Google atualiza ao longo do dia; a análise usa os últimos 30 dias completos.
- Conversões dos últimos dias podem **aumentar retroativamente** (janela de atribuição).
- O relatório de termos de pesquisa **omite termos de baixo volume** (privacidade do Google) — é impossível ver 100% dos termos.
- A API **não mede lucro**, só conversões. As regras falam em desperdício e eficiência, não em lucro real.
