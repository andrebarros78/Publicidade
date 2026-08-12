# Publicidade — Almoxarifado, Laboratório e Oficina do ADS-AI-HUB

Este repositório é a área técnica de preparação do ADS-AI-HUB multicanal.

## Zonas

- `almoxarifado/` — snapshots limpos e rastreáveis dos componentes doadores.
- `laboratorio/` — comparações, testes de contrato, segurança e integração.
- `oficina/` — montagem do HUB, contratos canônicos, adapters e infraestrutura executável.
- `inventario/` — origem, commit, licença e função de cada componente.

## Regra de origem

Todo doador deve manter sua licença e atribuição originais. Cada snapshot recebe um arquivo `_ORIGIN.json` com repositório, commit e data da coleta. Históricos `.git`, credenciais, builds locais e caches não entram nos snapshots.

## Arquitetura-alvo

IA (Codex/ChatGPT/outra) → Higress → ADS-AI-HUB → Policy/Cofre/Fila → Meta Adapter / TikTok Adapter → APIs oficiais.

Este repositório não deve armazenar tokens, senhas, chaves ou segredos reais.
