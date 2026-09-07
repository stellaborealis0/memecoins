import asyncio
import aiohttp
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging
from datetime import datetime
import json

@dataclass
class ResearchResult:
    source: str
    data: Dict
    confidence: float
    timestamp: str
    error: Optional[str] = None

class MultiSourceResearcher:
    def __init__(self):
        self.sources = {
            'reddit': self._search_reddit,
            'twitter': self._search_twitter, 
            'youtube': self._search_youtube,
            'hacker_news': self._search_hacker_news,
            'polymarket': self._search_polymarket,
            'news_api': self._search_news,
            'finance_api': self._search_finance
        }
        self.logger = logging.getLogger(__name__)
        
    async def research_topic(self, topic: str, sources: List[str] = None) -> List[ResearchResult]:
        """Realiza investigación multi-source en paralelo"""
        if sources is None:
            sources = list(self.sources.keys())
        
        tasks = []
        for source_name in sources:
            if source_name in self.sources:
                task = asyncio.create_task(
                    self._safe_source_search(self.sources[source_name], topic, source_name)
                )
                tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        valid_results = []
        
        for result in results:
            if isinstance(result, ResearchResult):
                valid_results.append(result)
            elif isinstance(result, Exception):
                self.logger.error(f"Research task failed: {result}")
        
        return valid_results
    
    async def _safe_source_search(self, func, topic: str, source: str) -> ResearchResult:
        """Wrapper seguro para búsquedas por fuente"""
        try:
            result = await func(topic)
            return ResearchResult(
                source=source,
                data=result,
                confidence=self._calculate_confidence(result),
                timestamp=str(datetime.now()),
                error=None
            )
        except Exception as e:
            self.logger.error(f"Search failed for {source}: {e}")
            return ResearchResult(
                source=source,
                data={},
                confidence=0.0,
                timestamp=str(datetime.now()),
                error=str(e)
            )
    
    async def _search_reddit(self, topic: str) -> Dict:
        """Busca en Reddit API"""
        # Implementar búsqueda en Reddit API
        # Por ahora, retorno datos simulados
        return {
            'posts': [
                {'title': f'Reddit post about {topic}', 'score': 150, 'comments': 45},
                {'title': f'Discussion on {topic}', 'score': 89, 'comments': 23}
            ],
            'subreddits': ['cryptocurrency', 'investing', 'wallstreetbets'],
            'sentiment': 'mixed'
        }
    
    async def _search_twitter(self, topic: str) -> Dict:
        """Busca en Twitter/X API"""
        # Implementar búsqueda en Twitter/X API
        # Por ahora, retorno datos simulados
        return {
            'tweets': [
                {'text': f'Tweet about {topic}', 'retweets': 120, 'likes': 340},
                {'text': f'Discussion on {topic}', 'retweets': 45, 'likes': 120}
            ],
            'hashtags': ['#crypto', '#investing', f'#{topic.replace(" ", "")}'],
            'sentiment': 'positive'
        }
    
    async def _search_youtube(self, topic: str) -> Dict:
        """Busca en YouTube API"""
        # Implementar búsqueda en YouTube API
        # Por ahora, retorno datos simulados
        return {
            'videos': [
                {'title': f'Video about {topic}', 'views': 15000, 'likes': 450},
                {'title': f'Analysis of {topic}', 'views': 8900, 'likes': 230}
            ],
            'channels': ['CryptoNews', 'InvestmentAnalysis'],
            'sentiment': 'informative'
        }
    
    async def _search_hacker_news(self, topic: str) -> Dict:
        """Busca en Hacker News API"""
        # Implementar búsqueda en Hacker News API
        # Por ahora, retorno datos simulados
        return {
            'stories': [
                {'title': f'Hacker News story about {topic}', 'points': 89, 'comments': 34},
                {'title': f'Discussion on {topic}', 'points': 45, 'comments': 12}
            ],
            'domain': 'news.ycombinator.com',
            'sentiment': 'technical'
        }
    
    async def _search_polymarket(self, topic: str) -> Dict:
        """Busca en Polymarket API"""
        # Implementar búsqueda en Polymarket API
        # Por ahora, retorno datos simulados
        return {
            'markets': [
                {'question': f'Will {topic} increase?', 'probability': 0.65, 'volume': 12000},
                {'question': f'What will happen with {topic}?', 'probability': 0.45, 'volume': 8000}
            ],
            'trends': 'bullish',
            'liquidity': 'high'
        }
    
    async def _search_news(self, topic: str) -> Dict:
        """Busca en News API"""
        # Implementar búsqueda en News API
        # Por ahora, retorno datos simulados
        return {
            'articles': [
                {'title': f'News article about {topic}', 'source': 'Financial Times', 'date': '2026-03-25'},
                {'title': f'Analysis of {topic}', 'source': 'Bloomberg', 'date': '2026-03-24'}
            ],
            'sources': ['Financial Times', 'Bloomberg', 'Reuters'],
            'sentiment': 'neutral'
        }
    
    async def _search_finance(self, topic: str) -> Dict:
        """Busca en APIs financieras"""
        # Implementar búsqueda en APIs financieras
        # Por ahora, retorno datos simulados
        return {
            'analysis': [
                {'type': 'technical', 'rating': 'buy', 'confidence': 0.78},
                {'type': 'fundamental', 'rating': 'hold', 'confidence': 0.65}
            ],
            'indicators': {'rsi': 65, 'macd': 'bullish', 'volume': 'above_average'},
            'sentiment': 'cautiously_optimistic'
        }
    
    def _calculate_confidence(self, data: Dict) -> float:
        """Calcula confianza basada en la calidad de los datos"""
        if not data:
            return 0.0
        
        # Calcular confianza basada en cantidad y calidad de datos
        score = 0
        total_checks = 0
        
        # Check for presence of key data points
        if 'posts' in data and len(data['posts']) > 0:
            score += 1
            total_checks += 1
        if 'tweets' in data and len(data['tweets']) > 0:
            score += 1
            total_checks += 1
        if 'articles' in data and len(data['articles']) > 0:
            score += 1
            total_checks += 1
        if 'markets' in data and len(data['markets']) > 0:
            score += 1
            total_checks += 1
        if 'sentiment' in data:
            score += 0.5
            total_checks += 0.5
        
        confidence = score / total_checks if total_checks > 0 else 0.0
        return min(confidence, 1.0)  # Ensure confidence is between 0 and 1
    
    def aggregate_results(self, results: List[ResearchResult]) -> Dict:
        """Agrega resultados de múltiples fuentes"""
        aggregated = {
            'topic': '',
            'sources_analyzed': len(results),
            'total_confidence': 0,
            'average_confidence': 0,
            'data_points': {},
            'sentiment_analysis': {},
            'key_insights': [],
            'errors': [],
            'timestamp': str(datetime.now())
        }
        
        if not results:
            return aggregated
        
        # Calculate overall confidence
        valid_results = [r for r in results if r.confidence > 0]
        if valid_results:
            aggregated['total_confidence'] = sum(r.confidence for r in valid_results)
            aggregated['average_confidence'] = aggregated['total_confidence'] / len(valid_results)
        
        # Aggregate data from all sources
        for result in results:
            if result.error:
                aggregated['errors'].append({
                    'source': result.source,
                    'error': result.error
                })
            else:
                aggregated['data_points'][result.source] = result.data
                aggregated['sentiment_analysis'][result.source] = result.data.get('sentiment', 'unknown')
        
        # Extract key insights
        insights = set()
        for result in valid_results:
            data = result.data
            if 'posts' in data:
                for post in data['posts']:
                    insights.add(post.get('title', ''))
            if 'tweets' in data:
                for tweet in data['tweets']:
                    insights.add(tweet.get('text', ''))
            if 'articles' in data:
                for article in data['articles']:
                    insights.add(article.get('title', ''))
            if 'markets' in data:
                for market in data['markets']:
                    insights.add(market.get('question', ''))
        
        aggregated['key_insights'] = list(insights)[:10]  # Limit to top 10 insights
        
        return aggregated

# Función auxiliar para crear researcher
def create_multi_source_researcher():
    """Crea una instancia de MultiSourceResearcher"""
    return MultiSourceResearcher()

if __name__ == "__main__":
    # Ejemplo de uso
    async def main():
        researcher = MultiSourceResearcher()
        
        # Buscar un tema de ejemplo
        topic = "cryptocurrency market trends"
        results = await researcher.research_topic(topic, sources=['reddit', 'twitter', 'news_api'])
        
        print(f"Research results for '{topic}':")
        for result in results:
            print(f"Source: {result.source}")
            print(f"Confidence: {result.confidence}")
            print(f"Data: {json.dumps(result.data, indent=2)[:200]}...")
            if result.error:
                print(f"Error: {result.error}")
            print("-" * 50)
        
        # Agregar resultados
        aggregated = researcher.aggregate_results(results)
        print(f"\nAggregated results:")
        print(json.dumps(aggregated, indent=2))

    # Ejecutar ejemplo
    asyncio.run(main())