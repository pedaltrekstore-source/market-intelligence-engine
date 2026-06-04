# Market Intelligence Engine — MVP

Site de varredura de mercado. Busca dores, reclamações e tendências online para qualquer nicho.

## Fontes de dados (gratuitas, sem API key)
- **DuckDuckGo** — buscas orgânicas
- **Google News RSS** — notícias e discussões
- **Reddit RSS** — discussões de usuários reais

## Deploy no Railway (5 minutos)

1. Crie conta em https://railway.app
2. Clique em **New Project → Deploy from GitHub**
3. Faça upload deste projeto (ou conecte ao GitHub)
4. Railway detecta Python automaticamente
5. Adicione a variável de ambiente:
   - `SECRET_KEY` = qualquer string aleatória longa
6. Pronto! Railway fornece a URL pública.

## Rodar localmente

```bash
pip install -r requirements.txt
python app.py
# Acesse: http://localhost:5000
```

## Adicionar APIs no futuro

Edite o arquivo `.env` (copie de `.env.example`) e adicione:
- `SERPAPI_KEY` — para Google Trends real
- `OPENAI_KEY` — para análise de IA nos resultados

## Estrutura
```
app.py          # Flask server + rotas
scanner.py      # Motor de varredura
templates/
  index.html    # Interface completa (dashboard + feed)
```
