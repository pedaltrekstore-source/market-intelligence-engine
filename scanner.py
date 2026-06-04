"""
Market Intelligence Scanner - coleta dores e tendências de fontes gratuitas.
Fontes: DuckDuckGo, Google News RSS, Reddit RSS
"""
import time, re, requests
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

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; MarketResearch/1.0)'}

PAIN_PT = ['problema','erro','falha','ruim','péssimo','horrível','decepcionado',
           'não funciona','difícil','caro','impossível','nunca mais','vergonha',
           'absurdo','ridículo','lento','quebrado','defeito','reclamação',
           'insatisfeito','arrependido','pior','terrível','frustrante']

PAIN_EN = ['problem','issue','broken','bad','terrible','horrible','disappointed',
           'not working','difficult','expensive','impossible','never again',
           'awful','ridiculous','slow','defective','complaint','unsatisfied',
           'worst','frustrating','annoying','useless','scam']

EMOT_PT = ['ódio','raiva','indignado','revoltado','péssimo','horrível',
           'absurdo','vergonha','ridículo','nunca mais','lamentável','inaceitável']

EMOT_EN = ['hate','angry','outraged','furious','terrible','horrible',
           'absurd','shameful','ridiculous','never again','unacceptable']


def clean_text(text: str) -> str:
    text = re.sub(r'http\S+', '', str(text))
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:500]


def emotional_intensity(text: str, lang: str = 'pt') -> float:
    t = text.lower()
    words = EMOT_PT if lang == 'pt' else EMOT_EN
    hits = sum(1 for w in words if w in t)
    excl = t.count('!')
    caps = sum(1 for c in text if c.isupper()) / max(len(text), 1)
    return min(1.0, round(hits * 0.15 + excl * 0.08 + caps * 0.3, 2))


def is_pain_text(text: str, lang: str = 'pt') -> bool:
    t = text.lower()
    triggers = PAIN_PT if lang == 'pt' else PAIN_EN
    return any(w in t for w in triggers)


def extract_themes(texts: list, niche: str) -> list:
    stop = {'de','da','do','em','para','com','por','um','uma','que','se',
            'não','mas','ou','mais','como','até','foi','ele','ela',
            'the','and','for','with','that','this','have','from','are',
            'was','but','not','they','you','can','all','had','her','his',
            niche.lower()}
    word_counts = Counter()
    for text in texts:
        words = re.findall(r'\b[a-záàâãéêíóôõúüçA-Z]{4,}\b', text.lower())
        word_counts.update(w for w in words if w not in stop)

    top = [w for w, _ in word_counts.most_common(30)]
    themes, seen = [], set()

    for i, w1 in enumerate(top[:15]):
        if w1 in seen:
            continue
        related = [w1]
        for w2 in top[i+1:]:
            if w2 in seen:
                continue
            co = sum(1 for t in texts if w1 in t.lower() and w2 in t.lower())
            if co >= 2:
                related.append(w2)
            if len(related) >= 3:
                break

        theme_texts = [t for t in texts if any(w in t.lower() for w in related)]
        if theme_texts:
            themes.append({
                'label': ' + '.join(related[:3]).capitalize(),
                'keywords': related[:5],
                'evidence_count': len(theme_texts),
                'examples': [clean_text(t) for t in theme_texts[:3]],
                'avg_intensity': round(
                    sum(emotional_intensity(t) for t in theme_texts) / len(theme_texts), 2
                ),
            })
            seen.update(related)
        if len(themes) >= 8:
            break

    return sorted(themes, key=lambda x: x['evidence_count'], reverse=True)


def score_opp(theme: dict, total: int) -> float:
    freq = min(theme['evidence_count'] / max(total, 1) * 100, 100)
    intens = theme['avg_intensity'] * 100
    return round(min(freq * 0.50 + intens * 0.50, 100), 1)


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

        upd(15, 'Buscando no DuckDuckGo...')
        ddg = self._ddg()
        all_texts.extend(ddg)
        if ddg:
            sources_used.append('DuckDuckGo')

        upd(35, 'Coletando notícias (Google News RSS)...')
        news = self._news_rss()
        all_texts.extend(news)
        if news:
            sources_used.append('Google News')

        upd(50, 'Buscando discussões (Reddit RSS)...')
        reddit = self._reddit_rss()
        all_texts.extend(reddit)
        if reddit:
            sources_used.append('Reddit')

        upd(65, 'Filtrando dores e reclamações...')
        pain = [t for t in all_texts if is_pain_text(t, self.lang)]
        if len(pain) < 3:
            pain = all_texts

        upd(80, 'Agrupando temas e calculando scores...')
        themes = extract_themes(pain, self.niche)

        opportunities = []
        for th in themes:
            sc = score_opp(th, len(pain))
            opportunities.append({
                'name': th['label'],
                'score': sc,
                'evidence_count': th['evidence_count'],
                'keywords': th['keywords'],
                'example_phrases': th['examples'],
                'avg_intensity': th['avg_intensity'],
                'trend_direction': 'stable',
                'sources': sources_used,
            })
        opportunities.sort(key=lambda x: x['score'], reverse=True)
        upd(95, 'Finalizando...')

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
        }

    def _ddg(self) -> list:
        if not HAS_DDG or DDGS is None:
            return []
        qs = ([f'{self.niche} problema reclamação',
               f'{self.niche} não funciona ruim',
               f'{self.niche} reclamação review']
              if self.lang == 'pt' else
              [f'{self.niche} problem complaint',
               f'{self.niche} not working review',
               f'{self.niche} issue bad'])
        texts = []
        for q in qs:
            try:
                results = list(DDGS().text(q, max_results=15,
                               region='br-pt' if self.lang == 'pt' else 'us-en'))
                for r in results:
                    t = clean_text(f"{r.get('title','')} {r.get('body','')}")
                    if len(t) > 30:
                        texts.append(t)
                time.sleep(2.0)
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
            for e in feed.entries[:25]:
                t = clean_text(f"{e.get('title','')} {e.get('summary','')}")
                if len(t) > 30:
                    texts.append(t)
            return texts
        except Exception:
            return []

    def _reddit_rss(self) -> list:
        if not HAS_FEEDPARSER:
            return []
        try:
            q = f'{self.niche} problem' if self.lang == 'en' else f'{self.niche} problema'
            url = f'https://www.reddit.com/search.rss?q={requests.utils.quote(q)}&sort=relevance&limit=25'
            resp = requests.get(url, headers=HEADERS, timeout=12)
            feed = feedparser.parse(resp.text)
            texts = []
            for e in feed.entries[:25]:
                t = clean_text(f"{e.get('title','')} {e.get('summary','')}")
                if len(t) > 30:
                    texts.append(t)
            return texts
        except Exception:
            return []
