# ADS-AI-HUB
Hub multicanal para uma IA controlar Meta Ads e TikTok Ads por uma API única, com sandbox obrigatório por padrão e política de orçamento.

## Endpoints
- `GET /health`
- `GET /v1/platforms`
- `GET /v1/campaigns/meta`
- `GET /v1/campaigns/tiktok`
- `POST /v1/actions`
- `GET /docs`

## Segurança
`ADS_DRY_RUN=true` é o padrão. Nenhuma escrita externa ocorre sem alteração explícita para live e credenciais válidas. Aumentos de orçamento acima do limite autônomo exigem aprovação.

## Subir
`docker compose up --build -d`
