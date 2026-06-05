"""
Market Intelligence Scanner v2 - com análise GPT
Fontes: DuckDuckGo, Google News, Reddit
Análise: OpenAI GPT-4o-mini (barato e excelente)
"""
import os, time, re, json, requests
from collections import Counter
from typing import Callable, Optional

try:
    from ddgs import DDGS
    HAS_DDG = True
except ImportError:
    try:
        from duckduckgo_search import DDGS
        HAS_DDG = True
    except Exception:
        DDGS = None
        HAS_DDG = False

try:
    import feedparser
    HAS_FEEDPARSER = True
except Exception:
    HAS_FEEDPARSER = False

try:
    from openai import OpenAI
    HAS_OPENAI = True
except Exception:
    HAS_OPENAI = False

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; MarketResearch/1.0)'}

PAIN_PT = ['problema','erro','falha','ruim','péssimo','horrível','decepcionado',
           'não funciona','difícil','caro','impossível','nunca mais','vergonha',
           'absurdo','ridículo','lento','quebrado','defeito','reclamação',
           'insatisfeito','arrependido','pior','terrível','frustrante',
           'doente','machucado','passou mal','vomitou','reação','recall']

PAIN_EN = ['problem','issue','broken','bad','terrible','horrible','disappointed',
           'not working','difficult','expensive','impossible','never again',
           'awful','ridiculous','slow','defective','complaint','unsatisfied',
           'worst','frustrating','sick','recall','vomit','reaction']


def clean_text(text: str) -> str:
    text = re.sub(r'http\S+', '', str(text))
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:800]


def is_pain_text(text: str, lang: str = 'pt') -> bool:
    t = text.lower()
    triggers = PAIN_PT if lang == 'pt' else PAIN_EN
    return any(w in t for w in triggers)


def analyze_with_gpt(texts: list, niche: str, lang: str = 'pt') -> list:
    """Use GPT to analyze pain points and suggest products + copy angles."""
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key or not HAS_OPENAI:
        return []
    
    if not texts:
        return []
    
    # Take top texts to fit in context (max ~50)
    sample = texts[:50]
    sample_text = '\n---\n'.join(f'{i+1}. {t[:300]}' for i, t in enumerate(sample))
    
    prompt = f"""Você é um analista de mercado especializado em e-commerce e dropshipping.

Analisei textos reais da internet sobre o nicho: "{niche}"

Textos coletados:
{sample_text}

Sua tarefa: identificar de 3 a 7 DORES REAIS distintas neste nicho e retornar APENAS um JSON válido (sem markdown, sem ```) com esta estrutura:

{{
  "opportunities": [
    {{
      "pain_name": "Nome curto e descritivo da dor (max 60 chars)",
      "pain_description": "Descrição completa da dor em 1-2 frases",
      "target_audience": "Quem tem essa dor (perfil demográfico + comportamental)",
      "evidence_count_estimate": número estimado de textos que mencionam essa dor,
      "intensity": "alta" | "média" | "baixa",
      "products_to_sell": [
        "Produto físico 1 que resolve essa dor",
        "Produto físico 2",
        "Produto físico 3"
      ],
      "copy_angles": [
        "Ângulo de copy 1 (headline para anúncio)",
        "Ângulo de copy 2",
        "Ângulo de copy 3"
      ],
      "example_quotes": [
        "Citação real do texto que ilustra a dor (max 150 chars)",
        "Outra citação real"
      ],
      "score": número de 0 a 100 indicando potencial comercial
    }}
  ]
}}

REGRAS:
- Foque em dores que podem ser resolvidas com PRODUTOS FÍSICOS (dropshipping)
- Use citações REAIS dos textos fornecidos, não invente
- Score considera: frequência da dor + intensidade emocional + viabilidade comercial
- Retorne APENAS o JSON, sem texto antes ou depois"""
    
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Você é um analista de mercado expert. Sempre retorna apenas JSON válido."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        result_text = response.choices[0].message.content
        parsed = json.loads(result_text)
        return parsed.get('opportunities', [])
    except Exception as e:
        print(f'GPT error: {e}')
        return []


class Scanner:
    def __init__(self, niche: str, country: str = 'BR', language: str = 'pt'):
        self.niche = niche
        self.country = country
        self.language = language
        self.lang = 'pt' if language == 'pt' else 'en'

    def run(self, update_cb: Optional[Callable] = None) -> dict:
        def upd(p, m):
            if update_cb:
                update_cb(p, m)

        all_texts, sources_used = [], []

        upd(10, 'Buscando no DuckDuckGo...')
        ddg = self._ddg()
        all_texts.extend(ddg)
        if ddg:
            sources_used.append('DuckDuckGo')

        upd(25, 'Coletando notícias (Google News RSS)...')
        news = self._news_rss()
        all_texts.extend(news)
        if news:
            sources_used.append('Google News')

        upd(40, 'Buscando discussões (Reddit RSS)...')
        reddit = self._reddit_rss()
        all_texts.extend(reddit)
        if reddit:
            sources_used.append('Reddit')

        upd(55, 'Filtrando dores e reclamações...')
        pain = [t for t in all_texts if is_pain_text(t, self.lang)]
        if len(pain) < 5:
            pain = all_texts

        # NEW: GPT analysis
        upd(70, 'Analisando dores com IA (GPT-4o-mini)...')
        gpt_opportunities = analyze_with_gpt(pain, self.niche, self.lang)
        
        upd(90, 'Finalizando relatório...')
        
        # Format opportunities for frontend
        opportunities = []
        if gpt_opportunities:
            for opp in gpt_opportunities:
                opportunities.append({
                    'name': opp.get('pain_name', 'Dor identificada'),
                    'description': opp.get('pain_description', ''),
                    'target_audience': opp.get('target_audience', ''),
                    'score': opp.get('score', 50),
                    'evidence_count': opp.get('evidence_count_estimate', 0),
                    'intensity': opp.get('intensity', 'média'),
                    'products_to_sell': opp.get('products_to_sell', []),
                    'copy_angles': opp.get('copy_angles', []),
                    'example_phrases': opp.get('example_quotes', []),
                    'keywords': [],  # Backwards compat
                    'avg_intensity': {'alta': 0.9, 'média': 0.6, 'baixa': 0.3}.get(opp.get('intensity', 'média'), 0.5),
                    'trend_direction': 'stable',
                    'sources': sources_used,
                    'ai_powered': True,
                })

        # If GPT failed or no key, fall back to old behavior
        if not opportunities and pain:
            opportunities.append({
                'name': f'Análise básica de {self.niche}',
                'description': 'Análise IA não disponível. Configure OPENAI_API_KEY para análise completa.',
                'target_audience': '',
                'score': 30,
                'evidence_count': len(pain),
                'intensity': 'média',
                'products_to_sell': [],
                'copy_angles': [],
                'example_phrases': [clean_text(t)[:200] for t in pain[:3]],
                'keywords': [],
                'avg_intensity': 0.5,
                'trend_direction': 'stable',
                'sources': sources_used,
                'ai_powered': False,
            })

        opportunities.sort(key=lambda x: x['score'], reverse=True)
        upd(95, 'Concluído!')

        return {
            'niche': self.niche,
            'total_texts_collected': len(all_texts),
            'total_pain_texts': len(pain),
            'sources_used': sources_used,
            'opportunities': opportunities,
            'top_words': list(Counter(
                w for t in pain
                for w in re.findall(r'\b[a-záàâãéêíóôõúüç]{4,}\b', t.lower())
            ).most_common(20)),
            'scanned_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'ai_enabled': bool(os.environ.get('OPENAI_API_KEY')) and HAS_OPENAI,
        }

    def _ddg(self) -> list:
        if not HAS_DDG or DDGS is None:
            return []
        qs = ([f'{self.niche} problema reclamação',
               f'{self.niche} não funciona ruim',
               f'{self.niche} review experiência',
               f'{self.niche} dor dificuldade']
              if self.lang == 'pt' else
              [f'{self.niche} problem complaint',
               f'{self.niche} not working review',
               f'{self.niche} issue bad experience'])
        texts = []
        for q in qs:
            try:
                results = list(DDGS().text(q, max_results=20,
                               region='br-pt' if self.lang == 'pt' else 'us-en'))
                for r in results:
                    t = clean_text(f"{r.get('title','')} {r.get('body','')}")
                    if len(t) > 40:
                        texts.append(t)
                time.sleep(1.5)
            except Exception:
                time.sleep(3)
        return texts

    def _news_rss(self) -> list:
        if not HAS_FEEDPARSER:
            return []
        try:
            q = f'{self.niche} problema reclamação' if self.lang == 'pt' else f'{self.niche} problem complaint'
            hl = 'pt-BR' if self.lang == 'pt' else 'en-US'
            gl = self.country if self.country in ('BR','US','PT') else 'BR'
            ceid = f'{gl}:{self.lang[:2]}'
            url = f'https://news.google.com/rss/search?q={requests.utils.quote(q)}&hl={hl}&gl={gl}&ceid={ceid}'
            feed = feedparser.parse(url)
            texts = []
            for e in feed.entries[:30]:
                t = clean_text(f"{e.get('title','')} {e.get('summary','')}")
                if len(t) > 40:
                    texts.append(t)
            return texts
        except Exception:
            return []

    def _reddit_rss(self) -> list:
        if not HAS_FEEDPARSER:
            return []
        try:
            q = f'{self.niche} problem' if self.lang == 'en' else f'{self.niche} problema'
            url = f'https://www.reddit.com/search.rss?q={requests.utils.quote(q)}&sort=relevance&limit=30'
            resp = requests.get(url, headers=HEADERS, timeout=12)
            feed = feedparser.parse(resp.text)
            texts = []
            for e in feed.entries[:30]:
                t = clean_text(f"{e.get('title','')} {e.get('summary','')}")
                if len(t) > 40:
                    texts.append(t)
            return texts
        except Exception:
            return []
